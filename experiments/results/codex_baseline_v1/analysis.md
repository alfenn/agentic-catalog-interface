# Trace audit: steward vs Codex (codex_baseline_v1)

This audit compares three conditions on the ten frozen episodes, one sample each:

- **steward**: the frozen pilot records in `experiments/results/midpoint_v1_2_pilot/` (config 1.2.0, `gpt-6-luna` low). Its [analysis.md](../midpoint_v1_2_pilot/analysis.md) is the source for steward adjudications below, which this file reuses rather than repeats.
- **codex-matched**: Codex CLI 0.167.0, `gpt-6-luna` low. Same model and effort as the steward; only the harness differs.
- **codex-frontier**: Codex CLI 0.167.0, `gpt-6.1-sol` medium.

**Bottom line.** Under the unchanged scorer, episode successes are steward **5/10**, codex-matched **6/10** and codex-frontier **7/10**. On these fixtures the steward does not beat a general coding agent on episode success, including the one running its own model. The differences between conditions are mostly not where the score looks:

1. **Detection.** The steward has the highest recall (9/10 expected issues, against 7/10 and 8/10). It is the only condition that found the failing uniqueness claim in `change_customer_orders_grain` and the lifecycle problem in `rem_legacy_model_lifecycle`. Both rest on evidence its harness collects for every scoped asset: bounded profiles, lineage, and an episode diff.
2. **Over-reporting.** The steward has the most extra findings (6, against 5 and 3). Half of them are real gaps the labels do not anticipate (category (ii) in the pilot audit). Codex flags the same unlabelled seed gaps, but it does not flag the clean control's dbt description omission.
3. **Action policy.** The steward never edits the catalog during change review; it proposes. Codex patches the catalog in 3 (matched) and 4 (frontier) of the 6 change reviews. This writes metadata that matches an unreviewed code change. The scorer accepts it (patching is an allowed class for these issue types) and it verified mechanically, but in one run it settled a semantic question without raising it (`change_daily_revenue_filter`, matched).
4. **Shared model errors.** On `rem_customer_orders_wrong_grain`, codex-matched made exactly the steward's mistake: it labelled a grain mismatch `sql_metadata_drift`, which unlocked a grain patch. Same model, same error, different harness. The frontier model labelled it correctly and proposed.

Every claim in all 20 Codex runs is grounded in files or queries in the workspace. No Codex claim was fabricated, no isolation flag fired, and no run edited a file other than `catalog/overrides.json`.

## Method

For each Codex run I read the final answer, the full command stream, the project diff and the verification log, and re-checked each claim against the fixture overlays and base files (`data/fixtures/dbt_catalog/base`, `data/episodes/overlays/`). For each steward run I read the pilot record's plan, evidence kinds and verification, and use the pilot audit's adjudication. No model calls were made and no labels or scores were changed. "Inspected" lists what an agent actually read or ran. The steward's inspection is its harness-built evidence bundle plus any tool calls.

**Isolation.** No run triggered the automated scan, which looks for commands or file changes outside the workspace, parent-directory reads, label patterns, and the repository path or episode IDs in commands or output. A manual sweep of all 20 event streams agrees:

- No episode ID or repository path appears anywhere.
- The only absolute paths are Codex's own edits to the workspace's `catalog/overrides.json`.
- The single parent reference, `../warehouse.duckdb` in `rem_customer_orders_wrong_grain` / codex-matched, came from inside `project/` after a failed attempt with the plain name, so it stayed in the workspace.
- Several runs tried `git status` or `git log` (exit 128, no repository), which shows they looked for history and found none.

**Codex's self-reported verification.** `verification_performed` is not scored, so I checked it against the event stream. Every quoted command was run. Some are paraphrased ("python JSON assertions over ...") but match real commands. Several compound commands exited non-zero only because a trailing `git` call failed after the checks had printed their results. In `rem_daily_revenue_filter_drift` / codex-matched, one bounded query failed because `fetchdf()` needs numpy, which neither the tool environment nor the repository's default environment installs; Codex reported the failure rather than claiming the check. Other failed commands were working-directory slips (running from `project/` with workspace-relative paths) that Codex corrected on the next command.

## Per episode

Cells give TP/FP/FN and episode success (S) from the scorer, followed by the audit. "Patch" means a catalog field was written; "propose" and "report" change nothing.

### rem_daily_revenue_filter_drift (expected: sql_metadata_drift / daily_revenue)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 1/0/0 ✓ | 1/0/0 ✓ | 1/0/0 ✓ |
| Inspected | bundle (catalog, schema, SQL, parsed facts, manifest, lineage, profile) | catalog, overrides, SQL, schema, manifest node | same files plus a bounded DuckDB profile and a regex check of the SQL filter |
| Concluded / action | override says "all orders"; SQL keeps completed only. Patched description | same; patched description to the dbt schema's wording | same; patched description, identical value |
| Right? | yes (pilot audit; cache replay) | yes | yes |
| Files changed | overrides.json (description) | overrides.json (description) | overrides.json (description) |

All three wrote the same correct description, and all three patches verified: the field equals the declared value and `dbt parse` succeeds.

### rem_customer_orders_wrong_grain (expected: grain_or_join_drift / customer_orders)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 0/1/1 ✗ | 0/1/1 ✗ | 1/0/0 ✓ |
| Inspected | bundle | catalog, overrides, SQL, schema, manifest; bounded profile (after a failed first try); `dbt parse` | catalog, overrides, SQL, compiled SQL, manifest; bounded profile; sqlglot parse of the SQL |
| Concluded / action | grain override `order_id` contradicts customer aggregation; labelled `sql_metadata_drift`, patched grain to `customer_id` | same claim, same label, same patch | same claim, labelled `grain_or_join_drift`, proposed the correction (patching is not allowed for this type, and it said so) |
| Right? | claim right, label wrong, (iii) in the pilot audit; no uniqueness evidence cited | claim right, label wrong (iii); a bounded profile was run but grain patching is outside the manifest's "propose" | yes; acceptable action, with uniqueness evidence |
| Files changed | overrides.json (grain) | overrides.json (grain) | none |

The contract's overlapping types (a grain is an aggregation) let the same model reach a patch under both harnesses. The steward's validator enforces allowed actions *per label*, so it did not prevent this.

### rem_daily_revenue_missing_owner (expected: missing_required_metadata / daily_revenue)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 1/0/0 ✓ | 1/0/0 ✓ | 1/0/0 ✓ |
| Inspected | bundle | catalog, overrides, SQL, schema, manifest node; `dbt ls` | catalog, overrides, schema, compiled SQL, manifest; bounded profile |
| Concluded / action | null owner override masks `finance-analytics`; patched owner | same; patched owner | same; patched owner |
| Right? | yes, postcondition met | yes, postcondition met | yes, postcondition met |
| Files changed | overrides.json (owner) | overrides.json (owner) | overrides.json (owner) |

### rem_legacy_model_lifecycle (expected: lifecycle_drift / legacy_customer_orders)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 1/1/0 ✗ | 0/1/1 ✗ | 0/0/1 ✗ |
| Inspected | bundle, including lineage and the (empty) episode diff | catalog, overrides, both schemas, both SQL files; tried `git` | all models, catalog, overrides, schemas, manifest; bounded profiles of both models; tried `git` |
| Concluded / action | legacy copy marked active and canonical beside its source; proposed review. Extra `grain_or_join_drift` report | legacy description is vague; labelled `sql_metadata_drift`, patched the description | no finding: "no repository history was available to establish lifecycle drift"; raised "should legacy_customer_orders remain canonical?" as an unresolved question |
| Right? | lifecycle finding right; the extra is spurious, (i) in the pilot audit | missed the labelled issue. The new description is factually supported (the model selects from customer_orders), but the old one did not contradict the SQL, so the finding is spurious (i) | missed the labelled issue. It saw the problem but followed the contract's required evidence literally |
| Files changed | none | overrides.json (description) | none |

**Disputable.** `lifecycle_drift` requires `repository_diff_or_history`, and a remediation episode has neither: Codex's workspace has no diff, and `git` is absent. The steward met the requirement by citing the empty episode diff (`episode/input.diff`, content `""`), so its validator passed a finding whose required evidence kind carried no information. Codex-frontier declined for the reason the contract gives. Either the contract should not require history for remediation, or the episode should supply it.

### change_daily_revenue_filter (expected: sql_metadata_drift / daily_revenue)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 1/0/0 ✓ | 1/0/0 ✓ | 1/0/0 ✓ |
| Inspected | bundle plus diff | diff, catalog, SQL, schema, manifest node, run results; `rg` over the project | diff, catalog, SQL, schema, manifest; bounded DuckDB query of daily revenue |
| Concluded / action | metadata says refunded orders excluded; SQL now keeps `status != 'cancelled'`. Proposed review, asking whether refunded orders belong in revenue | same conflict; **patched** the catalog description to say refunded orders are included; no unresolved question | same conflict, confirmed one refunded order in the data; **patched** the description and asked whether including refunds is intended |
| Right? | yes. Understated (says refunds are "not explicitly excluded"), but the action is acceptable | detection right. The action approves the semantic change by rewriting metadata to match the code, without asking. Not a listed unsafe action, but outside the manifest's acceptable "request a semantic decision" | detection right. It patched first and asked second. Its question names the stale `completed_*` column names, which no other condition noticed |
| Files changed | none | overrides.json (description) | overrides.json (description) |

The score is identical, but the actions differ in kind. This is the clearest case of the action-policy difference.

### change_customer_orders_grain (expected: grain_or_join_drift and unsupported_reliability_claim / customer_orders)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 2/2/0 ✗ | 1/2/1 ✗ | 1/2/1 ✗ |
| Inspected | bundle (profile: 3 duplicate customer_id in 7 rows), diff | diff, catalog, all SQL, schema, manifest; bounded profile | diff, catalog, all SQL, seeds, manifest; two bounded profiles |
| Concluded / action | grain finding; failing customer uniqueness claim; extras `sql_metadata_drift` (restates grain) and `raw_order_items` undocumented. All proposals | grain finding (multiple rows per customer); extras `sql_metadata_drift` (description promises metrics) and `raw_order_items` (report). No file changed | grain finding (propose); extras `sql_metadata_drift` (**patched** the description to the new item-level output) and `raw_order_items` (propose) |
| Right? | both expected right; extras (iii) and (ii) | grain right. Missed the reliability claim: it saw the duplicates but never treated the `unique` test on customer_id as a claim, and ran no `dbt test`. Extras (iii) and (ii) | as matched. In addition, it wrote metadata for an item-level grain while asking reviewers whether item-level output is intended |
| Files changed | none | none | overrides.json (description) |

None of the conditions ran the dbt tests. The steward reached the reliability finding through the profile in its bundle.

### change_new_model_missing_metadata (expected: missing_required_metadata / high_value_orders)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 1/0/0 ✓ | 1/0/0 ✓ | 1/0/0 ✓ |
| Inspected | bundle plus diff | diff, catalog, SQL, schema, project config; bounded profile; tried `git` | diff, catalog, SQL, schema, manifest; bounded profiles of both models |
| Concluded / action | new model lacks description, owner, lifecycle and tests; proposed, with no invented owner | patched description ("Completed orders with amount at least 100") and grain `order_id`; owner left as an unresolved question | proposed owner, lifecycle and canonical; patched description (the SQL filter verbatim) and grain `order_id` |
| Right? | yes | yes. The description restates the SQL filter rather than inventing purpose, and the grain is supported by the upstream unique test and the profile. Patching beyond the manifest's "propose" | yes, as matched |
| Files changed | none | overrides.json (description, grain) | overrides.json (description, grain) |

### change_rename_without_lifecycle (expected: lifecycle_drift / daily_revenue; missing_required_metadata / revenue_daily)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 2/0/0 ✓ | 2/0/0 ✓ | 2/0/0 ✓ |
| Inspected | bundle plus diff, lineage | diff, catalog, all SQL, schema, manifest, dbt log; bounded profile | diff, catalog, schema, all SQL, manifest; warehouse relations and a profile |
| Concluded / action | both findings, proposals only | both findings. Patched description and grain on revenue_daily; reported the schema tests still attached to the removed model | both findings. Patched description, **owner** (`finance-analytics`) and grain on revenue_daily; proposed lifecycle and canonical |
| Right? | yes | yes. It also found that the rename left the dbt tests behind, which no other condition reported | yes. The owner patch infers ownership from the replaced model. Arguably "repository evidence", but the contract forbids inferring an owner without it, and a rename does not prove that ownership transfers |
| Files changed | none | overrides.json (description, grain) | overrides.json (description, owner, grain) |

### clean_new_model_documented (expected: no finding)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 0/1/0 ✗ | 0/1/0 ✗ | 0/1/0 ✗ |
| Concluded / action | `raw_customers` has no catalog or schema entry (propose) | same (report) | same (propose) |
| Right? | factually true, (ii) in the pilot audit | factually true (ii) | factually true (ii) |
| Files changed | none | none | none |

All three conditions fail this control for the same real, unlabelled gap. The label is the problem; see the pilot audit's recommendation to document the seeds or drop `raw_customers` from scope.

### clean_daily_revenue_metric (expected: no finding)

| | Steward | codex-matched | codex-frontier |
|---|---|---|---|
| Score | 0/1/0 ✗ | 0/0/0 ✓ | 0/0/0 ✓ |
| Concluded / action | dbt model description omits the new max-amount metric that the catalog override mentions (propose) | no issue; catalog override matches the SQL | no issue |
| Right? | factually true but borderline (ii), and it matches the manifest's listed unsafe action | correct per label. It did not notice the dbt description omission | correct per label, same |
| Files changed | none | none | none |

## Where the labels and scorer are disputable

These come in addition to the pilot audit's list, which still applies.

- **Clean controls are not clean.** `raw_customers` is undocumented in base, and all three conditions flag it. In `clean_daily_revenue_metric`, the dbt description lags the catalog. Accepting the (ii) cases would move the steward to 7/10, codex-matched to 7/10 and codex-frontier to 8/10. These are not re-scored results.
- **Overlapping issue types.** Grain-versus-SQL drift (`rem_customer_orders_wrong_grain`; the `sql_metadata_drift` restatements in `change_customer_orders_grain`) is mislabelled under both harnesses. Exact label matching turns one real finding into an FP and an FN.
- **Lifecycle evidence in remediation.** As above: the contract requires repository history that the remediation episode does not provide. One condition passed on an empty diff and another declined.
- **Patching during change review.** The scorer checks only that the action class is allowed. It cannot tell a proposal from a patch that rewrites metadata to match an unapproved change (`change_daily_revenue_filter`, `change_customer_orders_grain` frontier). Nor can it tell an owner patch backed by a direct declaration (`rem_daily_revenue_missing_owner`) from one inferred across a rename (`change_rename_without_lifecycle` frontier).
- **Verification is mechanical.** Every patch in all three conditions passed verification: the field equals the declared value and `dbt parse` succeeds. As the pilot audit notes, `dbt parse` does not read `catalog/`, so this does not check that a patch is semantically right. The auditor checked each patched value by hand against the SQL and schema. All are factually supported except the semantic choices noted above.
- **Evidence validity.** For Codex it means that cited files exist and cited commands were run (1.0 in all 20 runs). For the steward it means that cited evidence IDs resolve. Neither checks that the evidence supports the claim. The two measures are not comparable and are reported separately.

## Per-condition totals

Micro precision and recall are over distinct `(issue_type, asset)` pairs across the ten episodes (10 expected). "Unsafe action classes" is the scorer's count of findings whose action class the contract disallows. "Patch findings" counts findings with a patch action; several Codex runs patched more than one field of one asset.

| | Steward | codex-matched | codex-frontier |
|---|---:|---:|---:|
| Episode successes | 5/10 | 6/10 | 7/10 |
| TP / FP / FN | 9 / 6 / 1 | 7 / 5 / 3 | 8 / 3 / 2 |
| Micro precision | 0.60 | 0.58 | 0.73 |
| Micro recall | 0.90 | 0.70 | 0.80 |
| FP by category (i spurious / ii real unlabelled / iii mislabel or duplicate) | 1 / 3 / 2 | 1 / 2 / 2 | 0 / 2 / 1 |
| Unsafe action classes | 0 | 0 | 0 |
| Verification failures | 0 | 0 | 0 |
| Edits outside the override file | 0 (not possible for the steward) | 0 | 0 |
| Patch findings / runs that changed the catalog | 3 / 3 | 9 / 7 | 9 / 6 |
| Catalog patches during change review (runs) | 0 | 3 | 4 |
| Isolation flags | n/a | 0 | 0 |
| Run errors | 0 | 0 | 0 |

**What this supports, as observations on these ten author-built fixtures with one sample each:** given the same task, contract and data access, a general coding agent matches or exceeds the steward's episode-level score, with fewer extra findings. The steward finds more of the labelled issues, because its harness collects profiles and lineage for every scoped asset. And it never edits the catalog during change review, whereas Codex often writes metadata that accepts the proposed change.

**What it does not support:** any statistical claim (a 5/6/7 split over ten episodes, one sample; the paired check saw the same matched run go both ways across samples); a safety claim from the scorer's unsafe-action counts, which are zero for everyone; or a claim that the steward's architecture improves outcomes over Codex on this benchmark as scored.

## Recommended walkthrough cases

- **Remediation: `rem_legacy_model_lifecycle`.** The three conditions behave in three different ways on the same evidence. The steward raises the labelled lifecycle problem from its bundle (lineage and catalog flags), but it meets the contract's history requirement with an empty diff and adds a spurious grain report. Codex-matched edits a description that was not wrong. Codex-frontier sees the canonical/active conflict, declines to file it for lack of history, and leaves it as a question. The case shows what the evidence bundle and validator buy, and where the contract itself is the bottleneck. Runner-up: `rem_customer_orders_wrong_grain`, the same model making the same mislabel-and-patch under both harnesses.
- **Change review: `change_daily_revenue_filter`.** All three detect the conflict and score 1/0/0, but the steward asks whether refunded orders belong in revenue. Codex-matched silently rewrites the catalog to accept the new definition, and codex-frontier rewrites it and then asks. The case shows the action-policy difference that the score does not register. Runner-up: `change_customer_orders_grain`, where only the steward finds the failing uniqueness claim.
