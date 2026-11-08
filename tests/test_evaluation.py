from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from catalog_steward.episodes import episode_by_id, load_manifest, reset_episode
from catalog_steward.evaluation import (
    GENERIC_PROMPT_VERSION,
    ConditionResult,
    load_config,
    run_evaluation,
    run_generic,
    score_result,
    _run_dbt_tests,
)
from catalog_steward.evidence import EvidenceStore
from catalog_steward.llm import ScriptedLM
from catalog_steward.protocol import format_final, format_tool_call


def test_frozen_config_matches_implementation() -> None:
    config = load_config()

    assert config["frozen"] is True
    assert config["prompt_versions"]["generic"] == GENERIC_PROMPT_VERSION
    assert config["conditions"] == ["static", "generic", "steward"]
    assert len(config["episodes"]) == 10


def test_generic_agent_has_raw_access_and_same_plan_shape(tmp_path: Path) -> None:
    manifest = load_manifest()
    episode = episode_by_id(manifest, "change_daily_revenue_filter")
    workspace = reset_episode(episode["id"], destination=tmp_path / "episode")

    def final_from_tool_result(messages):
        raw_result = messages[-1]["content"].split("\n", 1)[1]
        evidence_id = json.loads(raw_result)["id"]
        plan = {
            "summary": "The raw SQL change conflicts with completed-only metadata.",
            "findings": [
                {
                    "issue_type": "sql_metadata_drift",
                    "asset": "daily_revenue",
                    "claim": "The filter changed without aligned metadata.",
                    "impact": "high",
                    "confidence": "medium",
                    "evidence_ids": [evidence_id],
                    "action": {
                        "class": "propose",
                        "operation": "request_review",
                        "rationale": "A reviewer must decide whether refunded orders belong in revenue.",
                    },
                }
            ],
            "unresolved_questions": ["Should refunded orders count as revenue?"],
        }
        return format_final(json.dumps(plan))

    model = ScriptedLM(
        [
            format_tool_call("read_file", {"path": "models/daily_revenue.sql"}),
            final_from_tool_result,
        ]
    )

    result = run_generic(workspace, episode, model)
    score = score_result(result, episode)

    assert result.status == "complete"
    assert [event["name"] for event in result.transcript if event["type"] == "tool_call"] == ["read_file"]
    assert score["recall"] == 1.0
    assert score["evidence_validity"] == 1.0
    assert score["episode_success"] is True


def test_static_evaluation_persists_raw_result_and_score(tmp_path: Path) -> None:
    config = load_config()
    output = tmp_path / "results"

    records = run_evaluation(
        config=config,
        output_dir=output,
        conditions=["static"],
        episode_ids=["change_new_model_missing_metadata"],
        workspace_root=tmp_path / "workspaces",
    )

    assert records[0]["result"]["status"] == "complete"
    assert records[0]["score"]["episode_success"] is True
    assert (output / "change_new_model_missing_metadata/static.json").exists()
    assert (output / "change_new_model_missing_metadata/static_artifacts/input.diff").exists()
    assert not (output / "workspaces").exists()
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["run_count"] == 1
    assert summary["episode_successes"] == 1


def test_scorer_penalizes_false_positive_and_disallowed_action() -> None:
    episode = episode_by_id(load_manifest(), "clean_daily_revenue_metric")
    result = ConditionResult(
        episode_id=episode["id"],
        mode=episode["mode"],
        condition="generic",
        status="complete",
        plan={
            "summary": "Noisy result.",
            "findings": [
                {
                    "issue_type": "grain_or_join_drift",
                    "asset": "daily_revenue",
                    "claim": "Unsupported warning.",
                    "impact": "low",
                    "confidence": "low",
                    "evidence_ids": ["ev_raw_1"],
                    "action": {
                        "class": "patch",
                        "operation": "update_catalog_field",
                        "field": "grain",
                        "value": ["order_date"],
                        "rationale": "Patch without enough support.",
                        "verification": {"field": "grain", "equals": ["order_date"]},
                    },
                }
            ],
            "unresolved_questions": [],
        },
        transcript=[],
        usage={"calls": 1, "cost_usd": 0.01},
        seconds=1.0,
        evidence=[{"id": "ev_raw_1"}],
        verification=[],
    )

    score = score_result(result, episode)

    assert score["false_positives"] == 1
    assert score["clean_change_pass"] is False
    assert score["unsafe_action_rate"] == 1.0
    assert score["episode_success"] is False


def test_one_runner_executes_all_three_conditions(tmp_path: Path) -> None:
    config = load_config()
    clean_plan = {
        "summary": "No evidence-backed hygiene finding.",
        "findings": [],
        "unresolved_questions": [],
    }

    records = run_evaluation(
        config=config,
        output_dir=tmp_path / "results",
        conditions=["static", "generic", "steward"],
        episode_ids=["clean_daily_revenue_metric"],
        model_factory=lambda condition, episode_id: ScriptedLM(
            [format_final(json.dumps(clean_plan))]
        ),
        workspace_root=tmp_path / "workspaces",
    )

    assert [record["result"]["condition"] for record in records] == [
        "static",
        "generic",
        "steward",
    ]
    assert all(record["result"]["status"] == "complete" for record in records)
    assert all(record["score"]["episode_success"] is True for record in records)


def test_dbt_invocation_failure_cannot_reuse_build_results(tmp_path: Path, monkeypatch) -> None:
    workspace = reset_episode("clean_daily_revenue_metric", destination=tmp_path / "episode")
    result_path = workspace.project_dir / "target/run_results.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text('{"results": []}', encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout="error"))

    with pytest.raises(RuntimeError, match="produced no run results"):
        _run_dbt_tests(workspace, ["daily_revenue"], EvidenceStore(workspace))


def test_duplicate_findings_do_not_inflate_action_rates() -> None:
    episode = episode_by_id(load_manifest(), "rem_daily_revenue_missing_owner")
    finding = {"issue_type": "missing_required_metadata", "asset": "daily_revenue",
               "evidence_ids": ["ev_1"], "action": {"class": "report"}}
    result = ConditionResult(episode_id=episode["id"], mode=episode["mode"], condition="generic",
                             status="complete", plan={"findings": [finding, finding]}, transcript=[],
                             usage={}, seconds=0, evidence=[{"id": "ev_1"}], verification=[])
    assert score_result(result, episode)["correct_action_rate"] == 1.0
    finding["action"]["class"] = "invalid"
    assert score_result(result, episode)["unsafe_action_rate"] == 1.0



def test_failed_agent_runs_keep_transcript_usage_and_evidence(tmp_path: Path) -> None:
    config = load_config()
    bad_plan = {
        "summary": "Cites a fabricated evidence ID.",
        "findings": [
            {
                "issue_type": "sql_metadata_drift",
                "asset": "daily_revenue",
                "claim": "Filter drift.",
                "impact": "high",
                "confidence": "high",
                "evidence_ids": ["ev_project_file_000000000000"],
                "action": {"class": "report", "operation": "report_only", "rationale": "Report."},
            }
        ],
        "unresolved_questions": [],
    }

    class CostedScript(ScriptedLM):
        def usage(self):
            return {**super().usage(), "cost_usd": 0.25}

    records = run_evaluation(
        config=config,
        output_dir=tmp_path / "results",
        conditions=["generic", "steward"],
        episode_ids=["rem_daily_revenue_filter_drift"],
        model_factory=lambda condition, episode_id: CostedScript(
            [format_tool_call("list_files", {}) if condition == "generic" else
             format_tool_call("get_change_diff", {}), format_final(json.dumps(bad_plan)),
             format_final(json.dumps(bad_plan))]
        ),
        workspace_root=tmp_path / "workspaces",
    )

    for record in records:
        result, score = record["result"], record["score"]
        assert result["status"] == "error"
        assert "unknown evidence IDs" in result["error"]
        assert not result["error"].startswith("ConditionFailed")
        assert [event["type"] for event in result["transcript"]].count("tool_call") == 1
        # The first bad plan used the one repair turn; the second is the error.
        assert [event["type"] for event in result["transcript"]].count("final_rejected") == 1
        assert result["repair_used"] is True
        assert result["protocol_rejections"] == 0
        assert result["final_text"] == json.dumps(bad_plan)
        assert result["evidence"]
        assert score["episode_success"] is False
        assert score["cost_usd"] == 0.25
        assert score["turns"] == 3


def test_steward_condition_uses_configured_max_turns(tmp_path: Path) -> None:
    config = {**load_config(), "max_turns": 2}

    records = run_evaluation(
        config=config,
        output_dir=tmp_path / "results",
        conditions=["generic", "steward"],
        episode_ids=["clean_daily_revenue_metric"],
        model_factory=lambda condition, episode_id: ScriptedLM(
            [format_tool_call("list_files", {}) if condition == "generic" else
             format_tool_call("get_change_diff", {})],
            repeat_last=True,
        ),
        workspace_root=tmp_path / "workspaces",
    )

    for record in records:
        assert "max_turns: stopped after 2 model turns" in record["result"]["error"]
        assert record["score"]["turns"] == 2


def test_config_must_match_version_and_pin_reasoning_effort(tmp_path: Path) -> None:
    import yaml

    from catalog_steward.evaluation import DEFAULT_CONFIG

    frozen = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert frozen["version"] == "1.2.0"
    assert frozen["reasoning_effort"] == "low"
    assert frozen["prompt_versions"] == {
        "generic": "generic-hygiene-v3",
        "steward": "specialized-steward-v3",
    }
    for change in (
        {"version": "1.1.0"},
        {"reasoning_effort": None},
        {"prompt_versions": {"generic": "generic-hygiene-v2", "steward": "specialized-steward-v2"}},
        {"frozen": False},
    ):
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({**frozen, **change}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_config(path)


def test_run_settings_are_recorded_in_summary_and_results(tmp_path: Path) -> None:
    config = load_config()
    output = tmp_path / "results"

    records = run_evaluation(
        config=config,
        output_dir=output,
        conditions=["static"],
        episode_ids=["clean_daily_revenue_metric"],
        workspace_root=tmp_path / "workspaces",
    )

    expected = {
        "model": config["model"],
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
        "max_turns": config["max_turns"],
        "reasoning_effort": "low",
    }
    assert records[0]["run_settings"] == expected
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["run_settings"] == expected
    stored = json.loads((output / "clean_daily_revenue_metric/static.json").read_text(encoding="utf-8"))
    assert stored["run_settings"] == expected


def test_live_evaluation_without_key_exits_before_any_reset(monkeypatch, tmp_path: Path, capsys) -> None:
    from catalog_steward import evaluation
    from catalog_steward.config import Settings

    monkeypatch.setattr(evaluation, "load_settings", lambda: Settings.from_mapping({}, root=tmp_path))

    def fail(*args, **kwargs):
        raise AssertionError("reset must not run without a key")

    monkeypatch.setattr(evaluation, "reset_episode", fail)

    code = evaluation.main(["--conditions", "static,generic,steward", "--live", "--output", str(tmp_path / "out")])

    assert code != 0
    error = capsys.readouterr().err.strip()
    assert error.count("\n") == 0 and "OPENROUTER_API_KEY" in error
    assert not (tmp_path / "out").exists()


def test_live_steward_without_key_exits_before_any_reset(monkeypatch, tmp_path: Path, capsys) -> None:
    from catalog_steward import steward
    from catalog_steward.config import Settings

    monkeypatch.setattr(steward, "load_settings", lambda: Settings.from_mapping({}, root=tmp_path))

    def fail(*args, **kwargs):
        raise AssertionError("reset must not run without a key")

    monkeypatch.setattr(steward, "reset_episode", fail)

    assert steward.main(["clean_daily_revenue_metric"]) != 0
    error = capsys.readouterr().err.strip()
    assert error.count("\n") == 0 and "OPENROUTER_API_KEY" in error


def test_repair_turn_fixes_bad_plan_once_for_both_conditions(tmp_path: Path) -> None:
    config = load_config()
    bad_plan = {
        "summary": "Cites a fabricated evidence ID.",
        "findings": [
            {
                "issue_type": "sql_metadata_drift",
                "asset": "daily_revenue",
                "claim": "Filter drift.",
                "impact": "high",
                "confidence": "high",
                "evidence_ids": ["ev_project_file_000000000000"],
                "action": {"class": "report", "operation": "report_only", "rationale": "Report."},
            }
        ],
        "unresolved_questions": [],
    }
    clean_plan = {"summary": "No evidence-backed finding.", "findings": [], "unresolved_questions": []}

    def repaired(messages):
        rejection = json.loads(messages[-1]["content"])
        assert rejection["type"] == "final_answer_rejected"
        assert "unknown evidence IDs" in rejection["error"]
        # Send the repaired plan as an object to exercise object content as well.
        return json.dumps({"type": "final", "content": clean_plan})

    output = tmp_path / "results"
    records = run_evaluation(
        config=config,
        output_dir=output,
        conditions=["generic", "steward"],
        episode_ids=["clean_daily_revenue_metric"],
        model_factory=lambda condition, episode_id: ScriptedLM(
            [format_final(json.dumps(bad_plan)), repaired]
        ),
        workspace_root=tmp_path / "workspaces",
    )

    for record in records:
        result = record["result"]
        assert result["status"] == "complete", result.get("error")
        assert result["plan"] == clean_plan
        assert result["repair_used"] is True
        assert result["protocol_rejections"] == 0
        assert record["score"]["episode_success"] is True
        assert record["score"]["turns"] == 2
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    for condition in ("generic", "steward"):
        row = summary["by_condition"][condition]
        assert row["run_count"] == 1
        assert row["repair_used_count"] == 1
        assert row["protocol_rejections"] == 0
        assert row["error_count"] == 0


def test_wrapped_reply_counts_as_rejection_in_results_and_summary(tmp_path: Path) -> None:
    config = load_config()
    clean_plan = {"summary": "No finding.", "findings": [], "unresolved_questions": []}
    wrapped = json.dumps({"final_answer": {"type": "final", "content": json.dumps(clean_plan)}})

    def factory(condition: str, episode_id: str) -> ScriptedLM:
        def retry(messages):
            error = json.loads(messages[-1]["content"])["error"]
            assert "['final_answer']" in error and "without a wrapper key" in error
            return format_final(json.dumps(clean_plan))

        return ScriptedLM([wrapped, retry])

    output = tmp_path / "results"
    records = run_evaluation(
        config=config,
        output_dir=output,
        conditions=["generic", "steward"],
        episode_ids=["clean_daily_revenue_metric"],
        model_factory=factory,
        workspace_root=tmp_path / "workspaces",
    )

    for record in records:
        assert record["result"]["status"] == "complete"
        assert record["result"]["protocol_rejections"] == 1
        assert record["result"]["repair_used"] is False
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    for condition in ("generic", "steward"):
        row = summary["by_condition"][condition]
        assert row["protocol_rejections"] == 1
        assert row["runs_with_protocol_rejections"] == 1
        assert row["repair_used_count"] == 0
        assert row["episode_successes"] == 1
