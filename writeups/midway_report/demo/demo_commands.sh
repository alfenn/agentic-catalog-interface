#!/usr/bin/env bash
# Commands for the interactive midway demo. demo_script.md says when each one runs.
#
# Run one part from anywhere in the repository:
#
#   writeups/midway_report/demo/demo_commands.sh setup     # before recording
#   writeups/midway_report/demo/demo_commands.sh steward   # 0:00 live steward shell: paste paste.txt   NEEDS OPENROUTER_API_KEY
#   writeups/midway_report/demo/demo_commands.sh codex     # 0:30 the saved Codex run on the same example
#   writeups/midway_report/demo/demo_commands.sh score     # 1:00 score both, step by step (press Enter)
#   writeups/midway_report/demo/demo_commands.sh compare   # 2:00 the two runs side by side
#   writeups/midway_report/demo/demo_commands.sh tidy      # after recording
#
# EXAMPLE=change_customer_orders_grain swaps the example; CODEX=codex-frontier shows the
# frontier Codex run instead of the matched one. Only "steward" calls a model.

set -euo pipefail
cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
EXAMPLE="${EXAMPLE:-change_daily_revenue_filter}"
CODEX="${CODEX:-codex-matched}"
PS4='$ '  # print each command before it runs

setup() {
  set -x
  # Install the locked dependencies (dbt, DuckDB).
  make sync
  # Check that a key is configured for the live steward run (no model call).
  make doctor-live
}

steward() {
  # Builds a fresh copy of the example, then waits for the task; paste paste.txt.
  set -x
  uv run python -m catalog_steward.demo steward --example "$EXAMPLE"
}

codex() {
  set -x
  uv run python -m catalog_steward.demo codex --example "$EXAMPLE" --codex "$CODEX"
}

score() {
  set -x
  uv run python -m catalog_steward.demo score --example "$EXAMPLE" --codex "$CODEX"
}

compare() {
  set -x
  uv run python -m catalog_steward.demo compare --example "$EXAMPLE" --codex "$CODEX"
}

tidy() {
  set -x
  # Remove the live results and workspaces (all under the ignored .runs/ folder).
  rm -rf .runs/demo
}

case "${1:-}" in
  setup | steward | codex | score | compare | tidy) "$1" ;;
  *) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
