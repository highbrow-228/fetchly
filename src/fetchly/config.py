"""Application settings. Every value comes from the environment (.env)."""

from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

from fetchly.links import Platform


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    bot_token: str
    webhook_secret: str
    owner_id: int
    allowed_chats: Annotated[frozenset[int], NoDecode] = frozenset()
    telegram_request_timeout_seconds: int
    telegram_retry_attempts: int

    # Network
    gateway_host: str
    gateway_port: int
    gateway_metrics_port: int
    worker_metrics_port: int
    bot_api_host: str
    bot_api_port: int
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    redis_host: str
    redis_port: int
    redis_password: str

    # Intake limits
    user_rate_per_minute: int
    chat_rate_per_minute: int
    max_links_per_message: int

    # Send limits
    send_rate_per_chat_per_minute: int
    send_rate_global_per_second: int

    # Media limits
    max_file_size_mb: int
    max_duration_seconds: int
    max_video_height: int
    max_album_items: int

    # Worker
    worker_concurrency: int
    job_max_attempts: int
    job_claim_idle_seconds: int
    job_heartbeat_seconds: int
    job_state_ttl_seconds: int
    queue_block_seconds: int
    download_timeout_seconds: int
    url_lock_ttl_seconds: int
    url_lock_wait_seconds: int
    cache_ttl_seconds: int
    pause_base_seconds: int
    pause_max_seconds: int
    maintenance_interval_seconds: int

    # Paths
    shared_dir: Path
    cookies_dir: Path

    # Per-platform proxies (empty = direct connection)
    proxy_tiktok: str = ""
    proxy_instagram: str = ""
    proxy_youtube: str = ""
    proxy_twitter: str = ""
    proxy_reddit: str = ""
    proxy_facebook: str = ""

    log_level: str

    @field_validator("allowed_chats", mode="before")
    @classmethod
    def _split_chats(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(int(part) for part in value.split(",") if part.strip())
        return value

    @property
    def postgres_url(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def bot_api_url(self) -> str:
        return f"http://{self.bot_api_host}:{self.bot_api_port}"

    @property
    def webhook_url(self) -> str:
        return f"http://{self.gateway_host}:{self.gateway_port}{WEBHOOK_PATH}"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def proxies(self) -> dict[Platform, str]:
        return {
            Platform.TIKTOK: self.proxy_tiktok,
            Platform.INSTAGRAM: self.proxy_instagram,
            Platform.YOUTUBE: self.proxy_youtube,
            Platform.TWITTER: self.proxy_twitter,
            Platform.REDDIT: self.proxy_reddit,
            Platform.FACEBOOK: self.proxy_facebook,
        }


WEBHOOK_PATH = "/webhook"


def load_settings() -> Settings:
    return Settings()
