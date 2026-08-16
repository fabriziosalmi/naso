# NASO Forensic Engine — Master Makefile

.PHONY: help bootstrap up down build logs demo test

help:
	@echo "NASO Commands:"
	@echo "  make bootstrap - Generate .secrets-mock/ and .env (run once, before 'make up')"
	@echo "  make up        - Start all containers"
	@echo "  make down      - Stop all containers"
	@echo "  make build     - Rebuild Docker images"
	@echo "  make logs      - Follow API and worker logs"
	@echo "  make demo      - Seed the database with 'Operation Lazarus' synthetic data"
	@echo "  make test      - Run the full test suite (pytest, vitest, playwright)"

# Compose mounts .secrets-mock/ at /run/secrets and will not start without it.
bootstrap:
	python cli/generate_secrets.py
	@test -f .env || cp .env.example .env
	@echo "Secrets generated. Now edit .env and replace every CHANGE_ME."

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

# `docker compose logs` takes SERVICE names. These used to be the container
# names (naso-api, naso-worker-pipeline), which Compose rejects.
logs:
	docker compose logs -f backend worker-pipeline

demo:
	docker exec naso-api python seed_demo_data.py

# Delegates to validate.sh so `make test` and CI run exactly the same checks.
# The old target called `npm run test` without --run, which left Vitest in
# watch mode and never returned.
test:
	./cli/validate.sh
