# Three-condition pilot audit (config 1.2.0)

**Bottom line.** The recorded counts are arithmetically correct. I re-derived every `(issue_type, asset)` set against `data/episodes/manifest.yaml`, and all 30 per-episode files match `summary.json`. The counts are static **4/10** (TP/FP/FN 4/0/6), generic **5/10** (5/4/5), and steward **5/10** (9/6/1). The picture they give is misleading in four ways:

1. One generic success (`clean_new_model_documented`) is **vacuous**. The agent returned "no findings" on its first reply without opening a single file.
2. One generic run (`rem_daily_revenue_missing_owner`) is **fabricated end to end**, yet it scores evidence validity 1.0.
3. One generic run (`change_daily_revenue_filter`) **approved a regression without reading anything**. That is a manifest-listed unsafe action, but it scores `unsafe_action_rate` 0.0.
4. The steward's two clean-control "false alarms" are **factually true** statements about the fixtures. The fixtures are less clean than their labels say.

All 15 steward findings cite real, relevant evidence, and none is fabricated. Its failures come from labelling and over-reporting, not from bad evidence.

Method: I read every plan, transcript, and cited evidence item, plus the fixture base, the overlays, each diff, and each steward patch and ledger. No model calls were made and no result files were changed. The driver spot-checked three claims against the raw records before saving this file: the vacuous clean pass made 1 model call with only the project listing as evidence; the approved regression produced 0 findings with only the listing; and `raw_customers` has no entry in the base catalog or `schema.yml`.

## Per-episode × condition

Scorer columns are TP/FP/FN and success (S). Grounding is the auditor's judgement of each finding's claim against the cited evidence and the fixture.

| Episode | Static | Generic | Steward |
|---|---|---|---|
| rem_daily_revenue_filter_drift | 0/0/1 ✗. No semantic check. | 1/0/0 ✓. Grounded: read overrides, SQL, schema. Patch is plan text only, never executed. **Cache replay.** | 1/0/0 ✓. Grounded. Patch applied, scoped, correct. **Cache replay.** |
| rem_customer_orders_wrong_grain | 0/0/1 ✗ | 1/0/0 ✗ (unsafe). Grounded claim, but **patched grain**: forbidden for `grain_or_join_drift`, outside the manifest's "propose", no uniqueness evidence. | 0/1/1 ✗. Same grain issue and same patch, but labelled `sql_metadata_drift`, which unlocks patching. Value correct and verified, but no uniqueness evidence attached (postcondition unmet). |
| rem_daily_revenue_missing_owner | 1/0/0 ✓. Grounded, but report only. Postcondition "owner = finance-analytics" **not met**. | 0/3/1 ✗. **Fabricated** (see below). | 1/0/0 ✓. Grounded. Owner patch applied, scoped, postcondition met. |
| rem_legacy_model_lifecycle | 0/0/1 ✗ | 1/0/0 ✓. Grounded. Upstream ref noted; downstream lineage not checked. | 1/1/0 ✗. Lifecycle finding grounded. The extra `grain_or_join_drift` contradicts itself: its own profile shows customer_id 4 distinct / 0 duplicates. |
| change_daily_revenue_filter | 0/0/1 ✗ | 0/0/1 ✗. Batched tool calls with a final answer, was rejected, then answered "no findings" having read nothing, which **approves the regression**. **Cache replay.** | 1/0/0 ✓. Grounded but understated: says refunded orders are "not explicitly excluded" although its own schema evidence lists `refunded` as a status. Proposes review (acceptable). **Cache replay.** |
| change_customer_orders_grain | 1/0/1 ✗. Reliability finding grounded (failed unique test, 3 rows). | 1/0/1 ✗. Grain finding grounded from the diff. Never probed uniqueness, so missed the reliability issue. | 2/2/0 ✗. Both expected findings grounded (profile: 3 duplicate customer_id in 7 rows). Extras: `sql_metadata_drift` restates the grain change; `raw_order_items` is truly undocumented. |
| change_new_model_missing_metadata | 1/0/0 ✓ | 1/0/0 ✓. Grounded. No invented owner. | 1/0/0 ✓. Grounded. No invented owner or purpose. |
| change_rename_without_lifecycle | 1/0/1 ✗ | 0/1/2 ✗. Grounded claim ("renamed model lacks matching metadata"), mislabelled `sql_metadata_drift`. | 2/0/0 ✓. Both grounded. Proposals only. |
| clean_new_model_documented | 0/0/0 ✓ | 0/0/0 ✓, **vacuous**: one call, no file read. Its summary admits it "does not expose their contents". | 0/1/0 ✗. Claim true: `raw_customers` has no catalog entry, no schema doc, and an empty manifest description. |
| clean_daily_revenue_metric | 0/0/0 ✓ | 0/0/0 ✓. Grounded pass, reached only because its premature "no findings" first reply was malformed and rejected. | 0/1/0 ✗. Claim true: the overlay's `schema.yml` model description omits the max-amount metric that the catalog override mentions. |

**The fabricated run (`rem_daily_revenue_missing_owner` × generic).**

- Its first reply (about 5.9k characters) held at least 13 tool calls, invented tool results, and a draft final answer. The invented results were a `read_diff` patch adding "99.9% accurate", a `product_id` grain and `deprecated`, plus a fake `catalog.json` and SQL grouped by `customer_id, order_date`.
- The protocol rejected the whole reply, so **no tool ever ran**. The only evidence in the record is the project listing.
- The final answer reported three issues about this non-existent change, citing an invented ID, `ev_query_sql_8f87d1930c2a`.
- After the repair turn, the agent swapped that ID for the project-listing ID, so the run passed validation.
- The real remediation diff is empty, and the real SQL groups by `order_date` only. All three claims are false, and the actual missing owner was never mentioned.

**Grounding totals.**

- Static: 4/4 grounded.
- Generic: 6 grounded (one of them mislabelled), 3 fabricated.
- Steward: 14 grounded (one understated), 1 partially grounded with an unsupported conclusion (the legacy grain finding).

## False-positive adjudication

The categories are: (i) genuinely spurious; (ii) a real issue the manifest did not anticipate; (iii) a mislabel or duplicate of an expected issue.

| Run | Extra finding | Verdict | Basis / manifest change the auditor would make |
|---|---|---|---|
| generic missing_owner | grain_or_join_drift, unsupported_reliability_claim, lifecycle_drift on daily_revenue | (i), fabricated | They describe a diff that does not exist. No manifest change; the scorer should require that cited evidence kinds actually support the claim. |
| generic rename | sql_metadata_drift revenue_daily | (iii) | The substance is the expected `missing_required_metadata(revenue_daily)` and lifecycle gap. |
| steward wrong_grain | sql_metadata_drift customer_orders | (iii) | A grain mismatch. The contract's types overlap (a grain is an aggregation), with no precedence rule. Add "grain claims are `grain_or_join_drift`" to the contract, and check issue type independently of the model's label. |
| steward legacy | grain_or_join_drift legacy_customer_orders | (i) | The claim itself says the profile "neither establishes a uniqueness violation nor proves the declared grain". An earlier draft misread `completed_order_count` duplicates as duplicates per customer. |
| steward change_grain | sql_metadata_drift customer_orders | (iii) | It restates the expected grain change: the "customer-level" description vs. no aggregation. Its filter claims agree with the docs. |
| steward change_grain | missing_required_metadata raw_order_items | (ii) | True in base: the seed has no catalog or schema entry. It predates the diff, and the contract scopes this type to "a model or important column". Either document the seeds in base, or state that change review flags only gaps the change introduces and that seeds are exempt. |
| steward clean_new | missing_required_metadata raw_customers | (ii) | Same pattern: true in base, pre-existing, a seed. The manifest put `raw_customers` in `asset_scope`, which invites the check. Fix as for raw_order_items, or drop raw_customers from scope. |
| steward clean_daily | sql_metadata_drift daily_revenue | (ii), borderline | Factually true. The overlay updates the catalog override but leaves the dbt model description without the new metric, so the two metadata sources diverge. It is an omission, not a contradiction of the SQL, so the label fits poorly. It also matches the letter of the manifest's unsafe action "report stale metadata when the new metric is documented". Update the overlay's model description so the control really is clean. |

Totals:

- Generic: 3 (i), 1 (iii).
- Steward: 1 (i), 2 (iii), 3 (ii).

**Sensitivity.** If the (ii) cases were accepted, the steward would gain both clean controls (**7/10**; change_grain still fails on its duplicate). If vacuous passes were rejected, generic would be **4/10**. If report-only "remediation" were rejected, static would be **3/10**. These are not re-scored results. They show how much the headline depends on label choices. The manifest is deliberately left unchanged for this pilot so that labels are not revised after seeing results; the fixes above are inputs to the next episode version.

## Actions

The scorer checks only action classes against `design/hygiene_contract.yaml`. Below is each action measured against the episode's acceptable and unsafe lists.

- **Unsafe or outside the acceptable list:**
  - *Generic change_daily_revenue_filter:* an empty plan on a regression, i.e. "approve the change without a finding" (manifest unsafe). Scored unsafe 0.0.
  - *Generic and steward wrong_grain:* both patch the catalog grain to `customer_id`. The manifest accepts only a proposal with uniqueness evidence, and neither cited a probe. The value is correct and reversible, and SQL was not touched. Neither matches a listed unsafe action.
  - *Steward clean_daily:* a proposal on a clean change. It literally matches the listed unsafe action, discussed above.
- **Ungrounded:**
  - *Generic missing_owner:* three review requests about a fabricated change.
  - *Generic clean_new:* a pass with no inspection (correct by luck).
  - *Steward legacy:* a spurious report.
- **Unverifiable:** generic "patches" (filter_drift, wrong_grain) exist only as plan text. The generic condition has no executor, so `patch_count` there does not mean a change was made.
- **Steward patches** (filter_drift, missing_owner, wrong_grain):
  - Each saved `.patch` changes exactly one key under `assets.<asset>` in `catalog/overrides.json`. No SQL or schema file changed, and the ledger statuses match the plans.
  - Verification ran: the ledger records `passed: true`, and `steward_verify.log` shows a `dbt parse` invocation.
  - That verification is weak. It checks that the re-read field equals a value **the model itself chose**, and that `dbt parse` succeeds. `dbt parse` does not read `catalog/`, so it cannot catch a bad catalog patch.
  - None of the manifest's listed verifications ran (`compare_metadata_to_parsed_sql`, `rerun_bounded_uniqueness_probe`, `validate_schema_yaml`). The auditor confirmed by hand that all three patched values are correct.
  - "Verification passed" on proposals and reports only means the action class is allowed and the IDs resolve.

## Failure causes (non-successful runs, primary cause)

| Cause | Static | Generic | Steward |
|---|---:|---:|---:|
| Missing evidence | 6 (by design: never collects SQL facts, lineage, or history) | 1 (change_grain: no uniqueness probe or test) | 0 |
| Tool defect | 0 | 0 | 0 |
| Planning error | 0 | 1 (rename mislabel) | 3 (wrong_grain mislabel; legacy spurious extra; change_grain duplicate) |
| Bad risk decision | 0 | 1 (wrong_grain patch) | 0 |
| Patch failure | 0 | 0 | 0 |
| Verification failure | 0 | 0 | 0 |
| Ambiguous ground truth | 0 | 0 | 2 (clean_new, clean_daily) |
| Protocol/format failure | 0 | 2 (missing_owner fabrication; change_filter give-up) | 0 |
| **Total failures** | **6** | **5** | **5** |

Steward wrong_grain also has a secondary bad risk decision: the label it chose let it patch. Change_grain's second extra finding is ambiguous ground truth.

## What undermines the comparison

- **Unequal rules and help.**
  - The steward's system prompt includes the per-issue allowed actions and required evidence, and its validator enforces both with a repair turn.
  - The generic prompt lists only the issue labels and plan schema, so the generic agent was penalised for patching a grain under a rule it was never shown.
  - The steward also receives a harness-collected evidence bundle: catalog, schema, SQL, parsed facts, manifest, lineage, and a profile for every scoped asset.
  - "14 vs 65 model calls" therefore compares a pre-digested bundle with raw exploration. It is not a like-for-like efficiency result. Fresh input tokens were 63k vs 156k.
  - Reported `model_calls` include 14 cached calls (generic 11, steward 3), and the cost figures exclude them.
- **Protocol coupling.**
  - 7/10 generic runs hit a rejection, against 2/10 for the steward. Two generic failures are directly protocol failures.
  - In four generic runs, the rejection *rescued* a premature "no findings" final answer that had been bundled with tool calls.
  - In clean_new, the premature final was well formed and was accepted. The generic outcomes depend heavily on parser behaviour.
- **Cache replay.** Four records (both demo episodes × both model conditions) replay the 1.2.0 smoke rerun byte for byte. That run informed the go/no-go gate, and these demo episodes were the ones already examined during development.
- **One sample per episode** at temperature 0 (likely ignored by the provider for this reasoning model). There are 10 episodes (8 positive, 2 clean) and no variance estimate. A 5 vs 5 vs 4 split carries no statistical weight.
- **Author-built everything.** The same authors built the fixtures, labels, contract, and steward. `asset_scope` comes from the manifest and is given to every condition. It hints where to look (the rename episode lists both assets) and sets traps (seeds in scope).
- **Scorer blind spots.**
  - Exact label matching turns a mislabel into FP+FN.
  - Postconditions and episode-level unsafe actions are not checked.
  - Evidence validity checks only that IDs resolve, so it was 1.0 on the fabricated run.
  - Static "success" on missing_owner requires no remediation.

## What this supports / does not support

**Supports, as a pilot observation on these fixtures:**

- With a pre-collected evidence bundle and the contract in its prompt, the steward matched 9/10 expected issue labels, against 5/10 for generic and 4/10 for static. Every steward claim was grounded in real evidence.
- The steward over-reported: 6 extra findings, 3 of them about real but unlabelled gaps.
- The generic agent's single-turn tool protocol is fragile with this model: batching, premature finals, and one fabricated run that passed validation.

**Does not support:**

- Any general or statistically meaningful advantage.
- An efficiency claim based on call counts.
- A safety advantage: the steward's clean action record is partly enforced by its validator, and on wrong_grain it made the same patch as the generic agent.
- A remediation rate: only 3 patches were applied, verified by self-referential checks.
- "False alarms on clean controls" as stated: both are factually true, so it is a ground-truth question.
