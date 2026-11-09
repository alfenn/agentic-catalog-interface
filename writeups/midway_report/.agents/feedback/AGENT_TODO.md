---
source: "claude-opus-5.5"
context: ["AGENT_PLAN.md", "agent_response_2__codex.md"]
datetime: 2026-11-08
---

# TODO: Codex baseline and system design

Work in order. Commit and push after each completed item, with the matching
entry in `../agent_notes.md`. Italic notes give each open item's current owner
or dependency.

## Setup

- [x] **S0 — Align main with the first round.** Moved local main onto the pushed
  first-round commit, committed the design-notes move and the follow-up
  feedback, and pushed.
- [x] **S1 — Plan and tracking.** Wrote `AGENT_PLAN.md` and this file.

## Experiment

- [ ] **E1 — Isolated tool environment.** _(in progress, runner worker)_ Create a dbt/DuckDB/Python environment
  outside the repository for Codex to use; confirm `dbt parse` and a DuckDB
  query run against an episode workspace with network off.
- [ ] **E2 — Codex runner.** _(in progress, runner worker)_ `codex_baseline.py`: build the fixture into an
  opaque temporary directory, strip label material, write the frozen prompt and
  output schema, invoke `codex exec`, capture the event stream and final answer,
  convert findings to plan form, run the post-run checks, score with
  `midpoint-score-v1`, and persist per-episode artifacts and `summary.json`.
- [ ] **E3 — Deterministic tests.** _(in progress, runner worker)_ Stand-in `codex` executable covering a clean
  run, a patch that verifies, a claimed patch with no file change, an edit
  outside the override file, malformed output, and a non-zero exit; label
  material absent from the prepared workspace.
- [ ] **E4 — Paired check.** _(in progress, runner worker)_ Run both Codex conditions on
  `rem_daily_revenue_filter_drift` and `change_daily_revenue_filter`; inspect
  traces for isolation, conversion and scoring problems; fix only the adapter.
- [ ] **E5 — Freeze and run.** _(queued, runner worker, after the E4 gate)_ Freeze `codex_baseline_v1.yaml`; run both
  conditions on all ten episodes into `experiments/results/codex_baseline_v1/`.
- [ ] **E6 — Trace audit.** _(queued, runner worker, after E5)_ `analysis.md`: per episode, what each agent
  inspected, what it concluded, whether it was right, and how that became the
  score; isolation check results; where the labels are disputable.

## Report

- [x] **R1 — Architecture and front matter.** Diagram of the implemented system;
  Methods cut to one or two high-level paragraphs around it and Environment &
  Data cut to about half, with the details in a new appendix section;
  implemented versus planned behavior separated.
- [ ] **R2 — Methods and evaluation.** _(waits for E5 data)_ Conditions with their exact differences;
  the seven-step evaluation once, updated for the Codex adapter.
- [ ] **R3 — Results.** _(waits for E5 and E6)_ Per-episode table for steward and both Codex conditions
  with metric definitions; one remediation and one change-review walkthrough
  citing saved traces; limitations next to the numbers.
- [x] **R4 — Pivots.** Each pivot as what the agent did, whether it was right,
  and what changed, citing saved runs (including the earlier unmatched two-case
  runs that motivated matching the model and task specification).
- [x] **R5 — Constraints.** _(the original feedback file keeps the word verbatim as provenance; R6 rechecks after Results)_ No cost data; problem stated for lakehouses
  generally; prohibited jargon absent from editable project files; static and
  custom generic conditions out of the report.
- [ ] **R6 — Build and check.** _(after R3)_ Regenerate figures, TeX and PDF; visually check
  that everything before the appendix, references included, fits in four total
  pages, plus legibility, clipping, and table/figure consistency.
- [ ] **R7 — README.** _(queued, runner worker, after E6)_ Reproduction steps for the Codex baseline.
- [ ] **R8 — Close out.** _(last)_ Implementation update in `agent_response_2__codex.md`,
  final notes, follow-ups and their importance.
