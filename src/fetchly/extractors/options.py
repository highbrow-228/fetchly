"""Settings shared by all extractors."""

from dataclasses import dataclass

from fetchly.links import Platform

VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".webm", ".mkv"})
PHOTO_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})

# Signs in tool output that the platform is blocking us rather than the media being absent.
BLOCK_MARKERS = (
    "http error 429",
    "429 too many requests",
    "too many requests",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "login required",
    "login_required",
    "sign in to confirm",
    "requires authentication",
    "authenticationerror",
    "authorizationerror",
    "authrequired",
    "challenge",
    "captcha",
)


@dataclass(frozen=True, slots=True)
class ExtractorOptions:
    timeout_seconds: int
    max_bytes: int
    max_duration_seconds: int
    max_height: int
    max_items: int
    proxies: dict[Platform, str]


def is_blocked(tool_output: str) -> bool:
    return any(marker in tool_output for marker in BLOCK_MARKERS)
