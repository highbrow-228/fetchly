import re

from pydantic import BaseModel, Field

from fetchly.extractors.base import (
    ExtractionError,
    ExtractionFailedError,
    LoginRequiredError,
    NoMediaError,
    PlatformBlockedError,
)
from fetchly.links import Platform

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".webm", ".mkv"})
PHOTO_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})

# Signs in a tool's error lines that the platform is throttling us (worth a pause).
BLOCK_MARKERS = (
    "http error 429",
    "429 too many requests",
    "too many requests",
    "rate limit",
    "rate-limit",
    "not a bot",
    "challengeerror",
)
# Signs that this one post needs an account (private, age-gated); no reason to pause.
LOGIN_MARKERS = (
    "login required",
    "login_required",
    "sign in to confirm",
    "requires authentication",
    "authenticationerror",
    "authorizationerror",
    "authrequired",
)
# Signs of a network hiccup: the same link may well work on the next attempt.
TRANSIENT_MARKERS = (
    "timed out",
    "timeout",
    "connection",
    "temporary failure",
    "http error 5",
)
_URL = re.compile(r"\S*://\S*")


class ExtractorOptions(BaseModel, frozen=True):
    timeout_seconds: int = Field(
        description="Seconds one yt-dlp / gallery-dl run may take before it is killed"
    )
    max_bytes: int = Field(description="Files larger than this many bytes are not downloaded")
    max_duration_seconds: int = Field(
        description="Videos longer than this many seconds are not downloaded"
    )
    max_height: int = Field(
        description="Wanted video height in pixels: the best quality not taller than it is picked"
    )
    max_items: int = Field(
        description="How many photos/videos are taken from one post; the rest are skipped"
    )
    proxies: dict[Platform, str] = Field(
        description="Proxy URL per platform; empty = connect directly"
    )


def failure(tool: str, returncode: int, tool_output: str) -> ExtractionError:
    """Why a tool run produced no media, judged by its exit status and lowercased output."""
    if _has_marker(tool_output, BLOCK_MARKERS):
        return PlatformBlockedError(tool)

    if _has_marker(tool_output, LOGIN_MARKERS):
        return LoginRequiredError(tool)

    if returncode == 0:
        return NoMediaError(tool)

    if returncode < 0 or _has_marker(tool_output, TRANSIENT_MARKERS):  # killed, or network
        return ExtractionError(f"{tool} exit {returncode}")

    return ExtractionFailedError(f"{tool} exit {returncode}")


def _has_marker(tool_output: str, markers: tuple[str, ...]) -> bool:
    """Look only at error lines, minus URLs: info lines and link slugs prove nothing."""
    errors = "\n".join(
        _URL.sub("", line)
        for line in tool_output.splitlines()
        if "error:" in line or "[error]" in line
    )

    return any(marker in errors for marker in markers)
