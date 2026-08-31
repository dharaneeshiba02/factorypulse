"""Async batch writer to TimescaleDB using asyncpg."""
import asyncio
import logging
from typing import List
import asyncpg
from ingestion.schemas import TelemetryReading
from ingestion.config import config

logger = logging.getLogger(__name__)

INSERT_SQL = """
    INSERT INTO telemetry (time, machine_id, sensor, value, quality)
    VALUES ($1, $2, $3, $4, $5)
"""


class BatchWriter:
    """Accumulates readings and flushes them in batches to TimescaleDB."""

    def __init__(self):
        self._buffer: List[TelemetryReading] = []
        self._pool: asyncpg.Pool | None = None
        self._flush_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Initialize the connection pool and periodic flush."""
        self._pool = await asyncpg.create_pool(
            config.database_url.replace("postgresql://", "postgres://"),
            min_size=2,
            max_size=10,
        )
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("BatchWriter started — pool ready.")

    async def stop(self):
        """Flush remaining buffer and close pool."""
        if self._flush_task:
            self._flush_task.cancel()
        await self._flush()
        if self._pool:
            await self._pool.close()
        logger.info("BatchWriter stopped.")

    async def enqueue(self, readings: List[TelemetryReading]):
        """Add readings to the buffer."""
        async with self._lock:
            self._buffer.extend(readings)
        if len(self._buffer) >= config.batch_size:
            await self._flush()

    async def _flush(self):
        """Write buffered readings to the database."""
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        if not self._pool:
            logger.error("No database pool — dropping %d readings", len(batch))
            return

        rows = [
            (r.time, r.machine_id, r.sensor, r.value, r.quality) for r in batch
        ]
        try:
            async with self._pool.acquire() as conn:
                await conn.executemany(INSERT_SQL, rows)
            logger.info("Flushed %d readings to TimescaleDB.", len(rows))
        except Exception:
            logger.exception("Failed to flush %d readings", len(rows))

    async def _periodic_flush(self):
        """Flush the buffer on a timer regardless of batch size."""
        while True:
            await asyncio.sleep(config.flush_interval_seconds)
            await self._flush()
