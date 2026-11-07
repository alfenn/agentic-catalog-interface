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
