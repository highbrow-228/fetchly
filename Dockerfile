# Application image for gateway, worker and migrate. Builds on amd64 and arm64.
FROM python:3.12-slim-bookworm

COPY --from=astral/uv:latest /uv /usr/local/bin/uv
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# The shared directory is world-writable with the sticky bit: the worker writes
# media there and the Bot API server (another user) reads it. A fresh named
# volume inherits these permissions from the image.
ARG SHARED_DIR
RUN useradd --uid 10001 --create-home fetchly \
 && mkdir -p /app "${SHARED_DIR}" \
 && chown fetchly:fetchly /app \
 && chmod 1777 "${SHARED_DIR}"

USER fetchly
WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

COPY --chown=fetchly:fetchly pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=fetchly:fetchly alembic.ini ./
COPY --chown=fetchly:fetchly docker/worker-entrypoint.sh ./docker/
COPY --chown=fetchly:fetchly src ./src
RUN uv sync --frozen --no-dev
