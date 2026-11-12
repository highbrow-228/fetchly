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


def _author(platform: Platform, entry: dict[str, Any]) -> str:
    name = entry.get("uploader") or entry.get("channel") or entry.get("uploader_id")
    if not name:
        return _MISSING
    url = entry.get("uploader_url") or entry.get("channel_url")
    # These two extractors return no profile link; the handle is enough to build one.
    if not url and platform is Platform.INSTAGRAM and entry.get("channel"):
        url = f"https://www.instagram.com/{entry['channel']}/"
    if not url and platform is Platform.REDDIT and entry.get("uploader"):
        url = f"https://www.reddit.com/user/{entry['uploader']}/"
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
