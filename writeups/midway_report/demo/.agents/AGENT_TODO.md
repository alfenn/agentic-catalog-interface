# Midway demo redo: plan

Source of the task: `.agents/feedback/FEEDBACK.md` (three-part script, slides as a PDF with a
live-run slide, redo the script and commands from scratch). Source of the story and numbers:
`../report.md` (Sections 2.1, 3.2, 3.3) and `experiments/results/codex_baseline_v1/analysis.md`.
Constraints: 3:00 hard limit (`../requirements/video.md`), no paid or live model calls while
preparing, no cost figures, the recount ties frontier-Codex and does not beat it.

## Decisions

- [x] Walkthrough example for part 2: **Revenue filter changed** (`change_daily_revenue_filter`).
  It is short to show (a one-line SQL diff against a one-sentence catalog description), all
  three conditions find the problem, and it carries part 3: the steward asks for a review,
  while both Codex runs rewrite the catalog to accept the new revenue definition and still
  score as successes.
- [x] Live step: run the evaluation CLI on that one example with the steward condition
  (needs `OPENROUTER_API_KEY`), then print its finding and score from the result file. Offline
  fallback: the same command with the static condition, which needs no key.
- [x] Report table: `make report` rebuilds Table 1 from the saved runs; the slides carry a
  simplified success grid of the same table.
- [x] Slides: LaTeX Beamer, 16:9, source `slides.tex` next to `slides.pdf`, built with latexmk.
  Reuse `../figures/architecture.pdf`. Do not reuse `figures/` here: those charts compare the
  pilot's static and generic conditions, not Codex, so they no longer match the report.

## Checklist

- [x] Read the requirements, report, README, Makefile, experiments index, both audits and the
  saved results for the walkthrough example; check CLI flags with `--help` and the code.
- [x] Check offline that `make report` and `make fixture EPISODE=change_daily_revenue_filter`
  work, and note that `make report` rewrites the three PDFs with timestamp-only changes.
- [x] Write `demo_commands.sh` from scratch: before-recording setup, part 2 commands (diff,
  catalog text, answer key, live run, score, Codex's saved patch, report table), each with a
  one-line comment; mark the steps that need a key or a Codex login.
- [x] Run every offline command in it; check the live commands' flags against the code.
- [x] Write `slides.tex` (sparse, about ten slides, one per beat) and build `slides.pdf`.
- [x] Render every page to PNG and inspect it; fix overflow, clipping or small text.
- [x] Write `demo_script.md` from scratch: three parts with timings under 3:00, word-for-word
  narration, an on-screen cue (slide and command) per beat, the slide build command, and a
  facts list tying each number to the report.
- [x] Check every number in the script and slides against the report and saved results; check
  that no file uses the word the brief bans and none gives cost figures.
- [x] Leave the worktree clean (restore PDFs rewritten by `make report`), commit, report done.

## Notes for review

- The live command was not run while preparing this (it needs `OPENROUTER_API_KEY` and makes a
  paid call). Its flags and result path were checked against `evaluation.py` and `--help`, its
  `jq` filter was run on the saved steward result, and its no-key exit was checked.
- `docs/midpoint_demo.md` and the README's pointer to it still describe the old demo; they are
  outside this folder and were left unchanged.
- `figures/` here holds the old pilot charts; nothing in the new demo uses them, and they were
  left in place.
