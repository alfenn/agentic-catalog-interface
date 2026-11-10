# Experiments

This directory holds the frozen run configurations (`configs/`) and the saved runs
(`results/`). Every run uses the ten examples in
[`data/episodes/manifest.yaml`](../data/episodes/manifest.yaml) and the scorer
`midpoint-score-v1`, with one sample per example and condition. The
[repository README](../README.md) explains how to reproduce each run.

## Layout of a saved run

Each folder under `results/` is one run:

- `summary.json` holds the per-condition totals and run settings.
- `<example>/<condition>.json` holds one run's plan, score and run settings. For
  Codex, the plan is its final answer converted to the steward's plan form.
- `<example>/<condition>_artifacts/` holds that run's inputs and logs. For the
  steward these are the dbt build log and run results, the change diff, the
  steward's plan (`steward/plan.json`) and its action ledger
  (`steward_ledger.jsonl`). For Codex they are the prompt, the event stream
  (`events.jsonl`), the final answer, the workspace diff, the verification log,
  stderr and the CLI version.
- `analysis.md` or `README.md` is the manual audit or the run description.

## Runs used in the midway report

Table 1 and Section 3 of the [midway report](../writeups/midway_report/report.pdf)
draw on two runs, each covering all ten examples:

| Folder | Report use | Conditions | Config | Recorded |
|---|---|---|---|---|
| [`results/midpoint_v1_2_pilot/`](results/midpoint_v1_2_pilot/) | Steward column (`<example>/steward.json`) | static, generic, steward | [`configs/midpoint_v1.yaml`](configs/midpoint_v1.yaml) (1.2.0) | 2026-11-08 |
| [`results/codex_baseline_v1/`](results/codex_baseline_v1/) | Both Codex columns, and the [trace audit](results/codex_baseline_v1/analysis.md) of all three conditions | codex-matched, codex-frontier | [`configs/codex_baseline_v1.yaml`](configs/codex_baseline_v1.yaml) (1.0.0) | 2026-11-09 |

The steward and Codex results sit in separate runs because the steward pilot was run
and frozen first. The Codex runs came afterwards on the same frozen examples, with
the steward unchanged, so nothing in the steward was tuned against Codex.

The report uses only the pilot's steward condition. The pilot's static (rules-only)
and generic conditions are earlier baselines; the generic condition is the simple
custom agent that Codex replaced (report Section 2.3). Four of the pilot's 20 model
records replay the earlier 1.2.0 preliminary run on the two demo examples
(`rem_daily_revenue_filter_drift` and `change_daily_revenue_filter`, for both model
conditions); [the pilot audit](results/midpoint_v1_2_pilot/analysis.md) marks them.

Example folders and the Table 1 rows they correspond to:

| Example folder | Table 1 row |
|---|---|
| `rem_daily_revenue_filter_drift` | Stale revenue-filter description |
| `rem_customer_orders_wrong_grain` | Wrong customer-order grain |
| `rem_daily_revenue_missing_owner` | Missing owner |
| `rem_legacy_model_lifecycle` | Legacy copy still active |
| `change_daily_revenue_filter` | Revenue filter changed |
| `change_customer_orders_grain` | Grain changed, metadata not |
| `change_new_model_missing_metadata` | New undocumented model |
| `change_rename_without_lifecycle` | Rename without lifecycle change |
| `clean_new_model_documented` | Documented new model |
| `clean_daily_revenue_metric` | Documented revenue metric |

## Other saved runs

These are kept for history and are not in Table 1:

| Folder | What it is | Examples | Recorded |
|---|---|---|---|
| [`results/codex_baseline_v1_paired_check/`](results/codex_baseline_v1_paired_check/README.md) | A check of the Codex adapter before the full run: workspace isolation, output schema, conversion and scoring. Not a result. | 2 | 2026-11-09 |
| [`results/codex_midway_two_case/`](results/codex_midway_two_case/README.md) | The first Codex comparison: two runs on `gpt-6.1-terra` with a prompt that lacked the hygiene contract. It is not matched to the steward, and it motivated matching the model and task in `codex_baseline_v1`. Superseded. | 2 | 2026-11-08 |
| [`results/midpoint_v1_static/`](results/midpoint_v1_static/analysis.md) | An earlier static-only (rules-only) run from before config 1.1.0. | 10 | 2026-11-07 |
