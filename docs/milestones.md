# FactoryPulse | Delivery Roadmap

> **Purpose**  
> Track the implementation of FactoryPulse from data foundations through a
> production-ready demo. Check off work only after implementation and acceptance
> evidence have been reviewed.

## Project status

- **M1** — Foundations and data engineering — Complete
- **M2** — Ingestion and storage — Complete
- **M3** — Core machine learning — Not started
- **M4** — Serving and alerting — Not started
- **M5** — GenAI maintenance copilot — Not started
- **M6** — MLOps hardening and demo — Not started

**Status key:** `Not started` -> `In progress` -> `Complete`  
Update the status in this table as work progresses. Mark a milestone complete
only when all its checklist items and exit criteria are satisfied.

### M1 acceptance review

**Result: Complete.** All five infrastructure services passed their Compose
health checks. The simulator image built and replayed the real processed
C-MAPSS data through MQTT. DVC canonicalization and unit-wise splitting
reproduced successfully: 505,512 canonical readings across 100 engine units
and 21 sensors, split into train/validation/test outputs. Five DVC objects were
pushed to the configured local remote, and a repeat `dvc repro split` reported
the M1 stages up to date. The database contains six demo machines, 30 sensors,
and five users with bcrypt-hashed passwords; Compose configuration validated
and `.env` remains ignored by Git. The remaining DVC status entries are for
later feature/training stages, outside M1.

## Milestones

### M2 acceptance review

**Result: Complete.** Compose configuration validated and the TimescaleDB
compatibility migration completed against the existing local volume. The
ingestion service built and reached readiness with database, Redis, and MQTT
connected. A live HTTP batch stored eight readings and 224 derived features;
an out-of-range temperature was rejected and recorded in the dead-letter table.
The Redis feature snapshot returned rolling, trend, FFT band-energy, and
spectral-kurtosis values. The corrected MQTT simulator replay stored 6,111
readings and 171,108 feature rows with no replay validation rejects. The replay
also verified automatic asset and sensor registration. These checks cover the
M2 ingestion and online-feature path; model training, inference, and alerting
remain later milestones.

### M1 - Architecture and project setup

**Objective:** Establish the repository, infrastructure, architecture decisions,
and reproducible project foundation for the FactoryPulse platform.

- [x] Add Python, environment, IDE, data, DVC, and operating-system exclusions
      to `.gitignore`.
- [x] Create the service, shared ML, data, script, configuration, and test
      directory scaffolds.
- [x] Add the source files and requested placeholder scaffold from the M1
      implementation PDF to the repository.
- [x] Document the system, service catalogue, datasets, setup, and milestone
      roadmap in `README.md`.
- [x] Document the architecture data flow and accepted TimescaleDB and copilot
      decisions.
- [x] Provide local environment settings and a development-only Mosquitto
      configuration without committing secrets.
- [x] Define the registry, telemetry, dead-letter, feature, prediction, alert,
      health, work-order, user, audit, and drift database tables.
- [x] Configure hypertables, aggregates, indexes, and telemetry retention in the
      database initialization script.
- [x] Configure the five local infrastructure containers with persistent
      volumes, health checks, and loopback-only ports.
- [x] Provide populated Dockerfiles and package metadata for all five
      application services.
- [x] Document and package the shared ML library and its dependencies.
- [x] Add Make targets for setup, infrastructure, builds, seeding, datasets,
      DVC, lint, test suites, demo preparation, shutdown, and cleanup.
- [x] Initialize DVC with a local development remote and create the public
      dataset preparation script.
- [x] Reproduce the C-MAPSS canonicalization and split stages; verify processed
      outputs contain the source dataset rather than placeholder readings and
      record the resulting dataset with DVC.
- [x] Build the simulator image and run a dataset replay through the Compose
      MQTT broker.
- [x] Seed six demo machines, 30 sensors, and five role-based users with locally
      configured, bcrypt-hashed passwords.
- [x] Validate the complete M1 data/DVC workflow, seed, and configuration, then
      record release evidence.

**Exit criteria:** All listed foundation artifacts are present, configuration
files validate, real dataset outputs are reproducible and DVC-tracked, and the
seed script matches the documented demo inventory with seed records loaded.

> **Release note:** M1 implementation is complete. Create the `v0.1.0-M1` tag
> only from an M1-only release commit. The current feature branch already
> contains M2 commits, so tagging its HEAD as M1 would mislabel the release.

### M2 - Ingestion and storage

**Objective:** Validate and store telemetry reliably, then make consistent
features available to batch training and online inference.

- [x] Define and validate telemetry schemas, units, physical ranges, and
      monotonic timestamps.
- [x] Implement HTTP batch ingestion and MQTT consumption with configurable
      machine streams.
- [x] Persist valid readings to TimescaleDB hypertables using batched writes;
      route rejected payloads and reason codes to a dead-letter table.
- [x] Add continuous aggregates, indexes, and retention policy for raw
      telemetry.
- [x] Implement rolling, spectral (FFT band energy and spectral kurtosis), and
      trend features with matching offline/online transforms.
- [x] Write windowed features to storage and cache online features in Redis with
      expiry and database fallback.
- [x] Implement REST asset registry operations for machines, sensors, and
      machine classes.
- [x] Add health/readiness endpoints and service configuration for ingestion and
      data components.

**Exit criteria: Met.** Replayed readings are validated and persisted, rejected
readings can be inspected in the dead-letter path, and the shared feature
transforms produce persisted and cached online features.

### M3 - Core machine learning

**Objective:** Train and evaluate the anomaly, RUL, failure-mode, and
thermal-analysis models with tracked, reproducible experiments.

- [ ] Train an LSTM autoencoder on healthy windows and fit adaptive anomaly
      thresholds per machine class.
- [ ] Train a Transformer RUL model on C-MAPSS and an XGBoost baseline; report
      RMSE and NASA scoring metrics.
- [ ] Train the AI4I failure-mode classifier for tool wear, heat dissipation,
      power, and overstrain; report macro-F1 and a confusion matrix.
- [ ] Implement thermal-image intake and synthetic hotspot generation; detect
      and score hotspots with the OpenCV pipeline and attach overlay evidence.
- [ ] Fuse thermal anomaly scores into machine health scoring inputs.
- [ ] Log parameters, metrics, artifacts, and evaluation reports to MLflow;
      support model registry stages and promotion/rollback.
- [ ] Generate reproducible evaluation reports for anomaly detection, RUL,
      classification, and thermal detection.
- [ ] Evaluate business targets: at least 48 hours of fault lead time, C-MAPSS
      FD001 RUL RMSE at most 20 cycles, and at least 60% fewer false alarms than
      the static-threshold baseline at fixed recall.

**Exit criteria:** Training is reproducible, results are tracked in MLflow, and
benchmark metrics and limitations are documented against the stated targets.

### M4 - Serving and alerting

**Objective:** Serve model results reliably and turn them into actionable,
auditable alerts in the operations console.

- [ ] Build the inference API to return anomaly score, RUL, failure-mode
      probabilities, model versions, and machine health.
- [ ] Load pinned Production models from MLflow, support safe hot
      reload/fallback, and run Staging candidates in shadow mode.
- [ ] Persist prediction snapshots and calculate a 0-100 health score from
      anomaly trend, RUL, open alerts, and thermal score.
- [ ] Implement deduplicated INFO/WARN/CRITICAL alerts with hysteresis and full
      model-output snapshots.
- [ ] Send CRITICAL alert webhooks with retry/backoff to a configurable
      endpoint.
- [ ] Build the console fleet view, machine detail charts (including anomaly
      overlay and RUL), and alert queue with acknowledge/resolve actions.
- [ ] Add JWT authentication, role-gated endpoints, bcrypt password hashing, and
      append-only audit records for alert actions and work-order approvals.
- [ ] Measure the end-to-end sensor-to-dashboard alert path against the
      five-second target and inference p95 against the 150 ms target.

**Exit criteria:** A replayed failing machine produces a persisted, deduplicated
alert that appears in the console with supporting prediction data and the
required access controls.

### M5 - GenAI maintenance copilot

**Objective:** Give technicians citation-backed diagnostic guidance and a
human-reviewed work-order workflow.

- [ ] Build a versioned document corpus from manuals, fault-code references,
      vibration severity tables, and maintenance logs.
- [ ] Chunk documents with heading/table context, metadata, and source
      locations; embed and index them in Qdrant.
- [ ] Implement hybrid dense and keyword retrieval, reciprocal-rank fusion, and
      reranking.
- [ ] Build the LangGraph copilot with tools for machine health, recent
      anomalies, RUL, manual search, and maintenance history.
- [ ] Generate alert-based work-order drafts with symptoms, probable cause,
      recommended parts, safety steps, and inline citations.
- [ ] Add claim-level groundedness checks, one regeneration attempt, and
      explicit uncertainty or missing-documentation messages.
- [ ] Require engineer/human approval before a work order can be approved;
      record edits and approval in the audit log.
- [ ] Add session memory, approved-case retrieval, bounded tool calls, and
      graceful tool-timeout handling.
- [ ] Expose the approved copilot tools through authenticated, audited MCP stdio
      and HTTP transports.
- [ ] Curate at least 60 golden Q&A examples and evaluate retrieval hit-rate@5
      (at least 0.85), citation-supported claims/groundedness (at least 0.90),
      and answer quality.
- [ ] Add the console copilot chat and work-order review/approval flow; measure
      first-token latency against the three-second target.

**Exit criteria:** A technician can ask about an alert, receive a grounded,
cited work-order draft, and route it through an auditable human approval step.

### M6 - MLOps hardening and demo

**Objective:** Verify operational quality, document recovery and deployment, and
deliver a repeatable end-to-end demonstration.

- [ ] Complete CI for formatting/lint, typing, unit and integration/API tests,
      and container image builds.
- [ ] Add scheduled train/evaluation workflow with metric gates and
      candidate-versus- production checks.
- [ ] Implement PSI/KS feature and prediction drift monitoring, MLflow reports,
      and retraining triggers.
- [ ] Complete unit, integration, API/auth matrix, AI evaluation,
      performance/load, and end-to-end coverage for the critical paths.
- [ ] Verify the core logic coverage target of at least 80% and test ingestion
      at 200 messages/second and inference at 50 requests/second with documented
      results.
- [ ] Verify reliability behavior: dead-lettering, simulator reconnects,
      last-known-good inference fallback, service health/readiness checks, and
      Compose restart policies.
- [ ] Complete security review for input validation, secret handling, role
      checks, prompt-injection boundaries, and sensitive-data logging.
- [ ] Finish architecture/runbook documentation, including local setup,
      recovery, backfill, model promotion/rollback, and prod-like deployment
      guidance.
- [ ] Implement the discrete-event maintenance-cost simulation and compare
      against calendar-based maintenance; target at least 25% simulated cost
      reduction.
- [ ] Prepare a repeatable demo script showing simulator-to-alert-to-copilot
      flow, model/drift views, and supporting metric results; record a demo
      video if required.
- [ ] Review all business objectives and document achieved values, gaps, and
      known limitations.

**Exit criteria:** The documented demo works from a clean setup, required
quality/performance/security checks have evidence, and business targets have
been evaluated and reported.

## Decision and progress log

- 2026-10-10 — M2 — Ingestion and telemetry path complete.
  - Evidence: Compose config and migration succeeded; HTTP ingestion stored
    8 readings and 224 feature rows; MQTT replay stored 6,111 readings and
    171,108 feature rows with zero rejects; `/api/v1/health` reported DB,
    Redis, and MQTT connected.

## Project completion

- [ ] All six milestones are complete and their exit criteria are met.
- [ ] Final results, known limitations, and links to evaluation evidence are
      recorded above.
