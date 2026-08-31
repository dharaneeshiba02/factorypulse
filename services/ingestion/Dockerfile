FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (needed for psycopg2 / asyncpg if building from source)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ ./src/

ENV PYTHONPATH=/app/src

# Run the ingestion service
CMD ["python", "-m", "ingestion.main"]
