from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

from fetchly.links import Platform


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    bot_token: str = Field(description="Bot token from @BotFather")
    webhook_secret: str = Field(
        description="Secret Telegram sends with every update; updates without it are rejected"
    )
    owner_id: int = Field(description="Telegram user id of the only person allowed to use /stats")
    allowed_chats: Annotated[frozenset[int] | None, NoDecode] = Field(
        default=frozenset(),
        description="Chats the bot answers in; None (`*` in .env) = every chat; "
        "empty = only chats with the owner or a trusted user",
    )
    trusted_user_ids: Annotated[frozenset[int], NoDecode] = Field(
        default=frozenset(),
        description="Other accounts of the owner; used with owner_id when allowed_chats is empty",
    )
    telegram_request_timeout_seconds: int = Field(
        description="Seconds to wait for one Bot API request before giving up"
    )
    telegram_retry_attempts: int = Field(
        description="Tries per Bot API request when Telegram answers 429 (too many requests)"
    )

    # Network
    gateway_host: str = Field(
        description="Host name of the gateway service; the Bot API server sends updates to it"
    )
    gateway_port: int = Field(description="Port the gateway receives Telegram updates on")
    gateway_metrics_port: int = Field(description="Port the gateway serves Prometheus metrics on")
    worker_metrics_port: int = Field(description="Port a worker serves Prometheus metrics on")
    bot_api_host: str = Field(description="Host name of the local Telegram Bot API server")
    bot_api_port: int = Field(description="Port of the local Telegram Bot API server")
    postgres_host: str = Field(description="Postgres host")
    postgres_port: int = Field(description="Postgres port")
    postgres_user: str = Field(description="Postgres user")
    postgres_password: str = Field(description="Postgres password")
    postgres_db: str = Field(description="Postgres database name")
    redis_host: str = Field(description="Redis host")
    redis_port: int = Field(description="Redis port")
    redis_password: str = Field(description="Redis password")

    # Intake limits
    user_rate_per_minute: int = Field(
        description="Links one user may send per minute; links over the limit are ignored"
    )
    chat_rate_per_minute: int = Field(
        description="Links one chat may send per minute; links over the limit are ignored"
    )
    max_links_per_message: int = Field(
        description="How many links are taken from one message; the rest are ignored"
    )

    # Send limits
    send_rate_per_chat_per_minute: int = Field(
        description="Messages the bot may send into one chat per minute; an album of N counts as N"
    )
    send_rate_global_per_second: int = Field(
        description="Messages the bot may send per second in total, across all chats and workers"
    )

    # Media limits
    max_file_size_mb: int = Field(description="Files larger than this many megabytes are not sent")
    max_duration_seconds: int = Field(
        description="Videos longer than this many seconds are not downloaded"
    )
    max_video_height: int = Field(
        description="Wanted video height in pixels: the best quality not taller than it is picked"
    )
    max_album_items: int = Field(
        description="How many photos/videos are taken from one post; the rest are skipped"
    )

    # Worker
    worker_concurrency: int = Field(
        description="How many jobs one worker container handles at the same time"
    )
    job_max_attempts: int = Field(
        description="How many times a failing job is tried before it is dropped as dead"
    )
    job_claim_idle_seconds: int = Field(
        description="A job whose worker is silent for this many seconds goes to another worker"
    )
    job_heartbeat_seconds: int = Field(
        description="Every this many seconds a worker signals that it is still working on its job"
    )
    job_state_ttl_seconds: int = Field(
        description="Seconds the bot remembers how many links of one message are still in work"
    )
    queue_block_seconds: int = Field(
        description="Seconds a worker waits for a new job before it looks for abandoned ones"
    )
    download_timeout_seconds: int = Field(
        description="Seconds one yt-dlp / gallery-dl run may take before it is killed"
    )
    url_lock_ttl_seconds: int = Field(
        description="Seconds a link stays locked so that two workers do not download it at once"
    )
    url_lock_wait_seconds: int = Field(
        description="Seconds another worker waits for that lock before giving up"
    )
    cache_ttl_seconds: int = Field(
        description="Seconds a file_id stays cached in Redis; Postgres keeps it forever"
    )
    pause_base_seconds: int = Field(
        description="Seconds a platform is paused after it rate-limits the bot; doubles on repeat"
    )
    pause_max_seconds: int = Field(description="Longest such pause, in seconds")
    maintenance_interval_seconds: int = Field(
        description="Seconds between cleanup runs (new DB partitions, leftover temp files)"
    )

    # Paths
    shared_dir: Path = Field(
        description="Directory for downloaded files; the worker and the Bot API server both see it"
    )
    cookies_dir: Path = Field(description="Directory with cookie files, one per platform")

    # Per-platform proxies (empty = direct connection)
    proxy_tiktok: str = Field(
        default="", description="Proxy URL for TikTok; empty = direct connection"
    )
    proxy_instagram: str = Field(
        default="", description="Proxy URL for Instagram; empty = direct connection"
    )
    proxy_youtube: str = Field(
        default="", description="Proxy URL for YouTube; empty = direct connection"
    )
    proxy_twitter: str = Field(
        default="", description="Proxy URL for X/Twitter; empty = direct connection"
    )
    proxy_reddit: str = Field(
        default="", description="Proxy URL for Reddit; empty = direct connection"
    )
    proxy_facebook: str = Field(
        default="", description="Proxy URL for Facebook; empty = direct connection"
    )

    log_level: str = Field(description="Minimum level of messages written to the log, e.g. INFO")

    @field_validator("allowed_chats", "trusted_user_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if isinstance(value, str):
            if value.strip() == "*":
                return None

            return frozenset(int(part) for part in value.split(",") if part.strip())

        return value

    @property
    def trusted_users(self) -> frozenset[int]:
        return self.trusted_user_ids | {self.owner_id}

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
