from collections.abc import Awaitable, Callable

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from fetchly.telemetry.metrics import Metrics

BeforeScrape = Callable[[], Awaitable[None]]


def add_telemetry_routes(app: web.Application, metrics: Metrics, refresh: BeforeScrape) -> None:
    async def scrape(_: web.Request) -> web.Response:
        await refresh()
        body = generate_latest(metrics.registry)

        return web.Response(body=body, headers={"Content-Type": CONTENT_TYPE_LATEST})

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    app.router.add_get("/metrics", scrape)
    app.router.add_get("/healthz", health)


async def start_site(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=port).start()

    return runner
