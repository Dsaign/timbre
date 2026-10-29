# Layout follows https://docs.astral.sh/uv/guides/integration/docker/
FROM python:3.13.18-slim-trixie AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
# uv installs everything; the base image's pip is unused and its vendored deps carry CVEs that Trivy flags.
RUN python -m pip uninstall -y pip
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# Runs pytest inside the Compose network, because the database port is not published.
FROM base AS tests
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
COPY tests ./tests
USER nobody
CMD ["pytest", "-p", "no:cacheprovider"]

FROM base AS api
USER nobody
EXPOSE 8000
CMD ["uvicorn", "timbre_back.main:app", "--host", "0.0.0.0", "--port", "8000"]
