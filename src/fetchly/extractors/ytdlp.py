import json
import sys
from pathlib import Path
from typing import Any

from fetchly.extractors.base import (
    MediaItem,
    MediaKind,
    MediaResult,
    MediaTooLargeError,
    MediaTooLongError,
    NoMediaError,
)
from fetchly.extractors.caption import build_caption
from fetchly.extractors.options import VIDEO_EXTENSIONS, ExtractorOptions, failure
from fetchly.extractors.process import ProcessOutput, run_process
from fetchly.extractors.workspace import Workspace
from fetchly.links import Platform, detect_platform

# Only these extractors are loaded (no "generic"), so a post cannot hand the tool off
# to another site.
_EXTRACTORS = r"tiktok.*,vm\.tiktok,instagram.*,youtube.*,twitter.*,reddit,facebook.*"
_META_FILE = "meta.jsonl"
_META_TEMPLATE = (
    "after_move:%(.{id,playlist_id,duration,width,height,filepath,"
    "uploader,uploader_id,uploader_url,channel,channel_url,"
    "upload_date,view_count,location,track,artist})j"
)


class YtDlpExtractor:
    name = "yt-dlp"

    def __init__(self, options: ExtractorOptions, workspace: Workspace) -> None:
        self._options = options
        self._workspace = workspace

    def supports(self, url: str) -> bool:
        return detect_platform(url) is not None

    async def extract(self, url: str) -> MediaResult:
        platform = detect_platform(url)
        if platform is None:
            raise NoMediaError(self.name)

        workdir = await self._workspace.create()

        try:
            command = await self._command(url, platform, workdir)
            output = await run_process(command, self._options.timeout_seconds)
            entries = _read_meta(workdir / _META_FILE)
            self._check(output, entries)

            return self._result(platform, entries, workdir)
        except BaseException:
            await self._workspace.discard(workdir)
            raise

    async def _command(self, url: str, platform: Platform, workdir: Path) -> list[str]:
        options = self._options

        command = [
            sys.executable, "-m", "yt_dlp",
            "--ignore-config", "--no-warnings", "--no-progress",
            "--use-extractors", _EXTRACTORS,
            "--no-playlist", "--playlist-items", f"1:{options.max_items}",
            "--paths", str(workdir), "--output", "%(autonumber)s.%(ext)s",
            "--format-sort", f"res:{options.max_height},vcodec:h264,acodec:aac",
            "--merge-output-format", "mp4", "--remux-video", "mp4",
            "--max-filesize", str(options.max_bytes),
            "--match-filter", f"duration<=?{options.max_duration_seconds} & !is_live",
            "--print-to-file", _META_TEMPLATE, str(workdir / _META_FILE),
        ]  # fmt: skip

        if proxy := options.proxies.get(platform):
            command += ["--proxy", proxy]

        if cookies := await self._workspace.cookies(platform, workdir):
            command += ["--cookies", str(cookies)]

        return [*command, "--", url]

    def _check(self, output: ProcessOutput, entries: list[dict[str, Any]]) -> None:
        text = output.text
        if "larger than max-filesize" in text:
            raise MediaTooLargeError(self.name)

        if "does not pass filter" in text:
            raise MediaTooLongError(self.name)

        if entries:
            return

        raise failure(self.name, output.returncode, text)

    def _result(
        self, platform: Platform, entries: list[dict[str, Any]], workdir: Path
    ) -> MediaResult:
        items = [
            MediaItem(
                kind=MediaKind.VIDEO,
                path=Path(entry["filepath"]),
                width=entry.get("width"),
                height=entry.get("height"),
                duration=round(entry["duration"]) if entry.get("duration") else None,
            )
            for entry in entries
            if Path(entry["filepath"]).suffix.lower() in VIDEO_EXTENSIONS
        ]

        if not items:
            raise NoMediaError(self.name)  # audio-only post, e.g. a photo slideshow

        media_id = str(entries[0].get("playlist_id") or entries[0]["id"])
        caption = build_caption(platform, entries[0])

        return MediaResult(
            platform=platform,
            media_id=media_id,
            extractor=self.name,
            items=items,
            workdir=workdir,
            caption=caption,
        )


def _read_meta(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
