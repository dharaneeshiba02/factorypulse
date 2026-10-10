"""Ingestion service entrypoint — starts FastAPI + MQTT consumer."""
import asyncio
import json
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ingestion.config import config
from ingestion.writer import BatchWriter
from ingestion.mqtt_consumer import MQTTConsumer
from ingestion.api.routes import router, set_mqtt_consumer, set_writer

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
    set_mqtt_consumer(consumer)
    app.state.writer = writer
    app.state.mqtt_consumer = consumer

    logger.info("Ingestion service ready.")
    yield

    await consumer.stop()
    await writer.stop()
    logger.info("Ingestion service shut down.")


app = FastAPI(
    title="FactoryPulse Ingestion",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def rejected_http_payload(request: Request, error: RequestValidationError):
    """Retain schema-invalid HTTP payloads in the dead-letter table."""
    writer = getattr(request.app.state, "writer", None)
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"raw": raw.decode("utf-8", errors="replace")}
    if writer is not None:
        await writer.record_dead_letter(payload, "schema", str(error.errors()[:5]))
    return JSONResponse(
        status_code=422,
        content={"detail": str(error.errors()[:5])},
    )


def main():
    uvicorn.run(
        "ingestion.main:app",
        host=config.api_host,
        port=config.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
