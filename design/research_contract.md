# Midpoint research and product contract

## Problem specification

The target user is a maintainer of a dbt-backed lakehouse whose catalog and
metadata become incomplete or misleading as pipeline code evolves. Evidence
needed to maintain the catalog is fragmented across dbt SQL and schema files,
compiled manifests, lineage, catalog metadata, code changes, and the data
itself. The project asks whether a specialized agentic steward can gather and
reconcile that evidence to repair existing hygiene debt and prevent new hygiene
regressions more safely and completely than static checks or a generic coding
agent with equivalent raw access.

## Headline outcomes

1. Starting from an unhealthy catalog, the steward produces a small set of
   evidence-backed changes or review proposals whose postconditions verify.
2. Given a proposed dbt change, the steward catches a catalog obligation or
   semantic ambiguity before the change lands, while allowing clean changes to
   pass without noisy findings.

## Frozen midpoint configuration

- **Stack:** dbt Core and DuckDB, using one repository-local fixture.
- **Agent transport:** OpenRouter through the cached wrapper in
  `catalog_steward.llm`.
- **Default model:** `openai/gpt-6-luna`, overrideable only through the recorded
  run configuration/environment.
- **Modes:** `remediation` and `change_review`, backed by one evidence/action/
  verification implementation.
- **Issue types:** the five versioned types in `hygiene_contract.yaml`.
- **Episode bounds:** one root model, at most two lineage hops, at most 20
  inspected assets, at most five findings, and bounded read-only data probes.
- **Action surface:** repository patches or structured proposals only; no
  direct live-catalog mutation.

## Safety and prioritization

Actions are classified as `patch`, `propose`, or `report`. Patches are limited
to deterministic, reversible technical metadata with direct evidence.
Descriptions, ownership, tests, and lifecycle decisions that depend on business
meaning are proposed for review. Destructive operations, unsupported claims,
and unresolved source conflicts are report-only. A run stops at its scope and
action limits rather than expanding until every possible warning is found.

The steward prioritizes high-impact, high-confidence findings that can be
verified. The midpoint does not optimize the number of warnings emitted.

## Deferred until after the midpoint

- Hosted catalog and warehouse integrations.
- More models or agent harnesses.
- A generic agent supplied with the full hygiene skill/checklist.
- Tool-versus-workflow ablations.
- Automatic table deletion, access-policy changes, generalized anomaly
  remediation, or inferred business definitions.
- Expansion from the audited 8-12 episode pilot to the 30-50 episode final
  study.

