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
