#!/usr/bin/env bash
# Run one new sample; inputs are snapshots, not expected labels. Requires authenticated Codex CLI.
set -euo pipefail
case "${1:-}" in
  a|b) case_name=$1 ;;
  *) printf 'Usage: %s a|b\n' "$0" >&2; exit 2 ;;
esac
root=$(cd "$(dirname "$0")" && pwd)
run=$(mktemp -d "${TMPDIR:-/tmp}/catalog-codex-${case_name}-XXXXXX")
mkdir "$run/workspace" "$run/results"
tar -xf "$root/inputs/case_${case_name}_before.tar" -C "$run/workspace"
printf '%s\n' "$run" >&2
cd "$run/workspace"
codex --version > "$run/results/version.txt" 2>&1
codex exec --ignore-user-config --model gpt-6.1-terra -c 'model_reasoning_effort="medium"' --sandbox workspace-write --skip-git-repo-check --ephemeral --json -o "$run/results/final.json" - < "$root/inputs/prompt_${case_name}.txt" > "$run/results/events.jsonl" 2> "$run/results/stderr.txt"
