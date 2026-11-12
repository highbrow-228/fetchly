import json
from pathlib import Path

from pydantic import BaseModel, Field

from fetchly.extractors.process import run_process


class VideoInfo(BaseModel, frozen=True):
    width: int | None = Field(description="Frame width in pixels; None = unknown")
    height: int | None = Field(description="Frame height in pixels; None = unknown")
    duration: int | None = Field(description="Length in seconds; None = unknown")


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
        return VideoInfo(width=None, height=None, duration=None)

    data = json.loads(output.stdout)
    stream = (data.get("streams") or [{}])[0]
    duration = data.get("format", {}).get("duration")

    return VideoInfo(
        width=stream.get("width"),
        height=stream.get("height"),
        duration=round(float(duration)) if duration else None,
    )
