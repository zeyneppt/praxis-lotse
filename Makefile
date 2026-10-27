# Praxis-Lotse – Befehle siehe CLAUDE.md
SHELL := /bin/bash

PYTHON ?= python3.12
VENV := backend/.venv
ROBOT ?= robot
ROBOT_OUT := reports/robot

ifdef SPEC
INCLUDES := --include spec-$(SPEC)
else
INCLUDES = $(shell scripts/aktive_specs.sh)
endif

.PHONY: up down ingest lint test acceptance acceptance-llm eval

up:
	mkdir -p reports/robot reports/eval
	docker compose up -d --build

down:
	docker compose down

ingest:
	docker compose exec -T backend python -m app.ingest

# MODUS=retrieval (Standard) oder voll (braucht LLM_PROVIDER=ollama oder anthropic).
# reports/eval vorher anlegen, damit der Ordner der aufrufenden Person gehört.
eval:
	mkdir -p reports/eval
	docker compose exec -T --user "$$(id -u):$$(id -g)" -e EVAL_MODUS=$(or $(MODUS),retrieval) backend python -m app.eval

$(VENV)/.installiert: backend/pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -e "backend[dev]"
	touch $@

frontend/node_modules/.package-lock.json: frontend/package-lock.json
	cd frontend && npm ci

lint: $(VENV)/.installiert frontend/node_modules/.package-lock.json
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy
	cd frontend && npx eslint . && npx tsc --noEmit

test: $(VENV)/.installiert
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test --silent

acceptance:
	@if [ -z "$(strip $(INCLUDES))" ]; then echo "Keine aktive Spec – keine Abnahmetests."; exit 0; fi; \
	$(ROBOT) --outputdir $(ROBOT_OUT) --exclude llm $(INCLUDES) tests/acceptance

acceptance-llm:
	@if [ -z "$(strip $(INCLUDES))" ]; then echo "Keine aktive Spec – keine Abnahmetests."; exit 0; fi; \
	$(ROBOT) --outputdir $(ROBOT_OUT) --exclude fake-only $(INCLUDES) tests/acceptance
