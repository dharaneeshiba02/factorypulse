# FactoryPulse

FactoryPulse is a predictive maintenance platform for industrial equipment. It
combines telemetry ingestion, time-series storage, machine-learning models,
alerting, and a maintenance copilot grounded in equipment documentation.

## Project status

The repository is organized around six delivery milestones. M1 establishes the
architecture and local infrastructure; later milestones build the simulator,
ingestion path, model training and serving, console, copilot, and operational
hardening. See the [milestone roadmap](docs/milestones.md) for the current
checklist.

## Architecture at a glance

- **Simulator:** Replays public or prepared sensor data over MQTT or HTTP.
- **Ingestion:** Validates telemetry and batches readings into TimescaleDB.
- **Feature and ML pipeline:** Prepares data, computes features, trains models,
  and tracks runs with DVC and MLflow.
- **Inference and alerting:** Scores machine data, calculates health, and
  creates prioritized alerts.
- **Copilot:** Retrieves maintenance evidence and drafts cited work orders for
  human review.
- **Operations console:** Presents fleet health, machine details, alerts,
  copilot conversations, and MLOps views.

See [docs/architecture.md](docs/architecture.md) for the component flow and
design decisions.

## Local development

Requirements: Docker Engine with the Compose plugin, Python 3.10 or newer, Git,
and GNU Make (or an equivalent `make` command).

1. Copy `.env.example` to `.env` and set a local database password, then use the
   same password in `POSTGRES_PASSWORD`, `DATABASE_URL`, and
   `INGEST_DATABASE_URL`. Replace the demo-user password and authentication
   secret as well.
2. Install the seed and data-download helpers:
   `python -m pip install -r scripts/requirements.txt`.
3. Start the local infrastructure: `make up`.
4. Populate demo machines, sensors, and users: `make seed`.

The M1 Compose stack starts TimescaleDB, Redis, Qdrant, Mosquitto, and MLflow.
Run `docker compose --profile demo run --rm simulator` to replay the processed
dataset from `data/processed` through MQTT; the simulator image mounts that data
read-only and connects to the Compose Mosquitto service. Compose volumes persist
between `make down` and `make up`; `make clean` also preserves those volumes.

To download datasets, run `make datasets`. The command downloads IMS and AI4I
from their published sources. NASA's
[C-MAPSS record](https://data.nasa.gov/dataset/c-mapss-aircraft-engine-simulator-data)
currently reports that its archive is unavailable, so this repository includes
`train_FD001.txt`; use `CMAPSS_URL` to provide an authorized archive URL when
one is available. Use `make dvc-status` to inspect data-pipeline changes.
Install the ML package with `python -m pip install -e ./ml` before running
`make train`.

After downloading the large IMS and AI4I archives, add them to DVC and upload
them to the configured local remote with `dvc add data/raw/ims_bearings`,
`dvc add data/raw/ai4i_2020`, and `dvc push`. The existing FD001 text file is
kept in Git for the current pipeline checkout.

## Data sources

| Dataset           | Use                    | Source             |
| :---------------- | :--------------------- | :----------------- |
| NASA C-MAPSS      | Remaining useful life  | [NASA record][cm]  |
| NASA IMS bearings | Bearing degradation    | [NASA record][ims] |
| AI4I 2020         | Failure classification | [UCI record][ai4i] |

[cm]: https://data.nasa.gov/dataset/c-mapss-aircraft-engine-simulator-data
[ims]: https://data.nasa.gov/dataset/ims-bearings
[ai4i]: https://doi.org/10.24432/C5HS5C

Dataset files are large or separately licensed; use DVC for downloaded data
artifacts while Git tracks code and DVC metadata. Review each source's terms
before redistribution.

## Useful commands

| Command         | Action                                 |
| :-------------- | :------------------------------------- |
| `make up`       | Start local infrastructure.            |
| `make down`     | Stop containers and preserve volumes.  |
| `make seed`     | Seed six assets, sensors, and users.   |
| `make datasets` | Download available public datasets.    |
| `make train`    | Run the DVC pipeline.                  |
| `make lint`     | Run Ruff checks.                       |
| `make clean`    | Stop Compose without deleting volumes. |

## Security notes

The included environment template is for local development. Keep `.env` out of
Git, use unique local passwords, and do not expose the development MQTT broker,
database, or vector store to an untrusted network. Production authentication,
TLS, secret storage, and broker access controls are deployment requirements.
