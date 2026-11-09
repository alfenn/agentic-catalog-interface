# Codex baseline paired check

A pipeline check of the Codex baseline adapter (`src/catalog_steward/codex_baseline.py`,
config `experiments/configs/codex_baseline_v1.yaml`, prompt `codex-hygiene-v1`) on two
episodes before the full ten-episode run. Its purpose was to confirm workspace
isolation, output-schema acceptance, conversion and scoring, and dbt and DuckDB
inside the Codex sandbox. It is not a result: one sample per episode and condition,
two episodes.

Recorded 2026-11-09 with Codex CLI 0.167.0, adapter at commit 7895cb2:

```
uv run python -m catalog_steward.codex_baseline --condition codex-matched \
  --episodes rem_daily_revenue_filter_drift,change_daily_revenue_filter --jobs 2 \
  --output experiments/results/codex_baseline_v1_paired_check
# then the same with --condition codex-frontier
```

| Episode | Condition | Findings (issue, asset, action) | TP/FP/FN | Success | Files changed | Isolation flags |
|---|---|---|---|---|---|---|
| rem_daily_revenue_filter_drift | codex-matched | sql_metadata_drift, daily_revenue, patch | 1/0/0 | yes | catalog/overrides.json | none |
| rem_daily_revenue_filter_drift | codex-frontier | sql_metadata_drift, daily_revenue, patch | 1/0/0 | yes | catalog/overrides.json | none |
| change_daily_revenue_filter | codex-matched | sql_metadata_drift, daily_revenue, propose | 1/0/0 | yes | none | none |
| change_daily_revenue_filter | codex-frontier | sql_metadata_drift, daily_revenue, patch | 1/0/0 | yes | catalog/overrides.json | none |

What the check established:

- The output schema (`design/codex_plan.schema.json`) was accepted by `--output-schema`;
  every final answer parsed and validated against it.
- No isolation flag fired. A manual read of every command found no absolute paths,
  no parent-directory reads, and no repository path or episode ID in any event.
- Every claimed patch changed `catalog/overrides.json`, the catalog field equalled the
  declared value, and `dbt parse` succeeded on Codex's final workspace. No file other
  than the override file changed.
- DuckDB queries ran inside the sandbox in all four runs. Codex read
  `project/target/manifest.json` rather than calling the dbt CLI in these runs, so
  dbt inside the sandbox was confirmed separately with
  `uv run python -m catalog_steward.codex_baseline --check-codex-sandbox`, which had
  Codex run `cd project && dbt parse` and a DuckDB query (both exit 0, no flags).

## Discarded attempts

Both attempts ran the same prompt, schema, models and episodes. They were discarded
because of adapter problems, not because of their outcomes, and are kept outside the
repository.

1. **Attempt 1 (adapter at ae13f13).** All four runs completed and scored 1/0/0 with
   episode success. The isolation scan raised two false flags: an `rg` glob
   (`-g '!**/.git/**'`) was read as an absolute path, and `../warehouse.duckdb`, run
   from inside `project/`, was read as leaving the workspace. Fixed in 266cb54 (glob
   characters end a path token; one level up is allowed because events do not record
   the working directory, while listing the parent or climbing two or more levels is
   still flagged).
2. **Attempt 2 (adapter at 266cb54).** Command-citation matching rejected a citation
   that Codex had in fact run: it cited one statement of a compound command, re-quoted
   to stand alone, so the strict substring test failed and evidence validity for
   change_daily_revenue_filter / codex-matched read 0.857. Fixed in 7895cb2 (commands
   are compared with shell quoting removed). The re-run is a new model sample. In
   attempt 2, that same run had also patched the description and added a second
   finding (`unsupported_reliability_claim` on `daily_revenue`, propose). That finding
   is a false positive, so the run was 1/1/0 without episode success, and it would score
   the same under the final adapter. The other three runs in attempt 2 matched the
   table above.

So across the three samples of change_daily_revenue_filter / codex-matched, two
succeeded and one had a false positive. Single samples per condition in the full run
should be read with that variability in mind.
