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

## 5. Execution plan

### Phase 0: lock the research and product contract

- [ ] Write the one-paragraph problem specification: the user is a maintainer
  of a dbt-backed lakehouse whose catalog degrades as code evolves.
- [ ] Select the one stack, one agent model/configuration, and four to six
  supported hygiene issue types.
- [ ] Define the two headline outcomes:
  1. improve an unhealthy catalog with verified, evidence-backed changes;
  2. prevent a proposed change from introducing a hygiene regression.
- [ ] Define safety boundaries, maximum episode scope, action limits, and the
  risk policy above.
- [ ] Record deferred items explicitly so they do not silently expand the
  midpoint scope.

**Exit criterion:** the hygiene contract is versioned and each supported issue
type names its required evidence, allowed actions, forbidden actions, and
verification procedure.

### Phase 1: construct the environment and evaluation episodes

- [ ] Build a deterministic dbt fixture with SQL models, schema YAML, manifest
  artifacts, lineage, representative metadata, and small seed tables.
- [ ] Provide a reset command that restores the exact starting state for an
  episode.
- [ ] Create a defect/change manifest with, at minimum:
  - episode ID and mode;
  - starting asset scope and input diff, if any;
  - defect or clean-control label;
  - required evidence and expected finding(s);
  - acceptable remediation set;
  - explicitly unsafe or unsupported actions;
  - expected postconditions and verification checks.
- [ ] Author 8-12 audited episodes, targeting roughly:
  - 3-4 existing-debt episodes;
  - 3-4 flawed change-review episodes;
  - 2-3 clean contributions that should pass without noisy findings.
- [ ] Include the connected demo story: first repair a stale description or
  technical claim, then introduce a later grain/filter change that makes it
  stale again.

**Exit criterion:** every episode is reproducible from a clean reset and can be
scored without subjective reconstruction after the run.

### Phase 2: implement the minimum evidence interface

- [ ] Expose compact, structured operations for:
  - catalog metadata and lifecycle state;
  - parsed dbt sources, filters, joins, aggregations, and grain candidates;
  - upstream/downstream lineage and change impact;
  - bounded uniqueness, nullability, accepted-value, freshness, and date-range
    probes;
  - current repository diff and relevant model/schema files.
- [ ] Give every evidence item a stable identifier and provenance pointer.
- [ ] Return technical facts rather than silently deciding business semantics.
- [ ] Add fixture-level tests for parsing, scope bounds, query bounds,
  provenance, and failure handling.

**Exit criterion:** the required evidence for every supported episode can be
retrieved through the interface and traced to its source.

### Phase 3: implement the shared steward loop

- [ ] Accept either a backlog/scheduled asset scope or a proposed code diff.
- [ ] Build a compact evidence bundle for the bounded asset/dependency scope.
- [ ] Compare the bundle to the hygiene contract and emit grouped findings with
  impact, confidence, and evidence IDs.
- [ ] Select a deliberately small action set instead of an unbounded lint list.
- [ ] Route each action through the patch/propose/report risk policy.
- [ ] Emit a reviewable repository patch or structured proposal.
- [ ] Reparse the project, rerun relevant dbt/schema checks and bounded probes,
  and verify every changed claim.
- [ ] Record a ledger entry containing episode, finding, evidence, decision,
  action, verification, and unresolved questions.
- [ ] Make reruns idempotent: a verified finding should not be rediscovered as
  unfinished work unless the evidence changed.

**Exit criterion:** both triggers complete the same inspect-plan-act-verify
state machine, and failed verification is visible rather than reported as a
successful repair.

### Phase 4: implement fair baselines and scoring

- [ ] **Static baseline:** run schema validation, required-field rules, dbt
  parsing/tests, and other deterministic checks that apply to the contract.
- [ ] **Generic-agent baseline:** give the same model repository access,
  catalog/raw metadata access, SQL access, and the same episode prompt, budget,
  timeout, stopping rule, and structured output schema, but no steward workflow
  or specialized evidence interface.
- [ ] **Specialized steward:** run the complete architecture against the same
  episode start state.
- [ ] Freeze prompts and run configurations before the scored pilot.
- [ ] Save raw tool traces, patches/proposals, ledger entries, verification
  results, timing, token/tool usage, and scorer outputs.

For the midpoint, conditions 1, 2, and 3 are sufficient. Defer the
generic-agent-plus-detailed-hygiene-skill baseline and tool/workflow ablations to
the final study unless the core pilot is already stable.

Score the following:

- episode success: acceptable remediation or correct escalation, no unsafe
  action, and required verification passed;
- finding precision and recall;
- correct remediation rate;
- unsafe or unsupported action rate;
- evidence validity;
- regression-detection rate on flawed changes;
- clean-change pass rate / false-positive rate;
- hygiene-score change from precondition to verified postcondition;
- successful post-change verification;
- patch-versus-escalation share;
- cost, turns, tool calls, and wall-clock time as secondary metrics.

**Exit criterion:** one command or documented short sequence runs all three
conditions from matched starting states and produces a machine-readable and
human-readable result summary.

### Phase 5: run and audit the midpoint pilot

- [ ] Dry-run two episodes to find broken fixtures, ambiguous ground truth, and
  schema/scorer failures.
- [ ] Audit every manifest entry and expected action before the scored run.
- [ ] Run all 8-12 episodes in the three midpoint conditions.
- [ ] Manually inspect evidence validity and every action marked unsafe,
  unsupported, or unverifiable.
- [ ] Classify failures by cause: missing evidence, tool defect, planning error,
  bad risk decision, patch failure, verification failure, or ambiguous ground
  truth.
- [ ] Generate a compact results table. With this small pilot, report counts and
  per-episode outcomes; do not imply statistical generality.

**Exit criterion:** the saved results support an honest statement about what the
vertical slice can and cannot yet do.

### Phase 6: write the 3-4 page midway report

Use exactly the required top-level sections:

1. **Research Questions or Problem Specification** — one paragraph naming the
   maintainer, fragmented-evidence problem, two steward modes, and comparison
   question.
2. **Environment & Data** — the largest section. Describe the stack, fixture,
   catalog/dbt/data evidence, hygiene contract, defect manifest, episode
   construction, clean controls, ground truth, success criteria, and metrics.
3. **Methods** — describe the two triggers and shared workflow, evidence tools,
   risk-aware action policy, verification ledger, and the three fair midpoint
   conditions.
4. **Summary of Progress** — clearly separate completed work, remaining work,
   observed pilot results, and obstacles. Never present planned work as
   completed.
5. **References** — use the proposal's reference format; cite only sources,
   systems, and datasets actually relied upon. No separate prior-work discussion
   is required.
6. **AI-Use Disclosure Statement** — describe actual AI assistance and the
   human verification performed; do not use a generic disclosure detached from
   the work.

Suggested space allocation before final formatting:

- problem specification: about 0.25-0.5 page;
- Environment & Data: about 1-1.25 pages;
- Methods: about 0.75-1 page;
- progress, limitations, and concerns: about 0.5-0.75 page;
- references and AI-use disclosure: remaining space.

The report should explicitly discuss these risks and mitigations:

- scope growth -> freeze a small versioned hygiene contract;
- ambiguous semantic ground truth -> acceptable action sets and escalation;
- plausible but unsupported descriptions -> evidence IDs and risk policy;
- weak or unfair generic baseline -> equal raw access, budgets, schema, and
  prompt-tuning discipline;
- warning overload -> clean-change controls and a small prioritized action set;
- small pilot size -> report episodes and limitations rather than broad claims.

**Exit criterion:** the rendered paper is 3-4 pages, readable at normal zoom,
contains all required sections, and every quantitative statement matches a
saved result.

### Phase 7: prepare the README and recorded demo

- [ ] Expand `README.md` with prerequisites, pinned versions, installation,
  fixture creation/reset, both steward entry points, all baseline commands,
  evaluation reproduction, output locations, known limitations, and safety
  behavior.
- [ ] Test the README from a fresh environment or clean local setup.
- [ ] Record one connected demo:
  1. show a catalog claim that disagrees with current SQL/data;
  2. run incremental remediation and inspect its evidence-backed patch;
  3. show verification and the ledger entry;
  4. introduce a later diff that changes grain or filtering without updating
     metadata;
  5. run change-time review and show the caught regression or semantic
     escalation;
  6. contrast the result with what static checks and the generic agent did;
  7. close with measured pilot outcomes and current limitations.
- [ ] Confirm the submitted repository link exposes the README and all
  non-sensitive artifacts needed to reproduce the prototype.

**Exit criterion:** the video demonstrates the actual working prototype, and
the repository can reproduce the shown path.

## 6. Final acceptance checklist

- [ ] One specialized workflow supports both remediation and change review.
- [ ] The midpoint prototype demonstrates one verified repair and one prevented
  regression (or correct escalation).
- [ ] The hygiene contract supports only 4-6 explicit issue types.
- [ ] The evaluation contains 8-12 audited episodes including clean controls.
- [ ] Ground truth includes acceptable and unsafe action sets, not only defect
  labels.
- [ ] Static, generic-agent, and steward conditions are matched fairly.
- [ ] All agent claims and changes are traceable to evidence.
- [ ] Verification failures cannot count as successful remediations.
- [ ] Raw pilot outputs, configuration, prompts, and generated summaries are
  retained.
- [ ] The report is 3-4 pages and contains all six required sections.
- [ ] The README is sufficient to run the prototype and evaluation.
- [ ] The recorded demo shows both modes and states limitations honestly.

## 7. Post-midpoint work, explicitly deferred

After the vertical slice and report are complete, expand to 30-50 episodes,
add the detailed-hygiene-skill baseline, run tool-versus-workflow ablations, and
only then consider additional models, harnesses, or catalog integrations. These
extensions must not displace the midpoint's working prototype, fair baselines,
or required paper/video/README deliverables.

