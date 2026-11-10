# Midway demo video: script

A three-minute video in three parts: the project, the evaluation (with one example run
live), and what the results mean. It follows the midway report (`../report.md`): every
number below is from its Table 1 and Section 3.3.

- **Length:** about 2:50 of narration, under the 3:00 limit in `../requirements/video.md`.
  About 420 words at roughly 150 words per minute.
- **Slides:** `slides.pdf` (source `slides.tex`, 11 slides). Build it from the repository root:

  ```sh
  latexmk -pdf -cd -quiet -interaction=nonstopmode writeups/midway_report/demo/slides.tex
  latexmk -c -cd -quiet -e '$clean_ext="nav snm vrb"' writeups/midway_report/demo/slides.tex
  ```

- **Commands:** `demo_commands.sh`. Each part is a short list of plain commands, each with a
  one-line comment, and the script prints each command before it runs it. Run a part with
  `writeups/midway_report/demo/demo_commands.sh <part>` from anywhere in the repository, or
  copy single commands and run them from the repository root.
- **Walkthrough example:** *Revenue filter changed* (`change_daily_revenue_filter`). It is
  quick to explain, the steward handles it the way the answer key wants, and it is also the
  example where the scorer passed both Codex runs for accepting a change before review, which
  part 3 needs.

## What needs a key or a login

| Part of `demo_commands.sh` | Needs | Used in the video |
|---|---|---|
| `setup` | nothing (its last step, `make doctor-live`, only checks that a key is set and fails without one) | before recording |
| `example` | nothing | optional (slide 5 shows the same content) |
| `live` | **`OPENROUTER_API_KEY`** in `.env`: it makes a paid model call | beat 6 |
| `offline` | nothing: the same evaluation with the rules-only static checks | beat 6, if there is no key |
| `table` | nothing (no model calls) | beat 7 |
| `codex` | nothing: it shows the saved Codex runs | optional (slide 9 shows the same content) |
| `tidy` | nothing | after recording |

Nothing in the video needs a Codex login. Rerunning Codex itself is described in the
[README's Codex baseline section](../../../README.md#codex-baseline) and needs the Codex CLI,
logged in; it is not part of the demo.

## Before recording

1. Run `writeups/midway_report/demo/demo_commands.sh setup`. It installs dependencies, builds
   the example's fixture and the slides, and checks that a key is configured. If it ends with
   `OPENROUTER_API_KEY is required`, use `offline` instead of `live` in beat 6.
2. Open `slides.pdf` full screen (Preview: View > Slideshow).
3. Open a terminal at the repository root with a large font (20 pt or more) and a clean
   prompt. Do not show `.env`.
4. Rehearse beat 6 once off camera. A live run builds the example (about 5 s) and then waits
   for the model; the evaluation prints only its output folder at the end, and the `jq` line
   after it prints the finding and score. If the wait is long, cut it in editing.
5. After recording, run `writeups/midway_report/demo/demo_commands.sh tidy`. It restores the
   PDFs that `make report` and the slide build rewrite with timestamp-only changes, and removes
   the scratch runs under `.runs/`.

## Run sheet

| # | Time | On screen | Command |
|---|---|---|---|
| | **Part 1: the project** | | |
| 1 | 0:00–0:08 | Slide 1, title | none |
| 2 | 0:08–0:26 | Slide 2, *Catalog metadata drifts away from the code* | none |
| 3 | 0:26–0:43 | Slide 3, *The harness: inspect, plan, validate, act* | none |
| | **Part 2: the evaluation** | | |
| 4 | 0:43–1:01 | Slide 4, *Evaluation: ten examples, each with an answer key* | none |
| 5 | 1:01–1:15 | Slide 5, *Example: Revenue filter changed* | none |
| 6 | 1:15–1:38 | Slide 6, *Live: run and score this example*, then the terminal | `demo_commands.sh live` (or `offline`) |
| 7 | 1:38–1:51 | Terminal, then slide 7, *The report table: make report* | `demo_commands.sh table` |
| | **Part 3: the results** | | |
| 8 | 1:51–2:12 | Slide 8, *Why the steward scored lower* | none |
| 9 | 2:12–2:29 | Slide 9, *The scorer passed an unreviewed change* | none |
| 10 | 2:29–2:38 | Slide 10, *Both eval errors fixed: a tie with frontier-Codex* | none |
| 11 | 2:38–2:52 | Slide 11, *Next* | none |

## Narration

### Part 1: the project (0:00–0:43)

**1 · 0:00–0:08 · Slide 1**
> Hi, I'm Alex Feng. My project is about agent tool interfaces for data catalogs.

**2 · 0:08–0:26 · Slide 2**
> A data catalog says what each table means. When the SQL changes, the description often
> doesn't, and people trust the wrong number. My catalog steward repairs this drift and reviews
> proposed changes. The question: does a specialized harness beat a general coding agent with
> the same access?

**3 · 0:26–0:43 · Slide 3**
> The harness first gathers an evidence bundle: catalog metadata, parsed SQL, lineage and data
> profiles, each with a stable ID. The model returns findings citing those IDs. A validator
> checks them, and each becomes a patch, a review proposal, or a report.

### Part 2: the evaluation (0:43–1:51)

**4 · 0:43–1:01 · Slide 4**
> I built ten examples: remediation, flawed changes, and clean controls with nothing to find.
> Each has an answer key. Success means no missed problem, no extra, and an allowed action. I
> compare the steward with Codex on the same model, and on a frontier model.

**5 · 1:01–1:15 · Slide 5**
> In this example, a change makes revenue count every order that isn't cancelled, so refunds
> count. The catalog still says refunds are excluded. The right response: flag it, and ask
> whether refunds belong in revenue.

**6 · 1:15–1:38 · Slide 6, then the terminal: `demo_commands.sh live`** (start it as you begin
speaking)
> Let's run it live. This builds a fresh copy of the example, runs the steward, and scores it
> against the answer key.
>
> *(when the `jq` output appears)* It found the drift, proposed a review instead of a patch, and
> asked whether refunded orders belong in revenue. One found, no extras, nothing missed: a
> success.

If there is no key, run `demo_commands.sh offline` and say instead: *"Without a model, the
same evaluation runs the static checks. dbt's tests still pass, so they find nothing and the
scorer counts a miss. The steward's saved run on this example is the one on the slide."*

**7 · 1:38–1:51 · Terminal: `demo_commands.sh table`; when the report opens, cut to slide 7**
> `make report` rebuilds the report's table from the saved runs, with no model calls. As
> scored, the steward succeeds on five of ten, matched-Codex on six, and frontier-Codex on
> seven.

### Part 3: the results (1:51–2:52)

**8 · 1:51–2:12 · Slide 8**
> So the steward looks worse. But four of its five failures miss nothing; they fail only on
> extras. Three of those extras are real problems the answer key misses. One, a metric the dbt
> docs leave out, is the one example behind the gap to matched-Codex. Crediting real gaps gives
> seven, seven, and eight.

**9 · 2:12–2:29 · Slide 9**
> The scorer has a hole too. Here, both Codex runs rewrote the catalog to accept the new
> revenue definition before any review, and still passed: the scorer only checks that a patch
> is allowed for the issue type. Failing them gives seven, six, seven.

**10 · 2:29–2:38 · Slide 10**
> With both errors fixed, the steward ties frontier-Codex and leads matched-Codex. With one run
> on ten examples, small gaps may be noise.

**11 · 2:38–2:52 · Slide 11**
> Next: an eval loop that fixes the answer key, a scorer that fails patches skipping a review,
> about fifty human-reviewed examples with several runs each, and frontier-Codex's selective
> reading built into the steward's tools. Thanks!

## Video description (paste when uploading)

```text
CS329Z midway demo (Alex Feng): agent tool interfaces for data catalogs. A catalog steward
repairs drifted catalog metadata in a dbt + DuckDB project and reviews proposed changes. On ten
hand-built examples it is compared with OpenAI's Codex CLI on the same model and on a frontier
model. The video runs one example live and explains how answer-key and scorer errors understate
the steward.

Code, examples, saved runs and the midway report:
https://github.com/alfenn/agentic-catalog-interface
The demo's slides, script and commands are in writeups/midway_report/demo/.
```

## Facts behind the narration (for checking, not for reading aloud)

- **Beats 2 and 3:** report Sections 1 and 2.2 and Figure 1 (`../figures/architecture.pdf`,
  reused on slide 3).
- **Beat 4:** report Section 2.1: four remediation examples, four flawed changes, two clean
  controls; success needs no extra, no missed problem, no failed verification and an allowed
  action class. Conditions (Section 2.2): steward on `gpt-6-luna` at low effort; Codex CLI
  0.167.0 on the same model and effort (matched) and on `gpt-6.1-sol` at medium effort
  (frontier).
- **Beat 5:** the change is `where status = 'completed'` to `where status != 'cancelled'` in
  `models/daily_revenue.sql`. The catalog says "Completed-order revenue at one row per order
  date; refunded and cancelled orders are excluded." The answer key
  (`data/episodes/manifest.yaml`) expects `sql_metadata_drift` on `daily_revenue`; acceptable:
  "request a semantic decision about whether refunded orders belong in revenue"; unsafe:
  "silently redefine refunded orders as completed".
- **Beat 6:** the saved steward run
  (`experiments/results/midpoint_v1_2_pilot/change_daily_revenue_filter/steward.json`) reports
  `sql_metadata_drift` on `daily_revenue` with action `propose`, asks "Should daily_revenue
  exclude only cancelled orders, or also refunded orders?", and scores 1 found, 0 extra, 0
  missed, success. A new live run is a fresh sample: if its output differs, describe what it
  shows. The offline fallback (static checks) was run while preparing this script: no finding,
  0/0/1, no success.
- **Beat 7:** Table 1: steward 5/10, matched-Codex 6/10, frontier-Codex 7/10. `make report`
  took about 12 s while preparing this script and writes Table 1 on page 3 of `report.pdf`.
- **Beat 8:** report Section 3.3 and `experiments/results/codex_baseline_v1/analysis.md`. The
  steward's failures: *Wrong customer-order grain* (0/1/1, a mislabel that matched-Codex shared),
  *Legacy copy still active* (1/1/0, one spurious extra), *Grain changed, metadata not* (2/2/0,
  a restatement and the undocumented `raw_order_items` seed), *Documented new model* (0/1/0,
  the undocumented `raw_customers` seed, which all three runs flagged), *Documented revenue
  metric* (0/1/0, the dbt model description omits the new metric; the one example behind the
  gap to matched-Codex). Crediting the real-gap extras in every run gives 7/10, 7/10 and 8/10.
- **Beat 9:** in `experiments/results/codex_baseline_v1/change_daily_revenue_filter/`, both
  `workspace.diff` files rewrite the `daily_revenue` description to include refunded orders,
  and both runs score as successes. The scorer checks only that an action class is allowed for
  the issue type, not each example's acceptable actions (report Section 2.1). Failing those two
  runs as well gives 7/10, 6/10 and 7/10.
- **Beat 10:** the recount ties frontier-Codex; it does not beat it. Recall is 0.90 for the
  steward against 0.70 and 0.80 (Table 1). Runs vary: matched-Codex passed *Revenue filter
  changed* in two of three earlier tries (report Section 3.4).
- **Beat 11:** report Section 3.4.
