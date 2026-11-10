"""Per-download scratch directories on the volume shared with the Bot API server."""

import asyncio
import shutil
import tempfile
import time
from pathlib import Path

from fetchly.links import Platform

_PREFIX = "job-"


class Workspace:
    def __init__(self, root: Path, cookies_dir: Path) -> None:
        self._root = root
        self._cookies_dir = cookies_dir

    async def create(self) -> Path:
        return await asyncio.to_thread(self._create)

    async def cookies(self, platform: Platform, workdir: Path) -> Path | None:
        """Private copy of the platform cookie file (tools rewrite it), if one exists."""
        return await asyncio.to_thread(self._copy_cookies, platform, workdir)

    async def discard(self, workdir: Path) -> None:
        await asyncio.to_thread(shutil.rmtree, workdir, True)

    async def purge_stale(self, max_age_seconds: int) -> None:
        """Remove directories left behind by workers that were killed mid-download."""
        await asyncio.to_thread(self._purge, time.time() - max_age_seconds)

    def _create(self) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(prefix=_PREFIX, dir=self._root))
        workdir.chmod(0o755)  # the Bot API server runs as another user and must read it
        return workdir

    def _copy_cookies(self, platform: Platform, workdir: Path) -> Path | None:
        source = self._cookies_dir / f"{platform.value}.txt"
        if not source.is_file():
            return None
        target = workdir / "cookies.txt"
        shutil.copyfile(source, target)
        target.chmod(0o600)
        return target

    def _purge(self, older_than: float) -> None:
        for workdir in self._root.glob(_PREFIX + "*"):
            if workdir.stat().st_mtime < older_than:
                shutil.rmtree(workdir, ignore_errors=True)
