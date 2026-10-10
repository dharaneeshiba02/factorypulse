FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir .
ENV PYTHONPATH=/app/src

EXPOSE 8002
CMD ["uvicorn", "copilot.main:app", "--host", "0.0.0.0", "--port", "8002"]
