FROM qdrant/qdrant:v1.12.1

# The upstream image is intentionally minimal and omits an HTTP client. Add
# curl so Compose can check Qdrant's own readiness endpoint.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

USER 0
