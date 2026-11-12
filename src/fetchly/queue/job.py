from typing import Any

from pydantic import BaseModel, Field

from fetchly.links import Platform


class Job(BaseModel, frozen=True):
    chat_id: int = Field(description="Chat the link was posted in")
    chat_type: str = Field(description="Telegram chat type: private, group, supergroup or channel")
    message_id: int = Field(description="Message with the link; the bot replies to it")
    platform: Platform = Field(description="Platform the link belongs to")
    url: str = Field(description="Link to download, in canonical form")
    attempt: int = Field(
        default=1,
        description="Which try this is: 1 for a new job, +1 each time a failed job is queued again",
    )

    def next_attempt(self) -> "Job":
        return self.model_copy(update={"attempt": self.attempt + 1})

    def to_fields(self) -> dict[Any, Any]:  # the key type redis-py's xadd expects
        return {
            "chat_id": str(self.chat_id),
            "chat_type": self.chat_type,
            "message_id": str(self.message_id),
            "platform": self.platform.value,
            "url": self.url,
            "attempt": str(self.attempt),
        }

    @classmethod
    def from_fields(cls, fields: dict[str, str]) -> "Job":
        return cls(
            chat_id=int(fields["chat_id"]),
            chat_type=fields["chat_type"],
            message_id=int(fields["message_id"]),
            platform=Platform(fields["platform"]),
            url=fields["url"],
            attempt=int(fields["attempt"]),
        )
