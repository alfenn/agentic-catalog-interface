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

- [x] **E1 — Isolated tool environment.** Create a dbt/DuckDB/Python environment
  outside the repository for Codex to use; confirm `dbt parse` and a DuckDB
  query run against an episode workspace with network off.
- [x] **E2 — Codex runner.** `codex_baseline.py`: build the fixture into an
  opaque temporary directory, strip label material, write the frozen prompt and
  output schema, invoke `codex exec`, capture the event stream and final answer,
  convert findings to plan form, run the post-run checks, score with
  `midpoint-score-v1`, and persist per-episode artifacts and `summary.json`.
- [x] **E3 — Deterministic tests.** _(108 tests pass)_ Stand-in `codex` executable covering a clean
  run, a patch that verifies, a claimed patch with no file change, an edit
  outside the override file, malformed output, and a non-zero exit; label
  material absent from the prepared workspace.
- [x] **E4 — Paired check.** _(all four runs passed the gate)_ Run both Codex conditions on
  `rem_daily_revenue_filter_drift` and `change_daily_revenue_filter`; inspect
  traces for isolation, conversion and scoring problems; fix only the adapter.
- [x] **E5 — Freeze and run.** _(20 runs, 0 errors, 0 isolation flags, nothing repeated)_ Freeze `codex_baseline_v1.yaml`; run both
  conditions on all ten episodes into `experiments/results/codex_baseline_v1/`.
- [x] **E6 — Trace audit.** `analysis.md`: per episode, what each agent
  inspected, what it concluded, whether it was right, and how that became the
  score; isolation check results; where the labels are disputable.

## Report

- [x] **R1 — Architecture and front matter.** Diagram of the implemented system;
  Methods cut to one or two high-level paragraphs around it and Environment &
  Data cut to about half, with the details in a new appendix section;
  implemented versus planned behavior separated.
- [x] **R2 — Methods and evaluation.** Conditions with their exact differences;
  the seven-step evaluation once, updated for the Codex adapter.
- [x] **R3 — Results.** _(walkthroughs: legacy-copy remediation and revenue-filter change)_ Per-episode table for steward and both Codex conditions
  with metric definitions; one remediation and one change-review walkthrough
  citing saved traces; limitations next to the numbers.
- [x] **R4 — Pivots.** Each pivot as what the agent did, whether it was right,
  and what changed, citing saved runs (including the earlier unmatched two-case
  runs that motivated matching the model and task specification).
- [x] **R5 — Constraints.** _(the original feedback file keeps the word verbatim as provenance; R6 rechecks after Results)_ No cost data; problem stated for lakehouses
  generally; prohibited jargon absent from editable project files; static and
  custom generic conditions out of the report.
- [x] **R6 — Build and check.** _(references end on page 4; the close-out worker rechecks after its edits)_ Regenerate figures, TeX and PDF; visually check
  that everything before the appendix, references included, fits in four total
  pages, plus legibility, clipping, and table/figure consistency.
- [x] **R7 — README.** Reproduction steps for the Codex baseline.
- [ ] **R8 — Close out.** _(in progress, close-out worker: stale-text and consistency sweep, implementation update; coordinator writes the final notes)_ Implementation update in `agent_response_2__codex.md`,
  final notes, follow-ups and their importance.
