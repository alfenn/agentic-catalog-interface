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
