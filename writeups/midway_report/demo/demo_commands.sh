#!/usr/bin/env bash
# Command sequence for the 3-minute midway demo video (see demo_script.md).
#
#   ./demo_commands.sh prep     # run BEFORE recording (slow: dbt builds and figures)
#   ./demo_commands.sh 1 .. 7   # one segment each, run on camera (each finishes in a few seconds)
#   ./demo_commands.sh time     # rehearsal: run segments 1-7 and print each one's wall time
#   ./demo_commands.sh clean    # remove the scratch replay folders this script creates
#
# Segments 3 and 5 display saved pilot artifacts; they never invoke a model.
# DEMO_NO_OPEN=1 prevents segment 7 from opening chart PNGs.
# Prep writes fixtures under .runs/ and regenerates demo figures.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO" || exit 1

PILOT=experiments/results/midpoint_v1_2_pilot
REM=rem_daily_revenue_filter_drift
CHG=change_daily_revenue_filter
REPLAY_REM=.runs/demo-video-rem
REPLAY_CHG=.runs/demo-video-change
FIGS=writeups/midway_report/demo/figures
if [ "${DEMO_NO_JQ:-0}" != 1 ] && command -v jq >/dev/null 2>&1; then HAVE_JQ=1; else HAVE_JQ=0; fi
if command -v python3 >/dev/null 2>&1; then PY=(python3); else PY=(uv run --quiet python); fi

if [ -t 1 ]; then B=$'\033[1m'; D=$'\033[2m'; C=$'\033[36m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[0m'
else B=""; D=""; C=""; G=""; Y=""; R=""; fi

banner() { printf '\n%s━━ %s ━━%s\n' "$B$C" "$*" "$R"; }
step()   { printf '%s$ %s%s\n' "$D" "$*" "$R"; }
note()   { printf '%s%s%s\n' "$Y" "$*" "$R"; }
label()  { printf '%s%-14s%s %s\n' "$B" "$1" "$R" "$2"; }

# py FILE 'python expression using d' : print the result (fallback when jq is absent)
py() { "${PY[@]}" -c 'import json,sys
d=json.load(open(sys.argv[1]))
exec(sys.argv[2])' "$1" "$2"; }

# Saved artifacts are the only source for model results in this demo.
replay() { echo "$PILOT/$1"; }

seg1() {
  banner "1  Problem: catalog metadata drifts away from the SQL"
  step "make contract   # the steward's hygiene contract"
  local f; f=$(mktemp); uv run --quiet python -m catalog_steward.contract >"$f"
  if [ $HAVE_JQ = 1 ]; then
    jq -r '"modes:       \(.modes|join(", "))", "issue types: \(.issue_types|join(", "))", "actions:     \(.action_surface)  (no live catalog writes)"' "$f"
  else
    py "$f" 'print("modes:       "+", ".join(d["modes"])); print("issue types: "+", ".join(d["issue_types"])); print("actions:     "+d["action_surface"]+"  (no live catalog writes)")'
  fi
  rm -f "$f"
}

seg2() {
  banner "2  Stale claim vs SQL evidence  ($REM)"
  local w=.runs/$REM/project
  step "jq .assets.daily_revenue.description $w/catalog/overrides.json"
  if [ $HAVE_JQ = 1 ]; then label "catalog says" "$(jq -r .assets.daily_revenue.description "$w/catalog/overrides.json")"
  else label "catalog says" "$(py "$w/catalog/overrides.json" 'print(d["assets"]["daily_revenue"]["description"])')"; fi
  step "grep where $w/models/daily_revenue.sql"
  label "SQL does" "$(grep -i '^ *where' "$w/models/daily_revenue.sql" | sed 's/^ *//')"
  step "make evidence EPISODE=$REM ASSET=daily_revenue"
  local f; f=$(mktemp)
  uv run --quiet python -m catalog_steward.evidence "$REM" daily_revenue --kind sql >"$f"
  if [ $HAVE_JQ = 1 ]; then
    label "evidence id" "$(jq -r .id "$f")"
    label "parsed filter" "$(jq -r '.content.filters|join(" AND ")' "$f")"
  else
    label "evidence id" "$(py "$f" 'print(d["id"])')"
    label "parsed filter" "$(py "$f" 'print(" AND ".join(d["content"]["filters"]))')"
  fi
  rm -f "$f"
}

seg3() {
  banner "3  Steward remediation: evidence-backed patch, verification, ledger"
  local dir; dir=$(replay "$REM" "$REPLAY_REM")
  local res=$dir/steward.json art=$dir/steward_artifacts
  if [ $HAVE_JQ = 1 ]; then
    jq -r '.result.plan.findings[0] as $f |
      "finding:   \($f.issue_type) on \($f.asset)  ->  \($f.action.class) \($f.action.field)",
      "cites:     \($f.evidence_ids|join(" "))"' "$res"
  else
    "${PY[@]}" - "$res" <<'PY'
import json, sys
f = json.load(open(sys.argv[1]))["result"]["plan"]["findings"][0]
print("finding:   %s on %s  ->  %s %s" % (f["issue_type"], f["asset"], f["action"]["class"], f["action"]["field"]))
print("cites:     " + " ".join(f["evidence_ids"]))
PY
  fi
  step "cat $art/steward/*.patch"
  grep '^[-+] ' "$art"/steward/*.patch | sed "s/^-/${Y}-/; s/^+/${G}+/; s/\$/${R}/"
  if [ $HAVE_JQ = 1 ]; then
    jq -r '.result.verification[0] | "verify:    \(.status)  [\(.verification.checks|join("; "))]"' "$res"
    step "tail -2 $art/steward_ledger.jsonl"
    jq -r 'if .event == "run_summary" then "ledger:    run_summary  outcomes=\(.outcome_statuses|join(","))"
           else "ledger:    finding \(.finding_key)  status=\(.status)  patch=\(.patch_path|split("/")|last)" end' "$art/steward_ledger.jsonl"
  else
    "${PY[@]}" - "$res" <<'PY'
import json, sys
v = json.load(open(sys.argv[1]))["result"]["verification"][0]
print("verify:    %s  [%s]" % (v["status"], "; ".join(v["verification"]["checks"])))
PY
    step "tail -2 $art/steward_ledger.jsonl"
    "${PY[@]}" -c 'import json,sys
for line in open(sys.argv[1]):
    r=json.loads(line)
    if r.get("event")=="run_summary": print("ledger:    run_summary  outcomes="+",".join(r["outcome_statuses"]))
    else: print("ledger:    finding %s  status=%s  patch=%s" % (r["finding_key"], r["status"], r["patch_path"].split("/")[-1]))' "$art/steward_ledger.jsonl"
  fi
}

seg4() {
  banner "4  Independent change fixture: metadata is stale  ($CHG)"
  local w=.runs/$CHG
  step "cat $w/input.diff"
  sed -n '/^[-+][^-+]/p' "$w/input.diff" | sed "s/^-/${Y}-/; s/^+/${G}+/; s/\$/${R}/"
  local desc patched
  if [ $HAVE_JQ = 1 ]; then
    desc=$(jq -r '.assets[]? // .[]? | select(.name? == "daily_revenue") | .description' "$w/project/catalog/catalog.json" 2>/dev/null | head -1)
    patched=$(jq -r '.result.plan.findings[0].action.value' "$PILOT/$REM/steward.json")
    label "dbt tests" "$(jq -r '.result.verification[0] | if .dbt_tests_ran and (.failed_assets|length)==0 then "all pass after the change (static check: no finding)" else "failures: \(.failed_assets)" end' "$PILOT/$CHG/static.json")"
  else
    desc=$(py "$w/project/catalog/catalog.json" 'a=d.get("assets",d); a=a.values() if isinstance(a,dict) else a; print(next(x["description"] for x in a if isinstance(x,dict) and x.get("name")=="daily_revenue"))')
    patched=$(py "$PILOT/$REM/steward.json" 'print(d["result"]["plan"]["findings"][0]["action"]["value"])')
    label "dbt tests" "$(py "$PILOT/$CHG/static.json" 'v=d["result"]["verification"][0]; print("all pass after the change (static check: no finding)" if v["dbt_tests_ran"] and not v["failed_assets"] else "failures: %s" % v["failed_assets"])')"
  fi
  label "catalog says" "$desc"
  if [ "$desc" = "$patched" ]; then label "" "(the exact text the steward wrote in step 3)"; fi
}

seg5() {
  banner "5  Change-time review: flag and escalate, do not patch"
  local dir; dir=$(replay "$CHG" "$REPLAY_CHG")
  local res=$dir/steward.json
  if [ $HAVE_JQ = 1 ]; then
    jq -r '.result.plan.findings[0] as $f | .result.verification[0] as $v |
      "finding:   \($f.issue_type) on \($f.asset)",
      "claim:     \($f.claim)",
      "action:    \($f.action.class) / \($f.action.operation)   status=\($v.status)  patch=\($v.patch_path // "none")",
      (.result.plan.unresolved_questions[] | "question:  \(.)")' "$res"
  else
    "${PY[@]}" - "$res" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))["result"]
f, v = d["plan"]["findings"][0], d["verification"][0]
print("finding:   %s on %s" % (f["issue_type"], f["asset"]))
print("claim:     " + f["claim"])
print("action:    %s / %s   status=%s  patch=%s" % (f["action"]["class"], f["action"]["operation"], v["status"], v["patch_path"] or "none"))
for q in d["plan"]["unresolved_questions"]:
    print("question:  " + q)
PY
  fi
}

seg6() {
  banner "6  Same two episodes, all three conditions (saved pilot results)"
  step "summarize $PILOT/{$REM,$CHG}/{static,generic,steward}.json"
  "${PY[@]}" - "$PILOT" "$REM" "$CHG" <<'PY'
import json, sys
pilot = sys.argv[1]
row = "{:<31}{:<10}{:<9}{:<7}{:<9}{}"
print(row.format("episode", "condition", "result", "found", "action", "note"))
for ep in sys.argv[2:]:
    for cond in ("static", "generic", "steward"):
        d = json.load(open("%s/%s/%s.json" % (pilot, ep, cond)))
        s, r = d["score"], d["result"]
        findings = r["plan"]["findings"]
        acts = ",".join(f["action"]["class"] for f in findings) or "-"
        note = ""
        if r.get("protocol_rejections"):
            note = "%d rejected reply" % r["protocol_rejections"]
            if not findings:
                note += " (batched tool calls), then gave up"
        result = "success" if s["episode_success"] else "missed"
        print(row.format(ep, cond, result, "%d/1" % s["true_positives"], acts, note))
    print()
PY
}

seg7() {
  banner "7  Pilot: 10 episodes x 3 conditions (frozen config 1.2.0)"
  step "summarize $PILOT/summary.json"
  "${PY[@]}" - "$PILOT/summary.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
expected = 0
agg = {}
for rec in d["records"]:
    s = rec["score"]
    a = agg.setdefault(s["condition"], {"won": 0, "tp": 0, "fp": 0, "fp_clean": 0, "fn": 0, "n": 0})
    a["n"] += 1
    a["won"] += bool(s["episode_success"])
    a["tp"] += s["true_positives"]; a["fp"] += s["false_positives"]; a["fn"] += s["false_negatives"]
    if s["episode_id"].startswith("clean_"):
        a["fp_clean"] += s["false_positives"]
row = "{:<10}{:<14}{:<14}{:<14}{}"
print(row.format("condition", "episodes won", "issues found", "false alarms", "of which on clean controls"))
for c in d["config"]["conditions"]:
    a = agg[c]
    print(row.format(c, "%d/%d" % (a["won"], a["n"]), "%d/%d" % (a["tp"], a["tp"] + a["fn"]), a["fp"], a["fp_clean"]))
PY
  if [ "${DEMO_NO_OPEN:-0}" != 1 ] && command -v open >/dev/null 2>&1; then
    step "open $FIGS/outcome_grid.png $FIGS/findings_vs_false_alarms.png"
    open "$FIGS/outcome_grid.png" "$FIGS/findings_vs_false_alarms.png"
  fi
}

prep() {
  banner "prep (run before recording)"
  for tool in uv make; do command -v $tool >/dev/null || { echo "missing $tool"; return 1; }; done
  [ $HAVE_JQ = 1 ] && echo "jq: found" || echo "jq: not found, using python fallbacks"
  step "make sync"; make sync >/dev/null 2>&1 || { echo "make sync failed"; return 1; }
  step "make fixture EPISODE=$REM"; make fixture EPISODE=$REM >/dev/null 2>&1 || { echo "fixture $REM failed"; return 1; }
  step "make fixture EPISODE=$CHG"; make fixture EPISODE=$CHG >/dev/null 2>&1 || { echo "fixture $CHG failed"; return 1; }
  step "make_figures.py $PILOT --out $FIGS --findings-chart --dpi 300"
  uv run --quiet --group report python writeups/midway_report/make_figures.py "$PILOT" --out "$FIGS" \
    --findings-chart --dpi 300 && rm -f "$FIGS"/*.pdf
  uv run --quiet python -m catalog_steward.contract >/dev/null
  echo "ready: segments 3 and 5 show saved pilot artifacts"

}

clean() {
  rm -rf "$REPLAY_REM" "$REPLAY_CHG" ".runs/evaluation/$(basename $REPLAY_REM)" ".runs/evaluation/$(basename $REPLAY_CHG)"
  echo "removed scratch replay folders"
}

time_all() {
  local n t0 t1
  for n in 1 2 3 4 5 6 7; do
    t0=$("${PY[@]}" -c 'import time; print(time.time())')
    DEMO_NO_OPEN=${DEMO_NO_OPEN:-1} "seg$n" >/dev/null 2>&1
    t1=$("${PY[@]}" -c 'import time; print(time.time())')
    "${PY[@]}" -c 'import sys; print(f"segment {sys.argv[1]}: {float(sys.argv[3])-float(sys.argv[2]):.1f}s")' "$n" "$t0" "$t1"
  done
}

case "${1:-}" in
  prep) prep ;;
  [1-7]) "seg$1" ;;
  time) time_all ;;
  clean) clean ;;
  *) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
