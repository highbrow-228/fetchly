from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()

        self.downloads = Counter(
            "fetchly_downloads_total",
            "Processed links by platform, result and whether served from cache",
            ["platform", "result", "cached"],
            registry=self.registry,
        )

        self.download_seconds = Histogram(
            "fetchly_download_seconds",
            "Time spent downloading media",
            ["platform", "extractor"],
            buckets=(1, 2, 5, 10, 20, 30, 60, 120, 300, 600),
            registry=self.registry,
        )

        self.blocks = Counter(
            "fetchly_platform_blocks_total",
            "Times a platform blocked us (HTTP 429, login wall)",
            ["platform"],
            registry=self.registry,
        )

        self.enqueued = Counter(
            "fetchly_jobs_enqueued_total",
            "Jobs put on the queue",
            ["platform"],
            registry=self.registry,
        )

        self.rate_limited = Counter(
            "fetchly_rate_limited_total",
            "Links dropped by intake rate limits",
            ["scope"],
            registry=self.registry,
        )

        self.queue_length = Gauge(
            "fetchly_queue_length", "Jobs waiting or in progress", registry=self.registry
        )
        self.dead_length = Gauge(
            "fetchly_dead_jobs", "Jobs in the dead-letter stream", registry=self.registry
        )
