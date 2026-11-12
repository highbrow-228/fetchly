import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field

from fetchly.links.platform import Platform, platform_for_host

# Query parameters that identify the media; everything else is tracking noise.
_FACEBOOK_PARAMS = ("v", "story_fbid", "fbid", "id")
_YOUTUBE_PATH_PREFIXES = ("/shorts/", "/live/", "/embed/")
# Paths of a single post. Profiles, feeds, searches and redirectors are not media links.
_POST_PATHS: dict[Platform, str] = {
    Platform.TIKTOK: r"/@[^/]+/(video|photo)/\d+|/t/\w+",
    Platform.INSTAGRAM: (
        r"/([^/]+/)?(p|reel|reels|tv)/[\w-]+|/share/((p|reel)/)?[\w-]+|/stories/[^/]+/\d+"
    ),
    Platform.TWITTER: r"/(i/web|[^/]+)/status(es)?/\d+(/(photo|video)/\d+)?",
    Platform.REDDIT: (
        r"(/(r|u|user)/[^/]+)?/comments/\w+(/[^/]*(/\w+)?)?|/r/[^/]+/s/\w+|/gallery/\w+"
    ),
    Platform.FACEBOOK: (
        r"/reel/\d+|/share(/[vrp])?/\w+|/videos/\d+|/[^/]+/(videos|posts)/([^/]+/)?\w+"
        r"|/groups/[^/]+/(permalink|posts)/\d+|/[^/]+/photos/[^/]+/\d+"
    ),
}
# Facebook pages whose post is named by the query string.
_FACEBOOK_QUERY_PATHS = (
    "/watch",
    "/photo",
    "/photo.php",
    "/video.php",
    "/story.php",
    "/permalink.php",
)
# Short-link hosts: the whole path is one opaque code (or a file name on i.redd.it).
_SHORT_HOSTS = ("vm.tiktok.com", "vt.tiktok.com", "redd.it", "v.redd.it", "i.redd.it", "fb.watch")
_SHORT_PATH = r"/[\w-]+(\.\w+)?"


class Link(BaseModel, frozen=True):
    platform: Platform = Field(description="Platform the link belongs to")
    url: str = Field(description="Link in canonical form: the same post always gives the same URL")


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

    return Link(platform=platform, url=url) if url else None


def _generic(platform: Platform, host: str, path: str, query: str) -> str | None:
    path = path.rstrip("/")
    host = host.removeprefix("www.")

    if platform is Platform.FACEBOOK and path in _FACEBOOK_QUERY_PATHS:
        post_params = _keep_params(query, _FACEBOOK_PARAMS)
        if post_params:
            return urlunsplit(("https", host, path, post_params, ""))

    pattern = _SHORT_PATH if host in _SHORT_HOSTS else _POST_PATHS[platform]
    if not re.fullmatch(pattern, path):
        return None

    return urlunsplit(("https", host, path, "", ""))


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
