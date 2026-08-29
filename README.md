# FactoryPulse

Real-Time Predictive Maintenance & Equipment Intelligence Platform for Smart Manufacturing.

## Overview
FactoryPulse ingests high-frequency sensor telemetry, detects anomalies in near-real-time, forecasts Remaining Useful Life (RUL), and provides an agentic maintenance copilot for diagnostic guidance.

## Architecture
- **Simulator**: Replays processed datasets over MQTT/HTTP.
- **Ingestion**: Validates and batches telemetry to TimescaleDB.
- **ML Pipeline**: DVC-tracked dataset ETL, PyTorch/LightGBM training.
- **Inference**: Evaluates rolling features against registered models.
- **Copilot**: LangGraph agent with Qdrant RAG.

## Quickstart
```bash
make up
make seed
```
