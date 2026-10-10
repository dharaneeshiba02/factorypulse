FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY services/ingestion/pyproject.toml ./
COPY services/ingestion/src/ ./src/
COPY ml/src/ ./ml-src/
RUN python -m pip install --no-cache-dir .
ENV PYTHONPATH=/app/src:/app/ml-src

CMD ["python", "-m", "ingestion.main"]
