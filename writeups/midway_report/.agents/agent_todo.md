---
source: "codex-5.6-sol-xhigh"
context: [
  "agent_plan.md",
  "agent_notes.md",
  "../../../design/proposal_feedback/agent_ideas_2__codex.md",
  "../requirements.md"
]
---

# Agent TODO

Complete work packages in order. Update this file and `agent_notes.md` in the
same commit as the implementation. Run the relevant deterministic tests before
each commit; run paid/live tests only through an explicit live target. Push each
completed work-package commit before beginning the next package.

## Foundation work packages

- [x] **F0 — Environment and command surface.**
  - Add a secret-free `.env.example`, ignored local/runtime paths, a Python
    project definition and lockfile, and a Makefile.
  - Make deterministic tests the default and expose live tests separately.
  - Add a safe configuration doctor and tests.
- [x] **F1 — Reusable agent-test harness.**
  - Adapt only the assignment harness patterns needed here: scripted model,
    disk cache/cost ledger/budget stop, structured tool protocol, deterministic
    loop tests, explicit live markers, bounded evaluation slices, and shared
    test utilities.
  - Keep project-specific steward logic separate from generic harness code.

## Execution plan

### Phase 0: lock the research and product contract

- [x] Write the one-paragraph problem specification: the user is a maintainer
  of a dbt-backed lakehouse whose catalog degrades as code evolves.
- [x] Select the one stack, one agent model/configuration, and four to six
  supported hygiene issue types.
- [x] Define the two headline outcomes:
  1. improve an unhealthy catalog with verified, evidence-backed changes;
  2. prevent a proposed change from introducing a hygiene regression.
- [x] Define safety boundaries, maximum episode scope, action limits, and the
  risk policy above.
- [x] Record deferred items explicitly so they do not silently expand the
  midpoint scope.

**Exit criterion:** the hygiene contract is versioned and each supported issue
type names its required evidence, allowed actions, forbidden actions, and
verification procedure.

### Phase 1: construct the environment and evaluation episodes

- [x] Build a deterministic dbt fixture with SQL models, schema YAML, manifest
  artifacts, lineage, representative metadata, and small seed tables.
- [x] Provide a reset command that restores the exact starting state for an
  episode.
- [x] Create a defect/change manifest with, at minimum:
  - episode ID and mode;
  - starting asset scope and input diff, if any;
  - defect or clean-control label;
  - required evidence and expected finding(s);
  - acceptable remediation set;
  - explicitly unsafe or unsupported actions;
  - expected postconditions and verification checks.
- [x] Author 8-12 audited episodes, targeting roughly:
  - 3-4 existing-debt episodes;
  - 3-4 flawed change-review episodes;
  - 2-3 clean contributions that should pass without noisy findings.
- [x] Include the connected demo story: first repair a stale description or
  technical claim, then introduce a later grain/filter change that makes it
  stale again.

**Exit criterion:** every episode is reproducible from a clean reset and can be
scored without subjective reconstruction after the run.

### Phase 2: implement the minimum evidence interface

- [x] Expose compact, structured operations for:
  - catalog metadata and lifecycle state;
  - parsed dbt sources, filters, joins, aggregations, and grain candidates;
  - upstream/downstream lineage and change impact;
  - bounded uniqueness, nullability, accepted-value, freshness, and date-range
    probes;
  - current repository diff and relevant model/schema files.
- [x] Give every evidence item a stable identifier and provenance pointer.
- [x] Return technical facts rather than silently deciding business semantics.
- [x] Add fixture-level tests for parsing, scope bounds, query bounds,
  provenance, and failure handling.

**Exit criterion:** the required evidence for every supported episode can be
retrieved through the interface and traced to its source.

### Phase 3: implement the shared steward loop

- [x] Accept either a backlog/scheduled asset scope or a proposed code diff.
- [x] Build a compact evidence bundle for the bounded asset/dependency scope.
- [x] Compare the bundle to the hygiene contract and emit grouped findings with
  impact, confidence, and evidence IDs.
- [x] Select a deliberately small action set instead of an unbounded lint list.
- [x] Route each action through the patch/propose/report risk policy.
- [x] Emit a reviewable repository patch or structured proposal.
- [x] Reparse the project, rerun relevant dbt/schema checks and bounded probes,
  and verify every changed claim.
- [x] Record a ledger entry containing episode, finding, evidence, decision,
  action, verification, and unresolved questions.
- [x] Make reruns idempotent: a verified finding should not be rediscovered as
  unfinished work unless the evidence changed.

**Exit criterion:** both triggers complete the same inspect-plan-act-verify
state machine, and failed verification is visible rather than reported as a
successful repair.

### Phase 4: implement fair baselines and scoring

- [x] **Static baseline:** run schema validation, required-field rules, dbt
  parsing/tests, and other deterministic checks that apply to the contract.
- [x] **Generic-agent baseline:** give the same model repository access,
  catalog/raw metadata access, SQL access, and the same episode prompt, budget,
  timeout, stopping rule, and structured output schema, but no steward workflow
  or specialized evidence interface.
- [x] **Specialized steward:** run the complete architecture against the same
  episode start state.
- [x] Freeze prompts and run configurations before the scored pilot.
- [x] Save raw tool traces, patches/proposals, ledger entries, verification
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
- [x] Audit every manifest entry and expected action before the scored run.
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

## Final acceptance checklist

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
