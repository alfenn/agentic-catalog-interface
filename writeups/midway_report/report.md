---
# Editable source of the CS329Z midway report. Build with `make report` from the
# repository root; it regenerates figures/, the generated regions below, report.tex,
# and report.pdf. Do not edit report.tex by hand.
title: '`[Midway Report] Is the Gap an Interface Gap?\\ Agent Tool Interfaces for Data Catalogs`{=latex}'
pdftitle: "Is the Gap an Interface Gap? Agent Tool Interfaces for Data Catalogs"
author: Alex Feng
running-header: "CS329Z: Engineering AI Agents -- Midway Report"
comment: "CS329Z midway report, generated from report.md."
---

# Problem Statement (Problem Specification) {#sec:problem}

Maintainers of lakehouses need catalog metadata (ownership, grain, filters, lifecycle state) that stays trustworthy as models evolve, but it drifts from the code---annotations "can become outdated or incorrect" as data models evolve [@lakafosis2025meta]---and the evidence for a correction is scattered across catalog metadata, SQL, lineage, tests, and the data. We are building a *catalog steward* for them with two triggers over one workflow: *remediation* of existing hygiene debt and *change review* of a proposed contribution. Our question: **does a specialized evidence-gathering, risk-aware action, and verification workflow produce more complete, grounded, and safe maintenance outcomes than a general-purpose coding agent with access to the same repository and warehouse?**

# Methodology {#sec:method}

## Environment & Data {#sec:env}

**Environment.** The environment is a repository-local dbt Core project [@dbtcore] backed by DuckDB [@raasveldt2019duckdb] through the dbt-duckdb adapter. Three small synthetic seed tables (5 customers, 8 orders, 10 order items) feed a staging model and two aggregates (`customer_orders`, `daily_revenue`), with schema documentation, dbt tests, and a JSON catalog snapshot; a compact `catalog/overrides.json` sidecar injects controlled metadata changes. It is a reproducible test bed, not evidence about production warehouses. Each episode copies the clean base, applies a debt or change overlay, generates the diff, and builds the project, so every condition starts from the same state.

**Hygiene contract.** A versioned contract (`design/hygiene_contract.yaml`, v0.1.0, validated by a JSON Schema) bounds the task to five issue types: missing required metadata, SQL/metadata drift, grain or join drift, unsupported reliability claims, and lifecycle drift. Each type names its required evidence, allowed and forbidden action classes, and verification. Limits: 20 assets, two lineage hops, five findings, and 10,000 probed rows; deleting assets, changing access policies, mutating a live catalog, inventing business semantics, and unbounded queries are forbidden.

**Evaluation data and ground truth.** The pilot suite has ten hand-constructed, versioned episodes (`data/episodes/manifest.yaml`): four *remediation* cases (a stale revenue-filter description, wrong customer-order grain, a missing owner, and a legacy copy still marked active and canonical), four *flawed change* cases (a changed revenue filter, a changed grain without updated grain metadata or tests, a new undocumented model, and a rename without a lifecycle transition), and two *clean controls* (a documented new model and a documented revenue metric). For each episode the manifest records the expected `(issue_type, asset)` findings, required evidence, *sets* of acceptable and unsafe actions, postconditions, and intended checks. Action sets let an escalation count as correct where business meaning is uncertain (e.g. in the filter-drift case, proposing a description fix is acceptable but editing the SQL to match stale prose is unsafe); clean controls are intended to measure spurious findings, although both contain unlabelled gaps.

**Reusable evaluation.** For each episode, (1) copy the base fixture; (2) apply the specified debt or change overlay and build the dbt project; (3) run each condition independently on that state with its recorded prompt and settings; (4) save and normalize findings to `(issue_type, asset)`, retaining evidence and actions; (5) match those pairs exactly to the manifest and count true positives (TP), extra findings (FP), and missed findings (FN); (6) count an episode as successful only if it completes without missing or extra findings, disallowed action classes, or a recorded verification failure; and (7) inspect the saved trace. Precision is TP/(TP+FP), recall TP/(TP+FN), and micro scores aggregate counts before division. The scorer checks that evidence IDs resolve, not that they support the claim; it checks action classes, not episode-specific acceptable actions or postconditions. The AI-assisted trace audit examines those distinctions separately.

## Methods {#sec:methods}

**Shared workflow and evidence tools.** Both triggers run the same inspect--plan--act--verify state machine; change review additionally collects the diff. For the scoped assets, the steward builds an evidence bundle from catalog metadata, the dbt schema and manifest, model SQL with facts parsed by SQLGlot [@mao_sqlglot] (sources, filters, joins, aggregates, grouping, grain candidates), one-hop lineage, and bounded profiles. Following the view that purpose-built agent--computer interfaces matter [@yang2024sweagent], every evidence item carries a stable content-hashed ID and provenance pointer, and absent metadata is explicit `present: false` evidence. During planning the model may call nine schema-checked, read-only tools (e.g. two-hop lineage, bounded profiles, confined file reads). It returns at most five prioritized findings, each with claim, confidence, impact, evidence, and action.

**Risk-aware action policy.** Before anything executes, a validator checks the plan schema, in-scope assets, supported issue types, each issue type's required evidence families, action permissions, and that every cited evidence ID resolves. Actions fall into three classes: a *patch* for evidence-backed, reversible technical metadata; a *proposal* that leaves semantic or organizational decisions to a reviewer; and a *report* when no action is justified. Patches touch only five catalog fields in the episode-local override file, never a live catalog.

**Verification and ledger.** For a patch the steward emits a unified diff, applies it inside the episode, checks that the catalog field now equals the value the model declared and that `dbt parse` succeeds, and otherwise restores the file and records a verification failure. This is weak: `dbt parse` does not read `catalog/`, and the contract's per-issue checks (e.g. comparing metadata to parsed SQL, rerunning a uniqueness probe) do not run yet. Proposals and reports get permission and evidence checks only; an append-only ledger records findings, evidence, actions, and checks.

**Conditions.** The steward uses `openai/gpt-6-luna` (low reasoning effort, at most 12 turns) under frozen configuration `experiments/configs/midpoint_v1.yaml` v1.2.0. For two selected cases we also ran OpenAI Codex CLI 0.167.0 [@openai_codex] with `gpt-6.1-terra` at medium reasoning effort on separately built fixtures. Codex had general repository tools and could edit files; the steward received a specialized evidence bundle and operated through a validated plan and patch executor. Their models, prompts, tools, limits and execution differ, so this comparison cannot isolate an interface effect. The original pilot's custom raw-tool workflow is not Codex and is excluded from this comparison.

## What Did Not Work, and Pivots {#sec:pivots}

**From catalog questions to maintenance.** The proposal's large catalog-question benchmark was narrowed after feedback to two maintenance triggers and a local fixture. The system now produces evidence-linked actions, but the pilot does not establish a production safety improvement.

**Protocol errors.** In an earlier two-episode run the model copied a reply wrapper instead of the expected object, causing rejected replies. The team clarified the shared format example and added one repair turn before the pilot. A later pilot trace for `change_daily_revenue_filter` shows the exploratory agent batching tool calls into a rejected reply and returning no finding; it missed the expected regression. The team did not tune the protocol after inspecting this pilot. The saved `change_daily_revenue_filter/generic.json` and pilot `analysis.md` record the outcome.

# Results (Summary of Progress) {#sec:results}

**Completed work and matched cases.** The fixture, evidence tools, steward workflow and evaluator are implemented. Table\ \ref{tbl:paired} compares the two selected cases using exact manifest labels. TP is a matching finding; FP is an extra finding; FN is a missed expected finding. Success requires no extras or misses and the checks described above. Each case has one record per condition; the revenue steward record reuses an earlier response. Codex findings were manually mapped from its path-based output to the same labels and its actions inspected separately; this was an adaptation of the scorer, not a run of the steward executor. Prompts, inputs, traces and scoring are in `experiments/results/codex_midway_two_case/README.md`.

| Case | Steward TP/FP/FN | Codex TP/FP/FN | Steward / Codex success |
|:--|:--:|:--:|:--:|
| Revenue-filter repair | 1/0/0 | 1/0/0 | yes / yes |
| Changed grain | 2/2/0 | 2/2/0 | no / no |

Table: Two illustrative episodes, one run per condition; matches and extras are relative to the existing manifest. {#tbl:paired}

**Case 1: revenue-filter repair.** In `rem_daily_revenue_filter_drift`, the catalog says all orders while SQL filters to completed orders. The expected finding is SQL/metadata drift on `daily_revenue`. The steward cited evidence and patched the description to completed orders: 1 TP, 0 FP, 0 FN, and episode success. Codex also patched the override and compared the JSON description; it did not run dbt tests. The steward checked written equality and dbt parsing, not semantic correctness. The pilot folder contains the plan and ledger for this episode.

**Case 2: changed grain.** In `change_customer_orders_grain`, the manifest expects grain drift and an unsupported reliability claim on `customer_orders`. The steward found both, but also reported a duplicate SQL-drift issue and an undocumented seed: 2 TP, 2 FP, 0 FN, so the episode fails despite complete recall. Codex also reported both expected issues and the same two extras, requested review, and made no changes. It calculated join cardinalities from CSV rather than running dbt tests. The seed is a real pre-existing gap, illustrating a disagreement between scope/labels and findings rather than an invented problem. The pilot folder contains this episode's plan and the audit.

**Limitations.** This is a small, single-sample, AI-constructed suite; both clean controls contain unlabelled gaps, and four records in the original pilot reuse earlier responses. The validator's issue-type rules can be bypassed by a mislabel: on the wrong-grain case the steward patched a correct value even though that episode accepts only a proposal with uniqueness evidence. Verification does not check that semantic postcondition. These two cases show no observed difference in exact-label scores, not evidence of equivalence or general superiority. Independent label review, more cases, repeated runs and matched ablations remain future work.

# Assets {#sec:assets}

**Repository:** `\mbox{\url{https://github.com/alfenn/agentic-catalog-interface}}`{=latex} [@feng2026repo]: `README.md` (setup, reproduction), `src/catalog_steward/`, `data/` (fixture, episodes), and `experiments/results/midpoint_v1_2_pilot/` (pilot results, audit `analysis.md`). Midpoint demo video: **[VIDEO URL TO BE ADDED]**.

# Timeline (Summary of Progress: Next Steps and Risks) {#sec:timeline}

**Milestones.** Course deadlines are Demo Day on December 9 and the final 8-page report on December 11; intermediate dates are our targets.

- *By November 13:* a new frozen episode version: documented seeds, truly clean controls, an issue-type precedence rule checked independently of the model's label, and human review of the AI-built labels.
- *By November 20:* postcondition-based success and episode-level unsafe-action checks; real per-issue patch verification; a batching-robust protocol.
- *By December 4:* a matched coding-agent baseline, tool-versus-workflow ablations, and growth toward 30--50 audited episodes.
- *December 9 and 11:* live demo of both modes; final report.

**Obstacles and concerns.** No credential or pipeline blocker remains. The main concern is validity: label choices and protocol behaviour move results as much as the workflow, so fixes go into a new frozen version, not a rescoring.

**Risks and mitigations.** *Scope growth:* a frozen five-type contract with hard limits. *Ambiguous ground truth* (seen in both clean controls): documented seeds, a precedence rule, human label review. *Unsupported claims* (one invented-evidence run passed): claim--evidence support checks and manual audit. *Unmatched comparison:* align model, prompts and action limits, then test bundle ablations. *Warning overload* (six steward extras): clean controls, a five-finding cap, flagging only gaps a change introduces. *Small pilot:* per-episode reporting, more episodes.

```{=latex}
\label{bodyend}
\clearpage
\bibliography{references}
\bibliographystyle{iclr2025_conference}
\appendix
```

# AI-Use Disclosure Statement {#sec:ai}

Generative AI agents did most of the implementation and writing at this stage. Codex also ran the two-case baseline and revised this report in response to human feedback. OpenAI Codex agents implemented the prototype (environment setup, agent harness, hygiene contract, evidence tools, steward workflow, and baseline runners), built the dbt/DuckDB fixtures and the ten evaluation episodes and their labels, wrote the evaluation and scoring code, ran and audited the static pilot, and drafted the README and an initial version of this report. Claude (Anthropic) agents then audited, tested, fixed, and finished the work, including the preflight audit of the paid-run pipeline and its fixes, running the preliminary runs and the three-condition pilot, the manual audit of every pilot trace, typesetting this report in the ICLR template, the references, the script that generates the charts and results table from saved results, and the revision of this report around the audit. Because AI agents constructed the episodes and labels as well as the system under test, the ground truth reflects their design choices and needs independent human review. **[AUTHOR TO COMPLETE: describe the human verification actually performed, e.g., which code, episode labels, results, and report claims the author reviewed.]** AI tools are not authors; the author takes full responsibility for the content of this work.
