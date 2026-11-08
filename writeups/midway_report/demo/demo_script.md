# Midway demo video: script and run sheet

Target length **2:45** (hard limit 3:00, per `../video__requirements.md`). One speaker. About 405 words of narration at roughly 147 words per minute. Every command is in [`demo_commands.sh`](demo_commands.sh). Run `./demo_commands.sh N` from any directory; the script `cd`s to the repository root itself. Each segment prints a banner, then the command it runs (prefixed `$`), then a few lines of compact output.

All numbers on screen come from `experiments/results/midpoint_v1_2_pilot/` (frozen config 1.2.0, 10 episodes × 3 conditions). The charts are generated from its `summary.json` by `../make_figures.py`. Nothing is typed by hand.

## Video description (paste when uploading)

Paste this as the YouTube or Google Drive description:

```text
CS329Z midway demo (Alex Feng). A catalog steward: an LLM agent that repairs stale data-catalog metadata with evidence, then reviews later dbt changes so the drift does not come back. It is compared with static checks and a generic coding agent on ten constructed maintenance episodes.

GitHub repository (code, fixtures, episode labels, frozen config and prompts, raw pilot results, and the manual audit):
https://github.com/alfenn/agentic-catalog-interface

The README covers setup and reproducing the pilot. The demo's script and commands are in writeups/midway_report/demo/.

Note: the steward runs shown are replays of the recorded pilot from the response cache (identical inputs, no new model calls). In the pilot itself, the generic-agent and steward records for these two demo episodes are cache replays of the final smoke run under the same frozen configuration.
```

## Before recording

1. **Setup (about 25 s, off camera):** from the repository root, run
   `writeups/midway_report/demo/demo_commands.sh prep`. It runs `make sync`, builds both episode fixtures (`make fixture`), regenerates the three chart PNGs into `figures/`, replays both steward runs from the response cache with a spend cap, checks that the replayed plans match the pilot byte for byte and that `make costs` is unchanged, and warms `uv`. It must end with **`ready: segments 3 and 5 will replay at $0`**. If it prints `not ready`, record segments 3 and 5 with `DEMO_SAVED=1` (see the fallbacks below).
2. **Cost check:** run `make costs` before and after recording. Both should read `97 calls | … | $0.0244` (the recorded total as of 2026-11-08). The on-camera replays make no provider call: they run with `CATALOG_STEWARD_BUDGET_USD=0.000001`, so a cache miss raises `BudgetExceeded` instead of paying.
3. **Terminal:** use a dark or light theme with high contrast, a font size of at least **20 pt** (about 100 columns across a 1920 px screen), and a window that fills the screen. Run `clear` before each segment. Lines are up to about 230 characters, so turn on soft wrap. Do not show `.env`.
4. **Windows to pre-open:**
   - the terminal, at the repository root, with `prep` already finished;
   - an optional title card with the project name and your name (segment 1);
   - `figures/outcome_grid.png` and `figures/findings_vs_false_alarms.png` in Preview (segment 7 also opens them with `open`; set `DEMO_NO_OPEN=1` if they are already open);
   - optional backup: `figures/success_by_category.png`.
5. **Rehearse once:** run `./demo_commands.sh time`, which runs segments 1 to 7 silently and prints each one's wall time. It should be close to the measured times below.
6. Afterwards, `./demo_commands.sh clean` removes the scratch replay folders (all under the gitignored `.runs/`).

## Run sheet

Timestamps are for the narration. Start each command at the start of its segment and talk over its output. "Measured" is wall time on the author's machine on 2026-11-08, after `prep`, from two `./demo_commands.sh time` runs (identical to 0.1 s).

| # | Time | On screen | Command | Measured |
|---|------|-----------|---------|----------|
| 1 | 0:00–0:21 | Title card, then the terminal: contract modes, issue types and action surface | `./demo_commands.sh 1` | 0.1–0.3 s |
| 2 | 0:21–0:43 | Catalog description vs the SQL `where` line, then the parsed-SQL evidence ID and filter | `./demo_commands.sh 2` | 0.2–0.3 s |
| 3 | 0:43–1:12 | Spend before/after (unchanged); the steward's finding and cited evidence IDs; the patch diff; verification checks; two ledger lines | `./demo_commands.sh 3` | 5.4 s |
| 4 | 1:12–1:32 | The change diff (`completed` → `!= 'cancelled'`); dbt tests pass; catalog text = the step-3 patch | `./demo_commands.sh 4` | < 0.1 s |
| 5 | 1:32–1:55 | Spend unchanged; the finding, the claim, `propose / request_review`, `status=proposed patch=none`, two open questions | `./demo_commands.sh 5` | 4.3 s |
| 6 | 1:55–2:15 | A six-row table: both episodes × static/generic/steward | `./demo_commands.sh 6` | < 0.1 s |
| 7a | 2:15–2:24 | Terminal pilot table, then `outcome_grid.png` full screen | `./demo_commands.sh 7` | < 0.1 s (+ Preview opening) |
| 7b | 2:24–2:45 | `findings_vs_false_alarms.png` full screen | none | n/a |

Command time totals about 10 s, all covered by narration. Narration is about 405 words over 165 s, which leaves 15 s of margin under the limit.

## Narration (word for word)

**1 · 0:00–0:21: Problem** (`./demo_commands.sh 1`)
> Data catalogs go stale. A table's description says one thing, the SQL that builds it does another, and analysts trust the wrong number. Our catalog steward is an LLM agent that repairs that drift with evidence and reviews later changes so it doesn't come back. Its contract allows only reviewable patches or proposals.

**2 · 0:21–0:43: Stale claim vs SQL evidence** (`./demo_commands.sh 2`)
> This is a local dbt and DuckDB fixture. The catalog says daily revenue covers all orders. The model's SQL keeps completed orders only. The steward doesn't trust either text on its own: it parses the SQL into evidence with a stable ID, here the filter status equals completed, and every claim must cite such IDs.

**3 · 0:43–1:12: Patch, verification, ledger** (`./demo_commands.sh 3`, start it as you begin speaking)
> Now the steward runs in remediation mode. This replays the recorded pilot run from our response cache, so the spend before and after is identical. It proposes one patch: rewrite the catalog description to say completed orders only, citing five evidence items, including that parsed SQL fact. The SQL is untouched. Verification re-reads the catalog and re-parses dbt. Both checks pass, and the ledger records the finding as verified.

**4 · 1:12–1:32: The later change** (`./demo_commands.sh 4`)
> Metadata goes stale again when code changes. In this second episode, a pull request changes the filter from completed to not cancelled, so refunded orders now count as revenue. The catalog still says refunds are excluded, which is exactly the text the steward wrote, and dbt tests still pass.

**5 · 1:32–1:55: Change-time review** (`./demo_commands.sh 5`, start it as you begin speaking)
> In change-review mode, the steward flags the contradiction, but it does not choose a revenue definition for the business. Whether refunds belong in revenue is a semantic decision, so the contract allows only a proposal: it requests review from the model owner, lists the open questions, and writes no patch. That escalation is the correct outcome here.

**6 · 1:55–2:15: Baselines on the same two episodes** (`./demo_commands.sh 6`)
> Compare the baselines on the same two episodes. Static required-field and dbt-test checks caught neither problem. A generic agent on the same model also fixed the first one, but on the change it batched several tool calls into one reply, was rejected, and gave up without a finding.

**7a · 2:15–2:24: Pilot outcomes** (`./demo_commands.sh 7`, then switch to `outcome_grid.png`)
> Across all ten pilot episodes, static checks succeeded on four, the generic agent on five, and the steward on five.

**7b · 2:24–2:45: Found issues vs false alarms, limitations** (switch to `findings_vs_false_alarms.png`)
> On this small, author-built pilot, the steward found nine of ten expected issues, against five for the generic agent, but tied on episode success: it raised six false alarms by our labels, including both clean controls. A hand audit showed three were real gaps our labels missed. Next: better labels, real verification, a larger study.

## Fallback if a command is slow or fails

| # | Live command | If slow or failing |
|---|--------------|--------------------|
| 1 | `make contract` via the module (0.1–0.3 s) | Keep talking over the title card. If it errors, skip the terminal: the narration does not depend on it. |
| 2 | Reads the fixture built in `prep`, plus `make evidence` (0.2–0.3 s) | If `.runs/rem_daily_revenue_filter_drift/` is missing, the read fails: run `make fixture EPISODE=rem_daily_revenue_filter_drift` off camera (about 5 s) and retake. The same evidence ID, `ev_parsed_sql_facts_05abec786ab2`, appears in the saved pilot result: `jq '.result.plan.findings[0].evidence_ids' experiments/results/midpoint_v1_2_pilot/rem_daily_revenue_filter_drift/steward.json`. |
| 3 | $0 cached steward replay (5.4 s) | Narration covers about 30 s, so a few extra seconds are fine. If the replay errors or spend changes, the script prints a yellow notice and shows the saved pilot artifacts automatically. To skip the replay entirely, run `DEMO_SAVED=1 ./demo_commands.sh 3`, and in the narration replace "This replays the recorded pilot run from our response cache, so the spend before and after is identical" with "These are the saved artifacts from the recorded pilot run". |
| 4 | Reads the change fixture built in `prep` (< 0.1 s) | If `.runs/change_daily_revenue_filter/` is missing, run `make fixture EPISODE=change_daily_revenue_filter` off camera (about 5 s), or show `experiments/results/midpoint_v1_2_pilot/change_daily_revenue_filter/steward_artifacts/input.diff`. |
| 5 | $0 cached steward replay (4.3 s) | Same as segment 3: `DEMO_SAVED=1 ./demo_commands.sh 5`. That segment's narration does not mention the cache, so no wording change is needed. |
| 6 | Reads saved pilot JSON (< 0.1 s) | No live dependency. |
| 7 | Reads `summary.json` and runs `open` on two PNGs (< 0.1 s) | If Preview is slow, use the pre-opened windows (`DEMO_NO_OPEN=1 ./demo_commands.sh 7`). |

## Facts behind the narration (for checking, not for reading aloud)

- **Segment 2:** `overrides.json` says "Revenue from all orders at one row per order date."; the SQL says `where status = 'completed'`. The steward's patch cites evidence `ev_parsed_sql_facts_05abec786ab2`, the same ID that `make evidence` prints.
- **Segment 3:** pilot `rem_daily_revenue_filter_drift/steward.json`. The action is `patch` on `description`, with five evidence IDs. The verification checks are "catalog description equals expected value: True" and "dbt parse succeeds after patch: True", with status `verified`. The ledger is `steward_artifacts/steward_ledger.jsonl`. The replay's plan is identical to the pilot's (checked by `prep`).
- **Segment 4:** the episodes reset independently from their own fixtures. The second does not carry the first's patch forward, but its catalog description is byte-identical to the steward's patched value, and the script checks that equality before printing the note. The static condition ran dbt tests on this change with no failures and no finding.
- **Segment 5:** action `propose / request_review`, status `proposed`, `patch_path` null, two unresolved questions. Episode success: true.
- **Segment 6:** remediation: static missed, generic success (patch), steward success (patch). Change: static missed. Generic missed: one rejected reply that put several tool calls in one message, then a final answer with no findings, saying it could not assess the change. Steward success (propose), also after one rejected reply.
- **Segment 7:** episode successes are static 4/10, generic 5/10 and steward 5/10. Found/false alarms are static 4/0, generic 5/4 and steward 9/6. The steward's false alarms include one on each clean control. The manual audit (`experiments/results/midpoint_v1_2_pilot/analysis.md`) classifies three of the steward's six extra findings, including both clean-control flags, as real fixture gaps the manifest did not anticipate; one is genuinely spurious and two are mislabels or duplicates of expected issues.
- **Disclosure (included in the video description above):** the four model records for these two demo episodes in the pilot (generic and steward) are exact cache replays of the config-1.2.0 smoke rerun, served by design because inputs and config were identical. Nothing was tuned in between. The total recorded model spend for the project is $0.0244.
