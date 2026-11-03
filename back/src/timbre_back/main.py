import asyncio
import os
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from timbre_back.db import conninfo, vector_literal
from timbre_back.embed import embed_query
from timbre_back.feedback import (
    Vote,
    as_visitor,
    forget_old_hashes_daily,
    hash_ip,
    normalize,
    record,
)
from timbre_back.preview import Spotify, delete_expired_daily, lookup

# An unset token matches nothing, so a misconfigured API refuses every caller.
FRONT_TOKEN = os.environ.get("FRONT_TOKEN", "").encode()
IP_HASH_SALT = os.environ.get("IP_HASH_SALT", "").encode()

bearer = HTTPBearer(auto_error=False)


async def require_front_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    if not (
        FRONT_TOKEN
        and credentials
        and secrets.compare_digest(credentials.credentials.encode(), FRONT_TOKEN)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def visitor(
    x_visitor_ip: Annotated[
        IPv4Address | IPv6Address,
        Header(description="The visitor's IP address, forwarded by front"),
    ],
) -> str:
    """The salted visitor hash. Trusted only behind require_front_token."""
    return hash_ip(x_visitor_ip, IP_HASH_SALT)


Visitor = Annotated[str, Depends(visitor)]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


class Health(BaseModel):
    status: Literal["ok"]


class SearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: Description
    n: Annotated[int, Field(ge=1, le=60)] = 24
    offset: Annotated[int, Field(ge=0, le=10_000)] = 0


class Match(BaseModel):
    id: UUID
    title: str
    artist: str
    vote: Vote | None = Field(description="The visitor's current vote, if any")


class SearchResult(BaseModel):
    count: int
    matches: list[Match]


# Fit = cosine similarity. Matches are Songs with Fit above the promoted model's cutoff,
# ordered by Fit + weight * log1p(listens) / log1p(max listens in the Catalog).
SEARCH_SQL = """
WITH model AS (
  SELECT cutoff, popularity_weight FROM catalog.model_versions WHERE promoted
), fit AS (
  SELECT id, title, artist, listens, 1 - (vector <=> %(vector)s::vector) AS fit
  FROM catalog.songs WHERE vector IS NOT NULL
), matches AS (
  SELECT id, title, artist,
    fit + popularity_weight * coalesce(
      ln(1 + listens) / nullif(ln(1 + (SELECT max(listens) FROM catalog.songs)), 0), 0
    ) AS rank
  FROM fit, model WHERE fit > cutoff
)
SELECT
  (SELECT count(*) FROM matches),
  coalesce((
    SELECT json_agg(
      json_build_object('id', id, 'title', title, 'artist', artist, 'vote', vote)
      ORDER BY rank DESC, id
    )
    FROM (
      SELECT * FROM matches ORDER BY rank DESC, id LIMIT %(n)s OFFSET %(offset)s
    ) page
    LEFT JOIN feedback.votes v ON v.song_id = page.id
      AND v.description = %(description)s AND v.visitor_hash = %(visitor)s
  ), '[]')
"""


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Description
    song_id: UUID
    vote: Literal["up", "down", "none"] = Field(description='"none" withdraws the vote')


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    song_ids: Annotated[list[UUID], Field(min_length=1, max_length=60)]


class Preview(BaseModel):
    song_id: UUID
    spotify_track_id: str | None = Field(
        description="Spotify track ID, or null when the Song is not available"
    )


router = APIRouter()


@router.get("/health")
async def health() -> Health:
    return Health(status="ok")


@router.get("/search")
async def search(
    params: Annotated[SearchParams, Query()], visitor: Visitor, request: Request
) -> SearchResult:
    vector = await run_in_threadpool(embed_query, params.q)
    pool: AsyncConnectionPool = request.app.state.search_pool
    async with pool.connection() as conn:
        await as_visitor(conn, visitor)
        cur = await conn.execute(
            SEARCH_SQL,
            {
                "vector": vector_literal(vector),
                "n": params.n,
                "offset": params.offset,
                "description": normalize(params.q),
                "visitor": visitor,
            },
        )
        count, matches = await cur.fetchone() or (0, [])  # always one row
    return SearchResult(count=count, matches=matches)


@router.post(
    "/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "The Song is not in the Catalog"}},
)
async def feedback(body: FeedbackRequest, visitor: Visitor, request: Request) -> None:
    """Vote on a Match. The latest vote per visitor, Description and Song wins."""
    vote = None if body.vote == "none" else body.vote
    if not await record(
        request.app.state.search_pool, visitor, body.description, body.song_id, vote
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post("/preview")
async def preview(body: PreviewRequest, request: Request) -> list[Preview]:
    """For each Song, its Spotify track or "not available" (errors included)."""
    found = await lookup(
        list(dict.fromkeys(body.song_ids)),
        request.app.state.search_pool,
        request.app.state.preview_pool,
        request.app.state.spotify,
    )
    return [Preview(song_id=i, spotify_track_id=t) for i, t in found.items()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    if not IP_HASH_SALT:
        raise RuntimeError("IP_HASH_SALT must be set: unsalted IP hashes reverse")
    await run_in_threadpool(embed_query, "warm up")  # load the model before traffic
    async with (
        AsyncConnectionPool(
            conninfo("api_search"),
            min_size=1,
            max_size=4,
            open=False,
            connection_class=AsyncConnection,
        ) as search_pool,
        # The Spotify cache has its own role and pool (ADR 0001).
        AsyncConnectionPool(
            conninfo("api_preview"),
            min_size=1,
            max_size=4,
            open=False,
            connection_class=AsyncConnection,
        ) as preview_pool,
        httpx.AsyncClient(timeout=5) as http,
    ):
        app.state.search_pool = search_pool
        app.state.preview_pool = preview_pool
        app.state.spotify = Spotify(
            http,
            os.environ.get("SPOTIFY_CLIENT_ID", ""),
            os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
        )
        cleanups = [
            asyncio.create_task(delete_expired_daily(preview_pool)),
            asyncio.create_task(forget_old_hashes_daily(search_pool)),
        ]
        yield
        for cleanup in cleanups:
            cleanup.cancel()


def create_app(app_env: str | None) -> FastAPI:
    dev = app_env == "development"
    app = FastAPI(
        title="timbre",
        lifespan=lifespan,
        dependencies=[Depends(require_front_token)],
        responses={401: {"description": "Missing or wrong front token"}},
        # Interactive docs and the live spec only in development.
        docs_url="/docs" if dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if dev else None,
    )
    app.include_router(router)
    return app


app = create_app(os.environ.get("APP_ENV"))
