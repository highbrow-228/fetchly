"""Video metadata via ffprobe."""

import json
from dataclasses import dataclass
from pathlib import Path

from fetchly.extractors.process import run_process


@dataclass(frozen=True, slots=True)
class VideoInfo:
    width: int | None
    height: int | None
    duration: int | None


async def probe_video(path: Path, timeout_seconds: float) -> VideoInfo:
    output = await run_process(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json", str(path),
        ],
        timeout_seconds,
    )  # fmt: skip
    if output.returncode != 0:
        return VideoInfo(None, None, None)
    data = json.loads(output.stdout)
    stream = (data.get("streams") or [{}])[0]
    duration = data.get("format", {}).get("duration")
    return VideoInfo(
        stream.get("width"), stream.get("height"), round(float(duration)) if duration else None
    )
