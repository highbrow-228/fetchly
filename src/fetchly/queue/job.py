"""Download job: one link from one message."""

from dataclasses import dataclass, replace

from fetchly.links import Platform


@dataclass(frozen=True, slots=True)
class Job:
    chat_id: int
    chat_type: str
    message_id: int
    platform: Platform
    url: str
    attempt: int = 1

    def next_attempt(self) -> "Job":
        return replace(self, attempt=self.attempt + 1)

    def to_fields(self) -> dict[str, str]:
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
