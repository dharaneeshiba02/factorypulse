.PHONY: up down seed test-unit test-integration test lint demo clean infra

# Start infrastructure only
infra:
	docker compose up -d timescaledb redis qdrant mosquitto mlflow
	@echo "Waiting for services..."
	@sleep 10
	@echo "Infrastructure ready."

# Start all services
up:
	docker compose up -d --build
	@echo "All services starting..."

down:
	docker compose down

# Seed database with demo data
seed:
	python scripts/seed_db.py

# Run test pyramid
test-unit:
	cd ml && python -m pytest ../tests/unit/ -v

test-integration:
	python -m pytest tests/integration/ -v

test-api:
	python -m pytest tests/api/ -v

test: test-unit test-integration test-api

# Lint
lint:
	ruff check ml/ services/ tests/
	mypy ml/src/ --ignore-missing-imports

# Full demo: infra + seed + services
demo: infra seed up
	@echo ""
	@echo "=== FactoryPulse Demo Ready ==="
	@echo "Console: http://localhost:8501"
	@echo "MLflow: http://localhost:5000"
	@echo "API Docs: http://localhost:8001/docs"
	@echo "Qdrant: http://localhost:6333/dashboard"
	@echo "==============================="

# Cleanup everything
clean:
	docker compose down -v
	rm -rf data/processed/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
