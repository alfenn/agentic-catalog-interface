---
source: "codex-5.6-sol-xhigh"
context: [
  "design/proposal_feedback/agent_ideas_2__codex.md",
  "writeups/midway_report/requirements.md"
]
---

# Midway implementation plan: agentic data-hygiene steward

## 1. Goal and governing thesis

Build and document a working vertical slice of an **agentic data-catalog
steward** for a dbt-backed lakehouse. The steward must use the same evidence
model and closed-loop workflow in two modes:

1. **Incremental remediation:** find and safely remediate existing catalog
   hygiene debt.
2. **Change-time review:** review a proposed dbt/catalog change and prevent new
   hygiene regressions.

The midway report should test this thesis:

> A specialized workflow that gathers and reconciles evidence from catalog
> metadata, dbt code, lineage, and bounded data probes can make safer, more
> complete, and more verifiable hygiene improvements than static checks or a
> generic coding agent with the same raw access.

The scientific object is the complete **inspect -> plan -> act/propose ->
verify** maintenance episode, not an isolated catalog question or the number of
warnings emitted.

## 2. Required deliverables and definition of done

| Deliverable | Concrete output | Done when |
| --- | --- | --- |
| Working prototype | One local, reproducible dbt-backed stack; evidence tools; steward loop; verification ledger | At least one existing-debt episode and one change-review episode complete end to end, producing reviewable patches/proposals and verification results |
| Evaluation data | Versioned hygiene contract, defect manifest, and 8-12 audited maintenance episodes | Episodes include existing debt, flawed changes, and clean controls; each records required evidence, acceptable actions, unsafe actions, and postconditions |
| Baselines and pilot | Static checks, a generic agent, and the specialized steward run under matched conditions | The agent conditions use the same model, raw information, budget, stopping rule, and structured result schema where applicable |
| Midpoint demo | Recorded walkthrough of the two modes as one connected story | The video shows the prototype running, the evidence behind its action, post-action verification, and a concise contrast with both baselines |
| Repository handoff | Root `README.md` with setup and reproduction instructions | A new user can install dependencies, build/reset the fixture, run both modes, run the pilot, and inspect outputs without undocumented steps |
| Midway report | A 3-4 page paper in `writeups/midway_report/` | It contains all six required sections, emphasizes Environment & Data, Methods, and Summary of Progress, and makes no claim unsupported by a checked-in artifact or result |

## 3. Scope to freeze before implementation

### In scope for the midpoint

- One local dbt-backed lakehouse/catalog stack. Prefer a lightweight,
  reproducible stack such as dbt Core + DuckDB unless another stack is already
  operational; do not add a second integration at the midpoint.
- Four to six issue types from this initial hygiene contract:
  - missing table/column documentation, ownership, or lifecycle metadata;
  - descriptions contradicted by SQL filters or aggregations;
  - undocumented or changed table grain and join cardinality;
  - unsupported key, uniqueness, nullability, accepted-value, or freshness
    claims;
  - renamed, replaced, deprecated, duplicated, or orphaned assets;
  - drift between dbt models/schema files and catalog metadata.
- Reviewable repository patches or proposals. Even deterministic changes should
  not write directly to a live production catalog during the prototype.
- Bounded dependency traversal and bounded validation queries so cost, runtime,
  and safety are measurable.

### Out of scope for the midpoint

- General data cleaning or anomaly remediation.
- Access-policy enforcement or automatic destructive lifecycle actions.
- Multiple catalog/lakehouse integrations.
- Broad model or harness sweeps.
- Automatic invention of business semantics, ownership, or deprecation policy.

### Risk policy

- **Patchable:** deterministic, reversible synchronization of technical facts,
  formatting, references, and metadata with direct evidence.
- **Propose for review:** inferred descriptions, owners, new tests, lifecycle
  decisions, or any action requiring business meaning.
- **Report only:** destructive actions, unresolved source conflicts, and cases
  with insufficient evidence.

Every action must carry evidence identifiers, confidence, risk class, and an
explicit verification result. Unsupported semantic claims must be escalated or
left unresolved rather than guessed.

## 4. Artifact layout

Use existing project conventions if they emerge; otherwise organize the work as
follows:

- `src/hygiene_contracts/`: versioned rules, action classes, evidence
  requirements, and verification requirements.
- `data/fixtures/`: reproducible dbt project, seed data, catalog snapshot, and
  proposed-change diffs.
- `data/episodes/manifest.*`: ground-truth episode definitions.
- `src/` (or the chosen language's conventional equivalent): evidence tools,
  steward orchestration, patch/proposal generation, verification, and ledger.
- `experiments/`: baseline runners, matched run configuration, scoring, and
  pilot scripts.
- `experiments/results/`: immutable raw outputs plus a compact generated
  summary used by the report.
- `writeups/midway_report/`: report source, figures/tables, references, and
  AI-use disclosure.

Do not hand-edit reported numbers. Generate report tables/figures from the saved
pilot outputs, and preserve the configuration and prompt used for every run.

## 5. Execution tracking

The actionable checklist, current work package, and completion state live in
[`agent_todo.md`](agent_todo.md). This document retains the design contract;
execution details are kept separately so progress can be updated without
rewriting the plan.

## 6. Post-midpoint work, explicitly deferred

After the vertical slice and report are complete, expand to 30-50 episodes,
add the detailed-hygiene-skill baseline, run tool-versus-workflow ablations, and
only then consider additional models, harnesses, or catalog integrations. These
extensions must not displace the midpoint's working prototype, fair baselines,
or required paper/video/README deliverables.

