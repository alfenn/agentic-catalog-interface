---
source: codex-5.6-sol-xhigh
reply-to: [agent_ideas__claude.md, agent_ideas__codex.md]
---

# Revised recommendation: pivot to an agentic data-hygiene steward

## Bottom line

I think this pivot is stronger than treating the project primarily as a
catalog-question-answering benchmark. It gives the work a clearer user and a
more consequential job: continuously improve the health of a data catalog and
prevent new changes from degrading it.

The most compelling version is a **catalog steward** with two operating modes:

1. **Incremental remediation:** inspect an existing data system, identify
   hygiene debt, prioritize evidence-backed improvements, make or propose safe
   changes, and verify the result.
2. **Change-time review:** inspect a proposed data-code change, determine which
   catalog and metadata obligations it creates, fix or flag omissions, and
   verify that the contribution meets the project's hygiene standard.

These are not two unrelated products. They are two triggers for the same agentic
workflow and the same underlying evidence model. One works through accumulated
debt; the other stops new debt from entering.

I would therefore choose the Codex response's broader product direction, while
retaining the strongest parts of Claude's evaluation design: injected defects,
known lure cases, grounded evidence, fair baselines, structured outputs, and a
deliberately pruned experiment. The revised weighting is roughly **60% Codex
product framing / 40% Claude evaluation discipline**.

## The project thesis

Data hygiene is not just a collection of missing-field checks. A useful steward
must determine what a table represents, how it is derived, which assumptions its
joins and filters encode, whether its metadata still agrees with its SQL and
data, and what downstream assets a change affects. That information is scattered
across the catalog, dbt models and manifests, lineage, data profiles, query
history, and the current code change. Each source may be incomplete or stale.

The manual workflow is therefore agentic in character: gather evidence from
several systems, reconcile conflicts, decide which action is justified, execute
or propose the action, and check that the change did not introduce a new error.
A specialized agent can encode this workflow and expose purpose-built operations
for it. A generic coding agent with a catalog MCP server, a CLI, and a broad
"improve data hygiene" prompt can technically reach much of the same raw
information, but it has no durable definition of hygiene, no systematic triage
loop, no confidence-based action policy, and no required verification cycle.

A concise thesis for the midway report is:

> We are building an agentic data-catalog steward that gathers and reconciles
> evidence from metadata, pipeline code, lineage, and the data itself to repair
> existing hygiene debt and prevent new hygiene regressions. We test whether a
> specialized evidence-gathering, action, and verification workflow produces
> safer and more complete improvements than static checks or a generic coding
> agent with ordinary catalog access.

This framing directly answers the proposal feedback. The motivation is no
longer three narrow questions; it is one maintenance problem that spans many
disparate workflows. It also yields two concrete "amazing" outcomes and an
evaluation designed around them.

## The two outcomes to center

### 1. The system measurably improves an unhealthy catalog over time

Starting from a lakehouse with incomplete, stale, or contradictory metadata,
the steward should produce a sequence of correct, useful, evidence-backed
changes. After each pass, catalog quality should be better without damaging the
underlying data semantics or inventing unsupported business meaning.

The important claim is not merely that the agent finds issues. It closes the
loop: inspect, prioritize, change, verify, and retain enough state not to repeat
the same work indefinitely.

### 2. The system prevents new work from introducing hygiene regressions

Given a proposed dbt or catalog change, the steward should identify the metadata,
documentation, lineage, ownership, and test obligations created by that change.
It should automatically repair low-risk omissions and clearly flag ambiguous or
semantic decisions for a person.

The striking demo is a contribution that looks reasonable to a generic code
reviewer but silently makes a description stale, changes a table's grain, or
introduces a non-unique join. The specialized steward follows the impact into
the catalog, detects the inconsistency, and proposes a grounded fix before the
change lands.

## Define “data hygiene” narrowly enough to evaluate

The pivot will become unmanageable if hygiene means every kind of data quality,
governance, observability, and code review. For this project, define it as the
consistency, completeness, and maintainability of catalog metadata and the
pipeline facts that support it.

An initial hygiene contract could cover:

- **Discoverability:** tables and important columns have descriptions, owners,
  lifecycle status, and useful tags.
- **Semantic consistency:** documented grain, sources, filters, joins, and
  aggregations agree with the defining SQL and manifest.
- **Basic reliability evidence:** claimed keys, nullability, accepted values,
  freshness, and date coverage are supported by bounded data probes or tests.
- **Lifecycle hygiene:** deprecated, duplicated, renamed, and orphaned assets
  are identified and handled consistently.
- **Change integrity:** when SQL or schemas change, affected metadata and tests
  are updated or explicitly reviewed.

Keep broad data cleaning, anomaly remediation, access-policy enforcement, and
automatic deletion of tables out of scope for the midpoint. They require
different ground truth and substantially higher safety guarantees.

## Proposed agent architecture

The architecture should make the domain workflow explicit rather than relying
on one long prompt.

### 1. Trigger and scope

The agent receives either a scheduled/backlog scan or a code-change diff. It
limits its search to a bounded set of assets and their dependencies. This keeps
cost predictable and makes verification possible.

### 2. Evidence collection

It builds a compact evidence bundle from:

- catalog metadata and lifecycle state;
- dbt SQL, YAML, and manifest structure;
- lineage and downstream impact;
- bounded data profiles and validation queries;
- the current diff and repository history, where relevant.

Purpose-built tools should expose technical facts such as parsed sources,
filters, joins, aggregations, grain candidates, and evidence-addressable data
profiles. The tools should not silently make semantic decisions for the agent.

### 3. Hygiene planning and prioritization

The agent compares the evidence bundle against an explicit hygiene contract,
groups related findings, estimates impact and confidence, and chooses a small
set of actions. This is where the incremental mode avoids producing an enormous,
low-value lint report.

### 4. Risk-aware action

Actions should be divided by reversibility and semantic risk:

- **Automatic or patchable:** deterministic metadata synchronization, generated
  technical facts, formatting, references, and other reversible changes with
  strong evidence.
- **Propose for review:** descriptions with inferred meaning, new tests, owners,
  deprecation decisions, and changes whose correctness depends on business
  context.
- **Report only:** destructive changes, unresolved conflicts between sources,
  or cases with insufficient evidence.

For the prototype, even automatic work can be emitted as a reviewable repository
patch rather than written directly to a live catalog.

### 5. Verification and ledger

After acting, the agent reparses the project, runs relevant dbt or schema checks,
repeats bounded probes, and verifies that every changed claim has supporting
evidence. A small ledger records the finding, evidence, action, verification,
and unresolved questions. This makes repeated improvement possible and prevents
the system from rediscovering the same issue on every run.

## A fair evaluation

The evaluation should use **maintenance episodes**, not isolated QA questions.
Each episode begins with a known catalog state or proposed change and ends with
an action set plus verification.

### Episode type A: existing hygiene debt

Seed a dbt-backed lakehouse with controlled defects such as:

- missing table or column metadata;
- descriptions contradicted by current SQL;
- undocumented filters, joins, or grain changes;
- deprecated duplicates that remain more prominent than canonical tables;
- claimed keys that are not unique;
- missing or stale ownership and lifecycle metadata;
- models or columns present in code but absent from catalog documentation.

Each defect should have required evidence, an acceptable remediation set,
explicitly unsafe actions, and a known postcondition.

### Episode type B: new-work hygiene

Create realistic diffs that:

- add a model without documentation, ownership, or tests;
- change a filter or aggregation without updating its description;
- change table grain or join cardinality;
- rename or replace a model without a lifecycle transition;
- add a field whose semantics cannot safely be inferred;
- correctly update everything and therefore should pass without noisy findings.

Including clean contributions is essential for measuring false positives and
review burden.

### Baselines

Use the same model, repository, raw information, budget, and output schema where
applicable. A strong final evaluation has four conditions:

1. **Static hygiene checks:** schema validation, required-field rules, and dbt
   lint/tests. This tests whether an agent is needed at all.
2. **Generic coding agent:** ordinary catalog MCP/CLI and repository access,
   plus a short generic hygiene prompt.
3. **Generic agent with a detailed hygiene skill/checklist:** same raw tools,
   but the workflow is described in instructions. This tests whether the result
   comes merely from writing a better prompt.
4. **Specialized steward:** structured evidence tools, planning, risk policy,
   action loop, verification, and ledger.

The third condition is important. Without it, a specialized architecture could
appear better simply because the baseline was never told what good hygiene
means. An additional ablation can give a generic agent the specialized evidence
tools without the steward workflow, separating tool quality from orchestration.

For the midpoint, conditions 1, 2, and 4 are sufficient. Add the detailed-skill
baseline and tool/workflow ablation for the final evaluation.

### Metrics

Measure outcomes at both the finding and system level:

- precision and recall of valid hygiene findings;
- correct remediation rate;
- unsafe or unsupported action rate;
- evidence validity for each finding and change;
- improvement in a predefined catalog-hygiene score;
- regression-detection rate on proposed changes;
- false-positive/pass rate on clean changes;
- percentage of findings safely auto-patched versus escalated;
- successful post-change verification;
- cost, turns, tool calls, and wall-clock time.

The main metric should not be the number of issues reported. A system that emits
many speculative warnings is worse than one that makes a smaller number of
correct, verifiable improvements.

## Recommended midpoint scope

The midpoint needs a working prototype, so the right target is one complete
remediation loop and one complete change-review loop on one stack. Do not begin
with multiple harnesses or a large model sweep.

### Build first

1. Write a versioned hygiene contract with four to six supported issue types.
2. Create a defect manifest and a small suite of existing-debt and change-time
   episodes.
3. Implement the minimum evidence tools for those issue types.
4. Implement the plan -> patch/proposal -> verify loop.
5. Add the generic-agent and static-check baselines with equal raw access.
6. Run a pilot, inspect failures, and only then expand the episode set.

An appropriate midpoint pilot is roughly **8-12 carefully audited episodes**,
split between existing debt, flawed contributions, and clean contributions. The
final study can grow to **30-50 episodes** before adding more models or harnesses.

### Demo

Show both modes using one connected story:

1. The steward scans an existing model whose description no longer matches its
   SQL, gathers catalog/code/data evidence, proposes a correction, and verifies
   the patch.
2. A later contribution changes that model's grain or filter without updating
   its metadata. The change-time steward follows the impact, catches the
   regression, and either patches it or requests the missing semantic decision.
3. Contrast this with a static checker and a generic agent. The static checker
   notices only syntactic omissions; the generic agent either misses the
   cross-system inconsistency or produces a less grounded action.

That demo makes the incremental and preventive loops feel like one coherent
system rather than two features.

## How to frame the midway report

### Research question / problem specification

Define the user as the maintainer of a dbt-backed lakehouse whose catalog and
metadata degrade as code evolves. Ask whether a specialized agentic steward can
make safer, more complete, and more grounded hygiene improvements than static
checks and generic coding agents.

### Environment & Data

Spend the most space here. Describe the lakehouse, catalog, dbt project, defect
manifest, change episodes, acceptable action sets, unsafe actions, clean
controls, and metrics. The unit of evaluation is a maintenance episode, not a
question.

### Methods

Describe the two triggers and shared inspect -> plan -> act -> verify workflow,
the evidence tools, the risk policy, and the three midpoint baselines. Make
clear which changes are automatic and which require review.

### Summary of Progress

Report the working vertical slice honestly: supported hygiene rules, tools,
episode count, actions the system can take, verification coverage, and baseline
results. Name the central risks:

- hygiene scope expands faster than implementation;
- ground truth for semantic metadata can be ambiguous;
- the agent invents plausible but unsupported descriptions;
- the generic-agent comparison is unfairly weak;
- too many warnings create unacceptable reviewer burden.

The scope definition, acceptable-action sets, confidence-based action policy,
strong prompt baseline, and clean-change controls are the corresponding
mitigations.

## Final recommendation

Make the pivot. It improves the motivation, better justifies an agentic system,
and produces a more useful artifact than a catalog QA interface alone. Preserve
the proposal's original interface insight as the mechanism: specialized tools
help the steward gather compact, trustworthy evidence from fragmented systems.
But make the scientific object the **closed-loop hygiene workflow**, not the
answer to an isolated question.

The key discipline is to avoid claiming "automated data hygiene" in the
abstract. Define a small hygiene contract, distinguish safe patches from
semantic decisions, and evaluate complete maintenance episodes. If the midpoint
can demonstrate one verified repair and one prevented regression against fair
baselines, the project will have a coherent story and a credible path to the
final report.
