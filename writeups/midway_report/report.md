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

Lakehouse maintainers need trustworthy catalog metadata (ownership, grain, filters, lifecycle state). This metadata drifts from the code: annotations "can become outdated or incorrect" as data models evolve [@lakafosis2025meta]. The evidence to correct it is scattered across catalog metadata, SQL, lineage, tests and data. I am building a *catalog steward*, prototyped on dbt and DuckDB, with two triggers over one workflow: *remediation* of existing hygiene debt and *change review* of a proposed contribution. Our question: **does a specialized evidence-gathering, risk-aware action, and verification workflow produce more complete, grounded, and safe maintenance outcomes than a general-purpose coding agent with access to the same repository and warehouse?**

# Methodology {#sec:method}

## Environment & Data {#sec:env}

**Environment and data.** The prototype environment is a small lakehouse fixture: a repository-local dbt Core project [@dbtcore] on DuckDB [@raasveldt2019duckdb] with three synthetic seed tables, a staging model, two aggregates, schema documentation, tests, and a JSON catalog snapshot. A versioned hygiene contract (`design/hygiene_contract.yaml`) binds the task to five issue types (missing required metadata, SQL/metadata drift, grain or join drift, unsupported reliability claims, lifecycle drift) and three action classes (patch, propose, report). The evaluation suite (`data/episodes/manifest.yaml`) has ten hand-built examples: four *remediation* cases, four *flawed changes*, and two *clean controls*. Each example comes with an answer key: the problems a careful reviewer should report, each named by its issue type and the table it affects (e.g., SQL/metadata drift on `daily_revenue`), plus the acceptable and unsafe responses.

**Evaluation.** Each condition runs once on an identical, freshly built copy of each example. Codex's answer is converted to the steward's plan form, and the harness then diffs its workspace and applies the steward's patch verification. A deterministic scorer ([`evaluation.py`](https://github.com/alfenn/agentic-catalog-interface/blob/main/src/catalog_steward/evaluation.py)) compares each plan with the answer key. A reported problem counts as correct only if both its issue type and its table match an entry in the answer key; otherwise it is an *extra* (a false positive), and the number of extras measures how much noise a harness puts in front of a reviewer. An example *succeeds* only if the run completes with no extra, no missed problem and no failed verification, and each action's class (patch, propose or report) is one the contract allows for that issue type. The scorer does not read the example's listed acceptable and unsafe actions, so an allowed patch passes even where a reviewer should decide first. An AI-assisted audit of every trace checks what the scorer cannot: whether claims are true, actions suit the example, and extras are real gaps the labels miss.

## Methods {#sec:methods}

**What I built.** The catalog steward (Figure\ \ref{fig:arch}) pairs a domain-specific evidence interface for catalog hygiene with an inspect--plan--act--verify workflow under a risk-aware action policy, shared by both triggers (change review adds the proposed diff). This pairing is the contribution. Rather than leaving a model to search a repository and edit files, the steward first gathers the facts hygiene decisions rest on into an evidence bundle (catalog metadata, dbt schema and manifest, model SQL with facts parsed by SQLGlot [@mao_sqlglot], lineage, bounded data profiles), each item carrying a stable, content-hashed ID. Following the view that purpose-built agent--computer interfaces matter [@yang2024sweagent], the model reads this bundle, may call read-only tools, and returns a structured plan of at most five findings, each with a claim, the evidence IDs it rests on and an action. A deterministic validator rejects a plan that breaks the schema or the contract's scope, evidence or action rules. It then routes each finding to a patch, a review proposal or a report, and logs every outcome in a ledger. Only reversible technical metadata may be patched, and only in an example-local override file.

**Limits.** Verification is weak. A patch is kept only if the written field equals the model's declared value and `dbt parse` succeeds. Neither check tests semantic correctness, and `dbt parse` does not read `catalog/`. The contract's per-issue checks (dashed in the figure) are planned.

![Catalog steward architecture as implemented in `src/catalog_steward/`. Both triggers feed one workflow. A deterministic validator accepts the plan or returns it once for repair, and each accepted finding is then patched, proposed or reported, and logged.](figures/architecture.pdf){#fig:arch width=100%}

**Conditions.** The *steward* runs on the agentic harness I built (evidence bundle, read-only tools, validator and executor) with `gpt-6-luna` at low reasoning effort for at most 12 turns. Two Codex comparisons run OpenAI Codex CLI 0.167.0 [@openai_codex]: *Codex, matched* on the same model and effort, so only the harness differs, and *Codex, frontier* on `gpt-6.1-sol` at medium effort. Both get the steward's task specification, including the hygiene contract (Section\ \ref{sec:env}), the same dbt project and warehouse, and, for change review, the proposed diff. Instead of the steward's harness, they get general shell and file tools in a sandbox writable only inside the workspace, with no network and no turn limit within a 30-minute timeout, and answer in a JSON output schema.

## What Did Not Work, and Pivots {#sec:pivots}

**From question answering to data hygiene.** My proposal planned a general-purpose data agent for question answering over a data lake, but its task categories and examples were too myopic for the problem I want to solve: keeping lakehouse metadata trustworthy as the lakehouse changes. Reframing the project around the data-hygiene process itself, through its two workflows (remediating existing debt and reviewing proposed changes), tackles that problem directly.

**From a bespoke baseline to Codex.** My first comparison agent was a simple custom agent with four raw tools (list files, read a file, read the diff, run a bounded SQL query) on the steward's model. It was easy to inspect and differed from the steward only in its tools, but it is not representative of the alternative someone would actually use to fix these hygiene issues. I replaced it with Codex, a frontier agent harness, and reran the comparison on all ten examples, trading the simpler agent's comparability and ease of inspection for realism.

# Results (Summary of Progress) {#sec:results}

## Reported Results {#sec:reported}

In Table\ \ref{tbl:results}, the steward succeeds on 5/10 examples (precision 0.60, recall 0.90), matched-Codex on 6/10 (0.58, 0.70) and frontier-Codex on 7/10 (0.73, 0.80). The steward reports the most extras: 6, against 5 for matched-Codex and 3 for frontier-Codex.

<!-- BEGIN GENERATED: results_table (make_figures.py; do not edit by hand) -->
```{=latex}
\begin{table}[t]
\caption{Per-example outcomes, one run each. TP: a reported problem matching an answer-key entry; FP: an \emph{extra}, a reported problem matching none; FN: an answer-key entry no reported problem matches. Precision and recall are micro-averaged because per-example (macro) recall divides by the number of answer-key entries, which is zero for the \emph{clean control} examples. The last row counts forbidden actions, failed verifications and edits outside the override file (n/a for the steward).}
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

I draw on two runs indexed in [`experiments/README.md`](https://github.com/alfenn/agentic-catalog-interface/blob/main/experiments/README.md), each with one folder per example: the steward's (`midpoint_v1_2_pilot`) and the Codex conditions' (`codex_baseline_v1`).

**Steward vs. matched-Codex.** The steward succeeds on one fewer example (5/10 vs. 6/10), with higher recall (0.90 vs. 0.70) and similar precision (0.60 vs. 0.58). With the same model, the steward harness finds more: its bundle covers every in-scope table, so only it caught the failing uniqueness claim ([*Grain changed, metadata not*](https://github.com/alfenn/agentic-catalog-interface/tree/main/experiments/results/codex_baseline_v1/change_customer_orders_grain)) and the legacy copy ([*Legacy copy still active*](https://github.com/alfenn/agentic-catalog-interface/tree/main/experiments/results/codex_baseline_v1/rem_legacy_model_lifecycle)). It also reports more extras (6 vs. 5), but the example behind the success gap is an eval error it caught: in [*Documented revenue metric*](https://github.com/alfenn/agentic-catalog-interface/tree/main/experiments/results/codex_baseline_v1/clean_daily_revenue_metric), its bundle showed the dbt model description omits a new metric, which the answer key misses. The error the steward and matched-Codex shared ([*Wrong customer-order grain*](https://github.com/alfenn/agentic-catalog-interface/tree/main/experiments/results/codex_baseline_v1/rem_customer_orders_wrong_grain)) is in labelling, not understanding: both found the wrong grain and its fix, but filed it as SQL/metadata drift which allows a patch, instead of as a grain problem which allows only a proposal.

**Steward vs. frontier-Codex.** Frontier-Codex succeeds on 7/10 vs. 5/10, with higher precision (0.73 vs. 0.60) but lower recall (0.80 vs. 0.90). It succeeds on two examples the steward fails. The first, [*Wrong customer-order grain*](https://github.com/alfenn/agentic-catalog-interface/tree/main/experiments/results/codex_baseline_v1/rem_customer_orders_wrong_grain), is the stronger model's: matched-Codex, with the same harness but the steward's model, made the same labelling mistake, while frontier-Codex labelled it correctly ([frontier](https://github.com/alfenn/agentic-catalog-interface/blob/main/experiments/results/codex_baseline_v1/rem_customer_orders_wrong_grain/codex-frontier.json) vs. [steward](https://github.com/alfenn/agentic-catalog-interface/blob/main/experiments/results/midpoint_v1_2_pilot/rem_customer_orders_wrong_grain/steward.json)). The second is the eval error above. Its three failures come from three extras, which both other runs also made, and two misses, notably both problems only the steward caught: [the uniqueness claim](https://github.com/alfenn/agentic-catalog-interface/blob/main/experiments/results/codex_baseline_v1/change_customer_orders_grain/codex-frontier.json) and [the legacy copy](https://github.com/alfenn/agentic-catalog-interface/blob/main/experiments/results/codex_baseline_v1/rem_legacy_model_lifecycle/codex-frontier.json) (it noticed the legacy-copy problem but did not report it).

**Why Codex scored higher.** Codex scored higher partly because the eval understates the steward. The scorer passed an unreviewed change by Codex: in [*Revenue filter changed*](https://github.com/alfenn/agentic-catalog-interface/tree/main/experiments/results/codex_baseline_v1/change_daily_revenue_filter), both Codex runs edited the catalog to match a change counting refunded orders as revenue, before approval. The scorer sees only a patch, which this issue type allows when a description is merely stale. A revised scorer should fail patches that skip a required review. Crediting the [real problems the answer key misses](https://github.com/alfenn/agentic-catalog-interface/blob/main/experiments/results/codex_baseline_v1/analysis.md) and failing those two runs would tie the steward with frontier-Codex (7/10), ahead of matched-Codex (6/10).

## Limitations and Next Steps {#sec:limits}

**Few, single runs.** Each result is a single run, and runs vary: matched-Codex passed one example in two of three earlier tries, so a gap of one or two successes may be noise. *Things I want to try next:* expand the evaluation set from 10 to 50 examples and run each several times without caching.

**Incomplete answer key.** The answer key is not comprehensive enough: it counts some extras as failures when they are in fact real problems, which deflates the steward's performance. *Things I want to try next:* an eval loop that reviews each extra and fixes the answer key when it is wrong.

**Steward vs. a stronger model.** Frontier-Codex beat the steward harness, and its traces suggest its selective reading helped: it chose what to read and reported half as many extras as the steward, which shows its model every in-scope table. *Things I want to try next:* build that selectivity into the harness's tools for the weaker model, so it sees only the evidence each candidate issue needs.

**Narrow comparison.** The steward has not run on the frontier model, so its harness is untested with a stronger model, and Codex is the only baseline. *Things I want to try next:* run the steward with a frontier model, and use the Pi harness alongside Codex as a further point of reference. I also want to compare against non-agentic workflows such as dbt-project-evaluator and Great Expectations.

# Assets {#sec:assets}

**Repository:** `\url{https://github.com/alfenn/agentic-catalog-interface}`{=latex}: `README.md` (setup, reproduction), `src/catalog_steward/`, `data/` (fixture, examples), `experiments/` (indexed runs).

# Timeline (Summary of Progress: Next Steps and Risks) {#sec:timeline}

Each milestone addresses a next step from Section\ \ref{sec:limits}, starting with the evaluation fixes. Demo Day (December 9) and the final report (December 11) are fixed; other dates are my targets.

- *By November 20:* I will build the eval loop that reviews each extra and corrects the answer key when it is real, and revise the scorer so that patches skipping a required review fail.
- *By November 27:* I will use 50 examples and run each setup several times without caching.
- *By December 4:* I will run the steward with a frontier model, add frontier-Codex's selective reading to its tools, and rerun all conditions on the 50 examples.

If time remains, I will add the Pi harness and a non-agentic baseline. The main risk is that reviewing 50 examples takes longer than planned; I would then report repeated runs on fewer examples.

```{=latex}
\bibliography{references}
\label{referencesend}
\bibliographystyle{iclr2025_conference}
```

# AI-Use Disclosure Statement {#sec:ai .unnumbered}

In this work, I used generative AI tools to refine the hypothesis, to brainstorm task formulations, and to give feedback on the research methodology. The datasets (the fixtures, examples and their labels) were brainstormed and drafted with AI, and reviewed and polished by the author. Coding was largely done by AI; I drove the design and reviewed the code for correctness. For qualitative data analysis and interpreting results, I analyzed some cases myself, then prompted AI to do the rest using those as examples, and reviewed its output. Additionally, I used generative AI tools for brainstorming, identifying gaps in prior work, searching for and summarizing relevant literature, and providing editing suggestions for readability. I have reviewed all AI-assisted work, including the literature summaries, for accuracy, and I take responsibility for the final content of this work, including text, claims, or artifacts produced with the aid of generative AI.
