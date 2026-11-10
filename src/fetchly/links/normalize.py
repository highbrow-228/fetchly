"""URL normalization: one canonical string per media link (the cache key)."""

from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from fetchly.links.platform import Platform, platform_for_host

# Query parameters that identify the media; everything else is tracking noise.
_FACEBOOK_PARAMS = ("v", "story_fbid", "fbid", "id")
_YOUTUBE_PATH_PREFIXES = ("/shorts/", "/live/", "/embed/")


@dataclass(frozen=True, slots=True)
class Link:
    platform: Platform
    url: str


def parse_link(raw: str) -> Link | None:
    """Return a normalized supported link, or None if the URL is not supported."""
    candidate = raw.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    parts = urlsplit(candidate)
    host = (parts.hostname or "").lower()
    platform = platform_for_host(host)
    if platform is None or parts.scheme not in ("http", "https"):
        return None
    if platform is Platform.YOUTUBE:
        url = _youtube(host, parts.path, parts.query)
    else:
        url = _generic(platform, host, parts.path, parts.query)
    return Link(platform, url) if url else None


def _generic(platform: Platform, host: str, path: str, query: str) -> str | None:
    path = path.rstrip("/")
    kept = _keep_params(query, _FACEBOOK_PARAMS) if platform is Platform.FACEBOOK else ""
    if not path and not kept:
        return None
    return urlunsplit(("https", host.removeprefix("www."), path, kept, ""))


def _youtube(host: str, path: str, query: str) -> str | None:
    video_id: str | None = None
    if host.endswith("youtu.be"):
        video_id = path.strip("/").split("/")[0]
    elif path == "/watch":
        video_id = parse_qs(query).get("v", [""])[0]
    else:
        for prefix in _YOUTUBE_PATH_PREFIXES:
            if path.startswith(prefix):
                video_id = path.removeprefix(prefix).split("/")[0]
    if not video_id:
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


def _keep_params(query: str, names: tuple[str, ...]) -> str:
    params = parse_qs(query)
    return urlencode([(name, params[name][0]) for name in names if name in params])
