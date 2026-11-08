# Catalog steward: midpoint handoff

This prototype investigates whether an evidence-grounded steward can repair catalog hygiene debt and review dbt changes more safely and completely than static checks or a generic agent. It uses a local dbt/DuckDB fixture, not a hosted catalog. The frozen ten-episode midpoint configuration is in [experiments/configs/midpoint_v1.yaml](experiments/configs/midpoint_v1.yaml); the episode definitions and expected outcomes are in [data/episodes/manifest.yaml](data/episodes/manifest.yaml). See the [recorded-demo runbook](docs/midpoint_demo.md).

## Setup and configuration

Prerequisites: `uv`, `make`, and Python 3.11 or newer (`uv sync` selects or downloads a suitable interpreter if the system Python is older). No dbt installation is needed; dbt Core and dbt-duckdb come from the lockfile. From the repository root:

```sh
make setup
make doctor
make contract
make episodes
make test
```

`make setup` copies `.env.example` to `.env` only if missing and runs `uv sync`. For an existing setup, `make sync` installs from the lockfile with `uv sync --locked`. `.env` is ignored by Git; keep credentials there or in the environment and never commit them. The configuration reads:

- `OPENROUTER_API_KEY`: required for live calls; leave empty for local deterministic work.
- `CATALOG_STEWARD_MODEL` (default `openai/gpt-6-luna`), `CATALOG_STEWARD_REASONING_EFFORT` (`low`), and `CATALOG_STEWARD_BUDGET_USD` (`10`): model and cost controls.
- `CATALOG_STEWARD_EVAL_SLICE` (empty) and `CATALOG_STEWARD_EVAL_CONCURRENCY` (`2`): reserved evaluation settings. `make doctor` reports them, but the current midpoint evaluation CLI reads neither: it iterates its selected episodes and conditions serially; use its `--episodes` option to select a subset.
- `CATALOG_STEWARD_CACHE_DIR` (`.lm_cache`), `CATALOG_STEWARD_RESULTS_DIR` (`experiments/results`), `CATALOG_STEWARD_DBT_PROJECT_DIR` (`data/fixtures/dbt_catalog`), and `CATALOG_STEWARD_WAREHOUSE_PATH` (`.artifacts/catalog.duckdb`): local paths. The cache and results directories affect the Make targets; episode workspaces use their own project and warehouse paths. The evaluation CLI writes to `<CATALOG_STEWARD_RESULTS_DIR>/<UTC timestamp>` by default; use `--output` to choose another location.

`make doctor-live` checks that live configuration includes a key; it does not prove the provider accepts it. Without a key it prints the one-line error `error: OPENROUTER_API_KEY is required for live model calls; ...` and exits non-zero. `make test` excludes tests marked `live`; `make test-live` and `make test-all` explicitly include paid or external tests, which are skipped when no key is set. `PYTEST_ARGS` can narrow a Make test invocation.

## Contract and episodes

[design/hygiene_contract.yaml](design/hygiene_contract.yaml) defines five issue types, required evidence, allowed actions and verification. `make contract` validates and summarizes it. Scope is at most 20 assets, two lineage hops, five findings, and 10,000 probe rows. Patches require direct evidence and review; semantic or organizational decisions are proposals, and insufficient or conflicting evidence calls for a report. The policy forbids deleting assets, live catalog mutation, access-policy changes, invented business semantics, and unbounded queries. See [design/research_contract.md](design/research_contract.md) for the research scope.

```sh
make episodes-check
make fixture EPISODE=rem_daily_revenue_filter_drift
make evidence EPISODE=rem_daily_revenue_filter_drift ASSET=daily_revenue
```

`episodes-check` builds every episode in temporary directories. `fixture` resets and builds the named episode under `.runs/<episode_id>`; it replaces an existing directory only when its marker matches that episode, so preserve anything needed from an earlier run first. The workspace contains `before/`, `project/`, `input.diff`, `episode.json`, `warehouse.duckdb`, and `dbt_build.log`; dbt artifacts are under `project/target/`. The evidence command resets the same workspace again (without building for SQL evidence) and prints parsed SQL facts for the selected asset, replacing the previous build artifacts. A change episode can be inspected with:

```sh
make fixture EPISODE=change_daily_revenue_filter
make evidence EPISODE=change_daily_revenue_filter ASSET=daily_revenue
```

## Steward and evaluation

The first two commands need a valid OpenRouter credential, and the steward can incur charges; `make costs` only reads the local ledger and prints `No LLM calls recorded yet.` before any live call:

```sh
make doctor-live
make steward EPISODE=rem_daily_revenue_filter_drift
make costs
```

The steward resets and builds the episode again, prints its result as JSON, and writes a plan and any generated patch artifacts under `.runs/steward/<workspace token>/artifacts/`; the workspace directory is printed first. Workspace directories that a model can see are named by an opaque, deterministic token rather than the episode ID, because episode IDs name the expected finding. Without a key it exits non-zero with a one-line `OPENROUTER_API_KEY is required` error before resetting or building anything. Inspect the evidence, findings, verification and any proposal before treating the run as successful. Output can vary with model behavior.

```sh
make pilot-static
make pilot
```

`pilot-static` runs only the non-model baseline; `pilot` runs static, generic and steward conditions and requires paid live calls. Both use the frozen configuration and write timestamped directories under `experiments/results/`, with `summary.json`, per-episode condition JSON and copied artifacts; the path is printed on the last line. Timestamped directories (`experiments/results/2*/`) are ignored by Git; copy a run to a named folder, such as `experiments/results/midpoint_v1_static/`, to check it in. Episode workspaces for an evaluation run are kept under `.runs/evaluation/<output directory name>/<workspace token>/`, one per episode and condition. `--live` checks for `OPENROUTER_API_KEY` before any reset or build: without one `make pilot` exits non-zero with a one-line error and writes nothing. The evaluation CLI supports a smaller, separately recorded run, for example:

```sh
uv run python -m catalog_steward.evaluation --conditions static --episodes rem_daily_revenue_filter_drift,change_daily_revenue_filter --output .runs/demo-static
```

Add `--live` and select `generic` or `steward` in `--conditions` only when ready for paid calls. Evaluation uses the model and `reasoning_effort` pinned in its frozen config (version `1.1.0`, prompt versions `generic-hygiene-v2` and `specialized-steward-v2`), rather than the standalone steward's environment settings, and records model, temperature, max tokens, max turns and reasoning effort as `run_settings` in `summary.json` and each result file. The checked-in [static summary](experiments/results/midpoint_v1_static/summary.json) records 4 successful episodes out of 10 under fixture-level episode scoring, not remediation success; see the [static results audit](experiments/results/midpoint_v1_static/analysis.md) for interpretation. It is not a comparison with agent performance.

The model wrapper caches responses and records spend under the cache directory. `make costs` summarizes its ledger. The budget checks recorded spend before a cache miss, so a call can cross the threshold; it is not a provider-side hard cap. Use a small episode selection, inspect the ledger, and set a suitable budget before live runs.

## Midpoint limitations

The checked-in results establish only the static baseline. A working live credential and completed live pilot are still needed to substantiate generic-versus-steward comparisons; do not present expected episode outcomes as observed agent results. The fixture and ten curated episodes are a small local study, not evidence of production performance. Hosted integrations, broader study coverage, and automatic destructive or business-semantic decisions remain outside the midpoint scope.
