from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import ChatMemberRestricted
from redis.asyncio import Redis

# How long the answer "is a trusted user in this chat" is remembered.
PRESENCE_TTL_SECONDS = 600
_ABSENT = (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)


class ChatAccess:
    """Decides whether the bot works in a chat.

    With a list of allowed chats, only those chats (or every chat for `*`).
    Without one, only chats that have at least one trusted user as a member.
    """

    def __init__(
        self,
        bot: Bot,
        redis: Redis,
        *,
        allowed_chats: frozenset[int] | None,
        trusted_users: frozenset[int],
    ) -> None:
        self._bot = bot
        self._redis = redis
        self._allowed_chats = allowed_chats
        self._trusted_users = trusted_users

    async def allows(self, chat_id: int) -> bool:
        if self._allowed_chats is None:
            return True

        if self._allowed_chats:
            return chat_id in self._allowed_chats

        key = f"fetchly:access:{chat_id}"
        remembered = await self._redis.get(key)
        if remembered is not None:
            return bool(int(remembered))

        present = await self._has_trusted_user(chat_id)
        await self._redis.set(key, int(present), ex=PRESENCE_TTL_SECONDS)

        return present

    async def _has_trusted_user(self, chat_id: int) -> bool:
        for user_id in self._trusted_users:
            try:
                member = await self._bot.get_chat_member(chat_id, user_id)
            except TelegramAPIError:  # Telegram does not know this user in this chat
                continue

            if isinstance(member, ChatMemberRestricted):
                if member.is_member:
                    return True
            elif member.status not in _ABSENT:
                return True

        return False
