"""Periodic housekeeping: download partitions and orphaned scratch directories."""

import asyncio
import contextlib

import structlog

from fetchly.db import DownloadRepository
from fetchly.extractors import Workspace

log = structlog.stdlib.get_logger(__name__)


class Maintenance:
    def __init__(
        self,
        downloads: DownloadRepository,
        workspace: Workspace,
        *,
        interval_seconds: int,
        stale_seconds: int,
    ) -> None:
        self._downloads = downloads
        self._workspace = workspace
        self._interval = interval_seconds
        self._stale = stale_seconds

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self._downloads.ensure_partitions()
                await self._workspace.purge_stale(self._stale)
            except Exception:
                log.exception("maintenance_failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), self._interval)
