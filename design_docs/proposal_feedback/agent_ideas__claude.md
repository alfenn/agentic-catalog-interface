---
source: claude-5.5-opus-medium
reply-to: [attachments/feedback.md]
---

# Addressing the proposal feedback

The feedback makes three points:

1. The motivation reads as "answer one of three specific questions." The real argument is that deciding which data to trust is hard and spans many disconnected workflows. That did not land on first read.
2. The evaluation sweep is too ambitious. Prune models and harnesses, but keep the fair with/without-tools comparison and the generic-harness baselines.
3. Name the 1-2 really amazing outcomes, then design the eval around them.

These are connected. If we pick the headline outcomes first, they tell us how to reframe the motivation and which parts of the sweep to cut. So this doc starts with point 3.

---

## 1. The 1-2 amazing things

### Candidates

| Candidate claim | Why it is exciting | Weakness |
|---|---|---|
| **A. Cheap model + better tools ≥ frontier model with generic tools**, at a fraction of the cost | Vivid, easy to put in one plot, and directly answers "is the gap an interface gap?" | Needs a strong, fair baseline or it reads as a strawman |
| **B. The agent avoids the traps a messy lakehouse sets**, such as deprecated duplicates, stale comments, and filters hidden in SQL. It cites evidence, or it says no trustworthy answer exists | Matches the "data hygiene / trust" framing the grader wants. It is also the failure that actually hurts practitioners: a confident wrong number | Needs a carefully built trap set, which we control because we build the lake |
| C. Variance decomposition: tools explain more variance than harness or model | The cleanest research statement | Abstract. It needs the full grid, which is exactly what the feedback says to cut |
| D. Evidence IDs make answers auditable | Useful | More a feature than a finding. It works better as the mechanism behind B |

### Recommendation: A as the headline, B as the second result

- **Amazing thing #1 (A):** *With the catalog interface, a small model matches or beats a frontier model using generic tools, at a fraction of the cost.* This is the "interface gap" thesis in one sentence. The figure is a cost-vs-accuracy Pareto plot where the "with tools" frontier sits up and to the left of the "generic" frontier.
- **Amazing thing #2 (B):** *Generic agents fall for the lakehouse's traps, and the interface agent does not.* It picks the canonical table, finds the refund filter in the SQL instead of trusting the comment, and abstains when no trustworthy answer exists. This is the result that makes the motivation concrete.

C becomes a supporting analysis inside A rather than its own goal. D becomes the mechanism we measure inside B, through evidence validity. Dropping C as a headline is what makes the sweep easy to prune.

---

## 2. Reframing the motivation

### The core shift

Current framing: *"Practitioners answer three kinds of questions: selection, derivation, and joins."*

Proposed framing: *"Before using a table, a practitioner has to make a trust decision. Is this the right table, is it built the way I think, and does it join the way I think? Answering requires piecing together evidence from the catalog, the pipeline code, lineage, the data itself, and colleagues. Today this is a manual, multi-tool workflow, and getting it wrong produces silently wrong numbers."*

Selection, derivation, and joins then become **facets of one trust decision**, not three separate tasks. That is the "data hygiene involves many disparate workflows" point the grader inferred.

### Concrete edits

- **Open with a vignette, not a taxonomy.** Example: an analyst is asked for net revenue by region. They find four plausible tables. One is deprecated but still more popular. One has a comment saying "excludes refunds," but the SQL changed six months ago. One duplicates rows on the join key. To get it right they open the catalog, the lineage view, the dbt repo, and a SQL console, and they Slack a colleague. Each step uses a different tool, and none of them tells them which answer is correct.
- **Name the cost of being wrong, not only the time spent.** The Lyft figure of about 30% of time spent on discovery covers time. Add the stakes: wrong tables produce wrong dashboards and decisions, and nothing flags them. This is why *evidence* and *abstention* matter, and it sets up amazing thing #2.
- **Say explicitly why each existing tool covers only one slice.** Catalog search finds candidates but does not judge them. Lineage shows edges but not filters. NL-to-SQL works only on curated slices. The proposal already has this material in the "gaps" and "prior work" sections. Move a compressed version up so the reader sees the fragmentation before the three question types.
- **Introduce the three question types after the framing,** as how we *operationalize* trust decisions for evaluation, not as the motivation itself.
- **Connect motivation to hypothesis in one line.** "Because the difficulty comes from evidence scattered across sources, we expect the fix to be an interface that gathers that evidence, not a bigger model or a fancier harness." Then the research question follows from the motivation instead of feeling bolted on.

### Draft opening paragraph for the midway report

> Before a data practitioner can use a table in a lakehouse, they must decide whether to trust it: whether it is the canonical source, whether it is computed the way its name and comments suggest, and whether it joins cleanly with the other tables they need. The evidence for that decision is scattered across the catalog's metadata, the pipeline code and lineage that produced the table, and the data itself. Practitioners stitch it together by hand, across several tools and colleagues. When they get it wrong, nothing fails loudly. A deprecated table or a stale comment simply produces a wrong number. Coding agents connected to catalog tools can automate the lookups, but today they inherit the same fragmentation. They answer from table names and comments rather than from the code and data, and they rarely say when no trustworthy answer exists. We ask whether this gap is an interface gap: whether exposing that scattered evidence through better tools lets inexpensive agents make trust decisions as well as frontier agents.

Small fix while editing: the title "An Agent Tool Interfaces for…" has a grammar slip. Use "Agent Tool Interfaces for…" or "An Agent Tool Interface for…".

---

## 3. An eval that captures the two amazing things

### Build the question set around injected defects

We build the lakehouse, so we control the ground truth for every mess we inject. Make that the backbone of the eval:

1. **Write a defect manifest first.** List each injected defect: deprecated duplicate table, stale comment, undocumented column, filter that lives only in SQL, non-unique "key", stale or partial date range, and so on.
2. **Derive questions from defects.** For each defect, write questions where the obvious answer, the one you get from names, comments, or popularity, is wrong. Record that **lure answer** alongside the correct answer.
3. **Include a control set** of clean questions with no trap, so we can show the tools do not just help on adversarial cases.
4. **Include unanswerable questions,** where the correct output is "no trustworthy answer" because, for example, the data needed does not exist or two candidates conflict.

### Score each run four ways

- **Correct**, with valid evidence.
- **Lured**, meaning the run gave the trap answer. This is the most telling metric for amazing thing #2.
- **Abstained**, which is correct on unanswerable questions and a miss on answerable ones.
- **Other wrong.**

Also measure **evidence validity**: do the cited evidence IDs, or for the baseline the cited files and queries, actually support the claim? This can be checked mostly automatically because evidence IDs resolve to tool results.

### Headline figures

- **Figure 1 (amazing thing #1):** cost vs. accuracy per model, with and without tools, on one harness. Show both Pareto frontiers. The key callout is the small model with tools against the frontier model without.
- **Figure 2 (amazing thing #2):** lure rate and correct-abstention rate by defect type, with vs. without tools. This shows *which* kinds of mess the interface fixes.
- **Supporting:** a leave-one-tool-family-out ablation (no metadata tools, no pipeline tools, no data probes) on one model. It shows which part of the interface matters, which partly answers "which component." It is a cheaper way to get at component attribution than a full harness grid.

### Making "with vs. without" fair

The grader explicitly flagged fairness. The baseline must have the **same information access**, or we are measuring access instead of interface.

- **Same raw access.** The generic condition gets a shell, a SQL console, the stock catalog MCP or REST access, and **read access to the dbt project files and manifest**. A generic agent can in principle read the SQL. Our claim is that it does not do so reliably or cheaply.
- **Same budget and stopping rule** in both conditions: dollar cap, turn cap, and timeout.
- **Same task prompt and answer format.** Ask for evidence in both conditions. The baseline cites file paths and queries, ours cites evidence IDs. Only tool descriptions differ.
- **Equal prompt-tuning effort.** If we iterate on our tool descriptions, give the baseline prompt an equal number of iterations, or freeze both before the main runs.
- **Guard against question leakage.** Write the defect manifest and questions before finalizing the tools, and keep a held-out split we do not look at while developing tools. Otherwise the tools can quietly overfit to our own questions.

---

## 4. Pruning the sweep

### Why it is too big

As written the grid is 5 harnesses × about 9 models × 180 questions × 2 conditions × 3 repetitions. That comes to tens of thousands of agent runs. Many of the harness-model pairs are also not crossable. Claude Code and Codex CLI mostly run their own vendor's models, so harness and model are confounded there anyway.

### Proposed tiers

**Tier 1, core grid (supports amazing thing #1).** Fully crossed, 3 repetitions.
- **Harnesses:** 2 model-agnostic harnesses, mini-SWE-agent as the minimal one and OpenCode as the full-featured one. Both run every model, so harness is cleanly separated from model.
- **Models:** 4, as 2 × 2 of {small, frontier} × {closed, open-weight}. For example Haiku and Opus, plus a small and a large Qwen or DeepSeek.
- **Questions:** about 100-120, split across defect-derived, control, and unanswerable.

**Tier 2, native-harness spot check (supports generality).**
- Claude Code with one Claude model and Codex CLI with one OpenAI model, both conditions, 1 repetition, on a 40-60 question subset.
- The claim here is only "the effect direction holds in production harnesses," not a full comparison.

**Tier 3, ablation (supports component attribution).**
- One harness and one small model, leave-one-tool-family-out, on the full question set.

### What to drop or defer

- **DeepSeek Harness.** It is a developer preview from August 2026, so integration risk is high and the payoff is low. Add it only if time allows.
- **Agent Client Protocol (ACP) as a hard dependency.** Use it where it works and fall back to each harness's non-interactive CLI mode. Do not let one driver abstraction block the project.
- **Middle model sizes.** Small vs. frontier is the contrast the thesis needs. Middle sizes add points to the curve, not to the argument.
- **Verification as a separate category.** Fold verification-style checks into the trust questions. "Is the key unique" naturally becomes part of a join question.

### Sequence the spend

1. **Pilot** on about 30 questions with one harness, one small model, and one frontier model, 1 repetition, both conditions. Check that the effect exists and is large, measure per-run cost, and find broken questions.
2. **Size Tier 1** from the pilot. If the effect is large, 3 repetitions on about 100 questions is plenty. If it is small, add questions, not harnesses. Report confidence intervals with a paired bootstrap over questions.
3. Run Tiers 2 and 3 only after Tier 1 is clean.

This keeps the strong parts of the original plan, which are many combinations, fair with/without runs, and generic-harness baselines. It spends compute only where it supports the two headline claims.

---

## 5. How this maps onto the midway report

- **Research question (one paragraph).** Use the reframed opening above and state the two headline claims as the research questions:
  1. Does a better catalog interface let small models match frontier models at lower cost?
  2. Does it reduce trap-induced errors and enable correct abstention?
- **Environment & Data.** Cover the lakehouse, the defect manifest, and how questions are derived from defects, with lure answers, controls, and unanswerable questions. Give success criteria and metrics: correct, lured, abstained, evidence validity, and cost.
- **Methods.** Cover the interface's three tool families, the fair-baseline definition, and the tiered run plan.
- **Progress / risks.** Name the risks: harness integration, question leakage, and judge reliability for free-text derivation answers. A mitigation for the last one is to require structured answer fields, such as table name, filters, and join keys, wherever possible, so most grading is exact-match.
