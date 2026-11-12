"""Database schema. No message text or user names are stored anywhere."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    type: Mapped[str] = mapped_column(String(16))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class MediaCache(Base):
    __tablename__ = "media_cache"

    platform: Mapped[str] = mapped_column(String(16), primary_key=True)
    media_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    media_type: Mapped[str] = mapped_column(String(16))
    # [{"kind": "photo" | "video" | "animation", "file_id": "..."}], in album order
    items: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    caption: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinkAlias(Base):
    __tablename__ = "link_aliases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["platform", "media_id"],
            ["media_cache.platform", "media_cache.media_id"],
            ondelete="CASCADE",
        ),
        Index("ix_link_aliases_media", "platform", "media_id"),
    )

    url: Mapped[str] = mapped_column(Text, primary_key=True)
    platform: Mapped[str] = mapped_column(String(16))
    media_id: Mapped[str] = mapped_column(String(128))


class Download(Base):
    """Download log, range-partitioned by month on created_at."""

    __tablename__ = "downloads"
    __table_args__ = (
        Index("ix_downloads_chat", "chat_id", "created_at"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    chat_id: Mapped[int] = mapped_column(BigInteger)
    platform: Mapped[str] = mapped_column(String(16))
    result: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    from_cache: Mapped[bool] = mapped_column(Boolean)
