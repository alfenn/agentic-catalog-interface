UV ?= uv
PYTEST_ARGS ?=
EPISODE ?= rem_daily_revenue_filter_drift
ASSET ?= daily_revenue
REPORT_RESULTS ?= experiments/results/midpoint_v1_2_pilot

.PHONY: help setup sync lock doctor doctor-live contract episodes episodes-check fixture evidence steward pilot-static pilot test test-live test-all costs report

help:
	@printf '%s\n' \
	  'setup        create .env if needed and install locked dependencies' \
	  'sync         install locked dependencies' \
	  'lock         refresh uv.lock from pyproject.toml' \
	  'doctor       validate non-live configuration' \
	  'doctor-live  validate configuration required for paid model calls' \
	  'contract     validate and summarize the hygiene contract' \
	  'episodes     list and validate evaluation episodes' \
	  'episodes-check reset and build every episode in temporary directories' \
	  'fixture      reset and build EPISODE=<episode_id>' \
	  'evidence     inspect SQL facts for EPISODE=<id> ASSET=<model>' \
	  'steward      run the live steward for EPISODE=<episode_id>' \
	  'pilot-static run the frozen static baseline on all episodes' \
	  'pilot        run all frozen midpoint conditions (paid)' \
	  'test         run deterministic tests only' \
	  'test-live    run paid/external tests explicitly' \
	  'test-all     run deterministic and live tests' \
	  'costs        summarize recorded live-model cost' \
	  'report       regenerate midway-report charts, report.tex, and report.pdf from REPORT_RESULTS'

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

contract:
	$(UV) run python -m catalog_steward.contract

episodes:
	$(UV) run python -m catalog_steward.episodes list

episodes-check:
	$(UV) run python -m catalog_steward.episodes validate --build

fixture:
	$(UV) run python -m catalog_steward.episodes reset $(EPISODE) --build

evidence:
	$(UV) run python -m catalog_steward.evidence $(EPISODE) $(ASSET) --kind sql

steward:
	$(UV) run python -m catalog_steward.steward $(EPISODE)

pilot-static:
	$(UV) run python -m catalog_steward.evaluation --conditions static

pilot:
	$(UV) run python -m catalog_steward.evaluation --conditions static,generic,steward --live

test:
	$(UV) run pytest $(PYTEST_ARGS)

test-live:
	$(UV) run pytest -m live -s $(PYTEST_ARGS)

test-all:
	$(UV) run pytest -m "live or not live" -s $(PYTEST_ARGS)

costs:
	$(UV) run python -m catalog_steward.llm

report:
	$(UV) run --group report python writeups/midway_report/build_report.py --results $(REPORT_RESULTS)
