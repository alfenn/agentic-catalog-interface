# Research Questions or Problem Specification

Maintainers of a dbt-backed lakehouse need catalog information that remains trustworthy as models evolve. Ownership, grain, filters, and lifecycle state can become incomplete or contradict the code, yet the evidence for a correction is distributed across metadata, SQL, lineage, tests, and data. We are building a catalog steward for these maintainers that addresses both existing hygiene debt and obligations introduced by a proposed change. Our research question is whether a specialized, evidence-gathering and verification workflow can produce more complete, grounded, and safe maintenance outcomes than static checks and a generic coding agent with ordinary repository access. We evaluate complete maintenance episodes, including clean changes that should pass, rather than counting warnings alone [1, 2].

# Environment & Data

The midpoint environment is a repository-local dbt Core project backed by DuckDB, with synthetic order, order-item, and customer seed data. Its base project includes staging and aggregate models, schema documentation and tests, and a JSON catalog. Catalog overrides provide controlled metadata changes. The environment is intentionally small enough to inspect and reset: it is a reproducible test fixture, not evidence of performance on a production warehouse. Each episode starts from a fresh copy of the base, applies a setup overlay for existing debt or a change overlay and deletions for a proposed contribution, and builds the project. This supplies the same initial state to each condition [2, 3].

The versioned hygiene contract bounds the task to five issue types: missing required metadata, SQL/metadata drift, grain or join drift, unsupported reliability claims, and lifecycle drift. It specifies required evidence, allowed and forbidden action classes, and intended verification for each. Scope limits include at most 20 assets, two lineage hops, five findings, and bounded data probes of at most 10,000 rows. The action surface is a repository patch or structured proposal; deleting assets, changing access policies, mutating a live catalog, inventing business semantics, and unbounded queries are forbidden [4]. These constraints make individual decisions reviewable and keep broad data cleaning and production integration outside the midpoint scope.

Our frozen pilot has ten hand-constructed, versioned episodes: four remediation cases, four flawed change-review cases, and two clean change controls [3, 5]. The defects cover a stale revenue filter description, incorrect customer-order grain, missing owner, a legacy model marked canonical, a changed revenue filter, a changed grain and uniqueness claim, a new undocumented model, and a rename without a lifecycle transition. The clean cases add a documented model and a documented revenue metric. For each episode the manifest records expected issue/asset pairs, required evidence, acceptable and unsafe actions, postconditions, and intended checks. For example, the filter-drift case allows a description proposal grounded in completed-only SQL but forbids changing SQL simply to match stale prose; the grain case asks for code and uniqueness evidence. The clean controls make spurious findings measurable. Because authors construct both defects and labels, these cases are interpretable but may reflect the designers' assumptions; independent auditing and broader cases remain necessary.

The configured comparison has three conditions: static required-field checks plus relevant dbt tests, a generic agent with repository and catalog access, and the specialized steward. The frozen model configuration uses `openai/gpt-6-luna`, temperature zero, a 4,096-token limit, and at most 12 turns for the model conditions [5]. The same episode fixture and structured finding schema support comparison. The static condition is deliberately limited to required metadata and dbt test results; it does not infer semantic repairs. The generic and specialized conditions are intended to use the same configured model, while their instructions and tools differ. A stronger checklist baseline and tool/workflow ablations are planned for later, so the initial comparison cannot isolate the contribution of every architectural component [1, 2].

The implemented scorer matches findings by issue type and asset against the manifest. It records precision and recall, clean-change pass, regression detection, action and evidence measures, verification failures, episode success, patch and escalation counts, cost, turns, and time. Episode success requires no false positives or false negatives, no action classified as unsafe by the scorer, no recorded verification failure, and a complete run. These measures have important limits: evidence validity checks whether cited IDs resolve, not whether evidence supports the claim; the action score checks permitted classes on matched findings, not the full episode-specific acceptable and unsafe action text. Likewise, a successful score is not a full audit of every specified postcondition. We will inspect traces and artifacts against episode expectations before interpreting numerical differences as safety or repair quality.

# Methods

Both modes use a shared inspect–plan–act–verify workflow. For the scoped assets, the steward gathers evidence from catalog metadata, dbt schema and manifest, model SQL and parsed SQL facts, lineage and bounded profiles where available; change review also supplies the diff. Evidence items carry IDs so findings can cite their sources. Collection errors are recorded in the evidence bundle, and the model may use read-only evidence tools to seek missing facts. The agent receives the issue contract and a structured plan schema, then returns prioritized findings with claims, confidence, impact, evidence, and proposed actions [4, 6]. The current collection follows the provided episode scope and uses one lineage hop; the contract's two-hop limit is an upper bound rather than a claim that every run explores two hops.

The plan validator checks the schema, supported issue types, action permissions, and evidence references before execution. The contract separates three action classes. A patch is reserved for evidence-backed, reversible technical metadata; a proposal leaves semantic or organizational decisions for review; a report records a condition when action is not justified. In the current implementation patches are confined to allowed fields in catalog overrides within the episode workspace. The steward emits a diff, checks the resulting catalog field and dbt parse, and rolls back the workspace edit if those checks fail. Proposals and reports are checked for action permission and resolvable evidence IDs, but they do not receive the same post-change verification as a patch. A ledger records findings and outcomes and can recognize an already verified finding [6]. Thus the implementation demonstrates a bounded local loop, while the richer per-issue verification in the contract remains an evaluation and development target rather than a guarantee that every listed check runs automatically.

The main investigation is whether the explicit contract, evidence bundle, and risk-aware workflow improve outcomes over the baselines. We will compare both detection and resulting actions on identical starting episodes, examine cited evidence and verification artifacts, and consider review burden and runtime alongside accuracy. The generic condition provides a useful comparison but does not yet have the full hygiene checklist. A subsequent checklist baseline and an evidence-tool ablation are needed to distinguish improvements from better instructions, better tools, and orchestration [1, 2]. No result from the static pilot establishes an advantage for the steward.

# Summary of Progress

The repository contains the local fixture, versioned contract and episode manifest, bounded evidence tools, structured agent protocol, steward workflow, baseline runners, and scoring code. The static condition has been run on all ten frozen pilot episodes, with individual results and dbt artifacts checked in [7]. Its outcome is 4/10 episode successes under the implemented scorer:

| Episode category | Successful episodes | Observed behavior |
| --- | ---: | --- |
| Existing debt | 1/4 | Detected the missing owner; missed filter drift, wrong grain, and lifecycle drift. |
| Flawed changes | 1/4 | Detected missing metadata on the new model. The grain and rename cases each had one matched finding but also one missed finding; the filter change was missed. |
| Clean changes | 2/2 | Both passed without a finding. |

The 4/10 figure is fixture-level episode success under the scorer, not a remediation rate. This small, constructed sample illustrates why semantic and lifecycle checks merit investigation, but it is not a population estimate. The static runner reports findings rather than making semantic fixes, and the scorer's episode-level result should be read with the limitations above. The paid generic and steward pilot results are **pending**: this checkout lacks an OpenRouter key. Consequently, there is no measured model comparison or demonstrated agent repair from this pilot to report yet.

Next we need to run the two model conditions on the frozen suite when credentials are available, audit their evidence and actions against each manifest, and inspect failures before expanding the data. The planned final study grows toward 30–50 audited episodes and adds a detailed-checklist baseline and tool/workflow ablations [2]. We also need to strengthen postcondition verification and review ambiguous labels, particularly when a change could have multiple legitimate business interpretations. The central risks are unsupported but plausible descriptions, weak ground truth, unfair baseline prompting, and excessive reviewer warnings. Bounded evidence, reviewable patches, proposal/report actions for uncertain decisions, explicit unsafe examples, and clean controls mitigate these risks but do not prove safety. Production catalogs, broader data distributions, and long-running maintenance remain future work.

# References

[1] Codex. Undated. “Revised recommendation: pivot to an agentic data-hygiene steward.” Project design feedback, `designs/proposal_feedback/agent_ideas_2__codex.md`.

[2] Catalog Steward project. Undated. “Midpoint research and product contract.” `design/research_contract.md`.

[3] Catalog Steward project. Undated. “Maintenance episode manifest,” version 0.1.0. `data/episodes/manifest.yaml`.

[4] Catalog Steward project. Undated. “Catalog steward midpoint hygiene contract,” version 0.1.0. `design/hygiene_contract.yaml`.

[5] Catalog Steward project. Undated. “Midpoint experiment configuration,” version 1.0.0. `experiments/configs/midpoint_v1.yaml`.

[6] Catalog Steward project. Undated. Steward, evidence, agent, and evaluation implementation. `src/catalog_steward/`.

[7] Catalog Steward project. Undated. “Midpoint static pilot results.” `experiments/results/midpoint_v1_static/`.

# AI-Use Disclosure Statement

OpenAI Codex agents assisted with implementation planning, drafting, and artifact synthesis. The project authors are responsible for verifying the claims and interpretations and for the accuracy of the final submission.
