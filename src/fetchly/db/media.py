"""Persistent file_id cache: media rows plus the links that point at them."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from fetchly.db.engine import SessionFactory
from fetchly.db.models import LinkAlias, MediaCache


class MediaRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    async def find_by_url(self, url: str) -> tuple[list[dict[str, str]], str | None] | None:
        statement = (
            select(MediaCache.items, MediaCache.caption)
            .join(
                LinkAlias,
                (LinkAlias.platform == MediaCache.platform)
                & (LinkAlias.media_id == MediaCache.media_id),
            )
            .where(LinkAlias.url == url)
        )
        async with self._sessions() as session:
            row = (await session.execute(statement)).one_or_none()
        return (row.items, row.caption) if row else None

    async def save(
        self,
        url: str,
        platform: str,
        media_id: str,
        media_type: str,
        items: list[dict[str, str]],
        *,
        caption: str | None,
    ) -> None:
        media = insert(MediaCache).values(
            platform=platform,
            media_id=media_id,
            media_type=media_type,
            items=items,
            caption=caption,
        )
        media = media.on_conflict_do_update(
            index_elements=[MediaCache.platform, MediaCache.media_id],
            set_={"media_type": media_type, "items": items, "caption": caption},
        )
        alias = insert(LinkAlias).values(url=url, platform=platform, media_id=media_id)
        alias = alias.on_conflict_do_update(
            index_elements=[LinkAlias.url], set_={"platform": platform, "media_id": media_id}
        )
        async with self._sessions.begin() as session:
            await session.execute(media)
            await session.execute(alias)
