# NASO Forensic Engine — Master Makefile

PYTHON ?= python3

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
# The script also renders .env from .env.example with the generated values, so
# the credentials the containers are provisioned with and the ones the
# application connects with actually agree. An existing .env is left alone.
#
# `python` and not `python3` was a portability bug in the first command of the
# documented quickstart: macOS ships no `python`, so a clean clone failed at
# `make bootstrap` with "make: python: No such file or directory". Override
# with `make bootstrap PYTHON=…` to use a specific interpreter or a venv.
bootstrap:
	$(PYTHON) cli/generate_secrets.py

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
