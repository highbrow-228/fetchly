"""file_id cache: Redis in front, Postgres as the source of truth."""

import hashlib
import json
from dataclasses import dataclass

from redis.asyncio import Redis

from fetchly.db import MediaRepository
from fetchly.extractors.base import MediaKind
from fetchly.links import Platform


@dataclass(frozen=True, slots=True)
class CachedItem:
    kind: MediaKind
    file_id: str


class FileIdCache:
    def __init__(self, redis: Redis, media: MediaRepository, ttl_seconds: int) -> None:
        self._redis = redis
        self._media = media
        self._ttl = ttl_seconds

    async def get(self, url: str) -> list[CachedItem] | None:
        key = _key(url)
        hot = await self._redis.get(key)
        if hot is not None:
            return _decode(json.loads(hot))
        rows = await self._media.find_by_url(url)
        if rows is None:
            return None
        await self._redis.set(key, json.dumps(rows), ex=self._ttl)
        return _decode(rows)

    async def put(
        self, url: str, platform: Platform, media_id: str, items: list[CachedItem]
    ) -> None:
        rows = [{"kind": item.kind.value, "file_id": item.file_id} for item in items]
        media_type = "album" if len(items) > 1 else items[0].kind.value
        await self._media.save(url, platform.value, media_id, media_type, rows)
        await self._redis.set(_key(url), json.dumps(rows), ex=self._ttl)


def _key(url: str) -> str:
    return "fetchly:cache:" + hashlib.sha256(url.encode()).hexdigest()


def _decode(rows: list[dict[str, str]]) -> list[CachedItem]:
    return [CachedItem(MediaKind(row["kind"]), row["file_id"]) for row in rows]
