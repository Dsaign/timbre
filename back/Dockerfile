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
# multilingual-e5-small (MIT), ONNX export from the model's own repo, pinned by revision and checksum.
# The directory comes first: ADD --chmod would also apply 644 to directories it creates.
RUN mkdir -p /models/e5
ARG E5=https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/onnx
ADD --chmod=644 --checksum=sha256:ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665 ${E5}/model.onnx /models/e5/model.onnx
ADD --chmod=644 --checksum=sha256:0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39 ${E5}/tokenizer.json /models/e5/tokenizer.json
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
