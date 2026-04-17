# NASO Forensic Engine - Master Makefile

.PHONY: help up down build logs demo test

help:
	@echo "NASO Commands:"
	@echo "  make up      - Start all containers"
	@echo "  make down    - Stop all containers"
	@echo "  make build   - Rebuild Docker images"
	@echo "  make logs    - View backend and worker logs"
	@echo "  make demo    - Seed the database with 'Operation Lazarus' synthetic intelligence data"
	@echo "  make test    - Run the draconian testing suite (Pytest & Vitest)"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f naso-api naso-worker-pipeline

demo:
	docker exec -it naso-api python seed_demo_data.py

test:
	docker exec naso-api pytest tests/ -v
	cd frontend && npm run test
