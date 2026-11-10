"""Gateway wiring: update routing and the webhook HTTP application."""

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

from fetchly.config import WEBHOOK_PATH
from fetchly.gateway.commands import StatsCommand, send_help
from fetchly.gateway.intake import LinkIntake
from fetchly.gateway.membership import MembershipTracker


def build_dispatcher(
    intake: LinkIntake, stats: StatsCommand, membership: MembershipTracker, owner_id: int
) -> Dispatcher:
    router = Router()
    # Bound __call__ methods: aiogram does not recognise callable objects as coroutines.
    router.message.register(send_help, Command("start", "help"))
    router.message.register(stats.__call__, Command("stats"), F.from_user.id == owner_id)
    router.message.register(intake.__call__, F.entities | F.caption_entities)
    router.my_chat_member.register(membership.__call__)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


def build_webhook_app(dispatcher: Dispatcher, bot: Bot, secret: str) -> web.Application:
    app = web.Application()
    # Updates are handled in background tasks, so Telegram gets its answer immediately.
    handler = SimpleRequestHandler(dispatcher, bot, handle_in_background=True, secret_token=secret)
    handler.register(app, path=WEBHOOK_PATH)
    return app
