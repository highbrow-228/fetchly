from enum import StrEnum
from urllib.parse import urlsplit


class Platform(StrEnum):
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    REDDIT = "reddit"
    FACEBOOK = "facebook"


# Exact hosts ("www." aside): other subdomains are redirectors, CDNs or unrelated services.
_HOSTS: dict[str, Platform] = {
    "tiktok.com": Platform.TIKTOK,
    "m.tiktok.com": Platform.TIKTOK,
    "vm.tiktok.com": Platform.TIKTOK,
    "vt.tiktok.com": Platform.TIKTOK,
    "instagram.com": Platform.INSTAGRAM,
    "instagr.am": Platform.INSTAGRAM,
    "youtube.com": Platform.YOUTUBE,
    "m.youtube.com": Platform.YOUTUBE,
    "music.youtube.com": Platform.YOUTUBE,
    "youtu.be": Platform.YOUTUBE,
    "twitter.com": Platform.TWITTER,
    "mobile.twitter.com": Platform.TWITTER,
    "x.com": Platform.TWITTER,
    "mobile.x.com": Platform.TWITTER,
    "reddit.com": Platform.REDDIT,
    "old.reddit.com": Platform.REDDIT,
    "new.reddit.com": Platform.REDDIT,
    "redd.it": Platform.REDDIT,
    "v.redd.it": Platform.REDDIT,
    "i.redd.it": Platform.REDDIT,
    "facebook.com": Platform.FACEBOOK,
    "m.facebook.com": Platform.FACEBOOK,
    "web.facebook.com": Platform.FACEBOOK,
    "fb.watch": Platform.FACEBOOK,
}


def platform_for_host(host: str) -> Platform | None:
    return _HOSTS.get(host.lower().rstrip(".").removeprefix("www."))


def detect_platform(url: str) -> Platform | None:
    return platform_for_host(urlsplit(url).hostname or "")
