# FactoryPulse Architecture

## Data Flow

1. **Simulator** replays C-MAPSS/IMS data over MQTT at configurable speed
2. **Ingestion** validates (schema + physical range + timestamp monotonicity) -> writes to TimescaleDB; failures -> dead-letter table
3. **Feature Pipeline** computes windowed features (rolling stats, FFT, domain) -> materialized to feature table + Redis cache
4. **ML Training** (offline): trains anomaly/RUL/classifier -> MLflow tracked
5. **Inference Service** loads Production model from MLflow, reads features from Redis, scores real-time; Staging model in shadow mode
6. **Alert Engine** applies hysteresis thresholds, deduplicates, computes composite health scores, dispatches webhooks
7. **Copilot** (LangGraph) classifies intent -> plans tool calls (max 6) -> assembles evidence -> drafts response -> groundedness check
8. **Console** (Streamlit) renders fleet grid, machine detail, alert queue, copilot chat, drift dashboard

## Key Decisions

- Feature pipeline serialized with models (prevents training/serving skew)
- Shadow deployment (staging scores live traffic without risk)
- Hysteresis alerting (open at T_high, close at T_low)
- Grounded generation (embedding similarity + NLI verification)
