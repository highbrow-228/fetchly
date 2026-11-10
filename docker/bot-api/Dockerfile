# Local Telegram Bot API server. The upstream image is published for amd64 and
# arm64; this layer only makes it start as an unprivileged user.
FROM aiogram/telegram-bot-api:latest

# Mount point of the volume shared with the worker (see the main Dockerfile).
ARG SHARED_DIR
RUN mkdir -p "${SHARED_DIR}" && chmod 1777 "${SHARED_DIR}"

USER telegram-bot-api
ENTRYPOINT ["telegram-bot-api"]
