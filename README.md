# FactoryPulse - Industrial Equipment Intelligence Platform

Predictive maintenance platform that learns normal machine behavior, detects anomalies, predicts Remaining Useful Life (RUL), diagnoses faults, and generates work orders via an AI copilot grounded in plant documentation.

## Quick Start

```bash
cp .env.example .env # Add your LLM_API_KEY
make demo # Launches everything
```

## Services

| Service | Port | Description |
|-------------|------|------------------------------------------|
| Console | 8501 | Streamlit dashboard |
| Inference | 8001 | FastAPI model serving + shadow deployment |
| Copilot | 8002 | LangGraph agent with 5 tools |
| MLflow | 5000 | Experiment tracking & model registry |
| TimescaleDB | 5432 | Telemetry + application data |
| Redis | 6379 | Online feature cache |
| Qdrant | 6333 | Maintenance manual vector store |
| Mosquitto | 1883 | MQTT broker for sensor data |

## Datasets

| Dataset | Source | ML Task |
|--------------------|---------------------------|-------------------------------|
| C-MAPSS (FD001-04) | NASA Prognostics | RUL prediction |
| IMS Bearings | UC Irvine / NASA | Anomaly detection |
| AI4I 2020 | UCI ML Repository | Failure-mode classification |

## Milestones

| Milestone | Scope |
|-----------|-------------------------------------------------|
| M1 | Architecture, repo, Docker Compose, DB schema |
| M2 | Simulator, ingestion, feature pipeline |
| M3 | ML models (anomaly, RUL, classifier) |
| M4 | Inference service, alerts, health scoring |
| M5 | GenAI copilot, RAG, agentic workflow |
| M6 | Console, deployment, drift monitoring |
