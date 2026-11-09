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
- Completion validation: 34 deterministic tests pass, one paid live preliminary test
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
  deterministic tests pass; the live preliminary test remains deselected.

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
- Deferred to the paid preliminary run: the protocol is strict (a final answer
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

## 2026-11-08 — Paid preliminary run and protocol repair

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
- The preliminary run showed zero plan-validation failures, so the repair turn is
  symmetric insurance, not a response to an observed failure. It is cheap,
  identical across conditions, and visible in the results.
- Gate: the full pilot runs only if a preliminary rerun under 1.2.0 completes all
  four runs with at most one rejected reply each. There will be no further
  prompt iteration after that, to avoid tuning on the evaluation set.
- Still a scorer limitation, handled by manual audit: the manifest's
  episode-specific unsafe actions are not machine-checked; the scorer checks
  only action classes against the contract.

## 2026-11-08 — Full three-condition pilot (config 1.2.0)

- The protocol fix removed wrapper copying entirely. The 1.2.0 preliminary rerun
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
  model conditions) are exact cache replays of the 1.2.0 preliminary rerun. The
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

## 2026-11-08 — Manual audit of the three-condition pilot

- The audit (`experiments/results/midpoint_v1_2_pilot/analysis.md`) confirmed
  the scorer's arithmetic but changed what the numbers mean. Every steward
  finding cites real, relevant evidence. The steward's two clean-control
  "false alarms" are true statements about the fixtures: a seed with no
  documentation, and a model description that omits a newly documented
  metric. The generic agent's 5/10 includes one pass where it read no files,
  and one failure built entirely on tool results it invented, which still
  passed the ID-based evidence check. A third run approved the refund
  regression without reading anything, which the manifest lists as unsafe
  but the scorer cannot see.
- Decision: do not relabel the manifest or rescore for the midpoint.
  Changing labels after seeing results would make the comparison
  unfalsifiable. The audit reports a sensitivity range instead (steward 7/10
  if the defensible extras are accepted, generic 4/10 if vacuous passes are
  rejected, static 3/10 if report-only remediation is rejected). Seed
  documentation, a truly clean `clean_daily_revenue_metric` overlay, an
  issue-type precedence rule, and postcondition-based success go into the
  next episode version.
- Two acceptance items stay open honestly. The conditions are not fully
  matched: only the steward sees per-issue action rules and a pre-collected
  evidence bundle, so call counts and unsafe-action rates are not
  like-for-like. And not every agent claim is traceable to evidence: the
  fabricated generic run is the counterexample, and the evidence-validity
  metric cannot detect it.
- Steward patch verification is weaker than the contract describes. It
  checks that the written value equals the model's chosen value and that
  `dbt parse` succeeds; `dbt parse` does not read `catalog/`. The audit
  checked all three patched values by hand and found them correct. Real
  per-issue verification is a priority for the final study.
- The auditor's file write was blocked because subagents return findings as
  text, so the driver saved the audit verbatim, after spot-checking three
  claims against the raw records.

## 2026-11-08 — Three-minute demo package

- The rubric caps the video at 3 minutes, so the package targets 2:45 of
  narration (about 400 words at roughly 147 wpm) in seven timed segments
  (`writeups/midway_report/demo/demo_script.md`), with one shell function per
  segment (`demo_commands.sh`). Everything slow (dependency sync, dbt
  fixture builds, chart generation) runs in an off-camera `prep` step. Every
  on-camera command was rehearsed at under 6 seconds.
- On-camera steward runs replay the recorded pilot from the response cache.
  This was the payoff of the cache-stable prompt fix: replayed plans are
  byte-identical to the pilot and the spend ledger does not change ($0.0244
  before and after). The script runs replays with a near-zero budget, so a
  cache miss fails before any paid call and falls back to the saved
  artifacts instead of silently paying for, and showing, a different sample.
- The story uses the two demo episodes as separate fixtures and connects
  them honestly: the change episode's catalog text is byte-identical to the
  steward's earlier patch, and the script checks that before saying so.
- A third chart (expected issues found vs false alarms per condition) was
  added to the same generator, behind an opt-in flag, so the report's
  default figures are unchanged apart from a clipped-label fix in the
  outcome grid.
- The driver reworded the closing narration to match the audit: the
  steward's extra findings include real gaps the labels missed, so the
  follow-up is better labels and real verification, not only "fewer false
  alarms".

## 2026-11-08 — Report results, README, and handoff state

- The report now reports the three-condition pilot through the audit's
  framing. The steward matched 9/10 expected issues and every claim was
  grounded, but it tied the generic agent at 5/10 by over-reporting. The
  generic agent's score hides a no-inspection pass, an invented-evidence run,
  and an unread approval. The conditions are not like-for-like. The
  sensitivity range is given as explicitly not a rescoring. Body is 4 pages;
  references and the disclosure follow.
- `make report` failed intermittently because an editor auto-compiles
  `report.tex` in place, and the build's bibtex step read the editor's
  half-written `report.aux` from the report folder. The build now copies its
  sources into the temporary directory and compiles there, and the editor's
  LaTeX byproducts are gitignored. The default results folder for the report
  is the 1.2.0 pilot.
- The README's limitations section now states the pilot's real caveats
  instead of saying the live pilot is pending.
- Open by design, for the author: record the video from
  `writeups/midway_report/demo/demo_script.md`, add its URL to the report's
  Assets section, write the human-verification sentence in the AI-use
  disclosure, and decide on the title (the template's "An Agent Tool
  Interfaces" is ungrammatical and reflects the proposal's framing).
- Open as honest limitations, not oversights: the conditions are not fully
  matched, and not every agent claim is traceable to evidence (the
  fabricated generic run). Both are first-priority fixes for the final study,
  together with seed documentation and truly clean controls, an issue-type
  precedence rule, postcondition-based success, real per-issue patch
  verification, and a batching-robust protocol.

## 2026-11-08 — Repository link section and video description

- At the author's request, the report has a dedicated "Code Repository"
  section with the GitHub URL, placed in the appendix immediately before the
  AI-Use Disclosure, so it does not count toward the 4-page body. The Assets
  section keeps its link as well, because the rubric asks for links there.
- The URL sits on its own line: inline, the unbreakable URL stretched the
  justified spacing of its sentence.
- `demo/demo_script.md` now opens with a ready-to-paste video description
  containing the repository link and the cache-replay disclosure, so the
  disclosure travels with the video rather than depending on narration time.

## 2026-11-08 — Human feedback: scope and evidence

- The previous generic condition is a custom raw-tool workflow, not Pi or Codex. It cannot be relabeled as a coding-agent result; a separately recorded real-agent baseline is required before making that comparison. Existing results remain frozen.
- Prioritize a reusable evaluation walkthrough and trace-linked examples, with explicit limits on verification and label-dependent scoring. Broaden the motivation to lakehouses while keeping dbt/DuckDB as the actual experimental fixture.
- The report table generator emits a cost column, so removing report cost data requires updating the generator as well as prose; the recorded source data remain intact for provenance.

## 2026-11-08 — Evaluation narrative revision

- Replaced the aggregate comparison with a trace-linked steward-only description pending a real coding-agent baseline. The two selected cases demonstrate a successful exact match and a failed episode with complete recall and disputed extra findings. This avoids treating an exploratory harness as a named coding agent.
- Explained reset, execution, matching and episode scoring in one sequence. Removed report cost prose and the generated table's cost column; the underlying recorded fields remain unchanged.

## 2026-11-08 — Terminology and evidence preservation

- Updated editable explanations and the live integration test filename to use plain language. The original feedback and frozen raw records remain unchanged as provenance; generated report output will be rebuilt from the revised source.
- The requested named coding-agent comparison requires new, separately recorded runs. The earlier custom workflow cannot supply that evidence; only matched cases with their limitations can be compared.

## 2026-11-08 — Publication boundary

- The working report and supporting documents already contain uncommitted changes predating this feedback. A commit against the repository's current base would include those changes as well as this revision. Keep the implementation local and list the exact intended publication scope for review before pushing.

## 2026-11-08 — Coding-agent source

- Added the official OpenAI Codex repository as the software citation for the planned comparison; its public README describes the CLI as a local coding agent. The actual invocation version and results must come from the run record, not from that citation.

## 2026-11-08 — Delivery scope

- The delivery scope includes this report revision and the related earlier report, demo, README and audit improvements, plus the requested response, notes, test rename and any genuine comparative evidence. Unrelated existing file moves and the modified raw dbt result remain outside the change. An isolated branch and explicit staging will make the cumulative report changes reviewable before publication.

## 2026-11-08 — Two-case coding-agent comparison

- Added the independently recorded Codex results for the two preselected cases. Both conditions matched one issue without extras in the revenue case and both matched two with two extras in the grain case; episode success was one of two each. This is a descriptive comparison, not evidence of equivalence or advantage.
- Codex used a different model, tools, prompt, limits and executor; its grain-case cardinalities came from CSV rather than dbt tests. Retain those differences and the unlabelled-seed ambiguity in the report and packaged evidence.

## 2026-11-08 — Paired-run provenance

- Preserved the actual two-run prompts, isolated pre-run snapshots, event streams, final answers, and a scoring/action audit under `experiments/results/codex_midway_two_case/`. The interrupted ambiguous setup attempt is excluded. The README explains that mapping the coding-agent findings to manifest labels was manual and that the coding agent used path-based evidence rather than the steward's evidence-ID schema.

## 2026-11-08 — Feedback response reconciliation

- The response acquired a fuller seven-step plan while implementation was underway. Kept that text as a historical review and added a dated implementation update; the report now presents seven steps. The preselected changed-grain case was retained because it has an actual separately recorded coding-agent run and illustrates the requested scoring limits. The earlier suggestion of a filter-change walkthrough does not justify substituting an unrecorded comparison.

## 2026-11-08 — Round two: Codex baseline design (claude-opus-5.5)

- Local main was moved onto the pushed first-round commit (894f0ca) instead of re-committing the same files, so main and the first-round branch share history. The working tree matched that commit byte for byte. A frozen pilot run record that an editor had pretty-printed was restored to its original bytes; its JSON content was identical.
- Codex CLI offers `gpt-6-luna` at low reasoning, the steward's frozen model and effort. The primary baseline therefore holds the model fixed and varies only the harness, which is the question the report title asks. A second Codex condition on `gpt-6.1-sol` answers whether a small-model steward keeps up with a state-of-the-art agent on a frontier model.
- Codex gets the same task specification as the steward (trigger, scope, hygiene contract, five-finding cap, patch surface) but not the evidence bundle, validator or executor, which are the intervention. Its workspace is built outside the repository with label material removed, and its tools come from a separate environment, so neither the workspace nor `PATH` leads to the labelled repository.
- The steward side stays the frozen pilot. Re-running it would add a fresh sample but would also blur the claim that nothing was tuned after Codex results were seen.
- Work is split across subagents: the runner and tests in one, the architecture diagram and section in another. Shared tracking files (`agent_notes.md`, `AGENT_TODO.md`) are edited only by the coordinating agent to avoid concurrent overwrites.

## 2026-11-08 — Total page limit

- Removed the forced page break before references, keeping all text and ICLR typography intact. The regenerated report fits four total pages including references and AI-use disclosure; all four pages were visually inspected for legibility and overflow.
