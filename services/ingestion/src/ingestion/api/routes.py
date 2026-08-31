"""FastAPI routes for the ingestion service."""
import logging
from fastapi import APIRouter, HTTPException
from ingestion.schemas import TelemetryBatch, IngestResponse, HealthResponse
from ingestion.validators import validate_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingestion"])

# The writer is injected at app startup via app.state
_writer = None


def set_writer(writer):
    global _writer
    _writer = writer


@router.post("/telemetry", response_model=IngestResponse)
async def ingest_telemetry(batch: TelemetryBatch):
    """Receive a batch of telemetry readings via HTTP POST."""
    if _writer is None:
        raise HTTPException(status_code=503, detail="Writer not initialized")

    valid, errors = validate_batch(batch.readings)
    if valid:
        await _writer.enqueue(valid)

    return IngestResponse(
        accepted=len(valid),
        rejected=len(errors),
        errors=errors[:10],  # Cap error list
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    db_ok = _writer is not None and _writer._pool is not None
    return HealthResponse(status="ok" if db_ok else "degraded", db_connected=db_ok)
