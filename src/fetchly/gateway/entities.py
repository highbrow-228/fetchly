from aiogram.types import Message

from fetchly.links import Link, parse_link


def message_links(message: Message, limit: int) -> list[Link]:
    """Supported links from `url` and `text_link` entities, deduplicated, at most `limit`."""
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    raw: list[str] = []

    for entity in entities:
        match entity.type:
            case "url":
                raw.append(entity.extract_from(text))
            case "text_link" if entity.url:
                raw.append(entity.url)

    links = dict.fromkeys(link for url in raw if (link := parse_link(url)))

    return list(links)[:limit]
