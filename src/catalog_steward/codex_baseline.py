"""Codex CLI baseline: same task, inputs and data access as the steward, scored unchanged.

Each run builds a fresh episode fixture outside the repository, strips everything
that names the episode, and hands Codex only the built dbt project, the warehouse
and (for change review) the proposed diff. dbt, DuckDB and Python come from a tool
environment that is also outside the repository. After Codex exits, the harness
diffs the project, re-verifies every claimed patch with the steward's own checks,
scans the event stream for reads outside the workspace or of label material, and
scores the converted plan with the unchanged ``midpoint-score-v1`` scorer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jsonschema
import yaml

from catalog_steward.config import REPO_ROOT
from catalog_steward.contract import load_contract
from catalog_steward.episodes import (
    MARKER,
    EpisodeWorkspace,
    FixtureBuildError,
    directory_diff,
    episode_by_id,
    load_manifest,
    reset_episode,
    workspace_token,
)
from catalog_steward.evaluation import SCORING_VERSION, ConditionResult, score_result
from catalog_steward.evidence import EvidenceStore
from catalog_steward.steward import ALLOWED_PATCH_FIELDS

DEFAULT_CONFIG = REPO_ROOT / "experiments/configs/codex_baseline_v1.yaml"
CONFIG_VERSION = "1.0.0"
CODEX_PROMPT_VERSION = "codex-hygiene-v1"
CONDITIONS = ("codex-matched", "codex-frontier")
OVERRIDES = "catalog/overrides.json"
SYSTEM_PATH = ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
# Files reset_episode writes that name the episode or hold the pre-change copy.
LABEL_MATERIAL = ("episode.json", MARKER, "before", "dbt_build.log")
# Strings whose appearance in a Codex command means it reached for evaluation labels.
LABEL_PATTERNS = ("manifest.yaml", "episode.json", MARKER, "expected_findings", REPO_ROOT.name)
# Absolute repository paths: any appearance in the workspace, Codex's environment or its
# commands would point Codex at the labelled repository.
REPOSITORY_PATHS = tuple(sorted({str(REPO_ROOT), str(REPO_ROOT.resolve())}))
ALLOWED_READ_PREFIXES = ("/usr/", "/bin/", "/sbin/", "/dev/null", "/dev/stdin", "/dev/stdout", "/dev/stderr")


@dataclass(frozen=True)
class CodexInvocation:
    exit_code: int | None
    seconds: float
    events: list[dict[str, Any]]
    malformed_event_lines: int
    final_text: str | None
    timed_out: bool


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not config.get("frozen"):
        raise ValueError("codex baseline config must be explicitly frozen")
    if config.get("version") != CONFIG_VERSION:
        raise ValueError(
            f"codex baseline config version {config.get('version')!r} does not match implementation {CONFIG_VERSION!r}"
        )
    if config.get("prompt_version") != CODEX_PROMPT_VERSION:
        raise ValueError("codex baseline prompt version does not match implementation")
    if config.get("scoring_version") != SCORING_VERSION:
        raise ValueError("codex baseline scoring version does not match implementation")
    if set(config.get("conditions", {})) != set(CONDITIONS):
        raise ValueError(f"codex baseline config must define exactly {list(CONDITIONS)}")
    for name, condition in config["conditions"].items():
        missing = [key for key in ("model", "reasoning_effort") if not condition.get(key)]
        if missing:
            raise ValueError(f"condition {name} must pin {', '.join(missing)}")
    return config


# Tool environment -----------------------------------------------------------


def locked_versions(packages: Iterable[str], lock_path: Path = REPO_ROOT / "uv.lock") -> dict[str, str]:
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions = {package["name"]: package["version"] for package in lock["package"]}
    return {name: versions[name] for name in packages}


def tool_env_path(config: dict[str, Any]) -> Path:
    return Path(config["tool_environment"]["path"]).expanduser()


def ensure_tool_env(config: dict[str, Any]) -> Path:
    """Create or reuse the pinned dbt/DuckDB/Python environment; return its bin directory."""

    spec = config["tool_environment"]
    root = tool_env_path(config)
    if root.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise ValueError(f"tool environment must be outside the repository: {root}")
    versions = locked_versions(spec["packages"])
    stamp = {"python": str(spec["python"]), "packages": versions}
    stamp_path = root / "catalog-steward-tools.json"
    if stamp_path.exists() and json.loads(stamp_path.read_text(encoding="utf-8")) == stamp:
        return root / "bin"
    # Never let the repository's own environment leak into the install.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV" and not key.startswith("UV_")}
    subprocess.run(["uv", "venv", "--clear", "--python", str(spec["python"]), str(root)], env=env, check=True)
    subprocess.run(
        ["uv", "pip", "install", "--python", str(root / "bin/python"),
         *(f"{name}=={version}" for name, version in versions.items())],
        env=env,
        check=True,
    )
    stamp_path.write_text(json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root / "bin"


def codex_env(tool_bin: Path, workspace: Path) -> dict[str, str]:
    """Minimal environment for Codex: nothing that points at the repository."""

    env = {
        "HOME": str(Path.home()),
        "PATH": os.pathsep.join([str(tool_bin), *SYSTEM_PATH]),
        "TMPDIR": tempfile.gettempdir(),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "CATALOG_STEWARD_WAREHOUSE_PATH": str(workspace / "warehouse.duckdb"),
        "DBT_PROFILES_DIR": str(workspace / "project"),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
    }
    leaked = [key for key, value in env.items() if any(path in value for path in REPOSITORY_PATHS)]
    if leaked:
        raise ValueError(f"codex environment points at the repository: {leaked}")
    return env


def check_tool_env(config: dict[str, Any], tool_bin: Path) -> dict[str, Any]:
    """Run dbt parse and a DuckDB query in a prepared workspace with network denied."""

    episode_id = config["episodes"][0]
    with tempfile.TemporaryDirectory(prefix="csb-") as temporary:
        workspace = prepare_workspace(episode_id, Path(temporary), condition="tool-check", tool_bin=tool_bin)
        env = codex_env(tool_bin, workspace.root)
        script = (
            "cd project && which dbt python && dbt parse --profiles-dir . >/dev/null && echo dbt-parse-ok && "
            "python -c \"import duckdb; c = duckdb.connect('../warehouse.duckdb', read_only=True); "
            "print('duckdb-query-ok', c.sql('select count(*) from main.stg_orders').fetchone()[0])\""
        )
        command = ["bash", "-c", script]
        sandbox = shutil.which("sandbox-exec")
        if sandbox:
            command = [sandbox, "-p", "(version 1)(allow default)(deny network*)", *command]
        result = subprocess.run(
            command, cwd=workspace.root, env=env, text=True, capture_output=True, check=False
        )
    return {
        "network_denied": bool(sandbox),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr[-4000:],
    }


SANDBOX_CHECK_COMMANDS = (
    "cd project && dbt parse",
    "python -c \"import duckdb; print(duckdb.connect('warehouse.duckdb', read_only=True)"
    ".sql('select count(*) from main.stg_orders').fetchone()[0])\"",
)


def check_codex_sandbox(config: dict[str, Any], tool_bin: Path, codex_bin: str) -> dict[str, Any]:
    """Have Codex run dbt and a DuckDB query inside its own sandbox in a prepared workspace.

    Uses the codex-matched model and the frozen invocation; results come from the
    event stream (exit codes the harness observed), not from the model's answer.
    """

    episode_id = config["episodes"][0]
    schema = {
        "type": "object",
        "properties": {"done": {"type": "boolean"}},
        "required": ["done"],
        "additionalProperties": False,
    }
    prompt = (
        "Run each of these shell commands from the current directory, exactly as written, then answer "
        "with done=true. Do not run anything else.\n"
        + "\n".join(f"{index}. `{command}`" for index, command in enumerate(SANDBOX_CHECK_COMMANDS, 1))
        + "\n"
    )
    work_parent = Path(tempfile.mkdtemp(prefix="csb-"))
    harness = Path(tempfile.mkdtemp(prefix="csb-harness-"))
    try:
        workspace = prepare_workspace(episode_id, work_parent, condition="sandbox-check", tool_bin=tool_bin)
        schema_path = harness / "schema.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        command = codex_command(
            codex_bin, config, "codex-matched",
            schema_path=schema_path, final_path=harness / "final.json", workspace=workspace.root,
        )
        invocation = invoke_codex(
            command,
            prompt=prompt,
            env=codex_env(tool_bin, workspace.root),
            cwd=workspace.root,
            timeout=float(config["timeout_seconds"]),
            events_path=harness / "events.jsonl",
            stderr_path=harness / "stderr.txt",
            final_path=harness / "final.json",
        )
        observed = [
            {
                "command": inner_command(str(item.get("command", ""))),
                "exit_code": item.get("exit_code"),
                "output_tail": str(item.get("aggregated_output", ""))[-600:],
            }
            for item in completed_items(invocation.events)
            if item.get("type") == "command_execution"
        ]
        flags = isolation_flags(invocation.events, workspace.root, tool_root=tool_bin.parent, manifest=load_manifest())
    finally:
        shutil.rmtree(work_parent, ignore_errors=True)
        shutil.rmtree(harness, ignore_errors=True)
    passed = invocation.exit_code == 0 and all(
        any(" ".join(expected.split()) in " ".join(row["command"].split()) and row["exit_code"] == 0 for row in observed)
        for expected in SANDBOX_CHECK_COMMANDS
    )
    return {"passed": passed, "codex_exit_code": invocation.exit_code, "commands": observed, "isolation": flags}


# Workspace -----------------------------------------------------------------


def prepare_workspace(
    episode_id: str,
    parent: Path,
    *,
    condition: str,
    tool_bin: Path,
    manifest: dict[str, Any] | None = None,
) -> EpisodeWorkspace:
    """Build a fresh fixture under ``parent`` and remove everything that names the episode."""

    manifest = manifest or load_manifest()
    episode = episode_by_id(manifest, episode_id)
    destination = parent / workspace_token(episode_id, condition)
    if destination.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise ValueError(f"codex workspace must be outside the repository: {destination}")
    workspace = reset_episode(episode_id, destination=destination, manifest=manifest)
    build_with_tools(workspace, tool_bin)
    for name in LABEL_MATERIAL:
        path = workspace.root / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    if episode["mode"] != "change_review":
        workspace.diff_path.unlink(missing_ok=True)
    assert_no_label_material(workspace.root, manifest)
    return workspace


def build_with_tools(workspace: EpisodeWorkspace, tool_bin: Path) -> None:
    """The fixture build of ``episodes.build_fixture``, run with Codex's tool environment.

    dbt records its adapter and macro paths in ``target/``; building with the
    repository's own environment would write the repository path into files Codex reads.
    """

    env = codex_env(tool_bin, workspace.root)
    logs: list[str] = []
    for verb in ("seed", "run", "parse"):
        command = [str(tool_bin / "dbt"), verb, "--project-dir", "project", "--profiles-dir", "project"]
        result = subprocess.run(
            command, cwd=workspace.root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        logs.append(f"$ dbt {verb}\n{result.stdout}")
        if result.returncode != 0:
            workspace.build_log_path.write_text("\n".join(logs), encoding="utf-8")
            raise FixtureBuildError(f"fixture build failed (dbt {verb}); see {workspace.build_log_path}")
    workspace.build_log_path.write_text("\n".join(logs), encoding="utf-8")


def assert_no_label_material(root: Path, manifest: dict[str, Any]) -> None:
    forbidden = [episode["id"].encode() for episode in manifest["episodes"]]
    forbidden.extend(path.encode() for path in REPOSITORY_PATHS)
    allowed_top = {"project", "warehouse.duckdb", "input.diff"}
    extra = sorted(item.name for item in root.iterdir() if item.name not in allowed_top)
    if extra:
        raise AssertionError(f"unexpected entries in codex workspace: {extra}")
    for path in root.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            for needle in forbidden:
                if needle in data:
                    raise AssertionError(f"label material in {path.relative_to(root)}: {needle.decode()}")


def snapshot_project(project: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(project)): path.read_bytes()
        for path in sorted(project.rglob("*"))
        if path.is_file() and not ({"target", "logs"} & set(path.relative_to(project).parts))
    }


def changed_files(before: dict[str, bytes], after: dict[str, bytes]) -> list[str]:
    return sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))


def snapshot_diff(before: dict[str, bytes], after: dict[str, bytes]) -> str:
    with tempfile.TemporaryDirectory(prefix="csb-diff-") as temporary:
        roots = {"a": Path(temporary) / "a", "b": Path(temporary) / "b"}
        for key, files in (("a", before), ("b", after)):
            roots[key].mkdir()
            for name, data in files.items():
                target = roots[key] / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        try:
            return directory_diff(roots["a"], roots["b"])
        except UnicodeDecodeError:
            return "".join(f"binary or undecodable change: {name}\n" for name in changed_files(before, after))


# Prompt --------------------------------------------------------------------


def build_prompt(episode: dict[str, Any], contract: dict[str, Any]) -> str:
    """Frozen task prompt. Uses only the trigger and asset scope, never expected findings."""

    # The same issue-contract fields the steward's system prompt carries.
    issue_contract = [
        {
            "id": issue["id"],
            "required_evidence": issue["required_evidence"],
            "allowed_actions": issue["allowed_actions"],
            "forbidden_actions": issue["forbidden_actions"],
        }
        for issue in contract["issue_types"]
    ]
    change_review = episode["mode"] == "change_review"
    layout = [
        "- `project/`: a dbt project (dbt-duckdb), already built; `project/target/` holds dbt's manifest and other artifacts.",
        "- `project/catalog/catalog.json`: the data catalog. An asset's catalog metadata is its entry there with "
        "`project/catalog/overrides.json` `assets.<asset>` (if present) merged over it.",
        "- `warehouse.duckdb`: the DuckDB warehouse with the built seeds and models (schema `main`).",
    ]
    if change_review:
        layout.append(
            "- `input.diff`: the proposed change under review, already applied to `project/`."
        )
    max_rows = contract["scope"]["max_probe_rows"]
    lines = [
        f"Prompt version: {CODEX_PROMPT_VERSION}",
        "",
        "You are reviewing data-catalog hygiene for a dbt project. Inspect the workspace, prioritize at most "
        "five findings, act on them within the rules below, and return the final answer as JSON matching "
        "the provided output schema.",
        "",
        "## Task",
        f"- Trigger: {episode['mode']}"
        + (" (review the proposed change before it is approved)." if change_review
           else " (find and fix existing hygiene debt)."),
        f"- Asset scope: {json.dumps(episode['asset_scope'])}",
        "",
        "## Workspace (the current directory)",
        *layout,
        "",
        "## Tools",
        "- `dbt` (run from `project/`; the profile is configured, e.g. `dbt parse`, `dbt ls`, `dbt compile`, `dbt test`).",
        "- `python` with the `duckdb` package; open the warehouse read-only, e.g. "
        "`duckdb.connect('warehouse.duckdb', read_only=True)`.",
        "- Standard shell utilities. There is no network access.",
        "",
        "## Rules",
        "- Work only inside this workspace. Do not read or write files outside it.",
        "- Do not use evaluation ground truth, invent business meaning, or exceed five prioritized findings.",
        f"- Keep data queries bounded (at most {max_rows} rows) and do not modify the warehouse.",
        "- The only file you may change is `project/catalog/overrides.json`, and only the fields "
        f"{json.dumps(sorted(ALLOWED_PATCH_FIELDS))} of assets in scope. Do not change SQL, dbt YAML, seeds or "
        "any other file.",
        "- Use only the issue types below. Each finding's action class must be one the issue allows; "
        "`required_evidence` names the facts a finding must rest on, which you establish from workspace "
        "files, dbt artifacts or bounded queries.",
        "",
        "## Hygiene issue contract",
        json.dumps(issue_contract, sort_keys=True),
        "",
        "## Actions",
        "- `patch`: you write the change to `project/catalog/overrides.json` yourself, then report it with "
        "operation `update_catalog_field`, the `field` and new `value`, and `verification` "
        "`{\"field\": <field>, \"equals\": <value>}` stating what the catalog field must equal afterwards.",
        "- `propose`: a reviewable proposal with no file change; operation `propose_metadata_change` or `request_review`.",
        "- `report`: a finding only, no change; operation `report_only`.",
        "- For `propose` and `report`, set `field`, `value` and `verification` to null.",
        "",
        "## Output",
        "- `findings`: at most five, highest priority first. `asset` must be an asset in scope.",
        "- `evidence`: one entry per fact: `kind` `file` with `source` a workspace-relative path such as "
        "`project/models/example.sql`, or `kind` `command` with `source` the exact command you ran; `fact` "
        "states what it shows.",
        "- `changes_made`: every file you changed and why (empty if none). `verification_performed`: commands "
        "you ran to check your work and their results.",
        "- `unresolved_questions`: decisions that need a human reviewer.",
        "- If there is no hygiene issue, return an empty `findings` list.",
    ]
    return "\n".join(lines) + "\n"


# Invocation ----------------------------------------------------------------


def codex_command(
    codex_bin: str,
    config: dict[str, Any],
    condition: str,
    *,
    schema_path: Path,
    final_path: Path,
    workspace: Path,
) -> list[str]:
    settings = config["conditions"][condition]
    return [
        codex_bin,
        "exec",
        "--ignore-user-config",
        *config.get("isolation_args", []),
        "--model",
        settings["model"],
        "-c",
        f'model_reasoning_effort="{settings["reasoning_effort"]}"',
        "--sandbox",
        config["sandbox"],
        "--skip-git-repo-check",
        "--ephemeral",
        "--json",
        "--output-schema",
        str(schema_path),
        "-o",
        str(final_path),
        "-C",
        str(workspace),
        "-",
    ]


def codex_version(codex_bin: str) -> str:
    result = subprocess.run([codex_bin, "--version"], text=True, capture_output=True, check=False)
    return (result.stdout or result.stderr).strip()


def invoke_codex(
    command: list[str],
    *,
    prompt: str,
    env: dict[str, str],
    cwd: Path,
    timeout: float,
    events_path: Path,
    stderr_path: Path,
    final_path: Path,
) -> CodexInvocation:
    started = time.time()
    timed_out = False
    with events_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True
        )
        try:
            process.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
    events: list[dict[str, Any]] = []
    malformed = 0
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            malformed += 1
    return CodexInvocation(
        exit_code=None if timed_out else process.returncode,
        seconds=time.time() - started,
        events=events,
        malformed_event_lines=malformed,
        final_text=final_path.read_text(encoding="utf-8") if final_path.exists() else None,
        timed_out=timed_out,
    )


def completed_items(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event["item"] for event in events if event.get("type") == "item.completed" and "item" in event]


def inner_command(command: str) -> str:
    """The script inside Codex's ``/bin/bash -c '<script>'`` wrapper."""

    try:
        parts = shlex.split(command)
    except ValueError:
        return command
    if len(parts) >= 3 and parts[0].endswith("sh") and parts[1] in {"-c", "-lc"}:
        return parts[2]
    return command


def token_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    usage = {"calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}
    for event in events:
        if event.get("type") == "turn.completed":
            usage["calls"] += 1
            for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
                usage[key] += int(event.get("usage", {}).get(key, 0) or 0)
    return usage


# Post-run checks -------------------------------------------------------------


# Absolute paths in a command; a slash after a word, dot or glob character (``a/b``,
# ``./x``, ``**/target/**``) is part of a relative path or pattern, not an absolute one.
_PATH_TOKEN = re.compile(r"(?<![\w.~*!-])(/[^\s'\"`;|&<>(){}$,]+)")
# Events do not record a command's working directory, and Codex often works from
# ``project/``, so one level up (``../warehouse.duckdb``) can stay in the workspace.
# Listing the parent itself or climbing two or more levels cannot be told apart from
# leaving the workspace and is flagged for the audit.
_PARENT_REFERENCE = re.compile(r"(^|[\s'\"=(])\.\./?(?=$|[\s'\";|&)])|\.\./\.\.")


def isolation_flags(
    events: list[dict[str, Any]],
    workspace: Path,
    *,
    tool_root: Path,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    """Flag commands or file changes that leave the workspace or reach for labels."""

    workspace_variants = {str(workspace), str(workspace.resolve())}
    allowed = (*ALLOWED_READ_PREFIXES, str(tool_root), str(tool_root.resolve()), *workspace_variants)
    episode_ids = [episode["id"] for episode in manifest["episodes"]]
    flags: list[dict[str, Any]] = []
    for item in completed_items(events):
        kind = item.get("type")
        texts: list[tuple[str, str]] = []
        if kind == "command_execution":
            texts.append(("command", inner_command(str(item.get("command", "")))))
            texts.append(("output", str(item.get("aggregated_output", ""))))
        elif kind == "file_change":
            texts.extend(("path", str(change.get("path", ""))) for change in item.get("changes", []))
        elif kind in {"web_search", "mcp_tool_call"}:
            flags.append({"item": item.get("id"), "type": kind, "reason": f"{kind} used"})
            continue
        else:
            continue
        for role, text in texts:
            reasons: list[str] = []
            if any(path in text for path in REPOSITORY_PATHS):
                reasons.append("repository path")
            reasons.extend(f"episode id {episode_id}" for episode_id in episode_ids if episode_id in text)
            if role != "output":
                reasons.extend(f"label pattern {pattern}" for pattern in LABEL_PATTERNS if pattern in text)
                paths = _PATH_TOKEN.findall(text) if role == "command" else [text]
                outside = sorted({path for path in paths if not path.startswith(allowed)})
                reasons.extend(f"path outside workspace {path}" for path in outside)
                if role == "command" and _PARENT_REFERENCE.search(text):
                    reasons.append("parent-directory reference")
            if reasons:
                flags.append({"item": item.get("id"), "type": kind, "role": role, "reasons": reasons, "text": text[:500]})
    return flags


def _dbt_parse(workspace: EpisodeWorkspace, log_path: Path) -> bool:
    """The steward's post-patch dbt check, run on Codex's final workspace."""

    env = os.environ.copy()
    env["CATALOG_STEWARD_WAREHOUSE_PATH"] = str(workspace.warehouse_path.resolve())
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    result = subprocess.run(
        ["dbt", "parse", "--project-dir", str(workspace.project_dir), "--profiles-dir", str(workspace.project_dir)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"$ dbt parse (exit {result.returncode})\n{result.stdout}\n")
    return result.returncode == 0


def _override_fields(raw: bytes | None) -> dict[tuple[str, str], Any]:
    if raw is None:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    assets = payload.get("assets", {}) if isinstance(payload, dict) else {}
    return {
        (asset, field): value
        for asset, fields in assets.items() if isinstance(fields, dict)
        for field, value in fields.items()
    }


def verify_findings(
    plan: dict[str, Any],
    workspace: EpisodeWorkspace,
    *,
    before: dict[str, bytes],
    after: dict[str, bytes],
    log_path: Path,
) -> list[dict[str, Any]]:
    """Steward-equivalent outcomes, plus patch-surface checks on what Codex actually changed."""

    before_fields = _override_fields(before.get(OVERRIDES))
    after_fields = _override_fields(after.get(OVERRIDES))
    changed_fields = {
        key for key in set(before_fields) | set(after_fields)
        if before_fields.get(key, ...) != after_fields.get(key, ...)
    }
    store = EvidenceStore(workspace)
    outcomes: list[dict[str, Any]] = []
    declared: set[tuple[str, str]] = set()
    parse_ok: bool | None = None
    for index, finding in enumerate(plan["findings"]):
        action = finding["action"]
        base = {
            "finding_index": index,
            "issue_type": finding["issue_type"],
            "asset": finding["asset"],
            "action_class": action["class"],
        }
        if action["class"] != "patch":
            status = "proposed" if action["class"] == "propose" else "reported"
            outcomes.append({**base, "status": status, "verification": {"passed": True, "checks": ["no file change claimed"]}})
            continue
        field = action.get("field")
        verification = action.get("verification") or {"field": field, "equals": action.get("value")}
        checks: list[str] = []
        passed = True
        if field not in ALLOWED_PATCH_FIELDS or verification.get("field") not in ALLOWED_PATCH_FIELDS:
            checks.append(f"catalog field is patchable: False ({field!r})")
            passed = False
        else:
            declared.add((finding["asset"], field))
            has_change = (finding["asset"], field) in changed_fields
            checks.append(f"{OVERRIDES} changed {finding['asset']}.{field}: {has_change}")
            try:
                metadata = store.catalog_metadata(finding["asset"]).content
            except (OSError, ValueError) as exc:
                checks.append(f"catalog metadata readable: False ({type(exc).__name__})")
                metadata = {}
            field_matches = metadata.get(verification["field"]) == verification["equals"]
            checks.append(f"catalog {verification['field']} equals expected value: {field_matches}")
            if parse_ok is None:
                parse_ok = _dbt_parse(workspace, log_path)
            checks.append(f"dbt parse succeeds after patch: {parse_ok}")
            passed = has_change and field_matches and parse_ok
        outcomes.append({
            **base,
            "status": "verified" if passed else "verification_failed",
            "verification": {"passed": passed, "checks": checks},
        })

    outside = [name for name in changed_files(before, after) if name != OVERRIDES]
    undeclared = sorted(f"{asset}.{field}" for asset, field in changed_fields - declared)
    surface_checks = [
        f"only {OVERRIDES} changed: {not outside}" + (f" (also changed: {outside})" if outside else ""),
        f"every changed override field is declared by a patch finding: {not undeclared}"
        + (f" (undeclared: {undeclared})" if undeclared else ""),
    ]
    surface_ok = not outside and not undeclared
    outcomes.append({
        "check": "patch_surface",
        "status": "verified" if surface_ok else "verification_failed",
        "verification": {"passed": surface_ok, "checks": surface_checks},
    })
    return outcomes


# Conversion ----------------------------------------------------------------


_LINE_SUFFIX = re.compile(r"(:\d+(-\d+)?|#L\d+(-L?\d+)?)$")


def _citation_valid(
    citation: dict[str, Any],
    workspace: Path,
    executed: list[str],
) -> bool:
    source = citation["source"].strip()
    if citation["kind"] == "file":
        source = _LINE_SUFFIX.sub("", source.strip("`"))
        candidates = [Path(source)] if Path(source).is_absolute() else [
            workspace / source,
            workspace / "project" / source,
        ]
        root = workspace.resolve()
        return any(
            path.resolve().is_relative_to(root) and path.is_file()
            for path in candidates
        )
    cited = " ".join(source.strip("`").split())
    # A cited command matches an executed one if either contains the other; very short
    # executed commands (``ls``, ``pwd``) only match exactly.
    return bool(cited) and any(
        cited in command or (len(command) >= 12 and command in cited) for command in executed
    )


def to_steward_plan(
    final: dict[str, Any],
    workspace: Path,
    events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Convert Codex's answer to the steward plan shape and its resolvable evidence list.

    Evidence validity then means: cited files exist in the workspace and cited commands
    were actually run successfully.
    """

    executed = [
        " ".join(inner_command(str(item.get("command", ""))).split())
        for item in completed_items(events)
        if item.get("type") == "command_execution" and item.get("exit_code") == 0
    ]
    evidence: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    for finding in final["findings"]:
        evidence_ids: list[str] = []
        for citation in finding["evidence"]:
            digest = hashlib.sha256(f"{citation['kind']}\0{citation['source']}".encode("utf-8")).hexdigest()[:12]
            evidence_id = f"ev_codex_{digest}"
            if evidence_id not in evidence_ids:
                evidence_ids.append(evidence_id)
            if _citation_valid(citation, workspace, executed):
                evidence.setdefault(evidence_id, {
                    "id": evidence_id,
                    "kind": f"codex_{citation['kind']}",
                    "asset": finding["asset"],
                    "source": citation["source"],
                    "content": {"facts": []},
                })["content"]["facts"].append(citation["fact"])
        action = finding["action"]
        converted = {"class": action["class"], "operation": action["operation"], "rationale": action["rationale"]}
        if action["class"] == "patch":
            converted["field"] = action["field"]
            converted["value"] = action["value"]
            converted["verification"] = action["verification"] or {"field": action["field"], "equals": action["value"]}
        findings.append({
            "issue_type": finding["issue_type"],
            "asset": finding["asset"],
            "claim": finding["claim"],
            "impact": finding["impact"],
            "confidence": finding["confidence"],
            "evidence_ids": evidence_ids,
            "action": converted,
        })
    plan = {
        "summary": final["summary"],
        "findings": findings,
        "unresolved_questions": final["unresolved_questions"],
    }
    return plan, list(evidence.values())


# Runner --------------------------------------------------------------------


def run_settings(config: dict[str, Any], condition: str, *, version: str, schema_text: str, prompt: str) -> dict[str, Any]:
    return {
        "condition": condition,
        "model": config["conditions"][condition]["model"],
        "reasoning_effort": config["conditions"][condition]["reasoning_effort"],
        "codex_cli_version": version,
        "pinned_codex_cli_version": config["codex_cli_version"],
        "prompt_version": config["prompt_version"],
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "output_schema": config["output_schema"],
        "output_schema_sha256": hashlib.sha256(schema_text.encode("utf-8")).hexdigest(),
        "sandbox": config["sandbox"],
        "isolation_args": list(config.get("isolation_args", [])),
        "timeout_seconds": config["timeout_seconds"],
        "tool_environment": {
            "path": config["tool_environment"]["path"],
            "python": str(config["tool_environment"]["python"]),
            "packages": locked_versions(config["tool_environment"]["packages"]),
        },
        "scoring_version": config["scoring_version"],
        "config_version": config["version"],
    }


def run_one(
    episode_id: str,
    condition: str,
    *,
    config: dict[str, Any],
    output_dir: Path,
    codex_bin: str,
    tool_bin: Path,
    version: str,
    manifest: dict[str, Any],
    contract: dict[str, Any],
    keep_workspace: bool = False,
) -> dict[str, Any]:
    episode = episode_by_id(manifest, episode_id)
    artifacts = output_dir / episode_id / f"{condition}_artifacts"
    if artifacts.exists():
        shutil.rmtree(artifacts)
    artifacts.mkdir(parents=True)
    schema_text = (REPO_ROOT / config["output_schema"]).read_text(encoding="utf-8")
    prompt = build_prompt(episode, contract)
    (artifacts / "prompt.txt").write_text(prompt, encoding="utf-8")
    (artifacts / "version.txt").write_text(version + "\n", encoding="utf-8")
    settings = run_settings(config, condition, version=version, schema_text=schema_text, prompt=prompt)
    verification_log = artifacts / "verification.log"
    verification_log.write_text("", encoding="utf-8")

    work_parent = Path(tempfile.mkdtemp(prefix="csb-"))
    harness = Path(tempfile.mkdtemp(prefix="csb-harness-"))
    invocation: CodexInvocation | None = None
    flags: dict[str, Any] = {}
    started = time.time()
    try:
        workspace = prepare_workspace(
            episode_id, work_parent, condition=condition, tool_bin=tool_bin, manifest=manifest
        )
        before = snapshot_project(workspace.project_dir)
        schema_path = harness / "codex_plan.schema.json"
        schema_path.write_text(schema_text, encoding="utf-8")
        final_path = harness / "final.json"
        command = codex_command(
            codex_bin, config, condition, schema_path=schema_path, final_path=final_path, workspace=workspace.root
        )
        settings["command"] = command
        invocation = invoke_codex(
            command,
            prompt=prompt,
            env=codex_env(tool_bin, workspace.root),
            cwd=workspace.root,
            timeout=float(config["timeout_seconds"]),
            events_path=artifacts / "events.jsonl",
            stderr_path=artifacts / "stderr.txt",
            final_path=final_path,
        )
        if invocation.final_text is not None:
            (artifacts / "final.json").write_text(invocation.final_text, encoding="utf-8")
        after = snapshot_project(workspace.project_dir)
        (artifacts / "workspace.diff").write_text(snapshot_diff(before, after), encoding="utf-8")
        extra_files = sorted(
            str(path.relative_to(workspace.root)) for path in workspace.root.rglob("*")
            if path.is_file() and path.relative_to(workspace.root).parts[0] not in {"project", "warehouse.duckdb", "input.diff"}
        )
        files_changed = changed_files(before, after)
        flags = {
            "files_changed": files_changed,
            "changes_outside_overrides": [name for name in files_changed if name != OVERRIDES],
            "files_created_outside_project": extra_files,
            "isolation": isolation_flags(
                invocation.events, workspace.root, tool_root=tool_bin.parent, manifest=manifest
            ),
            "malformed_event_lines": invocation.malformed_event_lines,
            "exit_code": invocation.exit_code,
            "timed_out": invocation.timed_out,
        }
        if invocation.timed_out:
            raise RuntimeError(f"codex timed out after {config['timeout_seconds']} seconds")
        if invocation.exit_code != 0:
            raise RuntimeError(f"codex exited with status {invocation.exit_code}")
        if invocation.final_text is None:
            raise ValueError("codex wrote no final message")
        try:
            final = json.loads(invocation.final_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"codex final message is not JSON: {exc}") from exc
        jsonschema.Draft202012Validator(json.loads(schema_text)).validate(final)
        plan, evidence = to_steward_plan(final, workspace.root, invocation.events)
        outcomes = verify_findings(plan, workspace, before=before, after=after, log_path=verification_log)
        status = "complete" if all(item["verification"]["passed"] for item in outcomes) else "verification_failed"
        result = ConditionResult(
            episode_id=episode_id,
            mode=episode["mode"],
            condition=condition,
            status=status,
            plan=plan,
            transcript=completed_items(invocation.events),
            usage={"model": settings["model"], **token_usage(invocation.events)},
            seconds=invocation.seconds,
            evidence=evidence,
            verification=outcomes,
        )
        score = score_result(result, episode, contract)
        # No cost is recorded for Codex runs; the scorer's placeholder would read as free.
        score.pop("cost_usd", None)
        payload = {
            "result": {**result.to_dict(), "codex_final": final},
            "score": score,
            "run_settings": settings,
            "flags": flags,
        }
    except Exception as exc:
        payload = {
            "result": {
                "episode_id": episode_id,
                "mode": episode["mode"],
                "condition": condition,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "final_text": invocation.final_text if invocation else None,
                "transcript": completed_items(invocation.events) if invocation else [],
                "usage": {"model": settings["model"], **token_usage(invocation.events if invocation else [])},
                "seconds": invocation.seconds if invocation else time.time() - started,
            },
            "score": {
                "scoring_version": SCORING_VERSION,
                "episode_id": episode_id,
                "condition": condition,
                "episode_success": False,
            },
            "run_settings": settings,
            "flags": flags,
        }
    finally:
        if keep_workspace:
            print(f"kept workspace: {work_parent}", file=sys.stderr)
        else:
            shutil.rmtree(work_parent, ignore_errors=True)
        shutil.rmtree(harness, ignore_errors=True)
    result_path = output_dir / episode_id / f"{condition}.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def condition_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_condition: dict[str, dict[str, Any]] = {}
    for record in records:
        result, score, flags = record["result"], record["score"], record.get("flags", {})
        row = by_condition.setdefault(result["condition"], {
            "run_count": 0,
            "error_count": 0,
            "episode_successes": 0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "patch_count": 0,
            "escalation_count": 0,
            "verification_failures": 0,
            "runs_with_changes_outside_overrides": 0,
            "runs_with_isolation_flags": 0,
        })
        row["run_count"] += 1
        row["error_count"] += result.get("status") == "error"
        row["episode_successes"] += bool(score.get("episode_success", False))
        for key in ("true_positives", "false_positives", "false_negatives", "patch_count",
                    "escalation_count", "verification_failures"):
            row[key] += int(score.get(key, 0) or 0)
        row["runs_with_changes_outside_overrides"] += bool(flags.get("changes_outside_overrides"))
        row["runs_with_isolation_flags"] += bool(flags.get("isolation"))
    return by_condition


def run_baseline(
    *,
    config: dict[str, Any],
    output_dir: Path,
    condition: str,
    episode_ids: list[str],
    jobs: int = 1,
    codex_bin: str | None = None,
    tool_bin: Path | None = None,
    keep_workspaces: bool = False,
) -> list[dict[str, Any]]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    codex_bin = codex_bin or shutil.which("codex")
    if not codex_bin:
        raise FileNotFoundError("codex executable not found on PATH")
    version = codex_version(codex_bin)
    if config["codex_cli_version"] not in version.split():
        raise RuntimeError(f"codex version {version!r} does not match pinned {config['codex_cli_version']}")
    tool_bin = tool_bin or ensure_tool_env(config)
    manifest = load_manifest()
    contract = load_contract()
    output_dir.mkdir(parents=True, exist_ok=True)

    def one(episode_id: str) -> dict[str, Any]:
        return run_one(
            episode_id,
            condition,
            config=config,
            output_dir=output_dir,
            codex_bin=codex_bin,
            tool_bin=tool_bin,
            version=version,
            manifest=manifest,
            contract=contract,
            keep_workspace=keep_workspaces,
        )

    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        list(pool.map(one, episode_ids))
    write_summary(config, output_dir)
    return [
        json.loads((output_dir / episode_id / f"{condition}.json").read_text(encoding="utf-8"))
        for episode_id in episode_ids
    ]


def write_summary(config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Summarize every recorded run in ``output_dir`` across both conditions."""

    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(output_dir.glob("*/codex-*.json"))
    ]
    summary = {
        "config": config,
        "records": [
            {
                "episode_id": record["result"]["episode_id"],
                "condition": record["result"]["condition"],
                "status": record["result"]["status"],
                "error": record["result"].get("error"),
                "score": record["score"],
                "flags": {
                    "files_changed": record.get("flags", {}).get("files_changed"),
                    "isolation": len(record.get("flags", {}).get("isolation", [])),
                },
            }
            for record in records
        ],
        "run_count": len(records),
        "episode_successes": sum(bool(record["score"].get("episode_success")) for record in records),
        "by_condition": condition_summary(records),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen Codex CLI baseline")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--condition", choices=CONDITIONS)
    parser.add_argument("--episodes", default="")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument(
        "--check-tools",
        action="store_true",
        help="create or reuse the tool environment and check dbt and DuckDB in a workspace with network denied",
    )
    parser.add_argument(
        "--check-codex-sandbox",
        action="store_true",
        help="have Codex run dbt parse and a DuckDB query inside its sandbox in a prepared workspace",
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.check_codex_sandbox:
        codex_bin = shutil.which("codex")
        if not codex_bin:
            parser.error("codex executable not found on PATH")
        report = check_codex_sandbox(config, ensure_tool_env(config), codex_bin)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 1
    if args.check_tools:
        tool_bin = ensure_tool_env(config)
        report = check_tool_env(config, tool_bin)
        print(json.dumps({"tool_bin": str(tool_bin), **report}, indent=2))
        return 0 if report["returncode"] == 0 else 1
    if not args.condition or not args.output:
        parser.error("--condition and --output are required")
    episode_ids = (
        [item.strip() for item in args.episodes.split(",") if item.strip()]
        if args.episodes
        else list(config["episodes"])
    )
    records = run_baseline(
        config=config,
        output_dir=args.output,
        condition=args.condition,
        episode_ids=episode_ids,
        jobs=args.jobs,
        keep_workspaces=args.keep_workspaces,
    )
    print(args.output)
    return 0 if all(record["result"].get("status") != "error" for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
