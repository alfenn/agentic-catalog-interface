UV ?= uv
PYTEST_ARGS ?=

.PHONY: help setup sync lock doctor doctor-live test test-live test-all

help:
	@printf '%s\n' \
	  'setup        create .env if needed and install locked dependencies' \
	  'sync         install locked dependencies' \
	  'lock         refresh uv.lock from pyproject.toml' \
	  'doctor       validate non-live configuration' \
	  'doctor-live  validate configuration required for paid model calls' \
	  'test         run deterministic tests only' \
	  'test-live    run paid/external tests explicitly' \
	  'test-all     run deterministic and live tests'

setup:
	@test -f .env || cp .env.example .env
	$(UV) sync

sync:
	$(UV) sync --locked

lock:
	$(UV) lock

doctor:
	$(UV) run python -m catalog_steward.config

doctor-live:
	$(UV) run python -m catalog_steward.config --require-live

test:
	$(UV) run pytest $(PYTEST_ARGS)

test-live:
	$(UV) run pytest -m live -s $(PYTEST_ARGS)

test-all:
	$(UV) run pytest -m "live or not live" -s $(PYTEST_ARGS)

