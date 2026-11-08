# Static pilot audit

The recorded **4/10 episode successes** and all per-episode finding precision and recall values agree with the frozen manifest and `midpoint-score-v1` set-matching rules. This is safe to cite as the **recorded static-baseline pilot result on these ten fixtures**, with the limitations below; it is not evidence that four tasks were remediated or that the method generalizes. The corrected runner regenerated the raw pilot files, and the outcome remained 4/10.

I independently compared each result's `(issue_type, asset)` set to `data/episodes/manifest.yaml`, checked each individual `static.json` against `summary.json`, and inspected the changed-grain and rename diffs, dbt results, and build logs. The ten recorded runs are complete. There are 4 true positives, 0 false positives, and 6 false negatives: micro precision **4/4 = 1.00**, micro recall **4/10 = 0.40**. Macro precision is **0.60** and macro recall **0.50**. Macro scores use the scorer's conventions: no predictions on a positive episode gives precision and recall 0; an empty prediction on a clean episode gives both 1. The two clean changes both pass; two of eight positive episodes succeed. All four predicted findings are reports, with no patches or model calls.

| Episode | Expected vs. observed | Precision / recall | Success |
|---|---|---:|---|
| rem_daily_revenue_filter_drift | SQL/metadata drift missed | 0 / 0 | No |
| rem_customer_orders_wrong_grain | Grain drift missed | 0 / 0 | No |
| rem_daily_revenue_missing_owner | Missing metadata detected | 1 / 1 | Yes |
| rem_legacy_model_lifecycle | Lifecycle drift missed | 0 / 0 | No |
| change_daily_revenue_filter | SQL/metadata drift missed | 0 / 0 | No |
| change_customer_orders_grain | Reliability failure detected; grain drift missed | 1 / 0.5 | No |
| change_new_model_missing_metadata | Missing metadata detected | 1 / 1 | Yes |
| change_rename_without_lifecycle | Replacement's missing metadata detected; old model's lifecycle drift missed | 1 / 0.5 | No |
| clean_new_model_documented | No finding expected or produced | 1 / 1 | Yes |
| clean_daily_revenue_metric | No finding expected or produced | 1 / 1 | Yes |

The grain-change dbt artifact records a failed `unique_customer_orders_customer_id` test (3 violating results), supporting the reported reliability finding, while its diff and expected labels require a separate grain finding. The rename diff removes `daily_revenue.sql` and adds `revenue_daily.sql`; its build succeeds, but the test artifact contains zero selected tests. A zero-test invocation is therefore not evidence of test coverage. The static baseline checks required fields and declared dbt tests, and does not inspect semantic alignment or lifecycle transitions, explaining these misses.

Two defects were identified and corrected before the pilot was regenerated. First, a dbt invocation that failed before writing results could silently reuse build results or appear clean. The runner now removes the prior results and reports missing results, execution errors, and unattributable test failures as errors; ordinary attributable failed tests still generate findings. Second, duplicate findings could make action rates exceed 1 because actions were counted per finding while denominators counted unique pairs. Correct actions are now counted per matching pair and unsafe actions per submitted finding. The regenerated pilot has the same finding sets and 4/10 result; its dbt test artifacts are fresh test invocations, and there are no duplicate findings. Attribution of failed tests still relies on asset names in dbt test IDs and can be ambiguous for custom test names.

The score measures exact issue/asset matching and allowed action **classes**, not whether an action meets episode-specific postconditions, whether cited evidence supports a claim, or whether a remediation was performed. The missing-owner episode counts as successful even though static only reports the missing owner and does not patch it. Evidence validity checks IDs, and empty results receive a vacuous 1.0; it does not establish evidentiary sufficiency. Success also does not require valid evidence. These fixtures and this single deterministic baseline provide no agent comparison, uncertainty estimate, or external validity. Do not cite the 40% as a remediation rate or a general performance estimate.
