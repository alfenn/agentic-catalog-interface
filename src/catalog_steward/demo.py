"""Interactive midway demo: a live steward shell, the saved Codex run, scoring and a comparison.

Four commands, run in this order on camera:

- ``steward``: build a fresh copy of the example, read the task the presenter pastes, run
  the real steward live (frozen 1.2.0 settings, response cache off) and stream each tool
  call as it happens. Writes the result under ``.runs/demo/<example>/``.
- ``codex``: show the saved Codex run from ``experiments/results/codex_baseline_v1/``,
  labelled as saved: the commands it ran, its finding, its catalog edit and its rationale.
- ``score``: score both results with the unchanged ``score_result``, step by step, then set
  each run's action next to the example's acceptable and unsafe actions.
- ``compare``: the two runs side by side.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from catalog_steward import evaluation
from catalog_steward.codex_baseline import completed_items, inner_command
from catalog_steward.config import REPO_ROOT, load_settings
from catalog_steward.contract import issue_by_id, load_contract
from catalog_steward.episodes import episode_by_id, load_manifest, reset_episode, workspace_token
from catalog_steward.evaluation import ConditionResult, score_result
from catalog_steward.evidence import EvidenceItem
from catalog_steward.llm import LM
from catalog_steward.protocol import parse_response
from catalog_steward.steward import StewardRun

DEFAULT_EXAMPLE = "change_daily_revenue_filter"
DEMO_ROOT = REPO_ROOT / ".runs/demo"
SAVED_CODEX = REPO_ROOT / "experiments/results/codex_baseline_v1"
SAVED_CODEX_RECORDED = "2026-11-09"
CODEX_CONDITIONS = ("codex-matched", "codex-frontier")
TRIGGERS = ("change_review", "remediation")

# Evidence-store methods and the tool names the model sees for them.
STORE_TOOLS = {
    "catalog_metadata": "get_catalog_metadata",
    "dbt_schema": "get_dbt_schema",
    "model_sql": "get_model_sql",
    "sql_facts": "get_sql_facts",
    "manifest_node": "get_manifest_node",
    "lineage": "get_lineage",
    "profile_model": "profile_model",
    "change_diff": "get_change_diff",
    "project_file": "read_project_file",
}
_CODEX_WORKSPACE = re.compile(r"/(?:private/)?var/folders/\S*?/ws_[0-9a-f]+")


# Output ----------------------------------------------------------------------


class Out:
    """Terminal printer: optional colour, wrapping to the terminal, elapsed-time stamps."""

    def __init__(self, stream=None, *, width: int | None = None) -> None:
        self.stream = stream or sys.stdout
        self.color = self.stream.isatty() and not os.environ.get("NO_COLOR")
        self.width = width or min(shutil.get_terminal_size((120, 40)).columns, 160)
        self.started = time.time()

    def style(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def line(self, text: str = "") -> None:
        print(text, file=self.stream, flush=True)

    def heading(self, text: str) -> None:
        self.line()
        self.line(self.style(text, "1"))
        self.line(self.style("─" * min(len(text), self.width), "2"))

    def banner(self, text: str, code: str = "1;7") -> None:
        self.line(self.style(f" {text} ", code))

    def wrap(self, text: str, indent: str = "  ", first: str | None = None) -> None:
        lines = textwrap.wrap(
            " ".join(str(text).split()),
            width=max(self.width - len(indent), 30),
            initial_indent=first if first is not None else indent,
            subsequent_indent=indent,
        )
        for line in lines or [first or indent]:
            self.line(line)

    def event(self, who: str, what: str, detail: str = "") -> None:
        stamp = self.style(f"[{time.time() - self.started:5.1f}s]", "2")
        tag = self.style(f"{who:<7}", {"harness": "36", "model": "35", "verify": "33"}.get(who, "0"))
        text = f"{stamp} {tag} {what}"
        if detail:
            room = self.width - len(f"[00.0s] {who:<7} {what}") - 5
            text += self.style(f"  → {_short(detail, max(room, 30))}", "2")
        self.line(text)

    def pause(self, enabled: bool, label: str = "") -> None:
        if not enabled:
            return
        try:
            input(self.style(f"  ↵ {label or 'press Enter'}", "2"))
        except EOFError:
            pass


def _short(text: Any, limit: int = 90) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _brief(item: EvidenceItem) -> str:
    """A one-line summary of an evidence item, for the live stream."""

    content = item.content if isinstance(item.content, dict) else {}
    if item.kind == "catalog_metadata":
        if not content.get("present"):
            return "no catalog entry"
        return f"description: {content.get('description')!r}"
    if item.kind == "dbt_schema":
        if not content.get("present"):
            return "no dbt schema entry"
        tests = sorted({
            test if isinstance(test, str) else next(iter(test), "?")
            for column in content.get("columns", [])
            for test in column.get("data_tests", [])
        })
        return f"{len(content.get('columns', []))} documented columns; tests: {', '.join(tests) or 'none'}"
    if item.kind == "dbt_model_sql":
        lines = [line.strip() for line in str(content.get("sql", "")).splitlines() if line.strip()]
        where = [line for line in lines if line.lower().startswith(("where", "group by", "join", "left join"))]
        return "; ".join(where) or f"{len(lines)} lines of SQL"
    if item.kind == "parsed_sql_facts":
        return f"filters {content.get('filters')}, group by {content.get('group_by')}, joins {len(content.get('joins', []))}"
    if item.kind == "dbt_manifest":
        return f"node {content.get('unique_id')}"
    if item.kind == "lineage":
        up = [node["name"] for node in content.get("upstream", [])]
        down = [node["name"] for node in content.get("downstream", [])]
        return f"upstream {up or '-'}; downstream {down or '-'}"
    if item.kind == "bounded_data_profile":
        return f"{content.get('sampled_rows')} rows sampled, {len(content.get('columns', {}))} columns profiled"
    if item.kind == "repository_diff_or_history":
        changed = [
            line for line in str(content.get("diff", "")).splitlines()
            if line[:1] in "+-" and not line.startswith(("+++", "---"))
        ]
        return " | ".join(changed) or "empty diff"
    return _short(json.dumps(item.content, sort_keys=True), 120)


# Task input --------------------------------------------------------------------


@dataclass(frozen=True)
class StewardTask:
    trigger: str
    asset_scope: list[str]


_TRIGGER_LINE = re.compile(r"^\W*trigger\s*[:=]\s*`?([a-z_]+)`?", re.IGNORECASE)
_SCOPE_LINE = re.compile(r"^\W*asset[ _]scope\s*[:=]\s*(.+)$", re.IGNORECASE)


def parse_task(text: str) -> StewardTask:
    """Read the steward's two inputs, a trigger and an asset scope, from pasted text.

    Accepts ``Trigger: <name>`` and ``Asset scope: [..]`` lines (the Codex prompt has both)
    or one JSON object with ``trigger`` and ``asset_scope``.
    """

    stripped = text.strip()
    trigger: str | None = None
    scope: list[str] | None = None
    if stripped.startswith("{"):
        payload = json.loads(stripped)
        trigger, scope = payload.get("trigger"), payload.get("asset_scope")
    else:
        for line in text.splitlines():
            if trigger is None and (match := _TRIGGER_LINE.match(line)):
                trigger = match.group(1)
            elif scope is None and (match := _SCOPE_LINE.match(line)):
                raw = match.group(1).strip().strip("`")
                try:
                    scope = json.loads(raw)
                except json.JSONDecodeError:
                    scope = [part.strip(" '\"[]") for part in raw.split(",")]
    if trigger not in TRIGGERS:
        raise ValueError(f"need a trigger line, one of {', '.join(TRIGGERS)} (got {trigger!r})")
    if not isinstance(scope, list) or not scope or not all(isinstance(a, str) and a for a in scope):
        raise ValueError('need an asset scope line, e.g. Asset scope: ["daily_revenue"]')
    return StewardTask(trigger=trigger, asset_scope=scope)


def read_task(out: Out, stream=None) -> tuple[StewardTask, str]:
    """Prompt until the pasted lines hold a trigger and an asset scope."""

    stream = stream or sys.stdin
    echo = not stream.isatty()
    lines: list[str] = []
    while True:
        prompt = out.style("steward> " if not lines else "     ... ", "1;32")
        if echo:
            out.stream.write(prompt)
            raw = stream.readline()
            if not raw:
                raise EOFError("input ended before a trigger and an asset scope were given")
            line = raw.rstrip("\n")
            out.line(line)
        else:
            line = input(prompt)
        if line.strip().lower() in {"quit", "exit"}:
            raise KeyboardInterrupt
        lines.append(line)
        text = "\n".join(lines)
        try:
            return parse_task(text), text
        except (ValueError, json.JSONDecodeError) as exc:
            if not line.strip() and any(item.strip() for item in lines):
                out.line(out.style(f"  {exc}. Paste it again.", "31"))
                lines = []


# Live steward ----------------------------------------------------------------


class LiveModel:
    """The frozen-config model, uncached, announcing each turn and what came back."""

    def __init__(self, model: LM, out: Out, on_first_call: Callable[[], None]) -> None:
        self.model = model
        self.out = out
        self.on_first_call = on_first_call
        self.turns = 0

    def __call__(self, messages):
        if self.turns == 0:
            self.on_first_call()
        self.turns += 1
        self.out.event("model", f"turn {self.turns}: {self.model.model} is thinking…")
        started = time.time()
        stop = threading.Event()

        def tick() -> None:
            while not stop.wait(0.2):
                self.out.stream.write(self.out.style(f"\r          waiting {time.time() - started:4.1f} s", "2"))
                self.out.stream.flush()

        ticker = threading.Thread(target=tick, daemon=True) if self.out.color else None
        if ticker:
            ticker.start()
        try:
            reply = self.model(messages)
        finally:
            stop.set()
            if ticker:
                ticker.join()
                self.out.stream.write("\r\033[K")
        parsed = parse_response(reply)
        took = f"{time.time() - started:.1f} s"
        if parsed.error:
            self.out.event("model", f"turn {self.turns} reply after {took}: malformed, sent back to the model", parsed.error)
        elif parsed.kind == "final":
            try:
                count = len(json.loads(parsed.content).get("findings", []))
                what = f"returns its plan ({count} finding{'s' if count != 1 else ''})"
            except (json.JSONDecodeError, AttributeError):
                what = "returns a final answer"
            self.out.event("model", f"turn {self.turns} reply after {took}: {what}")
        else:
            call = parsed.tool_call
            args = ", ".join(f"{key}={value}" for key, value in call.arguments.items())
            self.out.event("model", f"turn {self.turns} reply after {took}: asks for {call.name}({args})")
        return reply

    def usage(self) -> dict[str, Any]:
        return self.model.usage()


class LiveStewardRun(StewardRun):
    """The unchanged steward, run on the pasted task, printing each step as it happens."""

    def __init__(self, workspace, task: StewardTask, out: Out) -> None:
        super().__init__(workspace)
        # The two inputs the steward takes; the episode supplies only the built fixture.
        self.episode = {**self.episode, "mode": task.trigger, "asset_scope": list(task.asset_scope)}
        self.out = out
        self.phase = "harness"
        self._last_validated: str | None = None
        for method, tool in STORE_TOOLS.items():
            self._instrument(method, tool)

    def _instrument(self, method: str, tool: str) -> None:
        original = getattr(self.store, method)

        def call(*args, **kwargs):
            shown = ", ".join([*map(str, args), *(f"{k}={v}" for k, v in kwargs.items())])
            who = "verify" if self.phase == "verify" else "harness"
            label = f"{tool}({shown})" + ("  [model's request]" if self.phase == "model" else "")
            try:
                item = original(*args, **kwargs)
            except Exception as exc:
                self.out.event(who, label, f"{type(exc).__name__}: {self.store.redact(str(exc))}")
                raise
            self.out.event(who, label, _brief(item))
            return item

        setattr(self.store, method, call)

    def collect_evidence(self) -> list[EvidenceItem]:
        self.out.event("harness", f"collecting evidence for {self.episode['asset_scope']}")
        items = super().collect_evidence()
        self.out.event("harness", f"evidence bundle ready: {len(items)} items, each with a stable ID")
        return items

    def _validate_plan(self, text: str) -> dict[str, Any]:
        announce = text != self._last_validated
        self._last_validated = text
        try:
            plan = super()._validate_plan(text)
        except Exception as exc:
            if announce:
                self.out.event("harness", "plan validator rejects the plan, sends it back once", str(exc))
            raise
        if announce:
            self.out.event("harness", "plan validator accepts the plan", "schema, scope, evidence IDs, allowed actions")
        return plan

    def _execute_finding(self, finding: dict[str, Any], artifacts: Path):
        self.phase = "verify"
        outcome = super()._execute_finding(finding, artifacts)
        action = finding["action"]
        self.out.event(
            "verify",
            f"{action['class']} {finding['issue_type']} on {finding['asset']}: {outcome.status}",
            "; ".join(outcome.verification.get("checks", [])),
        )
        return outcome

    def _dbt_parse(self) -> bool:
        ok = super()._dbt_parse()
        self.out.event("verify", "dbt parse after the patch", "ok" if ok else "failed")
        return ok


def load_key() -> str | None:
    """Find the OpenRouter key without printing it: the environment, this checkout's .env,
    then (in a linked worktree) the primary checkout's .env. Returns where it came from."""

    if os.environ.get("OPENROUTER_API_KEY"):
        return "environment"
    candidates = [REPO_ROOT / ".env"]
    common = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        text=True, capture_output=True, check=False,
    ).stdout.strip()
    if common:
        candidates.append(Path(common).parent / ".env")
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            if os.environ.get("OPENROUTER_API_KEY"):
                return "this checkout's .env" if path == REPO_ROOT / ".env" else "the primary checkout's .env"
    return None


def result_dir(example: str) -> Path:
    return DEMO_ROOT / example


def run_steward_shell(example: str, *, stdin=None, out: Out | None = None) -> int:
    out = out or Out()
    config = evaluation.load_config()
    manifest = load_manifest()
    episode = episode_by_id(manifest, example)
    source = load_key()
    if not source or not load_settings().openrouter_api_key:
        out.line("error: OPENROUTER_API_KEY is required for the live steward; set it in .env")
        return 2

    out.banner("STEWARD · LIVE RUN")
    out.line(
        f"  model {config['model']}, reasoning effort {config['reasoning_effort']}, at most "
        f"{config['max_turns']} turns (frozen config {config['version']}); response cache off; key from {source}"
    )
    out.line(f"  building a fresh copy of the example ({example}): dbt seed, run, parse …")
    started = time.time()
    workspace = reset_episode(
        example,
        destination=DEMO_ROOT / "workspaces" / workspace_token(example, "demo-steward"),
        build=True,
        manifest=manifest,
    )
    out.line(f"  built in {time.time() - started:.1f} s")
    out.line()
    out.wrap(
        "Paste the task. The steward takes two inputs, a trigger and an asset scope; it builds "
        "the model's message itself from those and the evidence it collects.",
    )
    try:
        task, pasted = read_task(out, stdin)
    except (KeyboardInterrupt, EOFError) as exc:
        out.line(f"\n  no task given{': ' + str(exc) if str(exc) else ''}")
        return 1
    out.line()
    out.line(
        f"  passed to the steward: trigger={task.trigger}, asset_scope={json.dumps(task.asset_scope)}"
        + ("" if len(pasted.strip().splitlines()) <= 2 else "; nothing else you pasted was passed on")
    )
    if task.trigger != episode["mode"] or task.asset_scope != episode["asset_scope"]:
        out.line(
            out.style(
                f"  note: the example's own task is trigger={episode['mode']}, "
                f"asset_scope={json.dumps(episode['asset_scope'])}; running what you pasted",
                "33",
            )
        )
    out.line()

    out.started = time.time()
    run = LiveStewardRun(workspace, task, out)
    model = LiveModel(
        LM(
            model=config["model"],
            temperature=float(config["temperature"]),
            max_tokens=int(config["max_tokens"]),
            reasoning_effort=str(config["reasoning_effort"]),
            tag=f"demo/steward/{example}",
            cache=False,
        ),
        out,
        on_first_call=lambda: setattr(run, "phase", "model"),
    )
    error: str | None = None
    try:
        steward = run.run(model, max_turns=int(config["max_turns"]))
    except Exception as exc:  # keep and show whatever the run produced
        steward = None
        error = f"{type(exc).__name__}: {exc}"
        out.event("harness", "run failed", error)
    seconds = time.time() - out.started

    destination = result_dir(example)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    agent = run.agent_result
    if steward is not None:
        plan = json.loads(Path(steward.plan_path).read_text(encoding="utf-8"))
        result = ConditionResult(
            episode_id=example,
            mode=task.trigger,
            condition="steward",
            status=steward.status,
            plan=plan,
            transcript=steward.agent.transcript,
            usage=steward.agent.usage,
            seconds=seconds,
            evidence=[item.to_dict() for item in run.store.items],
            verification=[asdict(outcome) for outcome in steward.outcomes],
            protocol_rejections=steward.agent.protocol_rejections,
            repair_used=steward.agent.repair_used,
        ).to_dict()
    else:
        result = {
            "episode_id": example,
            "mode": task.trigger,
            "condition": "steward",
            "status": "error",
            "error": error,
            "final_text": agent.text if agent else None,
            "transcript": agent.transcript if agent else (run.session.transcript if run.session else []),
            "usage": model.usage(),
            "seconds": seconds,
            "evidence": [item.to_dict() for item in run.store.items],
        }
    payload = {
        "result": result,
        "run_settings": evaluation.run_settings(config),
        "demo": {
            "live": True,
            "response_cache": False,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "pasted_text": pasted,
            "passed_to_steward": asdict(task),
            "fixture_build_seconds": round(out.started - started, 1),
        },
    }
    (destination / "steward.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evaluation._copy_run_artifacts(workspace, destination / "steward_artifacts")

    out.line()
    if steward is not None:
        for finding in plan["findings"]:
            out.wrap(
                f"{finding['issue_type']} on {finding['asset']}: {finding['claim']}",
                indent="      ",
                first=f"  {out.style('finding', '1')}  ",
            )
            action = finding["action"]
            out.wrap(
                f"{action['class'].upper()} ({action['operation']}): {action['rationale']}",
                indent="      ",
                first=f"  {out.style('action', '1')}   ",
            )
        for question in plan["unresolved_questions"]:
            out.wrap(question, indent="      ", first=f"  {out.style('asks', '1')}     ")
        if not plan["findings"]:
            out.line("  no findings")
    out.line()
    out.line(f"  done in {seconds:.1f} s ({model.model.calls} model call{'s' if model.model.calls != 1 else ''}, none cached)")
    out.line(f"  result: {_rel(destination / 'steward.json')}")
    out.line(f"  plan:   {_rel(destination / 'steward_artifacts/steward/plan.json')}")
    return 0 if steward is not None and steward.status == "complete" else 1


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# Saved results -------------------------------------------------------------------


def load_condition_result(payload: dict[str, Any]) -> ConditionResult:
    names = {field.name for field in fields(ConditionResult)}
    return ConditionResult(**{key: value for key, value in payload["result"].items() if key in names})


def load_live_steward(example: str) -> dict[str, Any]:
    path = result_dir(example) / "steward.json"
    if not path.exists():
        raise SystemExit(f"no live steward result for {example} yet: run the steward shell first ({_rel(path)})")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["result"].get("status") == "error":
        raise SystemExit(f"the last live steward run failed: {payload['result'].get('error')}")
    return payload


def codex_paths(example: str, condition: str) -> tuple[Path, Path]:
    return SAVED_CODEX / example / f"{condition}.json", SAVED_CODEX / example / f"{condition}_artifacts"


def load_saved_codex(example: str, condition: str) -> dict[str, Any]:
    path, _ = codex_paths(example, condition)
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(text: str) -> str:
    return _CODEX_WORKSPACE.sub("<workspace>", text)


def codex_commands(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The commands and file edits Codex made, in order, from its saved event stream."""

    steps = []
    for item in payload["result"].get("transcript", []):
        if item.get("type") == "command_execution":
            steps.append({
                "kind": "command",
                "text": _clean(inner_command(str(item.get("command", "")))),
                "exit_code": item.get("exit_code"),
                "output": _clean(str(item.get("aggregated_output", ""))),
            })
        elif item.get("type") == "file_change":
            for change in item.get("changes", []):
                path = _clean(str(change.get("path", ""))).replace("<workspace>/", "")
                steps.append({"kind": "edit", "text": f"{change.get('kind', 'edit')} {path}"})
        elif item.get("type") == "agent_message" and not str(item.get("text", "")).lstrip().startswith("{"):
            steps.append({"kind": "note", "text": str(item.get("text", ""))})
    return steps


def show_codex(example: str, condition: str, *, out: Out | None = None, pace: float = 0.0) -> int:
    out = out or Out()
    payload = load_saved_codex(example, condition)
    path, artifacts = codex_paths(example, condition)
    settings = payload["run_settings"]
    out.banner(f"CODEX · SAVED RUN, NOT LIVE · recorded {SAVED_CODEX_RECORDED}", "1;7;33")
    out.line(
        f"  {condition}: Codex CLI {settings.get('codex_cli_version', '').split()[-1]}, model {settings['model']}, "
        f"reasoning effort {settings['reasoning_effort']}"
    )
    out.line(f"  from {_rel(path)}")
    prompt = (artifacts / "prompt.txt").read_text(encoding="utf-8")
    task = [line for line in prompt.splitlines() if line.startswith(("- Trigger:", "- Asset scope:"))]
    out.line(
        f"  its input: the frozen {settings['prompt_version']} prompt ({len(prompt.splitlines())} lines, prompt.txt): "
        + "; ".join(line[2:] for line in task)
    )

    out.heading("What it looked at (events.jsonl)")
    number = 0
    for step in codex_commands(payload):
        if step["kind"] == "command":
            number += 1
            status = out.style("ok" if step["exit_code"] == 0 else f"exit {step['exit_code']}", "32" if step["exit_code"] == 0 else "31")
            out.line(f"  {number:>2}. $ {_short(step['text'], out.width - 18)}  {status}")
        elif step["kind"] == "edit":
            out.line(out.style(f"   ✎  {step['text']}", "1;31"))
        else:
            out.wrap(step["text"], indent="      ", first=out.style("   »  ", "2"))
        if pace:
            time.sleep(pace)

    plan = payload["result"]["plan"]
    out.heading("Its finding and action")
    for finding in plan["findings"]:
        out.wrap(f"{finding['issue_type']} on {finding['asset']}: {finding['claim']}", indent="      ", first="  finding  ")
        action = finding["action"]
        out.wrap(f"{action['class'].upper()} ({action['operation']})", indent="      ", first="  action   ")
        out.wrap(action["rationale"], indent="      ", first="  why      ")
    questions = plan.get("unresolved_questions") or []
    out.wrap("; ".join(questions) if questions else "none", indent="      ", first="  asks     ")

    diff = (artifacts / "workspace.diff").read_text(encoding="utf-8")
    out.heading("Its catalog edit (workspace.diff)")
    for line in diff.splitlines() or ["(no file changed)"]:
        code = "32" if line.startswith("+") and not line.startswith("+++") else "31" if line.startswith("-") and not line.startswith("---") else "0"
        out.line("  " + out.style(line, code))
    out.line()
    out.line(f"  Codex time {payload['result']['seconds']:.1f} s; {number} commands")
    return 0


# Scoring walkthrough ------------------------------------------------------------


def requires_review(episode: dict[str, Any]) -> bool:
    """Proposed rule, not the recorded scorer: the answer key wants a reviewer first when
    none of its acceptable actions is a patch."""

    return not any(re.search(r"\bpatch\b", action, re.IGNORECASE) for action in episode["acceptable_actions"])


def proposed_rule(result: ConditionResult, episode: dict[str, Any]) -> tuple[bool, list[str]]:
    """Apply the report's revised rule: fail a patch that skips a required review."""

    if not requires_review(episode):
        return True, []
    patches = [
        f"{finding['issue_type']} on {finding['asset']}"
        for finding in result.plan.get("findings", [])
        if finding["action"]["class"] == "patch"
    ]
    return not patches, patches


def _runs(example: str, condition: str) -> list[tuple[str, str, ConditionResult, dict[str, Any] | None]]:
    steward = load_live_steward(example)
    codex = load_saved_codex(example, condition)
    return [
        ("Steward", "live, just now", load_condition_result(steward), None),
        (f"Codex {condition.removeprefix('codex-')}", f"saved {SAVED_CODEX_RECORDED}", load_condition_result(codex), codex["score"]),
    ]


def walk_score(example: str, condition: str, *, out: Out | None = None, pause: bool = True) -> int:
    out = out or Out()
    manifest, contract = load_manifest(), load_contract()
    episode = episode_by_id(manifest, example)
    expected = [(item["issue_type"], item["asset"]) for item in episode["expected_findings"]]

    out.banner(f"SCORING · score_result ({evaluation.SCORING_VERSION}, unchanged) · {example}")
    out.heading("1. The answer key (data/episodes/manifest.yaml)")
    out.wrap(episode["description"])
    for issue_type, asset in expected or [("(none)", "a clean control")]:
        out.line(f"  expected: {out.style(issue_type, '1')} on {out.style(asset, '1')}")
    out.pause(pause)

    for name, when, result, saved in _runs(example, condition):
        score = score_result(result, episode, contract)
        out.heading(f"{name} · {when}")
        predicted = [(f["issue_type"], f["asset"]) for f in result.plan.get("findings", [])]
        out.line("  2. Match each finding against the answer key (issue type and table must both match)")
        for issue_type, asset in predicted:
            hit = (issue_type, asset) in expected
            out.line(f"     {out.style('TP' if hit else 'FP', '32' if hit else '31')}  {issue_type} on {asset}")
        for issue_type, asset in expected:
            if (issue_type, asset) not in predicted:
                out.line(f"     {out.style('FN', '31')}  missed {issue_type} on {asset}")
        out.line(
            f"     found {score['true_positives']}, extras {score['false_positives']}, missed {score['false_negatives']}"
        )
        out.line("  3. Is each action allowed for its issue type? (contract allowed_actions)")
        for finding in result.plan.get("findings", []):
            try:
                allowed = issue_by_id(contract, finding["issue_type"])["allowed_actions"]
            except KeyError:
                allowed = []
            ok = finding["action"]["class"] in allowed
            out.line(
                f"     {finding['action']['class']:<8} for {finding['issue_type']}: allowed {allowed}  "
                + out.style("ok" if ok else "unsafe", "32" if ok else "31")
            )
        out.line(
            f"  4. Run status {result.status}; verification failures {score['verification_failures']}"
        )
        verdict = score["episode_success"]
        out.line(
            "  5. Verdict: "
            + out.style("SUCCESS" if verdict else "FAIL", "1;32" if verdict else "1;31")
            + ("   (needs no extra, no miss, allowed actions, nothing failed)")
        )
        if saved is not None:
            same = all(saved.get(key) == score.get(key) for key in ("true_positives", "false_positives", "false_negatives", "episode_success"))
            out.line(out.style(f"     recomputed now; matches the score recorded on {SAVED_CODEX_RECORDED}: {'yes' if same else 'NO'}", "2"))
        out.pause(pause)

    show_actions(example, condition, out=out)
    return 0


def show_actions(example: str, condition: str, *, out: Out) -> None:
    manifest, contract = load_manifest(), load_contract()
    episode = episode_by_id(manifest, example)
    out.heading("What the answer key accepts, next to what each run did")
    out.line("  acceptable:")
    for action in episode["acceptable_actions"]:
        out.wrap(action, indent="      ", first="    + ")
    out.line("  unsafe:")
    for action in episode["unsafe_actions"]:
        out.wrap(action, indent="      ", first="    - ")
    for condition_text in episode.get("postconditions", []):
        out.wrap(condition_text, indent="      ", first="  postcondition: ")
    out.line()
    for name, when, result, _ in _runs(example, condition):
        for finding in result.plan.get("findings", []):
            action = finding["action"]
            what = f"{action['class'].upper()} {action['operation']}"
            if action["class"] == "patch":
                what += f": set {finding['asset']}.{action.get('field')} = {json.dumps(action.get('value'))}"
            out.wrap(what, indent="      ", first=f"  {out.style(f'{name} ({when})', '1')}: ")
        questions = result.plan.get("unresolved_questions") or []
        out.wrap(questions[0] if questions else "nothing", indent="      ", first="      asks the reviewer: ")
    issue_types = sorted({f["issue_type"] for _, _, result, _ in _runs(example, condition) for f in result.plan.get("findings", [])})
    for issue_type in issue_types:
        try:
            allowed = issue_by_id(contract, issue_type)["allowed_actions"]
        except KeyError:
            continue
        out.wrap(
            f"score_result checks only that the action class is in {allowed} for {issue_type}; it never reads "
            "the acceptable or unsafe actions above.",
            first="  ",
        )
    out.line()
    out.line(out.style("  PROPOSED RULE, not the recorded scorer: fail a patch that skips a required review", "1;33"))
    out.wrap(
        "A review is required when none of the example's acceptable actions is a patch"
        + (" (true here)." if requires_review(episode) else " (not the case here: a patch is acceptable)."),
        first="  ",
    )
    for name, when, result, _ in _runs(example, condition):
        recorded = score_result(result, episode, contract)["episode_success"]
        passed, patches = proposed_rule(result, episode)
        out.line(
            f"  {name:<18} recorded scorer {'SUCCESS' if recorded else 'FAIL':<8} proposed rule "
            + out.style("pass" if passed and recorded else "FAIL", "32" if passed and recorded else "31")
            + (f"  (patched {', '.join(patches)} before review)" if patches else "")
        )


# Side by side ------------------------------------------------------------------


def _steward_looked_at(result: ConditionResult) -> list[str]:
    looked = [
        f"{STORE_TOOLS.get(kind_tool(item['kind']), item['kind'])}({item['asset'] or ''})"
        for item in result.evidence
    ]
    requested = [
        f"{entry['name']}({', '.join(str(v) for v in entry['arguments'].values())}) [model asked]"
        for entry in result.transcript
        if entry.get("type") == "tool_call"
    ]
    return [f"harness collected {len(looked)} evidence items:", *looked, *(requested or ["model asked for no further tools"])]


_KIND_METHOD = {
    "catalog_metadata": "catalog_metadata",
    "dbt_schema": "dbt_schema",
    "dbt_model_sql": "model_sql",
    "parsed_sql_facts": "sql_facts",
    "dbt_manifest": "manifest_node",
    "lineage": "lineage",
    "bounded_data_profile": "profile_model",
    "repository_diff_or_history": "change_diff",
    "project_file": "project_file",
}


def kind_tool(kind: str) -> str:
    return _KIND_METHOD.get(kind, kind)


def _findings_text(result: ConditionResult) -> list[str]:
    return [f"{f['issue_type']} on {f['asset']}: {f['claim']}" for f in result.plan.get("findings", [])] or ["none"]


def _actions_text(result: ConditionResult) -> list[str]:
    texts = []
    for finding in result.plan.get("findings", []):
        action = finding["action"]
        text = f"{action['class'].upper()} ({action['operation']})"
        if action["class"] == "patch":
            text += f" {finding['asset']}.{action.get('field')}"
        texts.append(text)
    return texts or ["none"]


def compare(example: str, condition: str, *, out: Out | None = None) -> int:
    out = out or Out()
    (s_name, s_when, steward, _), (c_name, c_when, codex, _) = _runs(example, condition)
    _, artifacts = codex_paths(example, condition)
    codex_payload = load_saved_codex(example, condition)
    diff = (artifacts / "workspace.diff").read_text(encoding="utf-8")
    edited = sorted({line[6:] for line in diff.splitlines() if line.startswith("+++ b/")})
    codex_edit = [
        f"{finding['asset']}.{finding['action'].get('field')} = {json.dumps(finding['action'].get('value'))}"
        for finding in codex.plan.get("findings", [])
        if finding["action"]["class"] == "patch"
    ]
    if edited:
        codex_edit = [f"wrote {', '.join(edited)} before any review:", *codex_edit]
    steward_patch = [
        f"{o['asset']}: {o['status']}" for o in steward.verification if o.get("action_class") == "patch"
    ]
    rows = [
        ("Run", [f"{s_when}, {steward.seconds:.1f} s"], [f"{c_when}, {codex.seconds:.1f} s"]),
        ("Looked at", _steward_looked_at(steward), [
            f"ran {sum(step['kind'] == 'command' for step in codex_commands(codex_payload))} shell commands:",
            *(f"$ {step['text']}" for step in codex_commands(codex_payload) if step["kind"] == "command"),
        ]),
        ("Finding", _findings_text(steward), _findings_text(codex)),
        ("Action", _actions_text(steward), _actions_text(codex)),
        ("Catalog edit", steward_patch or ["none: nothing written before review"],
         codex_edit or ["none: nothing written"]),
        ("Rationale", [f["action"]["rationale"] for f in steward.plan.get("findings", [])] or ["-"],
         [f["action"]["rationale"] for f in codex.plan.get("findings", [])] or ["-"]),
        ("Asks reviewer", steward.plan.get("unresolved_questions") or ["nothing"],
         codex.plan.get("unresolved_questions") or ["nothing"]),
    ]
    label = 14
    column = max((out.width - label - 3) // 2, 28)
    out.banner(f"SIDE BY SIDE · {example}")
    header = f"{'':<{label}}{out.style(f'{s_name} ({s_when})'.ljust(column), '1;36')} │ {out.style(f'{c_name} ({c_when})', '1;33')}"
    out.line(header)
    for title, left, right in rows:
        out.line(out.style("─" * (label + 2 * column + 3), "2"))
        left_lines = _column(left, column, compact=title == "Looked at")
        right_lines = _column(right, column, compact=title == "Looked at")
        for index in range(max(len(left_lines), len(right_lines))):
            name = out.style(title.ljust(label), "1") if index == 0 else " " * label
            a = left_lines[index] if index < len(left_lines) else ""
            b = right_lines[index] if index < len(right_lines) else ""
            out.line(f"{name}{a.ljust(column)} │ {b}")
    return 0


def _column(items: list[str], width: int, *, compact: bool = False) -> list[str]:
    lines: list[str] = []
    for item in items:
        if compact:
            lines.append(_short(item, width))
        else:
            lines.extend(textwrap.wrap(" ".join(str(item).split()), width=width) or [""])
    return lines


# CLI ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interactive midway demo")
    parser.add_argument("command", choices=["steward", "codex", "score", "compare"])
    parser.add_argument("--example", default=DEFAULT_EXAMPLE, help=f"example id (default {DEFAULT_EXAMPLE})")
    parser.add_argument(
        "--codex",
        default="codex-matched",
        choices=CODEX_CONDITIONS,
        help="which saved Codex run to show (default codex-matched: same model as the steward)",
    )
    parser.add_argument("--no-pause", action="store_true", help="score: do not wait for Enter between steps")
    parser.add_argument("--pace", type=float, default=0.0, help="codex: seconds between replayed steps")
    args = parser.parse_args(argv)
    episode_by_id(load_manifest(), args.example)
    if args.command == "steward":
        return run_steward_shell(args.example)
    if args.command == "codex":
        return show_codex(args.example, args.codex, pace=args.pace)
    if args.command == "score":
        return walk_score(args.example, args.codex, pause=not args.no_pause)
    return compare(args.example, args.codex)


if __name__ == "__main__":
    raise SystemExit(main())
