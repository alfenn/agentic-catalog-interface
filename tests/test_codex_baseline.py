from __future__ import annotations

import json
import shlex
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from catalog_steward import codex_baseline
from catalog_steward.codex_baseline import (
    CONDITIONS,
    LABEL_MATERIAL,
    assert_no_label_material,
    build_prompt,
    codex_command,
    isolation_flags,
    load_config,
    prepare_workspace,
    run_baseline,
    to_steward_plan,
)
from catalog_steward.config import REPO_ROOT
from catalog_steward.contract import load_contract
from catalog_steward.episodes import episode_by_id, load_manifest

EPISODE = "rem_daily_revenue_filter_drift"
# The stand-in codex and the test fixtures use the repository's own environment.
TOOL_BIN = Path(sys.executable).parent

STANDIN = '''#!{python}
import json, shlex, sys
from pathlib import Path

args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.167.0")
    sys.exit(0)
ws = Path(args[args.index("-C") + 1])
out = Path(args[args.index("-o") + 1])
prompt = sys.stdin.read()
events = [{{"type": "thread.started", "thread_id": "standin"}}, {{"type": "turn.started"}}]

def command(text, output="", exit_code=0):
    events.append({{"type": "item.completed", "item": {{
        "id": f"item_{{len(events)}}", "type": "command_execution",
        "command": "/bin/bash -c " + shlex.quote(text), "aggregated_output": output,
        "exit_code": exit_code, "status": "completed"}}}})

final = None
{body}
if final is not None:
    out.write_text(final if isinstance(final, str) else json.dumps(final), encoding="utf-8")
events.append({{"type": "turn.completed", "usage": {{"input_tokens": 10, "output_tokens": 5}}}})
for event in events:
    print(json.dumps(event))
sys.exit({exit_code})
'''


def codex_finding(action_class: str = "report", **action: Any) -> dict[str, Any]:
    operations = {"patch": "update_catalog_field", "propose": "request_review", "report": "report_only"}
    return {
        "issue_type": "sql_metadata_drift",
        "asset": "daily_revenue",
        "claim": "Catalog prose says all orders; SQL keeps completed orders only.",
        "impact": "high",
        "confidence": "high",
        "evidence": [
            {"kind": "file", "source": "project/models/daily_revenue.sql", "fact": "WHERE status = 'completed'"},
            {"kind": "command", "source": "dbt parse", "fact": "project parses"},
        ],
        "action": {
            "class": action_class,
            "operation": operations[action_class],
            "field": None,
            "value": None,
            "rationale": "Directly supported by the SQL filter.",
            "verification": None,
            **action,
        },
    }


def codex_final(findings: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "summary": "Reviewed daily_revenue.",
        "findings": findings,
        "unresolved_questions": [],
        "changes_made": [],
        "verification_performed": [{"command": "dbt parse", "result": "ok"}],
        **extra,
    }


def make_codex(tmp_path: Path, body: str, *, exit_code: int = 0) -> str:
    path = tmp_path / "codex"
    path.write_text(
        STANDIN.format(python=sys.executable, body=textwrap.dedent(body), exit_code=exit_code),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return str(path)


@pytest.fixture
def repo_env_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests build fixtures with the repository's dbt, which records repository paths."""

    monkeypatch.setattr(codex_baseline, "REPOSITORY_PATHS", ("/nonexistent/repository/marker",))


def run(tmp_path: Path, body: str, *, exit_code: int = 0, episode: str = EPISODE) -> dict[str, Any]:
    output = tmp_path / "results"
    records = run_baseline(
        config=load_config(),
        output_dir=output,
        condition="codex-matched",
        episode_ids=[episode],
        codex_bin=make_codex(tmp_path, body, exit_code=exit_code),
        tool_bin=TOOL_BIN,
    )
    assert (output / episode / "codex-matched.json").exists()
    assert (output / "summary.json").exists()
    return records[0]


def test_frozen_config_matches_implementation() -> None:
    config = load_config()

    assert config["frozen"] is True
    assert config["codex_cli_version"] == "0.167.0"
    assert config["conditions"]["codex-matched"] == {"model": "gpt-6-luna", "reasoning_effort": "low"}
    assert config["conditions"]["codex-frontier"] == {"model": "gpt-6.1-sol", "reasoning_effort": "medium"}
    assert set(config["conditions"]) == set(CONDITIONS)
    assert len(config["episodes"]) == 10
    assert config["scoring_version"] == "midpoint-score-v1"


def _walk(schema: Any, path: str = "$"):
    if isinstance(schema, dict):
        yield path, schema
        for key, value in schema.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            yield from _walk(value, f"{path}[{index}]")


def test_output_schema_satisfies_strict_structured_output() -> None:
    schema = json.loads((REPO_ROOT / "design/codex_plan.schema.json").read_text(encoding="utf-8"))

    for path, node in _walk(schema):
        assert not {"allOf", "if", "then", "else", "oneOf", "$ref"} & set(node), path
        if "properties" in node and isinstance(node["properties"], dict) and not path.endswith(".properties"):
            assert node.get("additionalProperties") is False, path
            assert sorted(node["required"]) == sorted(node["properties"]), path
    for path, node in _walk(schema):
        if path.endswith(".properties"):
            for name, child in node.items():
                assert child, f"{path}.{name} is untyped"
                assert "type" in child or "anyOf" in child, f"{path}.{name} is untyped"


def test_command_pins_model_effort_sandbox_and_schema(tmp_path: Path) -> None:
    config = load_config()
    command = codex_command(
        "codex", config, "codex-frontier",
        schema_path=tmp_path / "s.json", final_path=tmp_path / "f.json", workspace=tmp_path / "ws",
    )

    assert command[:3] == ["codex", "exec", "--ignore-user-config"]
    assert command[command.index("--model") + 1] == "gpt-6.1-sol"
    assert 'model_reasoning_effort="medium"' in command
    assert command[command.index("--sandbox") + 1] == "workspace-write"
    assert {"--skip-git-repo-check", "--ephemeral", "--json"} <= set(command)
    assert command[command.index("--output-schema") + 1] == str(tmp_path / "s.json")
    assert command[command.index("-C") + 1] == str(tmp_path / "ws")
    assert command[-1] == "-"


def test_prompt_carries_contract_but_no_labels() -> None:
    manifest = load_manifest()
    contract = load_contract()
    for episode in manifest["episodes"]:
        prompt = build_prompt(episode, contract)
        assert all(other["id"] not in prompt for other in manifest["episodes"])
        assert episode["description"] not in prompt
        assert json.dumps(episode["asset_scope"]) in prompt
        assert all(issue["id"] in prompt for issue in contract["issue_types"])
        assert ("input.diff" in prompt) == (episode["mode"] == "change_review")


def test_prepared_workspace_has_no_label_material(tmp_path: Path, repo_env_allowed: None) -> None:
    manifest = load_manifest()
    remediation = prepare_workspace(EPISODE, tmp_path / "a", condition="codex-matched", tool_bin=TOOL_BIN)
    change = prepare_workspace(
        "change_daily_revenue_filter", tmp_path / "b", condition="codex-matched", tool_bin=TOOL_BIN
    )

    assert sorted(item.name for item in remediation.root.iterdir()) == ["project", "warehouse.duckdb"]
    assert sorted(item.name for item in change.root.iterdir()) == ["input.diff", "project", "warehouse.duckdb"]
    assert (change.project_dir / "target/manifest.json").exists()
    for workspace in (remediation, change):
        assert not any((workspace.root / name).exists() for name in LABEL_MATERIAL)
        assert workspace.root.name.startswith("ws_")
        for path in workspace.root.rglob("*"):
            if path.is_file():
                data = path.read_bytes()
                assert not any(episode["id"].encode() in data for episode in manifest["episodes"]), path

    (change.project_dir / "notes.txt").write_text("change_daily_revenue_filter", encoding="utf-8")
    with pytest.raises(AssertionError, match="label material"):
        assert_no_label_material(change.root, manifest)


def test_repository_path_in_workspace_is_label_material(tmp_path: Path) -> None:
    (tmp_path / "project").mkdir()
    (tmp_path / "project/manifest.json").write_text(json.dumps({"root": str(REPO_ROOT)}), encoding="utf-8")

    with pytest.raises(AssertionError, match="label material"):
        assert_no_label_material(tmp_path, load_manifest())


def test_clean_run_converts_and_scores(tmp_path: Path, repo_env_allowed: None) -> None:
    final = codex_final([codex_finding("propose", operation="propose_metadata_change")])
    record = run(tmp_path, f"""
        command("cat project/models/daily_revenue.sql", "select ...")
        command("dbt parse", "ok")
        final = {final!r}
    """)

    result, score, flags = record["result"], record["score"], record["flags"]
    assert result["status"] == "complete"
    assert result["condition"] == "codex-matched"
    assert [f["evidence_ids"][0].startswith("ev_codex_") for f in result["plan"]["findings"]] == [True]
    assert score["true_positives"] == 1 and score["false_positives"] == 0 and score["false_negatives"] == 0
    assert score["evidence_validity"] == 1.0
    assert score["episode_success"] is True
    assert "cost_usd" not in score
    assert flags["files_changed"] == [] and flags["isolation"] == []
    artifacts = tmp_path / "results" / EPISODE / "codex-matched_artifacts"
    assert {"prompt.txt", "events.jsonl", "stderr.txt", "final.json", "workspace.diff", "verification.log", "version.txt"} <= {
        path.name for path in artifacts.iterdir()
    }
    summary = json.loads((tmp_path / "results/summary.json").read_text(encoding="utf-8"))
    assert summary["by_condition"]["codex-matched"]["episode_successes"] == 1
    assert "cost" not in json.dumps(summary)


def test_patch_that_verifies(tmp_path: Path, repo_env_allowed: None) -> None:
    value = "Completed-order revenue at one row per order date."
    final = codex_final([codex_finding(
        "patch", field="description", value=value, verification={"field": "description", "equals": value}
    )])
    record = run(tmp_path, f"""
        path = ws / "project/catalog/overrides.json"
        data = json.loads(path.read_text())
        data["assets"]["daily_revenue"]["description"] = {value!r}
        path.write_text(json.dumps(data, indent=2))
        command("dbt parse", "ok")
        final = {final!r}
    """)

    outcome = record["result"]["verification"][0]
    assert outcome["status"] == "verified"
    assert record["result"]["status"] == "complete"
    assert record["flags"]["files_changed"] == ["catalog/overrides.json"]
    assert record["score"]["patch_count"] == 1
    assert record["score"]["verification_failures"] == 0
    assert record["score"]["episode_success"] is True
    assert '+      "description": "Completed-order revenue' in (
        tmp_path / "results" / EPISODE / "codex-matched_artifacts/workspace.diff"
    ).read_text(encoding="utf-8")


def test_claimed_patch_without_file_change_fails_verification(tmp_path: Path, repo_env_allowed: None) -> None:
    value = "Completed-order revenue at one row per order date."
    final = codex_final([codex_finding(
        "patch", field="description", value=value, verification={"field": "description", "equals": value}
    )])
    record = run(tmp_path, f"final = {final!r}")

    outcome = record["result"]["verification"][0]
    assert outcome["status"] == "verification_failed"
    assert "catalog/overrides.json changed daily_revenue.description: False" in outcome["verification"]["checks"]
    assert record["result"]["status"] == "verification_failed"
    assert record["score"]["verification_failures"] == 1
    assert record["score"]["episode_success"] is False


def test_edit_outside_override_file_is_flagged_and_fails(tmp_path: Path, repo_env_allowed: None) -> None:
    final = codex_final([codex_finding("report")])
    record = run(tmp_path, f"""
        path = ws / "project/models/daily_revenue.sql"
        path.write_text(path.read_text().replace("completed", "refunded"))
        final = {final!r}
    """)

    assert record["flags"]["changes_outside_overrides"] == ["models/daily_revenue.sql"]
    surface = record["result"]["verification"][-1]
    assert surface["check"] == "patch_surface" and surface["status"] == "verification_failed"
    assert record["score"]["true_positives"] == 1
    assert record["score"]["episode_success"] is False


def test_undeclared_override_change_fails_surface_check(tmp_path: Path, repo_env_allowed: None) -> None:
    final = codex_final([codex_finding("propose", operation="request_review")])
    record = run(tmp_path, f"""
        path = ws / "project/catalog/overrides.json"
        data = json.loads(path.read_text())
        data["assets"]["daily_revenue"]["grain"] = ["order_id"]
        path.write_text(json.dumps(data))
        final = {final!r}
    """)

    surface = record["result"]["verification"][-1]
    assert surface["status"] == "verification_failed"
    assert any("undeclared: ['daily_revenue.grain']" in check for check in surface["verification"]["checks"])
    assert record["score"]["episode_success"] is False


def test_malformed_output_is_recorded_as_error(tmp_path: Path, repo_env_allowed: None) -> None:
    record = run(tmp_path, """
        command("ls", "project")
        final = "I found one issue but forgot the JSON."
    """)

    assert record["result"]["status"] == "error"
    assert "not JSON" in record["result"]["error"]
    assert record["result"]["final_text"].startswith("I found one issue")
    assert record["result"]["transcript"][0]["type"] == "command_execution"
    assert record["score"]["episode_success"] is False
    assert (tmp_path / "results" / EPISODE / "codex-matched_artifacts/final.json").exists()
    summary = json.loads((tmp_path / "results/summary.json").read_text(encoding="utf-8"))
    assert summary["by_condition"]["codex-matched"]["error_count"] == 1


def test_schema_violation_is_recorded_as_error(tmp_path: Path, repo_env_allowed: None) -> None:
    final = {"summary": "missing the other fields"}
    record = run(tmp_path, f"final = {final!r}")

    assert record["result"]["status"] == "error"
    assert "ValidationError" in record["result"]["error"]


def test_nonzero_exit_is_recorded_as_error(tmp_path: Path, repo_env_allowed: None) -> None:
    final = codex_final([])
    record = run(tmp_path, f"final = {final!r}", exit_code=3)

    assert record["result"]["status"] == "error"
    assert "exited with status 3" in record["result"]["error"]
    assert record["flags"]["exit_code"] == 3
    assert record["score"]["episode_success"] is False


def test_isolation_flags_catch_outside_reads_and_label_material(tmp_path: Path) -> None:
    workspace = tmp_path / "ws_abc"
    tool_root = tmp_path / "tools"

    def item(command: str, output: str = "") -> dict[str, Any]:
        return {"type": "item.completed", "item": {
            "id": command, "type": "command_execution", "command": f"/bin/bash -c '{command}'",
            "aggregated_output": output, "exit_code": 0,
        }}

    events = [
        item("cat project/models/daily_revenue.sql"),
        item(f"{tool_root}/bin/dbt parse"),
        item(f"ls {workspace}/project"),
        item("cat /etc/hosts"),
        item("ls ../"),
        item("cat ../../secrets"),
        item("python -c \"duckdb.connect('../warehouse.duckdb')\""),
        item("rg --files -g '!**/.git/**' -g '!**/target/**'"),
        item("grep -r expected_findings ."),
        item("cat notes", output=f"from {EPISODE}"),
    ]
    flags = isolation_flags(events, workspace, tool_root=tool_root, manifest=load_manifest())
    flagged = {flag["item"]: flag["reasons"] for flag in flags}

    assert set(flagged) == {"cat /etc/hosts", "ls ../", "cat ../../secrets", "grep -r expected_findings .", "cat notes"}
    assert flagged["cat /etc/hosts"] == ["path outside workspace /etc/hosts"]
    assert flagged["ls ../"] == ["parent-directory reference"]
    assert flagged["cat notes"] == [f"episode id {EPISODE}"]


def test_command_citations_resolve_against_commands_that_ran(tmp_path: Path) -> None:
    (tmp_path / "project/models").mkdir(parents=True)
    (tmp_path / "project/models/daily_revenue.sql").write_text("select 1", encoding="utf-8")
    query = "print(c.execute('select 1 limit 10').fetchall())"
    ran = f'cat project/models/x.sql && python -c "import duckdb; {query}; print(2)"'
    cited = f'python -c "import duckdb; {query}"'
    events = [
        {"type": "item.completed", "item": {"id": "a", "type": "command_execution", "exit_code": 0,
                                            "command": "/bin/bash -c " + shlex.quote(ran)}},
        {"type": "item.completed", "item": {"id": "b", "type": "command_execution", "exit_code": 1,
                                            "command": "/bin/bash -c 'dbt test'"}},
    ]
    finding = codex_finding()
    finding["evidence"] = [
        {"kind": "command", "source": cited, "fact": "one statement of a compound command"},
        {"kind": "command", "source": "dbt test", "fact": "failed command"},
        {"kind": "command", "source": "dbt build", "fact": "never ran"},
        {"kind": "file", "source": "models/daily_revenue.sql:3", "fact": "relative to project"},
        {"kind": "file", "source": "project/models/missing.sql", "fact": "does not exist"},
    ]
    plan, evidence = to_steward_plan(codex_final([finding]), tmp_path, events)

    assert len(plan["findings"][0]["evidence_ids"]) == 5
    assert sorted(item["source"] for item in evidence) == ["models/daily_revenue.sql:3", cited]


@pytest.mark.live
def test_live_codex_matched_trial_run(tmp_path: Path) -> None:
    if shutil.which("codex") is None:
        pytest.skip("codex CLI is not installed")
    records = run_baseline(
        config=load_config(),
        output_dir=tmp_path / "results",
        condition="codex-matched",
        episode_ids=[EPISODE],
    )

    assert records[0]["result"]["status"] != "error", records[0]["result"].get("error")
    assert records[0]["flags"]["isolation"] == []
    assert episode_by_id(load_manifest(), EPISODE)["mode"] == records[0]["result"]["mode"]
