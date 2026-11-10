#!/bin/sh
# Platforms change constantly: take the latest extractors on every start.
# If the upgrade fails (no network), run with the versions from the image.
uv sync --no-dev --upgrade-package yt-dlp --upgrade-package gallery-dl \
  || echo '{"event": "extractor_upgrade_failed", "level": "warning"}'

exec uv run --no-sync python -m fetchly.worker
