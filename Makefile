PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: setup infra up down clean build seed datasets dvc-status train lint \
	test test-unit test-integration test-api demo simulator

# Install local helper dependencies used by dataset and database seed scripts.
setup:
	$(PYTHON) -m pip install -r scripts/requirements.txt

# Start the M1 infrastructure and wait for its health checks.
infra:
	$(COMPOSE) up -d --wait timescaledb redis qdrant mosquitto mlflow

up: infra

# Replay the prepared dataset through the MQTT broker in the Compose network.
simulator:
	$(COMPOSE) --profile demo run --rm simulator

down:
	$(COMPOSE) down

# Stop the local stack. Named volumes are kept intact.
clean: down

# Build each application image from its service directory.
build:
	docker build -f services/simulator/Dockerfile -t factorypulse-simulator:dev services/simulator
	docker build -f services/ingestion/Dockerfile -t factorypulse-ingestion:dev services/ingestion
	docker build -f services/inference/Dockerfile -t factorypulse-inference:dev services/inference
	docker build -f services/copilot/Dockerfile -t factorypulse-copilot:dev services/copilot
	docker build -f services/console/Dockerfile -t factorypulse-console:dev services/console

seed:
	$(PYTHON) db/seed/seed_assets.py

datasets:
	$(PYTHON) scripts/download_datasets.py

dvc-status:
	dvc status

train:
	dvc repro

lint:
	ruff check ml/src services tests scripts db/seed

test-unit:
	$(PYTHON) -m pytest tests/unit -q

test-integration:
	$(PYTHON) -m pytest tests/integration -q

test-api:
	$(PYTHON) -m pytest tests/api -q

test: test-unit test-integration test-api

# M1 demo target prepares infrastructure and seed records. Application
# containers and the interactive demo arrive in later milestones.
demo: infra seed
	@echo "FactoryPulse M1 infrastructure and seed data are ready."
