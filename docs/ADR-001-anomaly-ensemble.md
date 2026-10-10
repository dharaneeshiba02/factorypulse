# ADR-001: Anomaly Detection Ensemble

## Status: Accepted

## Context

Single-model approaches miss different failure patterns.

## Decision

Use an ensemble of LSTM Autoencoder + Isolation Forest:
- LSTM-AE: Trained on healthy-only data; high reconstruction error = anomaly. Captures temporal patterns and gradual degradation.
- Isolation Forest: Catches point anomalies and sudden shifts.
- Adaptive thresholds: Per-machine calibrated (not static across fleet).

## Consequences

- Two models to maintain, but coverage of gradual + sudden anomalies
- Higher compute cost per inference (acceptable given <5s SLO)
