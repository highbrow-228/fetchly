"""Download log and its monthly partitions."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Integer, cast, func, insert, select, text

from fetchly.db.engine import SessionFactory
from fetchly.db.models import Download

# Arbitrary constant: serializes partition DDL across workers.
_PARTITION_LOCK_ID = 7_081_901


@dataclass(frozen=True, slots=True)
class PlatformStats:
    platform: str
    total: int
    succeeded: int
    from_cache: int


class DownloadRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    async def record(
        self,
        *,
        chat_id: int,
        platform: str,
        result: str,
        duration_ms: int,
        size_bytes: int,
        from_cache: bool,
    ) -> None:
        statement = insert(Download).values(
            chat_id=chat_id,
            platform=platform,
            result=result,
            duration_ms=duration_ms,
            size_bytes=size_bytes,
            from_cache=from_cache,
        )
        async with self._sessions.begin() as session:
            await session.execute(statement)

    async def stats_since(self, since: datetime) -> list[PlatformStats]:
        succeeded = func.sum(cast(Download.result == "ok", Integer))
        cached = func.sum(cast(Download.from_cache, Integer))
        statement = (
            select(Download.platform, func.count(), succeeded, cached)
            .where(Download.created_at >= since)
            .group_by(Download.platform)
            .order_by(Download.platform)
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).all()
        return [PlatformStats(row[0], row[1], row[2] or 0, row[3] or 0) for row in rows]

    async def ensure_partitions(self) -> None:
        """Create partitions for the current and the next month if missing."""
        this_month = datetime.now(UTC).date().replace(day=1)
        async with self._sessions.begin() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:id)"), {"id": _PARTITION_LOCK_ID}
            )
            for start in (this_month, _next_month(this_month)):
                await session.execute(text(partition_ddl(start)))


def partition_ddl(start: date) -> str:
    end = _next_month(start)
    return (
        f"CREATE TABLE IF NOT EXISTS downloads_{start:%Y_%m} PARTITION OF downloads "
        f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
    )


def _next_month(day: date) -> date:
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)
