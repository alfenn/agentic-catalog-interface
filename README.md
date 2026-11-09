# Catalog steward: midpoint handoff

This prototype investigates whether an evidence-grounded steward can repair catalog hygiene debt and review dbt changes more safely and completely than a general-purpose coding agent (OpenAI's Codex CLI) given the same task and data access. It uses a local dbt/DuckDB fixture, not a hosted catalog. The frozen ten-episode midpoint configuration is in [experiments/configs/midpoint_v1.yaml](experiments/configs/midpoint_v1.yaml); the episode definitions and expected outcomes are in [data/episodes/manifest.yaml](data/episodes/manifest.yaml). See the [recorded-demo runbook](docs/midpoint_demo.md) and the [demo video script and commands](writeups/midway_report/demo/demo_script.md).

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

Add `--live` and select `generic` or `steward` in `--conditions` only when ready for paid calls. Evaluation uses the model and `reasoning_effort` pinned in its frozen config (version `1.2.0`, prompt versions `generic-hygiene-v3` and `specialized-steward-v3`), rather than the standalone steward's environment settings, and records model, temperature, max tokens, max turns and reasoning effort as `run_settings` in `summary.json` and each result file. Both model conditions share one reply protocol: a final answer whose `content` is a JSON object is serialized canonically, a malformed reply gets an error naming what was received, and a final answer that fails plan validation is sent back once for repair before it counts as an error. Each result records `protocol_rejections` and `repair_used`, and `summary.json` totals them per condition under `by_condition`. The midway report's steward condition comes from one run, [`experiments/results/midpoint_v1_2_pilot/`](experiments/results/midpoint_v1_2_pilot/summary.json): all three pilot conditions on the ten episodes under config `1.2.0`, one sample per episode. The report compares it with the [Codex baseline](#codex-baseline), not with the pilot's static and generic conditions. To run a new sample without overwriting the saved pilot, choose a new empty output directory, for example

```sh
uv run python -m catalog_steward.evaluation --conditions static,generic,steward --live --output .runs/new-midpoint-pilot
```

The saved pilot made 30 runs with 0 errors in about 8.5 minutes and cost $0.0172 in model spend ($0.0244 for all paid calls in the project, as `make costs` reports). Four of its 20 model records are cache replays of the earlier `1.2.0` preliminary run on the two demo episodes. The pilot's episode successes are static 4/10, generic 5/10 and steward 5/10 under fixture-level scoring; read them with the [manual audit](experiments/results/midpoint_v1_2_pilot/analysis.md), which bounds what they support. `make report` rebuilds the report's figures and table from this saved folder and the saved Codex baseline by default, without model calls. A new paid run is a fresh sample and need not reproduce these exact outputs; the response cache is not included in a checkout. The older [static-only run](experiments/results/midpoint_v1_static/summary.json) predates config `1.1.0` and is kept for history.

The model wrapper caches responses and records spend under the cache directory. `make costs` summarizes its ledger. The budget checks recorded spend before a cache miss, so a call can cross the threshold; it is not a provider-side hard cap. Use a small episode selection, inspect the ledger, and set a suitable budget before live runs.

## Codex baseline

The Codex baseline gives OpenAI's Codex CLI the steward's task: the same trigger, asset scope, hygiene contract (issue types, required evidence, allowed and forbidden actions), five-finding cap and patch surface (the five catalog fields in `catalog/overrides.json`). It also gets the same inputs and data access: a freshly built fixture with the dbt project, its `target/` artifacts, the DuckDB warehouse and, for change review, the diff. It does not get the steward's evidence bundle, plan validator, executor or verifier; those are what the comparison tests. The frozen configuration is [experiments/configs/codex_baseline_v1.yaml](experiments/configs/codex_baseline_v1.yaml) (Codex CLI 0.167.0, prompt `codex-hygiene-v1`, output schema [design/codex_plan.schema.json](design/codex_plan.schema.json), sandbox `workspace-write`, scorer `midpoint-score-v1`). It defines two conditions: `codex-matched` (`gpt-6-luna`, low reasoning effort, the steward pilot's model and effort) and `codex-frontier` (`gpt-6.1-sol`, medium effort).

Prerequisites: the Codex CLI 0.167.0 on `PATH`, logged in (`codex login`; runs use that account's quota, not OpenRouter), plus `uv`. dbt, DuckDB and Python for Codex come from a separate tool environment at `~/.cache/catalog-steward/codex-tools`, outside the repository, so nothing on Codex's `PATH` points at the labelled repository. The runner creates it on first use with the dbt-core, dbt-duckdb and duckdb versions pinned in `uv.lock`, and reuses it afterwards. To create it and check it, and to check dbt and DuckDB inside the Codex sandbox (one short Codex call):

```sh
uv run python -m catalog_steward.codex_baseline --check-tools
uv run python -m catalog_steward.codex_baseline --check-codex-sandbox
```

Run one condition at a time into a new, empty output directory:

```sh
uv run python -m catalog_steward.codex_baseline --condition codex-matched --jobs 3 --output .runs/codex-baseline
uv run python -m catalog_steward.codex_baseline --condition codex-frontier --jobs 3 --output .runs/codex-baseline
```

`--episodes a,b` selects a subset, and `--keep-workspaces` keeps the temporary workspaces for inspection. Each run builds its episode in a new temporary directory outside the repository with an opaque name. It removes the episode file, marker, pre-change copy and build log, checks that no episode ID or repository path remains anywhere in the workspace, and invokes `codex exec` with a minimal environment. Codex's personal settings, rules, hooks, connectors, plugins, memories and web search are disabled, and it runs a non-login shell. After Codex exits, the harness diffs the project, re-runs the steward's patch verification (the catalog field equals the declared value and `dbt parse` succeeds) on the final workspace, fails any edit outside the override file or any undeclared override change, flags commands that leave the workspace or touch label material, and scores the converted plan with the unchanged scorer. Evidence validity for Codex means that cited files exist in the workspace and cited commands were actually run. Results land in `<output>/<episode_id>/<condition>.json` (result, score, run settings, flags). Artifacts go in `<output>/<episode_id>/<condition>_artifacts/` (prompt, event stream, stderr, final answer, workspace diff, verification log, CLI version), and `<output>/summary.json` holds per-condition totals. No cost is recorded. A failed or malformed run is saved as an error, not dropped. A new run is a fresh sample and need not reproduce the saved outputs.

The saved runs are the [paired check](experiments/results/codex_baseline_v1_paired_check/README.md) on two episodes, which validated the adapter, and the [frozen ten-episode run](experiments/results/codex_baseline_v1/README.md) of both conditions, with its [trace audit](experiments/results/codex_baseline_v1/analysis.md). The earlier [two-case Codex runs](experiments/results/codex_midway_two_case/README.md) used a different model and a prompt without the contract, and are superseded.

## Midpoint limitations

The checked-in pilot is one sample per episode on ten author-built fixtures, so it supports per-episode observations, not a general or statistical comparison. Its [audit](experiments/results/midpoint_v1_2_pilot/analysis.md) records the main caveats: only the steward receives the evidence bundle, per-issue action rules and a plan validator, so call counts and unsafe-action rates are not like-for-like; the scorer matches exact issue labels and checks action classes, not episode postconditions or episode-specific unsafe actions; evidence validity only checks that cited IDs resolve, so it missed a generic run built on invented tool output; steward patch verification confirms the written value and `dbt parse`, not semantic correctness; and both clean controls contain real gaps that the labels do not anticipate. The Codex baseline has the same one-sample limit. Its [trace audit](experiments/results/codex_baseline_v1/analysis.md) finds that the steward did not win on episode success (5/10, against 6/10 for codex-matched and 7/10 for codex-frontier), and records where the labels and the scorer are disputable. The fixture is a small local study, not evidence of production performance. Hosted integrations, broader study coverage, and automatic destructive or business-semantic decisions remain outside the midpoint scope.
