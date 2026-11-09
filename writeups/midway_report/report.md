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

**Evaluation.** Each condition runs once on an identical, freshly built copy of each episode; Codex's copy sits outside the repository with every file that names the episode removed. Codex's structured answer is converted into the steward's plan form, and after each Codex run the harness diffs the workspace, applies the steward's own patch verification to what Codex wrote, and scans its commands for reads outside the workspace. Findings are reduced to `(issue_type, asset)` pairs and matched exactly against the manifest. An episode succeeds only with no missed or extra findings, no forbidden action class and no failed verification, and every saved trace is then audited. Appendix\ \ref{sec:envdetails} gives the fixture, contract and episodes, the step-by-step procedure with what the scorer does not check, and every difference between the conditions.

## Methods {#sec:methods}

**What we built.** The catalog steward (Figure\ \ref{fig:arch}) pairs a domain-specific evidence interface for catalog hygiene with an inspect--plan--act--verify workflow under a risk-aware action policy, and both triggers share it: remediation starts from existing hygiene debt, and change review adds the proposed diff. This pairing is the contribution. Rather than leaving a model to search a repository and edit files, the steward first gathers the facts that hygiene decisions rest on into an evidence bundle (catalog metadata, dbt schema and manifest, model SQL with facts parsed by SQLGlot [@mao_sqlglot], lineage, bounded data profiles), each item carrying a stable, content-hashed ID. Following the view that purpose-built agent--computer interfaces matter [@yang2024sweagent], the model reads this bundle, may call read-only tools, and returns a structured plan of at most five findings, each with a claim, the evidence IDs it rests on and an action. A deterministic validator rejects a plan that breaks the schema or the contract's scope, evidence or action rules, with one repair turn. It then routes each finding to a catalog patch, a review proposal or a report, and appends every outcome to a ledger. Only reversible technical metadata may be patched, and only in an episode-local override file.

**Limits.** Verification is weak. A patch is kept only if the written field equals the value the model declared and `dbt parse` still succeeds. Neither check tests semantic correctness, and `dbt parse` does not read `catalog/`. The contract's per-issue checks (dashed in the figure) are not implemented yet. Appendix\ \ref{sec:details} details the evidence, tools, validator rules and verification.

![Catalog steward architecture as implemented in `src/catalog_steward/`. Both triggers feed one workflow. The model reads a bundle of content-hashed evidence, may call read-only tools, and returns a structured plan. A deterministic validator accepts the plan or returns it once for repair, and each accepted finding is then patched, proposed or reported, and logged. The only planned element is dashed: the contract's per-issue verification checks.](figures/architecture.pdf){#fig:arch width=100%}

**Conditions.** We compare three conditions on the ten episodes. The *steward* is the frozen pilot (`experiments/configs/midpoint_v1.yaml` v1.2.0): `gpt-6-luna` at low reasoning effort, at most 12 turns, with the evidence bundle, read-only tools, validator and executor; two of its ten records replay responses from an earlier identical run. *Codex, matched* is OpenAI Codex CLI 0.167.0 [@openai_codex] on the same model and effort, so the harness is what differs; *Codex, frontier* is the same harness on `gpt-6.1-sol` at medium effort. Both Codex conditions receive the steward's task specification, including the hygiene contract's required evidence and allowed actions, and the same project, warehouse and diff, but work with general shell and file tools instead of the bundle, validator and executor: a sandbox that can write only inside the workspace, no network, no turn limit within a 30-minute timeout, and a JSON output schema (`experiments/configs/codex_baseline_v1.yaml`). Appendix\ \ref{sec:envdetails} lists every difference.

## What Did Not Work, and Pivots {#sec:pivots}

**Reply format.** In a preliminary run the model copied a wrapper key from the format example, so its replies were rejected; we fixed the example and added one shared repair turn (commit `d2a547b`).

**Raw-tool exploration.** On `change_daily_revenue_filter` our raw-tool agent batched tool calls; once rejected, it reported nothing and missed the regression. Another run cited unreceived output yet passed the ID-only evidence check (pilot `analysis.md`). Codex replaced it.

**Label choice.** On `rem_customer_orders_wrong_grain` the steward labelled a grain error SQL/metadata drift, a patchable type, and patched a correct value, but the episode required a proposal with uniqueness evidence, so it failed. Next, issue type is checked apart from the label.

**Unmatched baseline.** A first Codex run matched the steward on two cases, but a different model, no contract rules in the prompt and hand-mapped labels confounded harness with model and wording (`codex_midway_two_case/README.md`). The new baseline removes all three (Appendix\ \ref{sec:pivotdetails}).

# Results (Summary of Progress) {#sec:results}

**What we compared.** Every component in Figure\ \ref{fig:arch} is implemented, as is the Codex adapter. Table\ \ref{tbl:results} reports the steward and both Codex conditions on all ten episodes. **[TODO after the full Codex run: one or two sentences on the totals, read from the table.]**

<!-- BEGIN GENERATED: results_table (make_figures.py; do not edit by hand) -->
```{=latex}
\begin{table}[!ht]
\caption{Per-episode outcomes, one run per condition and episode. A \emph{true positive} (TP) is a finding whose (issue type, asset) pair matches an expected one exactly, a \emph{false positive} (FP) is any other finding, and a \emph{false negative} (FN) is an expected finding left unmatched. An episode \emph{succeeds} only if the run completes with no FP or FN, no action class the contract forbids for the issue type, and no failed patch verification. Micro precision and recall are $\sum$TP$/\sum$(TP$+$FP) and $\sum$TP$/\sum$(TP$+$FN) over the ten episodes. An errored run counts its expected findings as missed; a dash is a run not yet recorded; the steward cannot edit any file but the override file (n/a). Sources: \nolinkurl{experiments/results/midpoint_v1_2_pilot/} and \nolinkurl{experiments/results/codex_baseline_v1/}.}
\label{tbl:results}
\centering\small
\begin{tabular}{@{}lcccccc@{}}
\toprule
 & \multicolumn{2}{c}{Steward} & \multicolumn{2}{c}{Codex, matched} & \multicolumn{2}{c}{Codex, frontier} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}
Episode & TP/FP/FN & Success & TP/FP/FN & Success & TP/FP/FN & Success \\
\midrule
\multicolumn{7}{@{}l}{\emph{Remediation}} \\
\quad Stale revenue-filter description & 1/0/0 & yes & -- & -- & -- & -- \\
\quad Wrong customer-order grain & 0/1/1 & no & -- & -- & -- & -- \\
\quad Missing owner & 1/0/0 & yes & -- & -- & -- & -- \\
\quad Legacy copy still active & 1/1/0 & no & -- & -- & -- & -- \\
\midrule
\multicolumn{7}{@{}l}{\emph{Flawed change}} \\
\quad Revenue filter changed & 1/0/0 & yes & -- & -- & -- & -- \\
\quad Grain changed, metadata not & 2/2/0 & no & -- & -- & -- & -- \\
\quad New undocumented model & 1/0/0 & yes & -- & -- & -- & -- \\
\quad Rename without lifecycle change & 2/0/0 & yes & -- & -- & -- & -- \\
\midrule
\multicolumn{7}{@{}l}{\emph{Clean control}} \\
\quad Documented new model & 0/1/0 & no & -- & -- & -- & -- \\
\quad Documented revenue metric & 0/1/0 & no & -- & -- & -- & -- \\
\midrule
Episode successes & \multicolumn{2}{c}{5/10} & \multicolumn{2}{c}{--} & \multicolumn{2}{c}{--} \\
Micro precision / recall & \multicolumn{2}{c}{0.60 / 0.90} & \multicolumn{2}{c}{--} & \multicolumn{2}{c}{--} \\
Findings with a forbidden action & \multicolumn{2}{c}{0} & \multicolumn{2}{c}{--} & \multicolumn{2}{c}{--} \\
Patch verification failures & \multicolumn{2}{c}{0} & \multicolumn{2}{c}{--} & \multicolumn{2}{c}{--} \\
Runs editing another file & \multicolumn{2}{c}{n/a} & \multicolumn{2}{c}{--} & \multicolumn{2}{c}{--} \\
\bottomrule
\end{tabular}
\end{table}
```
<!-- END GENERATED: results_table -->

**Remediation walkthrough.** **[TODO after the full Codex run and audit: one remediation episode. What each agent inspected and did, whether it was right, what we expected, how it could have done better, and how that became its score, citing the saved records by path.]**

**Change-review walkthrough.** **[TODO after the full Codex run and audit: one change-review episode, covered the same way.]**

**Limitations.** Each cell is one sample. In the paired check, matched Codex succeeded on the revenue-filter change in two of three samples and added an unsupported reliability finding in the third (`experiments/results/codex_baseline_v1_paired_check/README.md`), so a one-episode difference can be noise. AI agents built the episodes and labels, and both clean controls contain unlabelled gaps, so some extras are disputable. The scorer matches labels exactly; it checks that evidence resolves, not that it supports the claim, and checks action classes, not each episode's acceptable actions or postconditions. Patch verification checks the written value and `dbt parse`, not semantic correctness. **[TODO after the full Codex run: what the observed differences do and do not support; no superiority or equivalence claim beyond ten single-sample episodes.]**

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
\bibliography{references}
\label{referencesend}
\bibliographystyle{iclr2025_conference}
\appendix
```

# Environment, Episodes, Evaluation and Conditions {#sec:envdetails}

**Fixture.** Three seed tables (5 customers, 8 orders, 10 order items) feed a staging model and two aggregates (`customer_orders`, `daily_revenue`) through the dbt-duckdb adapter, with schema documentation, dbt tests and a JSON catalog snapshot. A compact `catalog/overrides.json` sidecar injects controlled metadata changes. Each episode copies the clean base, applies a debt or change overlay, generates the diff, and builds the project (`dbt seed`, `run`, `parse`), so every condition starts from the same state.

**Hygiene contract.** The contract (v0.1.0, validated by a JSON Schema) names, for each of the five issue types, its required evidence, allowed and forbidden action classes, and intended verification. Limits: 20 assets, two lineage hops, five findings and 10,000 probed rows. Deleting assets, changing access policies, mutating a live catalog, inventing business semantics and unbounded queries are forbidden.

**Episodes and ground truth.** The four remediation cases are a stale revenue-filter description, wrong customer-order grain, a missing owner, and a legacy copy still marked active and canonical. The four flawed changes are a changed revenue filter, a changed grain without updated grain metadata or tests, a new undocumented model, and a rename without a lifecycle transition. The two clean controls are a documented new model and a documented revenue metric. For each episode the manifest records the expected `(issue_type, asset)` findings, required evidence, *sets* of acceptable and unsafe actions, postconditions, and intended checks. Action sets let an escalation count as correct where business meaning is uncertain. In the filter-drift case, for example, proposing a description fix is acceptable but editing the SQL to match stale prose is unsafe. The clean controls are meant to measure spurious findings, although both contain unlabelled gaps.

**Evaluation procedure.** For each episode and condition: (1) copy the base fixture, apply the episode's debt or change overlay and build the dbt project; for Codex the build goes to a temporary directory with an opaque name outside the repository, and the episode file, the marker file that names the episode, the pre-change copy and the build log are removed, leaving `project/` (with dbt's `target/`), `warehouse.duckdb` and, for change review, `input.diff`; (2) run the condition once on that state with its recorded prompt and settings; (3) save its findings with their evidence and actions; Codex's answer, which cites file paths or commands rather than evidence IDs, is validated against its output schema and converted to the steward's plan form, each citation becoming an evidence entry; (4) for Codex, run the post-run checks below; (5) reduce findings to `(issue_type, asset)` pairs, match them exactly to the manifest and count TP, FP and FN; (6) count the episode as successful only if the run completes without missing or extra findings, forbidden action classes, or a failed verification; and (7) inspect the saved trace. Precision is TP/(TP+FP) and recall is TP/(TP+FN); micro scores sum the counts over episodes before dividing. The scorer (`midpoint-score-v1`, unchanged for Codex) checks that evidence resolves, not that it supports the claim. It checks action classes, not episode-specific acceptable actions or postconditions. The AI-assisted trace audit examines those distinctions separately.

**Post-run checks for Codex.** After each run the harness (a) diffs the project before and after and records every changed file; (b) applies the steward's patch verification to every patch finding: the override file changed that field, the merged catalog field equals the value Codex declared, and `dbt parse` succeeds on Codex's final workspace, so a claimed patch with no file change fails; (c) checks that only `catalog/overrides.json` changed and that every changed field is declared by a patch finding; and (d) scans the event stream for the repository path, episode IDs, label file names, paths outside the workspace, parent-directory reads, and web or connector use. A failure in (b) or (c) is a verification failure; (d) flags a run for the audit without changing its score. For Codex, evidence validity is the share of citations whose file exists in the workspace or whose command ran successfully; it is not the steward's check that evidence IDs resolve, so it is reported separately.

**Shared by all three conditions.** The episode fixtures and their build; the trigger and asset scope; the contract's five issue types with their required evidence and allowed and forbidden actions; the five-finding cap; the patch surface (five fields of an asset in scope in `catalog/overrides.json`); the instruction not to use ground truth or invent business meaning; and the scorer.

**Different between the steward and Codex.** *Inputs:* the steward receives a precomputed evidence bundle and may call nine read-only tools; Codex reads the same project, warehouse and diff itself with a shell, `dbt`, and Python with DuckDB from a tool environment outside the repository. *Evidence:* the steward cites content-hashed evidence IDs; Codex cites workspace paths or the commands it ran. *Budget:* the steward has at most 12 turns of at most 4,096 output tokens at temperature 0; Codex has no turn limit within a 30-minute timeout and otherwise the CLI's defaults. *Plan checks:* the steward's validator enforces the schema and the contract's scope, evidence and action rules with one repair turn; Codex's answer must match a JSON output schema, and the contract's rules are stated in its prompt but not enforced during the run. *Execution:* the steward's executor writes each patch, verifies it and restores the file on failure; Codex edits the override file itself (its sandbox can write anywhere in the workspace), and the harness verifies afterwards. *Data access:* the steward's profile opens DuckDB read-only with external access disabled and caps rows in code; Codex is told to open the warehouse read-only and keep queries within 10,000 rows, which nothing enforces. *Environment:* Codex runs as an ephemeral session that ignores user configuration, rules, hooks, apps, plugins and memories, with web search disabled, no network, and a non-login shell whose `PATH` holds only the tool environment and system directories. *Model access:* the steward calls `gpt-6-luna` through OpenRouter; Codex calls its model through the CLI. *Records:* two steward records (both revenue-filter episodes) replay an earlier identical run; every Codex record is a fresh run.

**Between the two Codex conditions,** only the model and reasoning effort differ: `gpt-6-luna` at low effort (matched) and `gpt-6.1-sol` at medium effort (frontier).

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
