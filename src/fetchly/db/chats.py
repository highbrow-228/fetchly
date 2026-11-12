from sqlalchemy.dialects.postgresql import insert

from fetchly.db.engine import SessionFactory
from fetchly.db.models import Chat


class ChatRepository:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    async def ensure(self, chat_id: int, chat_type: str) -> None:
        """Register a chat seen for the first time; known chats are left untouched."""
        statement = insert(Chat).values(id=chat_id, type=chat_type).on_conflict_do_nothing()

        async with self._sessions.begin() as session:
            await session.execute(statement)

    async def set_active(self, chat_id: int, chat_type: str, *, active: bool) -> None:
        statement = insert(Chat).values(id=chat_id, type=chat_type, is_active=active)
        statement = statement.on_conflict_do_update(
            index_elements=[Chat.id], set_={"type": chat_type, "is_active": active}
        )

        async with self._sessions.begin() as session:
            await session.execute(statement)
