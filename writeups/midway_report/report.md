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

Maintainers of lakehouses need catalog metadata (ownership, grain, filters, lifecycle state) that stays trustworthy as models evolve, but it drifts from the code---annotations "can become outdated or incorrect" as data models evolve [@lakafosis2025meta]---and the evidence for a correction is scattered across catalog metadata, SQL, lineage, tests, and the data. We are building a *catalog steward*, prototyped on dbt and DuckDB, with two triggers over one workflow: *remediation* of existing hygiene debt and *change review* of a proposed contribution. Our question: **does a specialized evidence-gathering, risk-aware action, and verification workflow produce more complete, grounded, and safe maintenance outcomes than a general-purpose coding agent with access to the same repository and warehouse?**

# Methodology {#sec:method}

## Environment & Data {#sec:env}

**Environment and data.** The prototype environment is a small lakehouse fixture: a repository-local dbt Core project [@dbtcore] on DuckDB [@raasveldt2019duckdb] with three synthetic seed tables, a staging model, two aggregates, schema documentation, tests, and a JSON catalog snapshot. It is a reproducible test bed, not evidence about production warehouses. A versioned hygiene contract (`design/hygiene_contract.yaml`) bounds the task to five issue types (missing required metadata, SQL/metadata drift, grain or join drift, unsupported reliability claims, lifecycle drift) and three action classes (patch, propose, report) under hard scope limits. The pilot suite (`data/episodes/manifest.yaml`) has ten hand-built episodes: four *remediation* cases, four *flawed changes*, and two *clean controls*. Each records its expected `(issue_type, asset)` findings and its acceptable and unsafe actions.

**Evaluation.** Each condition runs on an identical, freshly built copy of each episode. Its findings are reduced to `(issue_type, asset)` pairs and matched exactly against the manifest, giving true positives (TP), extra findings (FP) and missed findings (FN). An episode succeeds only with no misses or extras, no disallowed action class and no recorded verification failure, and every saved trace is then audited. Appendix\ \ref{sec:envdetails} gives the fixture, contract and episodes in full, and the step-by-step procedure with what the scorer does not check.

## Methods {#sec:methods}

**What we built.** The catalog steward (Figure\ \ref{fig:arch}) pairs a domain-specific evidence interface for catalog hygiene with an inspect--plan--act--verify workflow under a risk-aware action policy, and both triggers share it: remediation starts from existing hygiene debt, and change review adds the proposed diff. This pairing is the contribution. Rather than leaving a model to search a repository and edit files, the steward first gathers the facts that hygiene decisions rest on into an evidence bundle (catalog metadata, dbt schema and manifest, model SQL with facts parsed by SQLGlot [@mao_sqlglot], lineage, bounded data profiles), each item carrying a stable, content-hashed ID. Following the view that purpose-built agent--computer interfaces matter [@yang2024sweagent], the model reads this bundle, may call read-only tools, and returns a structured plan of at most five findings, each with a claim, the evidence IDs it rests on and an action. A deterministic validator rejects a plan that breaks the schema or the contract's scope, evidence or action rules, with one repair turn. It then routes each finding to a catalog patch, a review proposal or a report, and appends every outcome to a ledger. Only reversible technical metadata may be patched, and only in an episode-local override file.

**Limits.** Verification is weak. A patch is kept only if the written field equals the value the model declared and `dbt parse` still succeeds. Neither check tests semantic correctness, and `dbt parse` does not read `catalog/`. The contract's per-issue checks (dashed in the figure) are not implemented yet. Appendix\ \ref{sec:details} details the evidence, tools, validator rules and verification.

![Catalog steward architecture as implemented in `src/catalog_steward/`. Both triggers feed one workflow. The model reads a bundle of content-hashed evidence, may call read-only tools, and returns a structured plan. A deterministic validator accepts the plan or returns it once for repair, and each accepted finding is then patched, proposed or reported, and logged. The only planned element is dashed: the contract's per-issue verification checks.](figures/architecture.pdf){#fig:arch width=100%}

**Conditions.** The steward uses `openai/gpt-6-luna` (low reasoning effort, at most 12 turns) under frozen configuration `experiments/configs/midpoint_v1.yaml` v1.2.0. For two selected cases we also ran OpenAI Codex CLI 0.167.0 [@openai_codex] with `gpt-6.1-terra` at medium reasoning effort on separately built fixtures. Codex had general repository tools and could edit files; the steward received a specialized evidence bundle and operated through a validated plan and patch executor. Their models, prompts, tools, limits and execution differ, so this comparison cannot isolate an interface effect. The original pilot's custom raw-tool workflow is not Codex and is excluded from this comparison.

## What Did Not Work, and Pivots {#sec:pivots}

**Reply format.** In a preliminary run the model copied a wrapper key from the format example, so its replies were rejected; we fixed the example and added one shared repair turn (commit `d2a547b`).

**Raw-tool exploration.** On `change_daily_revenue_filter` our raw-tool agent batched tool calls; once rejected, it reported nothing and missed the regression. Another run cited unreceived output yet passed the ID-only evidence check (pilot `analysis.md`). Codex replaced it.

**Label choice.** On `rem_customer_orders_wrong_grain` the steward labelled a grain error SQL/metadata drift, a patchable type, and patched a correct value, but the episode required a proposal with uniqueness evidence, so it failed. Next, issue type is checked apart from the label.

**Unmatched baseline.** A first Codex run matched the steward on two cases, but a different model, no contract rules in the prompt and hand-mapped labels confounded harness with model and wording (`codex_midway_two_case/README.md`). The new baseline removes all three (Appendix\ \ref{sec:pivotdetails}).

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
\bibliography{references}
\bibliographystyle{iclr2025_conference}
\appendix
```

# Environment, Episodes and Evaluation {#sec:envdetails}

**Fixture.** Three seed tables (5 customers, 8 orders, 10 order items) feed a staging model and two aggregates (`customer_orders`, `daily_revenue`) through the dbt-duckdb adapter, with schema documentation, dbt tests and a JSON catalog snapshot. A compact `catalog/overrides.json` sidecar injects controlled metadata changes. Each episode copies the clean base, applies a debt or change overlay, generates the diff, and builds the project (`dbt seed`, `run`, `parse`), so every condition starts from the same state.

**Hygiene contract.** The contract (v0.1.0, validated by a JSON Schema) names, for each of the five issue types, its required evidence, allowed and forbidden action classes, and intended verification. Limits: 20 assets, two lineage hops, five findings and 10,000 probed rows. Deleting assets, changing access policies, mutating a live catalog, inventing business semantics and unbounded queries are forbidden.

**Episodes and ground truth.** The four remediation cases are a stale revenue-filter description, wrong customer-order grain, a missing owner, and a legacy copy still marked active and canonical. The four flawed changes are a changed revenue filter, a changed grain without updated grain metadata or tests, a new undocumented model, and a rename without a lifecycle transition. The two clean controls are a documented new model and a documented revenue metric. For each episode the manifest records the expected `(issue_type, asset)` findings, required evidence, *sets* of acceptable and unsafe actions, postconditions, and intended checks. Action sets let an escalation count as correct where business meaning is uncertain. In the filter-drift case, for example, proposing a description fix is acceptable but editing the SQL to match stale prose is unsafe. The clean controls are meant to measure spurious findings, although both contain unlabelled gaps.

**Evaluation procedure.** For each episode: (1) copy the base fixture; (2) apply the specified debt or change overlay and build the dbt project; (3) run each condition independently on that state with its recorded prompt and settings; (4) save the findings and normalize them to `(issue_type, asset)`, keeping evidence and actions; (5) match those pairs exactly to the manifest and count TP, FP and FN; (6) count the episode as successful only if it completes without missing or extra findings, disallowed action classes, or a recorded verification failure; and (7) inspect the saved trace. Precision is TP/(TP+FP) and recall is TP/(TP+FN); micro scores aggregate counts before dividing. The scorer checks that evidence IDs resolve, not that they support the claim. It checks action classes, not episode-specific acceptable actions or postconditions. The AI-assisted trace audit examines those distinctions separately.

# System Details {#sec:details}

**Evidence bundle.** For each scoped asset (at most 20) the steward collects catalog metadata (the snapshot merged with the override file), dbt schema documentation and tests, model SQL, parsed SQL facts (sources, filters, joins, aggregates, grouping, grain candidates, select expressions), the dbt manifest node, one-hop lineage, and a bounded profile. Change review adds the diff. The profile reads at most 10,000 rows from a read-only DuckDB connection with external access disabled and reports per-column null, distinct and duplicate counts. Every item has an ID derived from a hash of its kind, asset, source and content, plus a provenance pointer. Absent metadata is recorded as explicit `present: false` evidence. The prompt contains only the trigger, asset scope, evidence and collection errors, never the episode ID or labels.

**Agent loop and tools.** The model works through a JSON reply protocol for at most 12 turns. Three consecutive malformed replies end the run. During planning it may call nine read-only tools, whose arguments are checked against JSON Schemas: catalog metadata, dbt schema, model SQL, SQL facts, manifest node, lineage (up to two hops), a bounded profile of chosen columns, the change diff, and a file read confined to the episode project (at most 50 kB). No write tools are registered.

**Validator and action policy.** The final plan must be JSON that matches the steward plan schema, with at most five findings. Each finding must name an in-scope asset and an issue type in the contract, choose an action class that the contract allows for that issue type, cite only evidence IDs from this run, and cite every evidence kind the issue type requires. A failing plan is returned once with the error; a second failure ends the run with no action. Only missing required metadata and SQL/metadata drift allow a patch; grain, reliability and lifecycle issues allow only a proposal or a report. Because these rules key on the model's own issue label, a mislabelled finding can bypass them.

**Execution, verification and ledger.** A patch may set one of five fields (description, owner, lifecycle, grain, canonical) in the episode's `catalog/overrides.json`. The steward saves a unified diff and writes the file. It then re-reads the merged catalog metadata to check that the field equals the value the plan declared, and runs `dbt parse`. If either check fails, it restores the file and records a verification failure. A proposal or report is checked only for an allowed action class and resolved evidence IDs. Each outcome, with its finding, checks and patch path, is appended to `steward_ledger.jsonl` alongside a run summary. A finding already recorded as verified is not executed again. The contract's per-issue verification checks (for example, comparing metadata with parsed SQL, or rerunning a uniqueness probe) are not implemented.

# Pivot Evidence {#sec:pivotdetails}

Episode paths below are relative to the pilot folder `experiments/results/midpoint_v1_2_pilot/`.

**Reply format.** In the preliminary run (2 episodes, config 1.1.0), `render_tools()` showed both reply shapes as one object keyed by `tool_call` and `final_answer`, and the model copied that wrapper; 7 of 8 rejected replies had this cause, and one run repeated it three times and stopped before reading the diff. The raw records of that run were not kept; the diagnosis is recorded in commit `d2a547b` and `writeups/midway_report/.agents/agent_notes.md` (2026-11-08). The fix, in config 1.2.0, shows two plain example objects, makes protocol errors say what to send instead, and gives both model conditions one identical repair turn for an invalid final plan. Prompts were frozen after a rerun under 1.2.0 and before the pilot.

**Raw-tool exploration.** The first reply in `change_daily_revenue_filter/generic.json` holds several `read_diff` and `read_file` calls in one message and is rejected as more than one JSON object; the second reply is a final plan with no findings whose summary says the evidence "only lists project files". The only evidence in the record is the project listing. In `rem_daily_revenue_missing_owner/generic.json`, the first reply held at least 13 tool calls with invented results and a draft answer; no tool ran, and the final plan reported three issues about a change that does not exist, citing the project-listing ID after the repair turn. The scorer gave it evidence validity 1.0 because it checks only that IDs resolve. Seven of its ten pilot runs hit a rejection, against two for the steward (`analysis.md`).

**Label choice.** In `rem_customer_orders_wrong_grain/steward.json`, the steward's single finding is `sql_metadata_drift` on `customer_orders`, with a patch setting the catalog grain to `customer_id` and evidence from the catalog, dbt schema, SQL, parsed SQL facts and manifest but no uniqueness probe. The value is correct and was verified as written, but the manifest expects `grain_or_join_drift` with a proposal and uniqueness evidence, so the episode scores 0/1/1 and fails. The validator allowed the patch because its rules key on the model's own label.

**Unmatched baseline.** The first Codex runs used Codex CLI 0.167.0 with `gpt-6.1-terra` at medium effort, while the steward pilot used `gpt-6-luna` at low effort; they are recorded in `experiments/results/codex_midway_two_case/README.md`. The prompt listed the five issue types but not their required evidence or allowed actions, and Codex's path-based findings were mapped to manifest labels by hand. Both agents scored 1/0/0 on the revenue-filter case and 2/2/0 on the changed-grain case. The matched baseline in progress runs Codex on `gpt-6-luna` at low effort, gives it the contract's issue types with their required evidence and allowed actions and the same fixture access, and has it return labels directly through an output schema; a second condition uses a frontier model. Its results are not yet available.

# AI-Use Disclosure Statement {#sec:ai}

Generative AI agents did most of the implementation and writing at this stage. Codex also ran the two-case baseline and revised this report in response to human feedback. OpenAI Codex agents implemented the prototype (environment setup, agent harness, hygiene contract, evidence tools, steward workflow, and baseline runners), built the dbt/DuckDB fixtures and the ten evaluation episodes and their labels, wrote the evaluation and scoring code, ran and audited the static pilot, and drafted the README and an initial version of this report. Claude (Anthropic) agents then audited, tested, fixed, and finished the work, including the preflight audit of the paid-run pipeline and its fixes, running the preliminary runs and the three-condition pilot, the manual audit of every pilot trace, typesetting this report in the ICLR template, the references, the script that generates the charts and results table from saved results, and the revision of this report around the audit. Because AI agents constructed the episodes and labels as well as the system under test, the ground truth reflects their design choices and needs independent human review. **[AUTHOR TO COMPLETE: describe the human verification actually performed, e.g., which code, episode labels, results, and report claims the author reviewed.]** AI tools are not authors; the author takes full responsibility for the content of this work.
