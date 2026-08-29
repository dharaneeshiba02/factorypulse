FROM python:3.10-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml .
RUN pip install -e .

# Copy source code
COPY src/ /app/src/

CMD ["python", "src/simulator/main.py"]
