# Codex baseline, frozen ten-episode run

Both Codex conditions on the ten frozen pilot episodes, one sample per episode and
condition, recorded 2026-11-09 with Codex CLI 0.167.0 and adapter commit 7895cb2.
Configuration: `experiments/configs/codex_baseline_v1.yaml` (version 1.0.0, frozen;
prompt `codex-hygiene-v1`; output schema `design/codex_plan.schema.json`; scorer
`midpoint-score-v1`).

| Condition | Model | Reasoning effort |
|---|---|---|
| codex-matched | gpt-6-luna | low (the steward pilot's model and effort) |
| codex-frontier | gpt-6.1-sol | medium |

```
uv run python -m catalog_steward.codex_baseline --condition codex-matched --jobs 3 \
  --output experiments/results/codex_baseline_v1
uv run python -m catalog_steward.codex_baseline --condition codex-frontier --jobs 3 \
  --output experiments/results/codex_baseline_v1
```

Each condition was run once. All 20 runs completed (no errors, timeouts or
infrastructure failures), so none was repeated and there are no discarded attempts.
No isolation flag fired, and no run changed a file other than
`project/catalog/overrides.json`.

Layout: `summary.json` (per-condition totals, no cost fields);
`<episode_id>/<condition>.json` (converted plan, Codex's final answer, score, run
settings, post-run flags); `<episode_id>/<condition>_artifacts/` (prompt, Codex event
stream, stderr, final answer, project diff, verification log, CLI version).

The scores come from the unchanged scorer and are only half the picture. Read them
with [analysis.md](analysis.md), the per-episode trace audit across the steward pilot
and both Codex conditions, which records where the labels and the scorer are
disputable.
