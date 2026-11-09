---
source: codex-terra-5.6-medium
reply-to: [attachments/feedback.md]
---

# Proposed response to the feedback

The proposal should lead with the underlying problem, not the three questions the
system happens to answer. In a data lake, deciding what to clean, document, or
connect is difficult because the evidence is scattered across schemas, table
contents, query history, lineage, and inconsistent existing metadata. Teams
therefore either rely on costly manual investigation or make hygiene decisions
with incomplete context. The project can be framed as an agent that gathers and
reconciles this evidence to recommend the highest-value metadata and hygiene
actions.

## Two outcomes worth centering

1. **Make an unfamiliar data lake navigable.** Given raw or incomplete catalog
   information, the agent discovers useful metadata and relationships so that a
   user can understand what data exists and how it can be used.
2. **Prioritize trustworthy hygiene work.** The agent recommends a small,
   evidence-backed set of actions--for example, documenting a table, resolving
   an ambiguous field, adding a relationship, or flagging a quality issue--and
   explains why each action matters.

These claims are stronger and more cohesive than presenting independent answers
to specific catalog questions. They also make the project's intended contribution
clear: not merely producing metadata, but helping people decide where limited
data-management effort should go.

## Evaluation revision

Keep the fair comparison of agents with and without the proposed tools, but
reduce the combinatorial sweep. Select a small, representative set of models and
harnesses, then evaluate them deeply on the two outcomes above. For each outcome,
measure task success and quality of the agent's justification, and report cost or
tool-use efficiency as a secondary measure. A compact matrix with a strong
no-tool baseline will be easier to execute, interpret, and defend than a broad
but shallow collection of model-harness combinations.

## Concrete proposal edits

- Rewrite the motivation opening around fragmented evidence and the difficulty of
  prioritizing data-hygiene work.
- State the two outcomes above as the project's headline goals; position the
  current three questions as supporting capabilities or examples.
- Add one end-to-end motivating example: an unfamiliar table with sparse
  metadata, the evidence the agent inspects, its recommendation, and the
  resulting user benefit.
- Replace the exhaustive evaluation sweep with a scoped set of representative
  configurations and explicit baselines: the same agents without the tools and,
  where feasible, a simple non-agentic baseline.

