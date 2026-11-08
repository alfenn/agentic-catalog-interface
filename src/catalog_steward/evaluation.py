"""Matched midpoint baselines, run persistence, and episode scoring."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import jsonschema
import yaml

from catalog_steward.agent import AgentConfig, AgentSession
from catalog_steward.config import REPO_ROOT
from catalog_steward.contract import issue_by_id, load_contract
from catalog_steward.episodes import EpisodeWorkspace, episode_by_id, load_manifest, reset_episode
from catalog_steward.evidence import EvidenceStore
from catalog_steward.llm import ChatModel, LM
from catalog_steward.steward import PLAN_SCHEMA_PATH, StewardRun
from catalog_steward.tools import ToolSpec

DEFAULT_CONFIG = REPO_ROOT / "experiments/configs/midpoint_v1.yaml"
GENERIC_PROMPT_VERSION = "generic-hygiene-v1"
SCORING_VERSION = "midpoint-score-v1"


@dataclass(frozen=True)
class ConditionResult:
    episode_id: str
    mode: str
    condition: str
    status: str
    plan: dict[str, Any]
    transcript: list[dict[str, Any]]
    usage: dict[str, Any]
    seconds: float
    evidence: list[dict[str, Any]]
    verification: list[dict[str, Any]]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _object_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _report_action(reason: str) -> dict[str, Any]:
    return {"class": "report", "operation": "report_only", "rationale": reason}


def _finding(
    issue_type: str,
    asset: str,
    claim: str,
    evidence_ids: list[str],
    *,
    impact: str = "medium",
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "asset": asset,
        "claim": claim,
        "impact": impact,
        "confidence": confidence,
        "evidence_ids": evidence_ids,
        "action": _report_action("Static checks report the condition but do not infer a semantic fix."),
    }


def run_static(workspace: EpisodeWorkspace, episode: dict[str, Any]) -> ConditionResult:
    started = time.time()
    store = EvidenceStore(workspace)
    findings: list[dict[str, Any]] = []
    model_assets = [
        asset
        for asset in episode["asset_scope"]
        if (workspace.project_dir / "models" / f"{asset}.sql").exists()
    ]
    for asset in model_assets:
        catalog = store.catalog_metadata(asset)
        schema = store.dbt_schema(asset)
        missing = []
        if not catalog.content["present"]:
            missing.append("catalog entry")
        else:
            missing.extend(
                field for field in ("description", "owner", "lifecycle", "grain")
                if catalog.content.get(field) in (None, "", [])
            )
        if not schema.content["present"]:
            missing.append("dbt schema entry")
        if missing:
            findings.append(
                _finding(
                    "missing_required_metadata",
                    asset,
                    f"Missing required metadata: {', '.join(missing)}.",
                    [catalog.id, schema.id],
                )
            )

    test_evidence, failed_assets = _run_dbt_tests(workspace, model_assets, store)
    for asset in failed_assets:
        if not any(
            finding["issue_type"] == "unsupported_reliability_claim" and finding["asset"] == asset
            for finding in findings
        ):
            findings.append(
                _finding(
                    "unsupported_reliability_claim",
                    asset,
                    "At least one declared dbt test failed.",
                    [test_evidence.id],
                    impact="high",
                )
            )
    plan = {
        "summary": "Static required-field and dbt-test results.",
        "findings": findings[:5],
        "unresolved_questions": [],
    }
    return ConditionResult(
        episode_id=workspace.episode_id,
        mode=episode["mode"],
        condition="static",
        status="complete",
        plan=plan,
        transcript=[],
        usage={"model": None, "calls": 0, "cost_usd": 0.0},
        seconds=time.time() - started,
        evidence=[item.to_dict() for item in store.items],
        verification=[{"dbt_tests_ran": True, "failed_assets": failed_assets}],
    )


def _run_dbt_tests(
    workspace: EpisodeWorkspace,
    selected_assets: list[str],
    store: EvidenceStore,
) -> tuple[Any, list[str]]:
    env = os.environ.copy()
    env["CATALOG_STEWARD_WAREHOUSE_PATH"] = str(workspace.warehouse_path.resolve())
    command = [
        "dbt",
        "test",
        "--project-dir",
        str(workspace.project_dir),
        "--profiles-dir",
        str(workspace.project_dir),
    ]
    if selected_assets:
        command.extend(["--select", " ".join(selected_assets)])
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    run_results_path = workspace.project_dir / "target/run_results.json"
    run_results = (
        json.loads(run_results_path.read_text(encoding="utf-8"))
        if run_results_path.exists()
        else {"results": []}
    )
    failed_assets: set[str] = set()
    for item in run_results.get("results", []):
        if item.get("status") not in {"pass", "success", "skipped"}:
            unique_id = str(item.get("unique_id", ""))
            matches = [asset for asset in selected_assets if asset in unique_id]
            if matches:
                failed_assets.add(max(matches, key=len))
    evidence = store.external_evidence(
        "static_dbt_tests",
        source=run_results_path if run_results_path.exists() else "dbt test",
        content={
            "returncode": result.returncode,
            "failed_assets": sorted(failed_assets),
            "result_count": len(run_results.get("results", [])),
            "output_tail": result.stdout[-4000:],
        },
    )
    return evidence, sorted(failed_assets)


def generic_tools(store: EvidenceStore) -> list[ToolSpec]:
    return [
        ToolSpec(
            "list_files",
            "List raw files in the project.",
            _object_schema({}, []),
            lambda: store.project_listing().to_dict(),
        ),
        ToolSpec(
            "read_file",
            "Read one raw project text file by relative path.",
            _object_schema({"path": {"type": "string", "minLength": 1}}, ["path"]),
            lambda path: store.project_file(path, max_bytes=500_000).to_dict(),
        ),
        ToolSpec(
            "read_diff",
            "Read the raw proposed change diff.",
            _object_schema({}, []),
            lambda: store.change_diff().to_dict(),
        ),
        ToolSpec(
            "query_sql",
            "Run a bounded read-only SQL query against the episode warehouse.",
            _object_schema(
                {
                    "sql": {"type": "string", "minLength": 1},
                    "max_rows": {"type": "integer", "minimum": 1, "maximum": 10000},
                },
                ["sql", "max_rows"],
            ),
            lambda sql, max_rows: store.raw_query(sql, max_rows=max_rows).to_dict(),
        ),
    ]


def run_generic(
    workspace: EpisodeWorkspace,
    episode: dict[str, Any],
    model: ChatModel,
    *,
    max_turns: int = 12,
) -> ConditionResult:
    started = time.time()
    store = EvidenceStore(workspace)
    listing = store.project_listing()
    schema = json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
    issue_labels = [issue["id"] for issue in load_contract()["issue_types"]]
    system = (
        "Review this dbt/catalog maintenance task for data hygiene. Use the raw file and SQL tools "
        "as needed. Return a final response whose content is JSON matching the provided schema. "
        "Use only the listed issue labels and cite evidence IDs returned by tools.\n\n"
        f"Issue labels: {json.dumps(issue_labels)}\n"
        f"Output schema: {json.dumps(schema, sort_keys=True)}"
    )
    prompt = {
        "prompt_version": GENERIC_PROMPT_VERSION,
        "trigger": episode["mode"],
        "asset_scope": episode["asset_scope"],
        "project_listing": listing.to_dict(),
    }
    session = AgentSession(
        model,
        generic_tools(store),
        AgentConfig(max_turns=max_turns, system_prompt=system),
    )
    agent = session.send(json.dumps(prompt, sort_keys=True))
    if agent.status != "done":
        raise RuntimeError(f"generic agent did not finish: {agent.status}: {agent.text}")
    plan = json.loads(agent.text)
    jsonschema.Draft202012Validator(schema).validate(plan)
    available = {item.id for item in store.items}
    scope = set(episode["asset_scope"])
    for finding in plan["findings"]:
        if finding["asset"] not in scope:
            raise ValueError(f"generic finding asset is outside scope: {finding['asset']}")
        unknown = set(finding["evidence_ids"]) - available
        if unknown:
            raise ValueError(f"generic finding cites unknown evidence IDs: {sorted(unknown)}")
    return ConditionResult(
        episode_id=workspace.episode_id,
        mode=episode["mode"],
        condition="generic",
        status="complete",
        plan=plan,
        transcript=agent.transcript,
        usage=agent.usage,
        seconds=time.time() - started,
        evidence=[item.to_dict() for item in store.items],
        verification=[],
    )


def run_steward(
    workspace: EpisodeWorkspace,
    episode: dict[str, Any],
    model: ChatModel,
) -> ConditionResult:
    started = time.time()
    run = StewardRun(workspace)
    result = run.run(model)
    plan = json.loads(Path(result.plan_path).read_text(encoding="utf-8"))
    return ConditionResult(
        episode_id=workspace.episode_id,
        mode=episode["mode"],
        condition="steward",
        status=result.status,
        plan=plan,
        transcript=result.agent.transcript,
        usage=result.agent.usage,
        seconds=time.time() - started,
        evidence=[item.to_dict() for item in run.store.items],
        verification=[asdict(outcome) for outcome in result.outcomes],
    )


def score_result(
    result: ConditionResult,
    episode: dict[str, Any],
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or load_contract()
    expected = {
        (finding["issue_type"], finding["asset"])
        for finding in episode["expected_findings"]
    }
    predicted = {
        (finding["issue_type"], finding["asset"])
        for finding in result.plan.get("findings", [])
    }
    true_positive = expected & predicted
    false_positive = predicted - expected
    false_negative = expected - predicted
    precision = len(true_positive) / len(predicted) if predicted else (1.0 if not expected else 0.0)
    recall = len(true_positive) / len(expected) if expected else 1.0
    evidence_ids = {item["id"] for item in result.evidence}
    cited = {
        evidence_id
        for finding in result.plan.get("findings", [])
        for evidence_id in finding.get("evidence_ids", [])
    }
    valid_evidence = len(cited & evidence_ids) / len(cited) if cited else (1.0 if not predicted else 0.0)
    unsafe = 0
    correct_actions = 0
    for finding in result.plan.get("findings", []):
        try:
            issue = issue_by_id(contract, finding["issue_type"])
        except KeyError:
            unsafe += 1
            continue
        if finding["action"]["class"] not in issue["allowed_actions"]:
            unsafe += 1
        elif (finding["issue_type"], finding["asset"]) in true_positive:
            correct_actions += 1
    verification_failures = sum(
        item.get("status") == "verification_failed" or item.get("verification", {}).get("passed") is False
        for item in result.verification
    )
    clean_pass = not expected and not predicted
    episode_success = (
        not false_positive
        and not false_negative
        and unsafe == 0
        and verification_failures == 0
        and result.status == "complete"
    )
    action_classes = [finding["action"]["class"] for finding in result.plan.get("findings", [])]
    return {
        "scoring_version": SCORING_VERSION,
        "episode_id": episode["id"],
        "condition": result.condition,
        "true_positives": len(true_positive),
        "false_positives": len(false_positive),
        "false_negatives": len(false_negative),
        "precision": precision,
        "recall": recall,
        "correct_action_rate": correct_actions / len(true_positive) if true_positive else (1.0 if not expected else 0.0),
        "unsafe_action_rate": unsafe / len(predicted) if predicted else 0.0,
        "evidence_validity": valid_evidence,
        "regression_detection_rate": recall if episode["mode"] == "change_review" and expected else None,
        "clean_change_pass": clean_pass if episode["mode"] == "change_review" and not expected else None,
        "verification_failures": verification_failures,
        "episode_success": episode_success,
        "patch_count": action_classes.count("patch"),
        "escalation_count": action_classes.count("propose") + action_classes.count("report"),
        "cost_usd": float(result.usage.get("cost_usd", 0.0)),
        "turns": int(result.usage.get("calls", 0)),
        "wall_clock_seconds": result.seconds,
    }


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not config.get("frozen"):
        raise ValueError("evaluation config must be explicitly frozen")
    if config["prompt_versions"] != {
        "generic": GENERIC_PROMPT_VERSION,
        "steward": "specialized-steward-v1",
    }:
        raise ValueError("evaluation prompt versions do not match implementation")
    if config["scoring_version"] != SCORING_VERSION:
        raise ValueError("evaluation scoring version does not match implementation")
    return config


def run_evaluation(
    *,
    config: dict[str, Any],
    output_dir: Path,
    conditions: Iterable[str],
    episode_ids: Iterable[str],
    model_factory: Callable[[str, str], ChatModel] | None = None,
    workspace_root: Path | None = None,
) -> list[dict[str, Any]]:
    manifest = load_manifest()
    contract = load_contract()
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace_root = workspace_root or REPO_ROOT / ".runs/evaluation" / output_dir.name
    records: list[dict[str, Any]] = []
    for episode_id in episode_ids:
        episode = episode_by_id(manifest, episode_id)
        for condition in conditions:
            workspace: EpisodeWorkspace | None = None
            try:
                workspace = reset_episode(
                    episode_id,
                    destination=workspace_root / episode_id / condition,
                    build=True,
                )
                if condition == "static":
                    result = run_static(workspace, episode)
                else:
                    if model_factory is None:
                        raise ValueError("model_factory is required for agent conditions")
                    model = model_factory(condition, episode_id)
                    result = (
                        run_generic(workspace, episode, model, max_turns=int(config["max_turns"]))
                        if condition == "generic"
                        else run_steward(workspace, episode, model)
                    )
                score = score_result(result, episode, contract)
                payload = {"result": result.to_dict(), "score": score}
            except Exception as exc:
                payload = {
                    "result": {
                        "episode_id": episode_id,
                        "condition": condition,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                    "score": {"episode_id": episode_id, "condition": condition, "episode_success": False},
                }
            result_path = output_dir / episode_id / f"{condition}.json"
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if workspace is not None:
                _copy_run_artifacts(
                    workspace,
                    output_dir / episode_id / f"{condition}_artifacts",
                )
            records.append(payload)
    summary = {
        "config": config,
        "records": records,
        "episode_successes": sum(record["score"].get("episode_success", False) for record in records),
        "run_count": len(records),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return records


def _copy_run_artifacts(workspace: EpisodeWorkspace, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    files = {
        workspace.diff_path: "input.diff",
        workspace.build_log_path: "dbt_build.log",
        workspace.root / "steward_ledger.jsonl": "steward_ledger.jsonl",
        workspace.root / "steward_verify.log": "steward_verify.log",
        workspace.project_dir / "target/run_results.json": "dbt_run_results.json",
    }
    for source, name in files.items():
        if source.exists():
            shutil.copy2(source, destination / name)
    generated = workspace.root / "artifacts"
    if generated.exists():
        shutil.copytree(generated, destination / "steward", dirs_exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run matched catalog-steward evaluation conditions")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--conditions", default="static")
    parser.add_argument("--episodes", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--salt", default="midpoint-v1")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    conditions = [item.strip() for item in args.conditions.split(",") if item.strip()]
    invalid = set(conditions) - {"static", "generic", "steward"}
    if invalid:
        parser.error(f"unknown conditions: {sorted(invalid)}")
    if any(condition != "static" for condition in conditions) and not args.live:
        parser.error("agent conditions require --live because they make paid model calls")
    episode_ids = (
        [item.strip() for item in args.episodes.split(",") if item.strip()]
        if args.episodes
        else list(config["episodes"])
    )
    output = args.output or REPO_ROOT / "experiments/results" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    def model_factory(condition: str, episode_id: str) -> LM:
        return LM(
            model=config["model"],
            temperature=float(config["temperature"]),
            max_tokens=int(config["max_tokens"]),
            tag=f"midpoint/{condition}/{episode_id}",
            salt=f"{args.salt}:{condition}:{episode_id}",
        )

    records = run_evaluation(
        config=config,
        output_dir=output,
        conditions=conditions,
        episode_ids=episode_ids,
        model_factory=model_factory if args.live else None,
    )
    print(output)
    return 0 if all(record["result"].get("status") != "error" for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())

