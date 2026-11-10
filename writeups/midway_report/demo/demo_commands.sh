#!/usr/bin/env bash
# Commands for the midway demo video. demo_script.md says when each one runs.
#
# Every command below is plain shell, run from the repository root, so you can copy
# them one at a time. Or run one part (from anywhere in the repository):
#
#   writeups/midway_report/demo/demo_commands.sh setup     # before recording
#   writeups/midway_report/demo/demo_commands.sh example   # part 2: the example and its answer key
#   writeups/midway_report/demo/demo_commands.sh live      # part 2: run and score it    NEEDS OPENROUTER_API_KEY
#   writeups/midway_report/demo/demo_commands.sh offline   # part 2 fallback: same, static checks, no key
#   writeups/midway_report/demo/demo_commands.sh table     # part 2: rebuild the report table from saved runs
#   writeups/midway_report/demo/demo_commands.sh codex     # part 3: what Codex did on the same example
#   writeups/midway_report/demo/demo_commands.sh tidy      # after recording
#
# Only "live" calls a model. Nothing here needs a Codex login; the saved Codex runs are
# shown from experiments/results/codex_baseline_v1/.

set -euo pipefail
cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
PS4='$ '  # print each command before it runs

setup() {
  set -x
  # Install the locked dependencies (dbt, DuckDB, the report toolchain).
  make sync
  # Build the walkthrough example: a fresh dbt project and DuckDB warehouse under .runs/.
  make fixture EPISODE=change_daily_revenue_filter
  # Build slides.pdf from slides.tex, then remove the LaTeX byproducts.
  latexmk -pdf -cd -quiet -interaction=nonstopmode writeups/midway_report/demo/slides.tex
  latexmk -c -cd -quiet -e '$clean_ext="nav snm vrb"' writeups/midway_report/demo/slides.tex
  # Check that a key is configured for the live run (no model call). Fails without one: use "offline".
  make doctor-live
}

example() {
  set -x
  # The proposed change: revenue now keeps every order that is not cancelled, so refunds count.
  cat .runs/change_daily_revenue_filter/input.diff
  # What the catalog still says about daily_revenue: refunded orders are excluded.
  jq '.assets[] | select(.name == "daily_revenue") | .description' .runs/change_daily_revenue_filter/project/catalog/catalog.json
  # The answer key: the problem to report, and the acceptable and unsafe responses.
  grep -A18 'id: change_daily_revenue_filter' data/episodes/manifest.yaml
}

live() {
  set -x
  # Run the steward on this one example and score it against the answer key (a paid model call).
  uv run python -m catalog_steward.evaluation --conditions steward --live --episodes change_daily_revenue_filter --output .runs/demo-live
  # What the steward reported, what it did, and how the scorer graded it.
  jq '{finding: (.result.plan.findings[] | {issue_type, asset, action: .action.class}), questions: .result.plan.unresolved_questions, score: (.score | {true_positives, false_positives, false_negatives, episode_success})}' .runs/demo-live/change_daily_revenue_filter/steward.json
}

offline() {
  set -x
  # The same evaluation with the rules-only static checks: no model and no key.
  uv run python -m catalog_steward.evaluation --conditions static --episodes change_daily_revenue_filter --output .runs/demo-offline
  # Static checks see no problem here (dbt tests still pass), so the scorer counts a miss.
  jq '{findings: .result.plan.findings, score: (.score | {true_positives, false_positives, false_negatives, episode_success})}' .runs/demo-offline/change_daily_revenue_filter/static.json
}

table() {
  set -x
  # Rebuild the report's figures, Table 1 and report.pdf from the saved runs (no model calls).
  make report
  # Example successes behind Table 1: the steward's saved run, then both Codex runs.
  jq '.by_condition.steward.episode_successes' experiments/results/midpoint_v1_2_pilot/summary.json
  jq '.by_condition | map_values(.episode_successes)' experiments/results/codex_baseline_v1/summary.json
  # Open the rebuilt report; Table 1 is on page 3.
  open writeups/midway_report/report.pdf
}

codex() {
  set -x
  # Matched-Codex's edit to the catalog: it accepts the new revenue definition before any review.
  cat experiments/results/codex_baseline_v1/change_daily_revenue_filter/codex-matched_artifacts/workspace.diff
  # Frontier-Codex made the same kind of edit.
  cat experiments/results/codex_baseline_v1/change_daily_revenue_filter/codex-frontier_artifacts/workspace.diff
  # Both still score as successes: the scorer checks only that a patch is allowed for the issue type.
  jq '{condition: .result.condition, action: .result.plan.findings[0].action.class, success: .score.episode_success}' experiments/results/codex_baseline_v1/change_daily_revenue_filter/codex-matched.json experiments/results/codex_baseline_v1/change_daily_revenue_filter/codex-frontier.json
}

tidy() {
  set -x
  # make report and the slide build rewrite these PDFs even when only their timestamps change.
  # Restore them (skip this if you edited the report or the slides and want the new PDFs).
  git checkout -- writeups/midway_report/report.pdf writeups/midway_report/appendix.pdf writeups/midway_report/figures/architecture.pdf writeups/midway_report/demo/slides.pdf
  # Remove the demo's scratch runs (all under the ignored .runs/ folder).
  rm -rf .runs/demo-live .runs/demo-offline .runs/evaluation/demo-live .runs/evaluation/demo-offline
}

case "${1:-}" in
  setup | example | live | offline | table | codex | tidy) "$1" ;;
  *) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
