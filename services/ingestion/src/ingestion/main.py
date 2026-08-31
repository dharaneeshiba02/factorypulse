"""Ingestion service entrypoint — starts FastAPI + MQTT consumer."""
import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from ingestion.config import config
from ingestion.writer import BatchWriter
from ingestion.mqtt_consumer import MQTTConsumer
from ingestion.api.routes import router, set_writer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    writer = BatchWriter()
    await writer.start()
    set_writer(writer)

    loop = asyncio.get_running_loop()
    consumer = MQTTConsumer(writer, loop)
    consumer.start()

    logger.info("Ingestion service ready.")
    yield

    consumer.stop()
    await writer.stop()
    logger.info("Ingestion service shut down.")


app = FastAPI(
    title="FactoryPulse Ingestion",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


def main():
    uvicorn.run(
        "ingestion.main:app",
        host=config.api_host,
        port=config.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
