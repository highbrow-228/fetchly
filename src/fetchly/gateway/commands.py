from datetime import UTC, datetime, timedelta

from aiogram.types import Message

from fetchly.db import DownloadRepository, PlatformStats
from fetchly.queue import JobQueue

STATS_WINDOW = timedelta(hours=24)

HELP_TEXT = (
    "Я завантажую медіа за посиланнями з TikTok, Instagram, YouTube, X, Reddit і Facebook.\n\n"
    "Додайте мене до групи і надішліть посилання: я відповім відео або альбомом."
)


async def send_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


class StatsCommand:
    def __init__(self, downloads: DownloadRepository, queue: JobQueue) -> None:
        self._downloads = downloads
        self._queue = queue

    async def __call__(self, message: Message) -> None:
        stats = await self._downloads.stats_since(datetime.now(UTC) - STATS_WINDOW)
        lines = ["Статистика за 24 години:", *(_format(row) for row in stats)]

        if not stats:
            lines.append("завантажень не було")

        lines.append(f"Черга: {await self._queue.length()}")
        lines.append(f"Мертві задачі: {await self._queue.dead_length()}")
        await message.answer("\n".join(lines))


def _format(row: PlatformStats) -> str:
    success = round(100 * row.succeeded / row.total)
    cached = round(100 * row.from_cache / row.total)

    return f"{row.platform}: {row.total}, успішних {success}%, з кешу {cached}%"
