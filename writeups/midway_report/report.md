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

**Evaluation.** Each condition runs once on an identical, freshly built copy of each example. Codex's answer is converted to the steward's plan form, and the harness then diffs its workspace and applies the steward's patch verification. A reported problem counts as correct only if both its issue type and its table match an entry in the answer key. Every trace is also audited, with AI assistance, for what the scorer cannot check: whether each claim is true of the fixture, whether each action suits the example, and whether each extra finding is a real gap the labels miss.

## Methods {#sec:methods}

**What I built.** The catalog steward (Figure\ \ref{fig:arch}) pairs a domain-specific evidence interface for catalog hygiene with an inspect--plan--act--verify workflow under a risk-aware action policy, and both triggers share it: remediation starts from existing hygiene debt, and change review adds the proposed diff. This pairing is the contribution. Rather than leaving a model to search a repository and edit files, the steward first gathers the facts that hygiene decisions rest on into an evidence bundle (catalog metadata, dbt schema and manifest, model SQL with facts parsed by SQLGlot [@mao_sqlglot], lineage, bounded data profiles), each item carrying a stable, content-hashed ID. Following the view that purpose-built agent--computer interfaces matter [@yang2024sweagent], the model reads this bundle, may call read-only tools, and returns a structured plan of at most five findings, each with a claim, the evidence IDs it rests on and an action. A deterministic validator rejects a plan that breaks the schema or the contract's scope, evidence or action rules. It then routes each finding to a catalog patch, a review proposal or a report, and appends every outcome to a ledger. Only reversible technical metadata may be patched, and only in an example-local override file.

**Limits.** Verification is weak. A patch is kept only if the written field equals the value the model declared and `dbt parse` still succeeds. Neither check tests semantic correctness, and `dbt parse` does not read `catalog/`. The contract's per-issue checks (dashed in the figure) are not implemented yet.

![Catalog steward architecture as implemented in `src/catalog_steward/`. Both triggers feed one workflow. The model reads a bundle of content-hashed evidence, may call read-only tools, and returns a structured plan. A deterministic validator accepts the plan or returns it once for repair, and each accepted finding is then patched, proposed or reported, and logged. The only planned element is dashed: the contract's per-issue verification checks.](figures/architecture.pdf){#fig:arch width=100%}

**Conditions.** The *steward* is the frozen pilot (config v1.2.0): `gpt-6-luna` at low reasoning effort, at most 12 turns, with the evidence bundle, read-only tools, validator and executor; two of its ten records replay an earlier identical run. *Codex, matched* is OpenAI Codex CLI 0.167.0 [@openai_codex] on the same model and effort, so the harness is what differs; *Codex, frontier* uses `gpt-6.1-sol` at medium effort. Both get the steward's task specification, including the hygiene contract, and the same project, warehouse and diff, but general shell and file tools instead of the bundle, validator and executor: a sandbox writable only inside the workspace, no network, no turn limit within a 30-minute timeout, and a JSON output schema.

## What Did Not Work, and Pivots {#sec:pivots}

**Reply format.** In a preliminary run the model copied a wrapper key from the format example, so its replies were rejected; I fixed the example and added one shared repair turn (commit `d2a547b`).

**Raw-tool exploration.** On `change_daily_revenue_filter` our raw-tool agent batched tool calls; once rejected, it reported nothing and missed the regression. Another run cited unreceived output yet passed the ID-only evidence check (pilot `analysis.md`). Codex replaced it.

**Label choice.** On `rem_customer_orders_wrong_grain` the steward labelled a grain error SQL/metadata drift, a patchable type, and patched a correct value, but the example required a proposal with uniqueness evidence, so it failed. Next, issue type is checked apart from the label.

**Unmatched baseline.** A first Codex run matched the steward on two cases, but a different model, no contract rules in the prompt and hand-mapped labels confounded harness with model and wording (`codex_midway_two_case/README.md`). The new baseline removes all three.

# Results (Summary of Progress) {#sec:results}

**What I compared.** All of Figure\ \ref{fig:arch} and the Codex adapter are implemented. Under the unchanged scorer the steward does not win (Table\ \ref{tbl:results}): it succeeds on 5 examples, against 6 for matched and 7 for frontier Codex, with the highest recall (0.90, against 0.70 and 0.80) and the most extra findings (6, against 5 and 3). No run used a forbidden action, failed verification or edited another file, and no isolation flag fired. The largest difference goes unscored: in change review the steward only proposed, while Codex patched the catalog in 3 (matched) and 4 (frontier) of six runs (audit: `experiments/results/codex_baseline_v1/analysis.md`; records by example there and in the pilot folder).

<!-- BEGIN GENERATED: results_table (make_figures.py; do not edit by hand) -->
```{=latex}
\begin{table}[t]
\caption{Per-example outcomes, one run each. TP: a finding whose (issue type, asset) pair matches an expected one exactly; FP: any other finding; FN: an expected finding left unmatched. An example \emph{succeeds} if the run completes with no FP or FN, no forbidden action class and no failed verification. Micro precision and recall are $\sum$TP$/\sum$(TP$+$FP) and $\sum$TP$/\sum$(TP$+$FN). The last row counts forbidden action classes, failed patch verifications, and runs that edited a file other than the override file, which the steward cannot do (n/a).}
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
Example successes & \multicolumn{2}{c}{5/10} & \multicolumn{2}{c}{6/10} & \multicolumn{2}{c}{7/10} \\
Micro precision / recall & \multicolumn{2}{c}{0.60 / 0.90} & \multicolumn{2}{c}{0.58 / 0.70} & \multicolumn{2}{c}{0.73 / 0.80} \\
Forbidden / failed / other edits & \multicolumn{2}{c}{0 / 0 / n/a} & \multicolumn{2}{c}{0 / 0 / 0} & \multicolumn{2}{c}{0 / 0 / 0} \\
\bottomrule
\end{tabular}
\end{table}
```
<!-- END GENERATED: results_table -->

**Remediation: legacy copy still active** (`rem_legacy_model_lifecycle`). A pass-through copy of `customer_orders` is still marked active and canonical. I expect lifecycle drift, proposed or reported, on catalog, manifest, lineage and repository-history evidence. From its bundle's catalog flags and lineage the steward rightly proposed a lifecycle review, but met the history requirement with the example's empty diff and added a grain report its own claim calls unestablished: 1/1/0, no success. Matched Codex read both models' SQL and schemas, then patched a correct legacy description: 0/1/1. Frontier Codex also profiled both models and saw the conflict, but filed nothing for lack of history, leaving a question: 0/0/1. Each should have reported the conflict alone; the contract shares the blame, since a remediation example has no history to cite.

**Change review: revenue filter changed** (`change_daily_revenue_filter`). The change keeps `status != 'cancelled'`, so refunded orders now count while the catalog still excludes them. I expect SQL/metadata drift, answered by asking whether refunds belong in revenue or proposing a metadata update. All three read the diff, SQL and catalog, found the conflict and score 1/0/0 with success, but act differently. The steward proposed review and asked which statuses count, but understated the change ("not explicitly excluded", despite `refunded` in its schema evidence; a cache replay). Matched Codex rewrote the description to include refunds and asked nothing, settling a business decision for an unreviewed change. Frontier Codex confirmed a refunded row in the data and patched likewise, then asked if refunds were intended, noting the stale `completed_*` column names. Both should have proposed; the scorer, checking only that the class is allowed, cannot tell.

**Limitations.** Each cell is one sample; in the paired check, matched Codex succeeded on the filter change in two of three samples (paired-check `README.md`). AI agents built the examples and labels, and both clean controls contain real unlabelled gaps; crediting those the audit identifies would give 7, 7 and 8 successes (not a re-scoring). The scorer checks exact labels, resolvable evidence and allowed action classes, not whether evidence supports a claim or an action suits the example. A one- or two-example gap supports no ranking, and nothing here shows that the steward's design improves scored outcomes.

# Assets {#sec:assets}

**Repository:** `\mbox{\url{https://github.com/alfenn/agentic-catalog-interface}}`{=latex} [@feng2026repo]: `README.md` (setup, reproduction), `src/catalog_steward/`, `data/` (fixture, examples), `experiments/results/`. Midpoint demo video: **[VIDEO URL TO BE ADDED]**.

# Timeline (Summary of Progress: Next Steps and Risks) {#sec:timeline}

**Milestones.** Course deadlines are Demo Day on December 9 and the final 8-page report on December 11; intermediate dates are our targets.

- *By November 13:* a new frozen example version: documented seeds, truly clean controls, an issue-type precedence rule checked independently of the model's label, and human review of the AI-built labels.
- *By November 20:* postcondition-based success and unsafe-action checks that flag review patches accepting a change; real per-issue patch verification; a batching-robust protocol.
- *By December 4:* repeated samples, tool-versus-workflow ablations against matched Codex, and growth toward 30--50 audited examples.
- *December 9 and 11:* live demo of both modes; final report.

**Obstacles and concerns.** No credential or pipeline blocker remains. The main concern is validity: label choices and protocol behaviour move results as much as the workflow, so fixes go into a new frozen version, not a rescoring.

**Risks and mitigations.** *Scope growth:* a frozen five-type contract with hard limits. *Ambiguous ground truth* (seen in both clean controls): documented seeds, a precedence rule, human label review. *Unsupported claims* (one invented-evidence run passed): claim--evidence support checks and manual audit. *Warning overload* (six steward extras): clean controls, a five-finding cap, flagging only gaps a change introduces. *Small pilot:* per-example reporting, more examples.

```{=latex}
\bibliography{references}
\label{referencesend}
\bibliographystyle{iclr2025_conference}
```

# AI-Use Disclosure Statement {#sec:ai .unnumbered}

In this work, I used generative AI tools to refine the hypothesis, to brainstorm task formulations, and to give feedback on the research methodology. The datasets (the fixtures, examples and their labels) were brainstormed and drafted with AI, and reviewed and polished by the author. Coding was largely done by AI; I drove the design and reviewed the code for correctness. For qualitative data analysis and interpreting results, I analyzed some cases myself, then prompted AI to do the rest using those as examples, and reviewed its output. Additionally, I used generative AI tools for brainstorming, identifying gaps in prior work, searching for and summarizing relevant literature, and providing editing suggestions for readability. I have reviewed all AI-assisted work, including the literature summaries, for accuracy, and I take responsibility for the final content of this work, including text, claims, or artifacts produced with the aid of generative AI.
