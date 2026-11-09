---
source: "claude-opus-5.5"
context: ["human_feedback.md", "agent_response__codex.md", "human_response.md", "agent_response_2__codex.md", "../../requirements/midway_report.md"]
datetime: 2026-11-08
---

# Plan: Codex baseline and system design for the midway report

This plan implements `agent_response_2__codex.md` on top of the first round
(`agent_response__codex.md`, commit 894f0ca). The first round removed cost data,
generalized the problem statement, explained evaluation in seven steps, and
compared two unmatched Codex runs with the frozen steward pilot. What remains
is the experiment the follow-up asks for and the explanation of what was built.

Progress is tracked in `AGENT_TODO.md`; design decisions, problems and
pivots go in `../agent_notes.md` as each chunk lands.

## 1. Goal

Answer, on the ten frozen pilot episodes, whether the steward produces more
complete, grounded and safe maintenance outcomes than a state-of-the-art general
coding agent (OpenAI Codex CLI) given the same task, inputs and data access, and
explain the steward's architecture clearly enough that the comparison is
interpretable. The experiment tests that hypothesis; it does not assume the
steward wins.

## 2. Baseline design

**Two Codex conditions.**

- `codex-matched`: Codex CLI 0.167.0 with `gpt-6-luna` at low reasoning effort,
  the same model and effort the frozen steward pilot used. With the model held
  fixed, the remaining differences are the harness: general shell and file
  tools versus the steward's evidence bundle, validator and executor. This is
  the primary comparison.
- `codex-frontier`: the same harness and prompt with `gpt-6.1-sol` at medium
  effort. This answers the captain's question directly: does the steward on a
  small model match or beat a state-of-the-art agent on a frontier model?

**Steward condition.** The frozen `midpoint_v1_2_pilot` steward records
(config 1.2.0). They were recorded before any Codex run, so nothing was tuned
against the baseline. Four of the pilot's model records are cache replays; the
report keeps that caveat.

**Same task specification.** Codex receives what the steward is told: trigger,
asset scope, the hygiene contract's issue types with their required evidence and
allowed and forbidden actions, the five-finding cap, and the patch surface (the
five catalog fields in `catalog/overrides.json`). It does not receive the
steward's precomputed evidence bundle, plan validator, executor or verifier;
those are the intervention being tested.

**Same inputs and data access.** For every episode and condition, build a fresh
fixture with the existing `reset_episode` into a temporary directory outside
the repository with an opaque name. Codex's workspace contains only the built
dbt project (`project/`, including `target/`), `warehouse.duckdb`, and, for change
review, `input.diff`. The episode file, the marker file (which names the
episode), the pre-change copy and the build log are removed, so no label is
reachable inside the workspace. dbt, DuckDB and Python come from a separate
tool environment outside the repository, so `PATH` does not point at the
labelled repository. Network access stays off.

**Structured output.** Codex is run with `--output-schema` on a schema that
mirrors the steward plan schema, with path- or command-based evidence in place
of evidence IDs. The runner converts it to the plan format for scoring.

**Harness-independent checks after each Codex run.**

1. Diff the workspace before and after the run and record every changed file;
   flag any change outside `catalog/overrides.json`.
2. For every finding Codex labels a patch, apply the steward's own
   verification: the catalog field equals the declared value and `dbt parse`
   succeeds. A patch finding with no corresponding file change fails
   verification.
3. Scan the event stream for commands that read outside the workspace or
   reach for label material; such a run is flagged in the audit.

**Scoring.** The unchanged `midpoint-score-v1` scorer: exact
`(issue_type, asset)` matching, the contract's allowed action classes, recorded
verification failures and run completion. Evidence validity is computed for
Codex as the share of cited files that exist in its workspace, and is reported
separately because it is not the same check as resolving steward evidence IDs.

**Order of work.** A paired check on two episodes first, to validate the
adapter, workspace isolation and scoring; then freeze the configuration and run
all ten episodes for both Codex conditions. Nothing in the prompt or adapter
changes after the full run is inspected. Failures and incomplete runs are
reported as such.

## 3. Deliverables

- `src/catalog_steward/codex_baseline.py`: workspace preparation, invocation,
  output conversion, post-run checks, scoring and persistence, with
  deterministic tests that use a stand-in `codex` executable.
- `experiments/configs/codex_baseline_v1.yaml` (frozen) and
  `design/codex_plan.schema.json`.
- `experiments/results/codex_baseline_v1/`: `summary.json`, per-episode result
  JSON, prompt, event stream, final answer, workspace diff and verification log,
  plus `analysis.md` with the trace audit.
- Report revision: an architecture section and diagram; evaluation explained
  once; the three-way per-episode comparison; one remediation and one
  change-review walkthrough citing steward and Codex traces; pivots told as
  what the agent did, whether it was right, and what changed; limitations next
  to the numbers. No cost data, no static or custom generic condition, no
  prohibited jargon; at most four body pages.
- README section on reproducing the Codex baseline.

## 4. What the architecture section must say

The contribution is a domain-specific evidence interface plus an
inspect-plan-act-verify workflow for catalog hygiene, shared by two entry
points (remediation of existing debt, review of a proposed change). The diagram
shows the two triggers feeding one workflow; the evidence sources (catalog,
dbt schema and manifest, SQL and parsed SQL facts, lineage, bounded profiles,
diff) and read-only tools; the model's structured plan; the validator and
action policy (patch, propose, report); and the outputs (a verified patch or a
review request, with the ledger). The caption and text separate what is
implemented from what is planned: patch verification checks the written value
and `dbt parse`, not semantic correctness.

## 5. Out of scope

- Re-running the steward or changing its prompt, contract or scorer.
- New episodes, new labels or relabelling (planned for the next frozen version).
- Repeated samples per episode; one sample per condition, stated as such.
- The video URL and the human verification statement, which stay author-owned.
