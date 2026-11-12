"""Caption under the media: author, date, views, location, TikTok track."""

from html import escape
from typing import Any

from fetchly.links import Platform

_MISSING = "None"


def build_caption(platform: Platform, entry: dict[str, Any]) -> str:
    """Telegram HTML built from one yt-dlp metadata entry."""
    lines = [
        f"👤 {_author(platform, entry)}",
        f"📅 {_date(entry.get('upload_date'))}",
        f"👁️ {_views(entry.get('view_count'))}",
        f"🌍 {_text(entry.get('location'))}",
    ]
    if platform is Platform.TIKTOK:
        lines.append(f"🎵 {_track(entry)}")
    return "\n".join(lines)


def from_gallery_dl(platform: Platform, meta: dict[str, Any]) -> dict[str, Any]:
    """Maps gallery-dl post metadata onto the yt-dlp field names used above."""
    entry: dict[str, Any] = {"upload_date": str(meta.get("date") or "")[:10].replace("-", "")}
    if platform is Platform.TIKTOK:
        author, music = _dict(meta.get("author")), _dict(meta.get("music"))
        handle = author.get("uniqueId") or meta.get("user")
        entry |= {
            "uploader": author.get("nickname") or handle,
            "uploader_url": f"https://www.tiktok.com/@{handle}" if handle else None,
            "view_count": _dict(meta.get("stats")).get("playCount"),
            "location": meta.get("locationCreated"),  # country code of the upload
            "track": music.get("title"),
            "artist": music.get("authorName"),
        }
    elif platform is Platform.INSTAGRAM:
        entry |= {
            "uploader": meta.get("fullname") or meta.get("username"),
            "channel": meta.get("username"),
            "location": meta.get("location_name"),
        }
    elif platform is Platform.TWITTER:
        author = _dict(meta.get("author"))
        handle = author.get("name")
        entry |= {
            "uploader": author.get("nick") or handle,
            "uploader_url": f"https://x.com/{handle}" if handle else None,
            "view_count": meta.get("view_count") or None,  # 0 means "not reported"
        }
    elif platform is Platform.REDDIT:
        entry |= {"uploader": meta.get("author")}
    elif platform is Platform.FACEBOOK:
        entry |= {"uploader": meta.get("username"), "uploader_id": meta.get("user_id")}
    return entry


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _author(platform: Platform, entry: dict[str, Any]) -> str:
    name = entry.get("uploader") or entry.get("channel") or entry.get("uploader_id")
    if not name:
        return _MISSING
    url = entry.get("uploader_url") or entry.get("channel_url")
    # These extractors return no profile link; the handle or id is enough to build one.
    if not url and platform is Platform.INSTAGRAM and entry.get("channel"):
        url = f"https://www.instagram.com/{entry['channel']}/"
    if not url and platform is Platform.REDDIT and entry.get("uploader"):
        url = f"https://www.reddit.com/user/{entry['uploader']}/"
    if not url and platform is Platform.FACEBOOK and entry.get("uploader_id"):
        url = f"https://www.facebook.com/{entry['uploader_id']}"
    if not url:
        return escape(str(name))
    return f'<a href="{escape(str(url))}">{escape(str(name))}</a>'


def _date(upload_date: Any) -> str:
    if not isinstance(upload_date, str) or len(upload_date) != 8:  # yt-dlp: YYYYMMDD
        return _MISSING
    return f"{upload_date[6:]}.{upload_date[4:6]}.{upload_date[:4]}"


def _views(count: Any) -> str:
    if not isinstance(count, int):
        return _MISSING
    return f"{count:,}".replace(",", " ")


def _track(entry: dict[str, Any]) -> str:
    track, artist = entry.get("track"), entry.get("artist")
    if track and artist:
        return escape(f"{track} — {artist}")
    return _text(track)


def _text(value: Any) -> str:
    return escape(str(value)) if value else _MISSING
