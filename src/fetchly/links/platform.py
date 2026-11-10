"""Platform detection by URL host."""

from enum import StrEnum
from urllib.parse import urlsplit


class Platform(StrEnum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    REDDIT = "reddit"
    FACEBOOK = "facebook"


_DOMAINS: dict[str, Platform] = {
    "tiktok.com": Platform.TIKTOK,
    "instagram.com": Platform.INSTAGRAM,
    "instagr.am": Platform.INSTAGRAM,
    "youtube.com": Platform.YOUTUBE,
    "youtu.be": Platform.YOUTUBE,
    "twitter.com": Platform.TWITTER,
    "x.com": Platform.TWITTER,
    "reddit.com": Platform.REDDIT,
    "redd.it": Platform.REDDIT,
    "facebook.com": Platform.FACEBOOK,
    "fb.watch": Platform.FACEBOOK,
}


def platform_for_host(host: str) -> Platform | None:
    host = host.lower().rstrip(".")
    for domain, platform in _DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return None


def detect_platform(url: str) -> Platform | None:
    return platform_for_host(urlsplit(url).hostname or "")
