"""Tracks which chats the bot is a member of."""

import structlog
from aiogram.types import ChatMemberUpdated

from fetchly.db import ChatRepository

log = structlog.stdlib.get_logger(__name__)

_GONE = frozenset({"left", "kicked"})


class MembershipTracker:
    def __init__(self, chats: ChatRepository) -> None:
        self._chats = chats

    async def __call__(self, update: ChatMemberUpdated) -> None:
        active = update.new_chat_member.status not in _GONE
        await self._chats.set_active(update.chat.id, update.chat.type, active=active)
        log.info("chat_membership", chat_id=update.chat.id, active=active)
