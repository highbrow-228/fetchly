"""Alembic environment: async engine, URL taken from application settings."""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from fetchly.config import load_settings
from fetchly.db.models import Base


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _migrate() -> None:
    engine = create_async_engine(load_settings().postgres_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


asyncio.run(_migrate())
