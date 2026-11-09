---


source: "codex-sol-6.1-high"
prompt: "look at the human feedback in the context and figure out how to implement it while maintaining the constraints of the midway report constraints/requirements"
context: ["human_feedback.md", "agent_response__codex.md", "human_response.md"]
datetime: 2026-11-08
---


# Response to the follow-up

The Codex comparison is the right next experiment. Your response resolves the
choice I left open: run Codex as the generic coding-agent baseline, collect its
results, and use that comparison to assess the steward. My earlier suggestion to
use the in-house generic loop for the immediate report no longer reflects the
requested direction. Its existing pilot remains historical evidence; it cannot
be relabeled as a Codex result.

The report also needs to explain the system itself before asking readers to
interpret the comparison. The contribution is the combination of a
domain-specific evidence interface and an inspect–plan–act–verify workflow for
catalog hygiene. The current prototype collects catalog metadata, dbt code and
manifest facts, lineage, and bounded data profiles; asks a model to produce a
structured plan; checks its evidence and action permissions; and records
reviewable patches or proposals and their verification. Both existing-debt
remediation and proposed-change review use this workflow. The implementation is
currently a dbt/DuckDB test bed, while the maintenance problem applies more
broadly to lakehouses.

The architecture diagram should show those two entry points feeding the shared
workflow, the evidence sources and tools, the action policy, and the resulting
patch or review request with its ledger and verification. Its caption and
surrounding text should distinguish implemented behavior from planned work:
current patch verification checks the written value and dbt parsing, but does
not independently establish semantic correctness.

## Experiment and reporting changes

1. Define and freeze a Codex baseline: record the CLI and model versions,
   instructions, tool access, execution limits, output schema, and scoring
   procedure. Give Codex the same episode fixtures and underlying catalog,
   code, diff, and data access as the steward. Record meaningful differences
   in model, permissions, and tooling rather than calling the conditions
   identical when they are not.
2. Adapt the runner to capture Codex's actual actions, final findings, evidence,
   patches, errors, and verification in per-episode artifacts. Reset independent
   fixtures for each condition, avoid exposing labels, and preserve the existing
   pilot rather than overwriting it.
3. Run a small paired check first to validate the adapter and scoring, then
   collect the frozen comparison on the selected episodes. Audit traces and
   report failures and incomplete runs as such. Do not assume the steward wins:
   the experiment tests that hypothesis, and a small pilot cannot establish a
   general state-of-the-art claim.
4. Revise Methods to explain the implemented architecture and diagram, then
   explain the evaluation once from fixture through scoring and trace review.
   Revise Results around one remediation and one change-review example, citing
   actual Codex and steward traces and explaining how their behavior maps to
   scores. Show aggregate results with clearly defined metrics and limitations.
5. Retain the original feedback: frame the problem for lakehouses generally,
   remove cost data from the report, replace the prohibited jargon throughout
   the project, and ground the discussion of failures and changes in saved run
   evidence. Regenerate and visually check the report within its page limit.

## Status

This file records the revised direction and the work needed. No Codex baseline
data, architecture diagram, or report revision is claimed as completed by this
response. The next implementation step is to inspect the existing runner and
Codex execution environment, then build and validate the paired experiment.

## Implementation update — 2026-11-08

The plan above has been carried out; the earlier status is retained as the state of this response when it was written.

**What was built.** A frozen Codex baseline (`experiments/configs/codex_baseline_v1.yaml`) with two conditions: `codex-matched` (Codex CLI 0.167.0, `gpt-6-luna` at low effort, the steward's own model and effort) and `codex-frontier` (`gpt-6.1-sol` at medium effort). The runner (`catalog_steward.codex_baseline`) builds each episode in a temporary directory outside the repository with an opaque name, removes every file that names the episode, and runs `codex exec` with user configuration, rules, hooks, apps, plugins, memories and web search disabled, a non-login shell and a separate tool environment. Codex receives the steward's task specification, including the hygiene contract, and the same project, warehouse and diff, and returns findings through a JSON output schema (`design/codex_plan.schema.json`). After each run the harness diffs the workspace, re-runs the steward's patch verification, fails edits outside `catalog/overrides.json` or undeclared override changes, and scans the event stream for label access or reads outside the workspace. The converted plan is scored by the unchanged `midpoint-score-v1` scorer. A two-episode paired check validated the adapter; the frozen ten-episode run of both conditions followed (`experiments/results/codex_baseline_v1/`), and all 20 Codex traces were audited against the steward pilot (`analysis.md` there). The README documents the reproduction steps. The existing steward pilot was not modified.

The report now has an architecture figure that separates the implemented workflow from the one planned element (the contract's per-issue verification checks) and states that patch verification checks only the written value and `dbt parse`. Methods and Environment & Data are shortened to a high-level explanation, with the procedure, condition differences and system details moved to appendices. The pivots are rewritten as what the agent did, whether it was right, and what changed, each tied to saved records. Results are rewritten around a per-episode three-condition table and two walkthroughs (`rem_legacy_model_lifecycle` and `change_daily_revenue_filter`). Everything before the appendix, references included, fits the four-total-page budget.

**Outcome.** The steward did not win on episode success: 5/10, against 6/10 for codex-matched and 7/10 for codex-frontier. It had the highest recall (micro precision/recall 0.60/0.90, against 0.58/0.70 and 0.73/0.80) and the most conservative change-review behavior: it only proposed, while Codex patched the catalog in 3 (matched) and 4 (frontier) of the six change reviews. The scorer does not credit that difference. No run used a forbidden action class, failed verification or edited another file, and no isolation flag fired.

**Limitations.** One sample per episode and condition on ten author-built fixtures, so a one- or two-episode gap supports no ranking; in the paired check the same matched run went both ways across samples. AI agents built the episodes and labels, and both clean controls contain real unlabelled gaps. The scorer checks exact labels, resolvable evidence and allowed action classes, not whether evidence supports a claim or whether an action suits the episode. The conditions differ in budget, plan enforcement and evidence form, as the report's appendix lists. One Codex query failed because the tool environment lacks numpy.

**Follow-ups, most important first.**

1. *Pre-registered scoring rule for patching versus proposing in change review* (high): the main behavioral difference between the conditions is currently unscored, and it must be fixed before any new run so the rule cannot be fitted to results.
2. *Label fixes in a new frozen episode version* (high): clean controls without real gaps (document the seeds or drop `raw_customers` from scope), a grain-versus-SQL-drift precedence rule checked independently of the model's label, and lifecycle history (or no history requirement) in remediation episodes. These move scores as much as the workflow does.
3. *Independent human review of the labels* (high): the ground truth reflects the design choices of the agents that built the system under test.
4. *Repeated samples per condition* (high for any ranking claim): needed before a 5/6/7 split can be read as a difference.
5. *Claim-to-evidence support checks* (medium): evidence validity only checks that citations resolve or ran, which passed an invented-evidence run in the pilot.
6. *numpy in a new tool-environment version* (low): affected one bounded query, which Codex reported as failed.
7. *Video URL and human-verification statement* (required for submission): both remain the author's to complete.
