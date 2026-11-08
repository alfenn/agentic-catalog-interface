---
source: "codex-5.6-sol-xhigh"
context: [
  "agent_plan.md",
  "agent_todo.md"
]
---

# Agent Notes

## 2026-11-07 — Environment and harness direction

- Adopted Python 3.11+, `uv`, a `src/` package layout, pytest, and dbt Core +
  DuckDB. The repository was a design skeleton, so a local DuckDB stack is the
  smallest reproducible path to a real dbt-backed vertical slice and avoids
  spending midpoint time on a hosted catalog integration.
- Adapted the assignment harness's operational split: deterministic tests run
  by default, paid/external tests require an explicit live target, `.env` and
  `.lm_cache/` remain local, and evaluation cost/slice/concurrency controls are
  configured through environment variables.
- Names were changed from the assignment-specific `CS329Z_*` namespace to
  `CATALOG_STEWARD_*`. Only the OpenRouter credential keeps its provider name.
- The configuration doctor reports whether a credential exists but never its
  value. Relative runtime paths resolve from the repository root so commands
  behave consistently from different working directories.
- Deferred copying the assignment's model wrapper and agent loop until the next
  work package. They need to be reduced to the steward's structured episode
  protocol rather than imported as a large, course-specific framework.
- The first dependency sync timed out while network access was restricted. A
  retried, explicitly authorized sync succeeded and produced `uv.lock`; no
  dependency versions or tests had to be weakened to work around the failure.
- Validation at completion: `make doctor` succeeded without credentials and
  `make test` passed 6 deterministic tests. Live configuration intentionally
  remains invalid until a local `OPENROUTER_API_KEY` is supplied.

## 2026-11-07 — Minimal reusable agent harness

- Chose one strict JSON object per model turn (`tool` or `final`) instead of
  copying the assignment harness's mixed prose/tag parser. This gives the
  steward a smaller protocol surface, makes malformed output unambiguous, and
  lets deterministic tests cover every transition cheaply.
- Preserved the assignment's high-value reliability patterns: exact scripted
  model replies, recorded model inputs, schema validation before tool
  execution, tool exceptions returned to the loop, bounded malformed replies
  and turns, disk caching, an append-only cost ledger, an environment budget,
  explicit live tests, and evaluation slicing.
- Write-capable tools are denied by default. The midpoint steward is intended
  to produce reviewable patches/proposals, so a future caller must opt in
  explicitly even if a write tool is registered.
- Kept the model wrapper provider-specific only at its final transport layer.
  The agent loop depends on a tiny callable protocol, allowing scripted tests
  and future baseline models to share the same loop without network calls.
- The first harness test run found that shared test helpers were not importable
  because `tests/` lacked a package marker. Added `tests/__init__.py`; no
  production import path or pytest configuration was loosened.
- The next deterministic run exposed two loop issues: JSON-encoding an entire
  tool event obscured the tool's already-JSON content, and the consecutive
  error counter reset before invalid arguments were classified. Tool results
  now use a plain status header plus verbatim content, and the counter resets
  only after a validly executed/denied tool call. This keeps evidence readable
  to the next turn and correctly stops repeated bad calls.
- Completion validation: 34 deterministic tests pass, one paid live smoke test
  is correctly deselected by default, `make costs` reports an empty ledger, and
  the tree passes whitespace checks. No model call was made during this work.

## 2026-11-07 — Midpoint research contract

- Froze the prototype around dbt Core + DuckDB and five hygiene issue types.
  Five is enough to exercise metadata completeness, SQL/documentation drift,
  grain/joins, reliability claims, and lifecycle state while staying within the
  feedback's 4-6 type boundary.
- Made the contract YAML data validated by a JSON Schema. The implementation,
  episode manifest, and report can now refer to stable issue IDs and executable
  scope limits instead of duplicating prose definitions.
- Set hard episode bounds at 20 assets, two lineage hops, five findings, and
  10,000 probed rows. These are conservative prototype limits chosen to make
  runtime and evidence review predictable; they should be revisited only after
  pilot failures show they exclude required evidence.
- Kept `patch` reviewable rather than synonymous with direct application. This
  resolves the tension between demonstrating a closed loop and avoiding live
  catalog mutation: the system can generate and verify a repository patch in an
  isolated episode while a person remains the final authority.
- Defaulted the experiment model to `openai/gpt-6-luna` to match the lightweight
  model available in the assignment harness, but made it a recorded environment
  setting. Expanding models is explicitly deferred until the episode design and
  baseline fairness are stable.
- Completion validation: the versioned contract summarizes successfully and 37
  deterministic tests pass; the live smoke test remains deselected.

## 2026-11-07 — Reproducible fixture and episode suite

- Built one clean dbt–DuckDB project and represented episode-specific debt or
  proposed changes as overlays. Each reset creates `before/`, `project/`, and a
  generated unified diff. This avoids ten drifting project copies and makes the
  same pre-change state available to all evaluation conditions.
- Added four remediation episodes, four flawed change-review episodes, and two
  clean controls. The connected demo uses `daily_revenue`: the remediation case
  corrects stale all-orders prose, then a later change starts including refunds
  without updating completed-only metadata.
- Catalog perturbations use a small `catalog/overrides.json` sidecar rather than
  replacing the whole catalog snapshot. The evidence layer will merge it over
  the base snapshot, making the injected difference compact and auditable.
- The reset command will replace only a directory carrying the matching episode
  marker. This safety check was retained even for generated `.runs/` state so a
  mistyped destination cannot erase an unrelated directory.
- Fixture construction runs `dbt seed`, `dbt run`, and `dbt parse`, but not
  `dbt test`. Some episodes intentionally violate a uniqueness claim, so tests
  are evidence to collect during the episode rather than a prerequisite for
  constructing it.
- Added an all-episode temporary validation command. All ten cases seeded,
  materialized, and emitted `target/manifest.json`; 44 deterministic tests pass
  and one paid live test remains deselected. The full build is slower than unit
  tests, so ordinary tests build one representative clean episode while
  `make episodes-check` is the explicit exhaustive check.

## 2026-11-07 — Evidence interface

- Evidence IDs hash the kind, asset, provenance pointer, and normalized content.
  Identical facts therefore keep a stable ID across repeated retrievals, while
  a changed source or result creates a new ID. The in-memory registry deduplicates
  repeated retrieval without erasing provenance.
- SQL models are parsed after replacing dbt `ref`/`source` templates with
  technical relation identifiers. The parser exposes sources, filters, joins,
  aggregates, grouping, and grain candidates, but intentionally does not label
  business meaning or declare a key.
- Data profiling opens DuckDB read-only and profiles at most the contract's
  10,000-row bound and 20 requested columns. It reports when the bound is hit
  rather than claiming a full-table result.
- Catalog evidence merges compact episode overrides over the base snapshot;
  absent catalog or schema entries are returned as explicit `present: false`
  evidence instead of errors or inferred metadata.
- Initial parsing tests showed that SQLGlot rendered a joined relation together
  with its alias. Split these into `relation` and `alias` fields so lineage/tool
  consumers can compare stable relation names without losing alias context.
- Exposed nine schema-checked read-only tools covering catalog metadata, dbt
  schema/SQL/manifest facts, lineage, bounded profiles, diffs, and bounded
  project files. File reads cannot escape the episode project and lineage hops
  cannot exceed the contract.
- Completion validation: the evidence CLI returns addressable parsed facts for
  the demo model, 51 deterministic tests pass, and one live test remains
  deselected. Tests cover provenance stability, missing metadata, duplicate-key
  detection, lineage bounds, query bounds, path traversal, and tool schemas.

## 2026-11-07 — Shared inspect-plan-act-verify loop

- The model produces judgment in a strict, saved steward plan, but it cannot
  directly mutate the project. Plan validation enforces in-scope assets, known
  evidence IDs, every issue type's required evidence families, allowed action
  classes, and a five-finding maximum before execution begins.
- Both remediation and change review use the same `StewardRun`; the only trigger
  difference is whether a proposed diff is collected. This avoids two products
  whose policies or evidence handling could diverge.
- Kept the midpoint patch executor intentionally narrow: it can update only five
  catalog fields in an episode-local override. It emits a unified patch, applies
  it only inside the generated episode project, checks the declared
  postcondition, and reruns `dbt parse`. Semantic, test, SQL, lifecycle, or
  ownership decisions without direct support remain proposals or reports.
- Verification failure restores the original override file and remains a
  `verification_failed` outcome in the append-only ledger. A deterministic test
  deliberately mismatches the proposed and expected value to prove the run does
  not report success or leave the failed change applied.
- Finding keys hash the issue, asset, claim, and action. A matching successful
  ledger entry causes a repeat to return `already_verified`; changed evidence
  should instead lead the planner to omit or revise the finding.
- The plan artifact plus per-finding and run-summary ledger records retain the
  evidence IDs, action, verification checks, patch path, and unresolved
  questions. This is sufficient for later scoring without reconstructing a
  model transcript.
- Completion validation: 56 deterministic tests pass and one live test remains
  deselected. Tests cover both triggers, tool use during planning, patching,
  proposals, evidence enforcement, policy rejection, rollback, and idempotence.

## 2026-11-07 — Fair baselines and scoring

- The static baseline is deliberately limited to required catalog/schema fields
  and actual dbt test results. It does not reuse parsed SQL or the steward's
  evidence workflow, so it measures what deterministic checks catch on their
  own.
- The generic agent receives the same repository, built warehouse, model,
  limits, and output schema, but only four raw operations: list files, read a
  file, read the raw diff, and run bounded read-only SQL. It gets issue labels
  for normalization but not issue-specific evidence requirements, risk rules,
  prioritization, or verification orchestration.
- The frozen `midpoint_v1.yaml` records the ten episodes, three conditions,
  model, sampling limits, prompt versions, and scoring version. The runner
  refuses an unfrozen or version-mismatched configuration.
- Scoring is exact at the `(issue_type, asset)` level and records precision,
  recall, supported-action rate, unsafe-action rate, evidence validity,
  regression detection, clean-change pass, verification failures, action mix,
  cost, turns, and wall time. Episode success requires no missed/extra finding,
  no disallowed action, no verification failure, and a completed run.
- The first persistence design placed full generated dbt workspaces under
  `experiments/results/`. That would have mixed large, disposable state with
  report evidence. Workspaces now live under ignored `.runs/`; persistent
  results copy only the raw result, input diff, dbt logs/results, steward plan,
  ledger, verification log, and patches.
- A deterministic matched-run test executes static, generic, and steward
  conditions through the same runner on one clean episode. All three complete
  and pass scoring, demonstrating the one-command evaluation path without a
  paid model call.
- Completion validation: 62 deterministic tests pass in about 2.5 minutes and
  one paid live test remains deselected. The longer runtime is dominated by
  intentionally fresh dbt builds for fixture, evidence, static-baseline, and
  matched-condition integration coverage.

## 2026-11-07 — Pilot execution status

- `make doctor-live` confirms that this project's local `.env` has no
  `OPENROUTER_API_KEY`. The assignment harness has its own private environment,
  but its credential was not copied or read into this project because credential
  reuse was not explicitly authorized. No paid model call has been made.
- Proceeded with the independently valid static pilot rather than weakening the
  comparison or substituting an unrecorded model. All ten episodes ran from
  fresh fixtures and persisted under `experiments/results/midpoint_v1_static/`;
  disposable workspaces remained in ignored `.runs/` state.
- The initial aggregate is 4/10 successful episodes. Static checks catch the
  missing-owner and missing-new-model cases, partially catch grain/rename cases
  through tests or required fields, miss cross-source SQL/metadata and lifecycle
  inconsistencies, and pass both clean controls. A separate audit is reviewing
  the saved artifacts and scorer before these numbers are treated as report
  evidence.
- An independent artifact audit confirmed every episode's exact-match score:
  four true positives, zero false positives, and six false negatives (micro
  precision 1.00, micro recall 0.40). The 4/10 number is fixture-level episode
  success under the implemented scorer, not a remediation rate or population
  estimate.
- The audit found two evaluator defects that did not alter the recorded finding
  sets: a failed `dbt test` invocation could reuse an older `run_results.json`,
  and duplicate findings could inflate action rates. The runner now deletes old
  test results before invocation and rejects missing/unattributable failures;
  action scoring deduplicates matched pairs and divides unsafe actions by
  submitted findings.
- Regenerated the full static pilot with the corrected evaluator. It remains
  4/10, and all seven targeted evaluation tests pass. The paid conditions remain
  pending the credential decision.

## 2026-11-07 — Reproducibility and demo handoff

- Expanded the README around the actual Make targets and frozen evaluation
  config rather than describing aspirational commands. A delegated worker
  verified the configuration, contract, episode listing, a change fixture
  build, SQL evidence for both demo episodes, and whitespace checks.
- Documented a non-obvious behavior: `make evidence` resets the named episode
  without building it, so it replaces any prior built workspace for that ID.
  The demo sequence calls this out to prevent someone from expecting earlier
  dbt artifacts to remain.
- Added a connected `daily_revenue` runbook that can demonstrate fixture and
  evidence behavior without credentials, then conditionally show live steward
  outputs only if they have actually been run. The baseline section links the
  audit and labels 4/10 as fixture-level episode success, not remediation.
- README links and all referenced local paths were checked after integration.
  A fresh-environment reproduction and the actual recorded video remain open.

## 2026-11-07 — Midway report draft

- A delegated writer produced a 1,594-word Markdown draft with exactly the six
  required sections. Environment & Data, Methods, and Summary of Progress carry
  most of the detail; no separate prior-work section was added.
- The draft cites versioned repository artifacts and the audited static result,
  states the scorer's limitations, and explicitly labels generic/steward results
  as pending. It does not turn deterministic scripted tests into empirical agent
  results.
- Updated planning-document context links to the repository's current
  `designs/proposal_feedback/` location; the newer executable contracts live in
  singular `design/`.
- Remaining report work is substantive: replace the pending live-result text
  after a real pilot or keep the limitation, confirm reference formatting with
  the proposal, render to the submission format, and verify the final output is
  3–4 pages. The draft is not marked complete until those checks pass.

## 2026-11-07 — Handoff to a Claude-driven finish

- The Codex session was interrupted after the report draft. A Claude Opus 5.5
  driver took over to validate and finish the remaining Phase 5–7 items, with
  Opus 5.5 medium-effort subagents doing the work. Subagents leave changes
  uncommitted; the driver reviews each chunk, then commits and pushes it, so
  parallel workers never share a git index.
- Unblocked the paid conditions: the author explicitly authorized reusing the
  course assignment harness's OpenRouter key. It was copied into this
  project's ignored `.env` without being printed or committed, and
  `make doctor-live` now passes. This resolves the open credential decision
  from the pilot-status entry above.
- Did not spend on the live pilot right away. Its generic and steward paths
  had only been exercised by scripted unit tests, so a no-network preflight
  audit goes first: two episodes through the real runner with a scripted
  model, a transport review, a fairness review, and a scorer review. Spending
  on a pipeline that fails on the first real reply would waste budget and
  could produce results that cannot be reported.
- In parallel: a fresh-clone README reproduction test, and typesetting the
  report as LaTeX (pandoc is unavailable; xelatex is installed) with
  references in the proposal's required format (alphabetical, full authors,
  year, title, outlet). The draft's references were all undated
  self-citations of repository files, which does not meet that format.

## 2026-11-07 — Preflight audit and README reproduction

- A scripted-model dry run drove one remediation and one change episode
  through the real evaluation runner for both model conditions. Correct
  replies scored as expected; malformed JSON, invented evidence IDs, and a
  mismatched patch were rejected or rolled back as designed. The real `LM`
  class was exercised with a fake OpenAI client, so request fields, cost
  parsing, the fallback price table, and the budget stop were checked
  without a network call.
- Fixed before any spend: a failed agent run discarded its transcript, cost,
  and evidence, so a paid failure could not be audited or costed. Failed runs
  now keep that partial record. Also fixed: the results directory setting was
  ignored, the steward hardcoded `max_turns` instead of reading the frozen
  config, and an error-only OpenRouter reply raised an opaque exception.
  68 deterministic tests pass.
- Decision — must fix before the pilot: the steward prompt contained the
  episode ID (for example `rem_daily_revenue_filter_drift`), which names the
  expected finding. Workspace paths also embedded it, and dbt writes those
  paths into artifacts the generic agent can read. This would have handed the
  steward the label and biased the comparison. The fix changes prompt input,
  so the steward prompt and frozen config versions are bumped. No paid run
  used the old versions, so freezing still precedes the scored pilot.
- Decision — fix now, cheaply: prompts were not byte-stable across runs
  (manifest `created_at`, file sizes in listings), so the response cache never
  hit. With stable prompts a crashed pilot can resume, and the demo can replay
  recorded model runs instantly instead of paying on camera.
- Decision — pin reasoning effort in the frozen config and record it in
  results. Temperature 0 is probably ignored for reasoning models, so each
  episode is one sample and the report must not imply determinism.
- Decision — not fixed, documented as a limitation: generic-agent "patch"
  actions are never applied or verified, while a steward patch that fails
  verification costs the steward the episode. This is conservative against
  the steward, so it cannot inflate the steward's advantage. Steward patch
  verification checks that the intended value was written, not that the value
  is semantically right.
- Deferred to the paid smoke run: the protocol is strict (a final answer
  whose `content` is an object, an out-of-scope asset name, or one invented
  ID makes the whole episode an error for either condition). Whether this
  needs a repair turn depends on how often a real model trips it.
- A fresh clone reproduced every credential-free README step, and the static
  rerun matched the committed per-episode results exactly. README fixes cover
  Python provisioning by uv, unused evaluation settings, the real output
  location, and no-key behavior. Code follow-ups found there (check the key
  before building, clean no-key messages, skip the live test without a key,
  ignore timestamped result folders) go with the pre-pilot fixes.
- Report direction: the Gradescope rubric recommends Problem Statement,
  Methodology, Results, Assets, and Timeline, which matches the author's
  `iclr_template.tex`; the course page requires six named sections. The report
  uses the rubric outline in the ICLR template and maps the six required
  sections into it, so both graders find what they look for. Page limits
  exclude references, and the video limit is 3 minutes.

## 2026-11-08 — Label isolation and cache-stable model inputs

- The label-leak hunt found more than the steward prompt. Workspace paths
  named the episode and dbt copied them into `manifest.json`,
  `run_results.json`, compiled seed SQL, and logs. Worse, the generic agent's
  bounded SQL tool could call DuckDB file readers such as
  `read_text('data/episodes/manifest.yaml')` relative to the repository root,
  which would have exposed every label. Workspaces now use an opaque,
  deterministic token, evidence and tool errors rewrite real paths to
  `/workspace` and `/repo`, and DuckDB opens with external access disabled.
  A test renders both conditions' first model inputs through the real runner
  and asserts that no episode ID, description, action set, postcondition,
  overlay path, or real path appears.
- The reset marker and `episode.json` still hold labels, but they sit outside
  the agent-readable `project/` directory and the marker is the reset safety
  check, so they stay.
- Per-run dbt fields (timestamps, invocation IDs, elapsed times) are
  normalized in everything a model can read, binary artifact sizes are hidden,
  and dbt telemetry is off, which also removes a random-ID `.user.yml`. A test
  shows two fresh runs under different roots give byte-identical first
  inputs, so the response cache now works for resuming and demo replay.
- Reasoning effort is pinned in the frozen config, and all run settings are
  recorded in the summary and in every result. Config is now 1.1.0, with
  `generic-hygiene-v2` and `specialized-steward-v2`; prompt wording, contract,
  manifest, and scoring are unchanged. The loader refuses a config missing
  any run setting.
- Paid entry points now check for the key before building anything, so a
  missing key costs seconds rather than a 3-minute run and an error-filled
  results folder.
- Consequence: the committed `midpoint_v1_static/` results were produced
  under config 1.0.0 with the old path handling. The full pilot regenerates
  the static condition under 1.1.0, and the report will cite that run as the
  single source for all three conditions. 79 deterministic tests pass.

## 2026-11-08 — Report in the ICLR template with generated charts

- `report.md` is the single editable source. `make report` regenerates the
  charts and results table from a results folder (`REPORT_RESULTS`), rewrites
  the generated table region in the Markdown, converts it with pandoc
  (pinned through the `report` dependency group, since no system pandoc
  exists) into the ICLR 2025 frame of the author's `iclr_template.tex`, and
  builds the PDF in a temporary directory. The temporary build avoids clashes
  with an editor auto-compiling `report.tex`, which made latexmk fail
  intermittently. `report.tex` is committed as generated output.
- The outline follows the Gradescope rubric (Problem Statement, Methodology,
  Results, Assets, Timeline) and names the course's six required sections
  inside it. Body is 4 pages and references plus the disclosure follow, which
  the course's "page limits exclude references" rule allows. Any longer
  results interpretation must replace text rather than add to it.
- Charts are produced by `writeups/midway_report/make_figures.py`, which
  renders conditions that have not run as pending, so the same script serves
  the static-only draft and the full pilot without edits. A "false alarm"
  state was added for findings on clean controls, which "missed" would
  mislabel.
- The three requirement files were reformatted without changing their
  wording. The Gradescope source URL had a signed query string containing a
  temporary AWS session token; it was stripped before anything was
  committed.
- The course site lists the midpoint as due Nov 6; this work is finishing
  after that date, so the date was flagged to the author rather than assumed
  to be covered by an extension.

## 2026-11-08 — Paid smoke run and protocol repair

- First paid calls: 2 episodes × generic/steward under config 1.1.0 cost
  $0.0039 in 18 model calls. The model ID and transport worked. Three of the
  four runs found the expected issue with supporting evidence; none took a
  manifest-listed unsafe action; no label appeared in any transcript.
- The protocol's own format example caused 7 of the 8 rejected replies:
  `render_tools()` showed both reply shapes as one object keyed by
  `tool_call` and `final_answer`, and the model copied the wrapper. The error
  text did not say what to fix, so one generic run repeated the wrapper three
  times and stopped before reading the diff. Because the generic agent makes
  more calls, format failures would count disproportionately against it and
  inflate the steward's apparent advantage. That makes this a fairness
  defect, not just noise.
- Decision: fix the shared protocol rather than add per-condition prompting.
  Show two separate example objects with no wrapper key, accept a final
  `content` sent as a JSON object by serializing it, make protocol errors
  name what was received and what to send instead, and give both conditions
  one identical repair turn when a final answer fails plan or schema
  validation. Rejected replies and repair use are recorded per result, so the
  report can show how much the scaffolding mattered. Versions go to 1.2.0 with
  v3 prompts.
- The smoke run showed zero plan-validation failures, so the repair turn is
  symmetric insurance, not a response to an observed failure. It is cheap,
  identical across conditions, and visible in the results.
- Gate: the full pilot runs only if a smoke rerun under 1.2.0 completes all
  four runs with at most one rejected reply each. There will be no further
  prompt iteration after that, to avoid tuning on the evaluation set.
- Still a scorer limitation, handled by manual audit: the manifest's
  episode-specific unsafe actions are not machine-checked; the scorer checks
  only action classes against the contract.

## 2026-11-08 — Full three-condition pilot (config 1.2.0)

- The protocol fix removed wrapper copying entirely. The 1.2.0 smoke rerun
  completed all four runs with at most one rejection each, so the gate
  passed and the full pilot ran once: 30 runs, 0 errors, 8.5 minutes,
  $0.0172 (total project spend $0.0244). Raw results are in
  `experiments/results/midpoint_v1_2_pilot/`.
- Outcome: static 4/10 episodes (4 TP / 0 FP / 6 FN), generic 5/10
  (5 / 4 / 5), steward 5/10 (9 / 6 / 1). The steward found nine of the ten
  expected issues with about a fifth of the generic agent's model calls (14
  vs 65), but it over-reported, including false alarms on both clean
  controls, so it ties the generic agent on episode success. This is a
  pilot result on ten author-built fixtures, not evidence of a general
  advantage.
- Disclosure: four of the twenty model records (both demo episodes × both
  model conditions) are exact cache replays of the 1.2.0 smoke rerun. The
  inputs and config were identical, so the cache served them by design. The
  go/no-go decision used those runs only to check pipeline health; nothing
  was tuned in between. The report must state this.
- New failure mode, not fixed, by the pre-committed no-iteration rule: the
  generic agent batched many tool calls into one reply (8 of its 9
  rejections). Once it also invented the tool results it expected, built
  its plan on them, and after the repair turn swapped an invented evidence ID
  for a real but irrelevant one, so the run passed validation with
  ungrounded claims. Evidence validity (IDs resolve) cannot detect this, so
  the manual audit has to. Scaffolding still costs the generic agent more
  (7 of 10 runs had a rejection vs 2 of 10 for the steward). Fixing batching
  is the first protocol change for the final study.
- Design finding: action permission is keyed on the model's own issue-type
  label. On the wrong-grain episode the steward called the problem
  `sql_metadata_drift`, where a patch is allowed, rather than
  `grain_or_join_drift`, where only a proposal is, and its grain patch
  verified. The final study should derive or check the issue type
  independently of the model's label.
