import os
import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

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


router = APIRouter()


@router.get("/health")
async def health() -> Health:
    return Health(status="ok")


def create_app(app_env: str | None) -> FastAPI:
    dev = app_env == "development"
    app = FastAPI(
        title="timbre",
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
