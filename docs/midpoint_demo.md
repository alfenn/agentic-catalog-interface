# Midpoint recorded-demo runbook

The recorded demo is now scripted from the completed three-condition pilot (`experiments/results/midpoint_v1_2_pilot/`, frozen config 1.2.0):

- [`writeups/midway_report/demo/demo_script.md`](../writeups/midway_report/demo/demo_script.md): a 2:45 run sheet with timestamps, what is on screen, word-for-word narration, measured command times, a pre-recording checklist, and a fallback for each live command.
- [`writeups/midway_report/demo/demo_commands.sh`](../writeups/midway_report/demo/demo_commands.sh): one function per segment (`./demo_commands.sh prep`, then `1` to `7`; `time` to rehearse).
- `writeups/midway_report/demo/figures/`: the charts, generated from the pilot's `summary.json` by `writeups/midway_report/make_figures.py --demo-charts`.

The connected story uses two episodes. Each resets independently from its own fixture, so the second does not carry forward the first's patch.

1. `rem_daily_revenue_filter_drift`: the catalog says all orders, while the SQL keeps completed orders only. The steward patches the catalog description (SQL unchanged), verifies it, and records it in its ledger.
2. `change_daily_revenue_filter`: a change starts including refunded orders while the metadata still says completed-only. The steward flags it as a proposal for human review, because the revenue definition is a semantic decision.

On camera, model results are not paid for and do not vary. The steward runs are replayed from the on-disk response cache (`.lm_cache`) by the evaluation CLI, with `CATALOG_STEWARD_BUDGET_USD` set far below the recorded spend, so a cache miss raises an error instead of calling the provider. `make costs` is identical before and after. The CLI's `--live` gate still requires `OPENROUTER_API_KEY` to be set, even though no call is made. Without a key, show the saved pilot artifacts (`DEMO_SAVED=1`). See the [README](../README.md) for setup, output locations and reproducibility details.
