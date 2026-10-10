# ADR 0001: Use TimescaleDB for telemetry storage

- **Status:** Accepted
- **Date:** 2026-10-10
- **Decision owners:** FactoryPulse engineering team

## Context

FactoryPulse receives timestamped, multi-channel readings from many machines.
The system needs efficient time-range queries, retention controls, and
aggregations while preserving PostgreSQL relationships for asset and alert
records.

## Decision

Use TimescaleDB as the PostgreSQL storage layer for high-volume time-series
data. Store raw telemetry, windowed features, predictions, and health history in
hypertables. Use continuous aggregates for common time buckets and retention
policies for high-volume raw data. Keep relational registry and maintenance
workflow records in ordinary PostgreSQL tables.

## Alternatives considered

- **Plain PostgreSQL tables:** familiar and compatible, but require more manual
  partitioning and maintenance as telemetry grows.
- **A separate time-series database:** could provide focused telemetry
  operations, but would split transactions, access patterns, and local
  development across two database systems.
- **A vendor-specific cloud time-series service:** useful for a managed
  deployment, but adds cloud dependency to a project intended to run locally.

## Consequences

- SQL, PostgreSQL tooling, and relational constraints remain available to
  application services.
- Hypertables and continuous aggregates provide time-oriented storage and query
  structures.
- Unique indexes on hypertables must include the time partitioning column.
- Retention settings and aggregate refresh windows require explicit operational
  review before production use.
- The Compose database is for local development; production backup, access
  control, and high availability remain deployment work.
