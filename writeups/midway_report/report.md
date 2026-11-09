---
# Editable source of the CS329Z midway report. Build with `make report` from the
# repository root; it regenerates figures/, the generated regions below, report.tex,
# and report.pdf, and builds the separate appendix from appendix.md. Do not edit
# report.tex or appendix.tex by hand.
title: '`[Midway Report] Is the Gap an Interface Gap?\\ Agent Tool Interfaces for Data Catalogs`{=latex}'
pdftitle: "Is the Gap an Interface Gap? Agent Tool Interfaces for Data Catalogs"
author: Alex Feng
running-header: "CS329Z: Engineering AI Agents -- Midway Report"
comment: "CS329Z midway report, generated from report.md."
---

# Problem Statement (Problem Specification) {#sec:problem}

Maintainers of lakehouses need trustworthy catalog metadata (ownership, grain, filters, lifecycle state). But this metadata drifts from the code: annotations "can become outdated or incorrect" as data models evolve [@lakafosis2025meta]. The evidence needed to correct it is scattered across catalog metadata, SQL, lineage, tests, and the data. I am building a *catalog steward*, prototyped on dbt and DuckDB, with two triggers over one workflow: *remediation* of existing hygiene debt and *change review* of a proposed contribution. Our question: **does a specialized evidence-gathering, risk-aware action, and verification workflow produce more complete, grounded, and safe maintenance outcomes than a general-purpose coding agent with access to the same repository and warehouse?**

# Methodology {#sec:method}

## Environment & Data {#sec:env}

**Environment and data.** The prototype environment is a small lakehouse fixture: a repository-local dbt Core project [@dbtcore] on DuckDB [@raasveldt2019duckdb] with three synthetic seed tables, a staging model, two aggregates, schema documentation, tests, and a JSON catalog snapshot. A versioned hygiene contract (`design/hygiene_contract.yaml`) binds the task to five issue types (missing required metadata, SQL/metadata drift, grain or join drift, unsupported reliability claims, lifecycle drift) and three action classes (patch, propose, report). The evaluation suite (`data/episodes/manifest.yaml`) has ten hand-built examples: four *remediation* cases, four *flawed changes*, and two *clean controls*. Each example comes with an answer key: the problems a careful reviewer should report, each named by its issue type and the table it affects (e.g., SQL/metadata drift on `daily_revenue`), plus the actions that are acceptable or unsafe in response.

**Evaluation.** Each condition runs once on an identical, freshly built copy of each example. Codex's answer is converted to the steward's plan form, and the harness then diffs its workspace and applies the steward's patch verification. A reported problem counts as correct only if both its issue type and its table match an entry in the answer key; otherwise it is an *extra* (a false positive), and the number of extras measures how much noise a harness puts in front of a reviewer. Every trace is also audited, with AI assistance, for what the scorer cannot check: whether each claim is true of the fixture, whether each action suits the example, and whether each extra is a real gap the labels miss.

## Methods {#sec:methods}

**What I built.** The catalog steward (Figure\ \ref{fig:arch}) pairs a domain-specific evidence interface for catalog hygiene with an inspect--plan--act--verify workflow under a risk-aware action policy, shared by both triggers (change review adds the proposed diff). This pairing is the contribution. Rather than leaving a model to search a repository and edit files, the steward first gathers the facts that hygiene decisions rest on into an evidence bundle (catalog metadata, dbt schema and manifest, model SQL with facts parsed by SQLGlot [@mao_sqlglot], lineage, bounded data profiles), each item carrying a stable, content-hashed ID. Following the view that purpose-built agent--computer interfaces matter [@yang2024sweagent], the model reads this bundle, may call read-only tools, and returns a structured plan of at most five findings, each with a claim, the evidence IDs it rests on and an action. A deterministic validator rejects a plan that breaks the schema or the contract's scope, evidence or action rules. It then routes each finding to a catalog patch, a review proposal or a report, and appends every outcome to a ledger. Only reversible technical metadata may be patched, and only in an example-local override file.

**Limits.** Verification is weak. A patch is kept only if the written field equals the value the model declared and `dbt parse` still succeeds. Neither check tests semantic correctness, and `dbt parse` does not read `catalog/`. The contract's per-issue checks (dashed in the figure) are not implemented yet.

![Catalog steward architecture as implemented in `src/catalog_steward/`. Both triggers feed one workflow. The model reads a bundle of content-hashed evidence, may call read-only tools, and returns a structured plan. A deterministic validator accepts the plan or returns it once for repair, and each accepted finding is then patched, proposed or reported, and logged. The only planned element is dashed: the contract's per-issue verification checks.](figures/architecture.pdf){#fig:arch width=100%}

**Conditions.** I compare three conditions. The *steward* runs on the agentic harness I built (evidence bundle, read-only tools, validator and executor) with `gpt-6-luna` at low reasoning effort for at most 12 turns. Two Codex comparisons run OpenAI Codex CLI 0.167.0 [@openai_codex]: *Codex, matched* on the same model and effort, so only the harness differs, and *Codex, frontier* on `gpt-6.1-sol` at medium effort. Both Codex comparisons get the steward's task specification, including the hygiene contract (Section\ \ref{sec:env}), the same dbt project and warehouse, and, for change-review examples, the proposed change's diff. Instead of the bundle, validator and executor, they get general shell and file tools in a sandbox writable only inside the workspace, with no network and no turn limit within a 30-minute timeout, and answer in a JSON output schema.

## What Did Not Work, and Pivots {#sec:pivots}

**From question answering to data hygiene.** My proposal planned a general-purpose data agent for question answering over a data lake, but its task categories and examples were too myopic for the problem I want to solve: keeping lakehouse metadata trustworthy as the lakehouse changes. Reframing the project around the data-hygiene process itself, through its two workflows (remediating existing debt and reviewing proposed changes), tackles that problem directly.

**From a bespoke baseline to Codex.** My first comparison agent was a simple custom agent with four raw tools (list files, read a file, read the diff, run a bounded SQL query) on the steward's model. It was easy to inspect and differed from the steward only in its tools, but it is not representative of the alternative someone would actually use to fix these hygiene issues. I replaced it with Codex, a frontier agent harness, and reran the comparison on all ten examples (`experiments/results/codex_baseline_v1/`), trading the simpler agent's comparability and ease of inspection for a comparison against a frontier harness.

**Next: more baselines.** I want to compare Codex with Pi, another open-source coding-agent harness, and to compare against standard data-hygiene automations (e.g., dbt-project-evaluator, Great Expectations) and CI workflows that run them on every change.

# Results (Summary of Progress) {#sec:results}

## Reported Results {#sec:reported}

In Table\ \ref{tbl:results}, the steward succeeds on 5/10 examples (precision 0.60, recall 0.90), matched-Codex on 6/10 (0.58, 0.70) and frontier-Codex on 7/10 (0.73, 0.80). The steward finds the most answer-key problems but also reports the most extras: 6, against 5 for matched-Codex and 3 for frontier-Codex.

<!-- BEGIN GENERATED: results_table (make_figures.py; do not edit by hand) -->
```{=latex}
\begin{table}[t]
\caption{Per-example outcomes, one run each. TP: a reported problem matching an answer-key entry (same issue type and table); FP: an \emph{extra}, a reported problem matching none; FN: an answer-key entry no reported problem matches. An example \emph{succeeds} if the run completes with no FP or FN, no forbidden action class and no failed verification. Precision and recall are micro-averaged: per-example recall divides by the number of answer-key entries, which is zero for examples that contain no hygiene problems. The last row counts forbidden action classes, failed verifications and edits outside the override file (n/a for the steward, which cannot make them).}
\label{tbl:results}
\centering\small
\begin{tabular}{@{}lcccccc@{}}
\toprule
 & \multicolumn{2}{c}{Steward} & \multicolumn{2}{c}{Codex, matched} & \multicolumn{2}{c}{Codex, frontier} \\
\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}
Example & TP/FP/FN & Success & TP/FP/FN & Success & TP/FP/FN & Success \\
\midrule
\multicolumn{7}{@{}l}{\emph{Remediation}} \\
\quad Stale revenue-filter description & 1/0/0 & yes & 1/0/0 & yes & 1/0/0 & yes \\
\quad Wrong customer-order grain & 0/1/1 & no & 0/1/1 & no & 1/0/0 & yes \\
\quad Missing owner & 1/0/0 & yes & 1/0/0 & yes & 1/0/0 & yes \\
\quad Legacy copy still active & 1/1/0 & no & 0/1/1 & no & 0/0/1 & no \\
\midrule
\multicolumn{7}{@{}l}{\emph{Flawed change}} \\
\quad Revenue filter changed & 1/0/0 & yes & 1/0/0 & yes & 1/0/0 & yes \\
\quad Grain changed, metadata not & 2/2/0 & no & 1/2/1 & no & 1/2/1 & no \\
\quad New undocumented model & 1/0/0 & yes & 1/0/0 & yes & 1/0/0 & yes \\
\quad Rename without lifecycle change & 2/0/0 & yes & 2/0/0 & yes & 2/0/0 & yes \\
\midrule
\multicolumn{7}{@{}l}{\emph{Clean control}} \\
\quad Documented new model & 0/1/0 & no & 0/1/0 & no & 0/1/0 & no \\
\quad Documented revenue metric & 0/1/0 & no & 0/0/0 & yes & 0/0/0 & yes \\
\midrule
Total TP / FP (extras) / FN & \multicolumn{2}{c}{9/6/1} & \multicolumn{2}{c}{7/5/3} & \multicolumn{2}{c}{8/3/2} \\
Example successes & \multicolumn{2}{c}{5/10} & \multicolumn{2}{c}{6/10} & \multicolumn{2}{c}{7/10} \\
Micro precision / recall & \multicolumn{2}{c}{0.60 / 0.90} & \multicolumn{2}{c}{0.58 / 0.70} & \multicolumn{2}{c}{0.73 / 0.80} \\
Forbidden / failed / other edits & \multicolumn{2}{c}{0 / 0 / n/a} & \multicolumn{2}{c}{0 / 0 / 0} & \multicolumn{2}{c}{0 / 0 / 0} \\
\bottomrule
\end{tabular}
\end{table}
```
<!-- END GENERATED: results_table -->

## Results Discussion and Observations {#sec:discussion}

**Steward vs. matched-Codex.** With the same model, the steward's harness finds more: its bundle covers every table in scope, so only the steward caught the failing uniqueness claim and the stale legacy copy. It also reports more extras, and one borderline extra decides the one-example gap. Both filed the wrong-grain problem as SQL/metadata drift and patched it, so that error is the model's.

**Steward vs. frontier-Codex.** The gap comes mostly from the stronger model, which labelled the wrong-grain problem correctly and reported half the extras. It still missed both problems only the steward caught. With no steward run on this model, model and harness are confounded.

**Why Codex scored higher.** Success is all-or-nothing, so one extra fails an example. The steward shows the model every table in scope, so it comments on more, and half its extras are real gaps the labels miss; Codex reads only what it chooses and reports less. The scorer misses the largest difference: in change review the steward only proposed, while Codex patched the catalog in 3 and 4 of six runs, e.g., rewriting the revenue description to accept an unreviewed change.

**How to improve the steward.** Keep the breadth but filter the report: in change review, flag only gaps the change introduces, and drop findings the model itself calls unestablished. Have the validator check evidence content, not presence (the legacy-copy finding cited an empty diff as history), and fix a precedence between overlapping issue types so a grain problem cannot be patched as drift.

## Limitations and Next Steps {#sec:limits}

Each cell is one run (matched-Codex passed the filter change in two of three earlier tries). AI agents built the examples and labels, and both examples meant to have no hygiene problems contain real gaps the labels miss (crediting them gives 7, 7 and 8 successes). The scorer checks neither evidence support nor action fit, and with ten examples a gap of one or two supports no ranking. *Next* (Section\ \ref{sec:timeline}): about 50 human-reviewed examples, repeated runs, the steward on the frontier model, and scoring change-review patches that accept unreviewed changes as unsafe.

# Assets {#sec:assets}

**Repository:** `\mbox{\url{https://github.com/alfenn/agentic-catalog-interface}}`{=latex} [@feng2026repo]: `README.md` (setup, reproduction), `src/catalog_steward/`, `data/` (fixture, examples), `experiments/results/`. Midpoint demo video: **[VIDEO URL TO BE ADDED]**.

# Timeline (Summary of Progress: Next Steps and Risks) {#sec:timeline}

**Milestones.** Demo Day is December 9 and the final report December 11; the rest are my targets.

- *By November 13:* a revised example set, locked before new runs: documented seeds, truly clean controls, a label-independent issue-type precedence rule, human label review.
- *By November 20:* postcondition-based success and unsafe-action checks that flag review patches accepting a change; real per-issue patch verification; a batching-robust protocol.
- *By December 4:* repeated samples, ablations and about 50 audited examples.

**Risks and mitigations.** *Scope growth:* a contract held at five issue types. *Ambiguous ground truth* (seen in both clean controls): documented seeds, a precedence rule, human label review. *Unsupported claims* (one invented-evidence run passed): claim--evidence checks and manual audit.

```{=latex}
\bibliography{references}
\label{referencesend}
\bibliographystyle{iclr2025_conference}
```

# AI-Use Disclosure Statement {#sec:ai .unnumbered}

In this work, I used generative AI tools to refine the hypothesis, to brainstorm task formulations, and to give feedback on the research methodology. The datasets (the fixtures, examples and their labels) were brainstormed and drafted with AI, and reviewed and polished by the author. Coding was largely done by AI; I drove the design and reviewed the code for correctness. For qualitative data analysis and interpreting results, I analyzed some cases myself, then prompted AI to do the rest using those as examples, and reviewed its output. Additionally, I used generative AI tools for brainstorming, identifying gaps in prior work, searching for and summarizing relevant literature, and providing editing suggestions for readability. I have reviewed all AI-assisted work, including the literature summaries, for accuracy, and I take responsibility for the final content of this work, including text, claims, or artifacts produced with the aid of generative AI.
