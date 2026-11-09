# Two-case Codex comparison

Two individual Codex CLI 0.167.0 runs, gpt-6.1-terra with medium reasoning, workspace-write; saved 2026-11-08. The steward comparison is the existing frozen midpoint pilot with gpt-6-luna low. Prompts, model, budgets, tools, evidence gathering and execution differ. This comparison cannot isolate an interface effect and is not statistically informative.

Inputs are pre-run fixture snapshots, with the contribution diff in B; they contain no episode manifest or expected answers. `reproduce.sh a` or `reproduce.sh b` creates a fresh temporary workspace and records a new run; it requires authenticated Codex and a service connection, may consume account usage, and does not promise identical results. The CLI workspace sandbox allows reads outside the workspace; prompts prohibit them and the recorded command transcripts were reviewed for external reads. Opaque original fixture paths exist in dbt logs, so this was not a hard confidentiality boundary. Snapshot A is remediation of daily revenue; B is changed customer grain.

| Case | Codex predicted | Expected | Exact TP/FP/FN | Steward pilot TP/FP/FN | Episode success each |
|---|---|---|---|---|---|
| A | sql_metadata_drift/daily_revenue | same | 1/0/0 | 1/0/0 | yes |
| B | grain_or_join_drift/customer_orders; unsupported_reliability_claim/customer_orders; sql_metadata_drift/customer_orders; missing_required_metadata/raw_order_items | first two | 2/2/0 | 2/2/0 | no |

Scoring is a manual adaptation of midpoint-score-v1's exact set intersection on (issue_type, asset), plus checking allowed action classes, completed run and reported verification failures. This is not a run of the existing evaluator: Codex uses path-based evidence, not its evidence-ID schema. Both agents' B extras overlap with a grain finding and flag an undocumented seed; the existing pilot audit adjudicates the latter a real unlabelled gap. Codex's A patch and B lack of changes were independently checked against pre-run snapshots; A compared JSON descriptions but ran no dbt tests, B computed CSV join cardinalities but ran no dbt tests. Successful episode score does not prove safety or postconditions.

Both process exits were 0. Each final JSON equals its last completed agent message; separate event thread IDs and paths are retained. Before/after snapshot review found only A's catalog/overrides.json changed and no file-content changes for B. macOS tar `._` metadata entries are not content files and were excluded from comparison. A prior setup attempt used shared output paths after a transport disconnect and was excluded regardless of outcome; it is retained separately in the private run directory, not counted here.
