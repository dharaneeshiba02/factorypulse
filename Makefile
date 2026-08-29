.PHONY: up down build test lint train seed

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

test:
	pytest tests/

lint:
	pre-commit run --all-files

train:
	dvc repro

seed:
	python db/seed/seed_assets.py
