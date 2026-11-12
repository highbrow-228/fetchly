"""file_id cache: Redis in front, Postgres as the source of truth."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from fetchly.db import MediaRepository
from fetchly.extractors.base import MediaKind
from fetchly.links import Platform


@dataclass(frozen=True, slots=True)
class CachedItem:
    kind: MediaKind
    file_id: str


@dataclass(frozen=True, slots=True)
class CachedMedia:
    items: list[CachedItem]
    caption: str | None


class FileIdCache:
    def __init__(self, redis: Redis, media: MediaRepository, ttl_seconds: int) -> None:
        self._redis = redis
        self._media = media
        self._ttl = ttl_seconds

    async def get(self, url: str) -> CachedMedia | None:
        key = _key(url)
        hot = await self._redis.get(key)
        if hot is not None:
            return _decode(json.loads(hot))
        found = await self._media.find_by_url(url)
        if found is None:
            return None
        payload = {"items": found[0], "caption": found[1]}
        await self._redis.set(key, json.dumps(payload), ex=self._ttl)
        return _decode(payload)

    async def put(
        self,
        url: str,
        platform: Platform,
        media_id: str,
        items: list[CachedItem],
        caption: str | None,
    ) -> None:
        rows = [{"kind": item.kind.value, "file_id": item.file_id} for item in items]
        media_type = "album" if len(items) > 1 else items[0].kind.value
        await self._media.save(url, platform.value, media_id, media_type, rows, caption=caption)
        payload = {"items": rows, "caption": caption}
        await self._redis.set(_key(url), json.dumps(payload), ex=self._ttl)


def _key(url: str) -> str:
    # v2: the payload carries the caption next to the items.
    return "fetchly:cache:v2:" + hashlib.sha256(url.encode()).hexdigest()


def _decode(payload: dict[str, Any]) -> CachedMedia:
    items = [CachedItem(MediaKind(row["kind"]), row["file_id"]) for row in payload["items"]]
    return CachedMedia(items, payload["caption"])
