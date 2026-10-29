import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from timbre_back.db import conninfo, vector_literal
from timbre_back.embed import embed_query

# An unset token matches nothing, so a misconfigured API refuses every caller.
FRONT_TOKEN = os.environ.get("FRONT_TOKEN", "").encode()

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


class Health(BaseModel):
    status: Literal["ok"]


class SearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
    ]
    n: Annotated[int, Field(ge=1, le=60)] = 24
    offset: Annotated[int, Field(ge=0, le=10_000)] = 0


class Match(BaseModel):
    id: UUID
    title: str
    artist: str


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
    SELECT json_agg(json_build_object('id', id, 'title', title, 'artist', artist))
    FROM (
      SELECT * FROM matches ORDER BY rank DESC, id LIMIT %(n)s OFFSET %(offset)s
    ) page
  ), '[]')
"""

router = APIRouter()


@router.get("/health")
async def health() -> Health:
    return Health(status="ok")


@router.get("/search")
async def search(
    params: Annotated[SearchParams, Query()], request: Request
) -> SearchResult:
    vector = await run_in_threadpool(embed_query, params.q)
    pool: AsyncConnectionPool = request.app.state.search_pool
    async with pool.connection() as conn:
        cur = await conn.execute(
            SEARCH_SQL,
            {"vector": vector_literal(vector), "n": params.n, "offset": params.offset},
        )
        count, matches = await cur.fetchone() or (0, [])  # always one row
    return SearchResult(count=count, matches=matches)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await run_in_threadpool(embed_query, "warm up")  # load the model before traffic
    async with AsyncConnectionPool(
        conninfo("api_search"), min_size=1, max_size=4, open=False
    ) as pool:
        app.state.search_pool = pool
        yield


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
