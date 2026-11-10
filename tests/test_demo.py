from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

from catalog_steward import demo
from catalog_steward.config import REPO_ROOT
from catalog_steward.episodes import episode_by_id, load_manifest, reset_episode
from catalog_steward.llm import ScriptedLM
from catalog_steward.protocol import format_final, format_tool_call

EXAMPLE = "change_daily_revenue_filter"
SAVED_STEWARD = REPO_ROOT / "experiments/results/midpoint_v1_2_pilot" / EXAMPLE / "steward.json"


def _out() -> tuple[demo.Out, io.StringIO]:
    buffer = io.StringIO()
    return demo.Out(buffer, width=150), buffer


@pytest.fixture
def demo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A demo results folder holding the saved pilot steward run in place of a live one."""

    monkeypatch.setattr(demo, "DEMO_ROOT", tmp_path)
    (tmp_path / EXAMPLE).mkdir()
    shutil.copy(SAVED_STEWARD, tmp_path / EXAMPLE / "steward.json")
    return tmp_path


def test_parse_task_reads_lines_json_and_the_codex_prompt() -> None:
    expected = demo.StewardTask("change_review", ["daily_revenue"])
    assert demo.parse_task('Trigger: change_review\nAsset scope: ["daily_revenue"]') == expected
    assert demo.parse_task('{"trigger": "change_review", "asset_scope": ["daily_revenue"]}') == expected
    assert demo.parse_task("trigger=change_review\nasset_scope: daily_revenue") == expected
    prompt = (
        REPO_ROOT / "experiments/results/codex_baseline_v1" / EXAMPLE / "codex-matched_artifacts/prompt.txt"
    ).read_text(encoding="utf-8")
    assert demo.parse_task(prompt) == expected


@pytest.mark.parametrize(
    "text",
    ["Trigger: review_everything\nAsset scope: [\"a\"]", "Trigger: change_review", "please review daily_revenue"],
)
def test_parse_task_rejects_text_without_both_inputs(text: str) -> None:
    with pytest.raises(ValueError):
        demo.parse_task(text)


def test_read_task_echoes_piped_input_and_retries_after_a_bad_paste() -> None:
    out, buffer = _out()
    stream = io.StringIO('hello\n\nTrigger: change_review\nAsset scope: ["daily_revenue"]\n')
    task, pasted = demo.read_task(out, stream)
    assert task == demo.StewardTask("change_review", ["daily_revenue"])
    assert pasted.startswith("Trigger: change_review")
    assert "Paste it again" in buffer.getvalue()


def test_live_steward_streams_each_tool_call_and_uses_the_pasted_scope(tmp_path: Path) -> None:
    workspace = reset_episode(EXAMPLE, destination=tmp_path / "episode")
    out, buffer = _out()
    run = demo.LiveStewardRun(workspace, demo.StewardTask("change_review", ["daily_revenue"]), out)

    def plan(messages):
        ids = {item.kind: item.id for item in run.store.items}
        finding = {
            "issue_type": "sql_metadata_drift",
            "asset": "daily_revenue",
            "claim": "The description excludes refunds; the SQL no longer does.",
            "impact": "high",
            "confidence": "high",
            "evidence_ids": [
                ids["catalog_metadata"],
                ids["dbt_model_sql"],
                ids["parsed_sql_facts"],
                ids["repository_diff_or_history"],
            ],
            "action": {"class": "propose", "operation": "request_review", "rationale": "A reviewer decides."},
        }
        return format_final(json.dumps({"summary": "One drift.", "findings": [finding], "unresolved_questions": []}))

    scripted = ScriptedLM([format_tool_call("get_model_sql", {"asset": "daily_revenue"}), plan])
    model = demo.LiveModel(scripted, out, on_first_call=lambda: setattr(run, "phase", "model"))
    result = run.run(model)

    text = buffer.getvalue()
    assert result.status == "complete"
    assert "harness get_catalog_metadata(daily_revenue)" in text
    assert "harness get_change_diff()" in text
    assert "asks for get_model_sql(asset=daily_revenue)" in text
    assert "get_model_sql(daily_revenue)  [model's request]" in text
    assert "plan validator accepts the plan" in text
    assert "propose sql_metadata_drift on daily_revenue: proposed" in text
    assert "evaluation" not in scripted.calls[0][1]["content"]


def test_live_steward_passes_on_a_pasted_scope_instead_of_the_example_scope(tmp_path: Path) -> None:
    workspace = reset_episode(EXAMPLE, destination=tmp_path / "episode")
    out, _ = _out()
    run = demo.LiveStewardRun(workspace, demo.StewardTask("change_review", ["stg_orders"]), out)
    run.collect_evidence()
    assert run.episode["asset_scope"] == ["stg_orders"]
    assert {item.asset for item in run.store.items} == {"stg_orders", None}


def test_proposed_rule_fails_the_saved_codex_patch_and_not_the_steward_proposal(demo_root: Path) -> None:
    episode = episode_by_id(load_manifest(), EXAMPLE)
    assert demo.requires_review(episode)
    assert not demo.requires_review(episode_by_id(load_manifest(), "rem_daily_revenue_filter_drift"))
    steward = demo.load_condition_result(demo.load_live_steward(EXAMPLE))
    codex = demo.load_condition_result(demo.load_saved_codex(EXAMPLE, "codex-matched"))
    assert demo.proposed_rule(steward, episode) == (True, [])
    assert demo.proposed_rule(codex, episode) == (False, ["sql_metadata_drift on daily_revenue"])


def test_score_walkthrough_uses_the_recorded_scorer_and_labels_the_proposed_rule(demo_root: Path) -> None:
    out, buffer = _out()
    assert demo.walk_score(EXAMPLE, "codex-matched", out=out, pause=False) == 0
    text = buffer.getvalue()
    assert text.count("Verdict: SUCCESS") == 2
    assert "matches the score recorded on 2026-11-09: yes" in text
    assert "request a semantic decision about whether refunded orders belong in revenue" in text
    assert "PROPOSED RULE, not the recorded scorer" in text
    assert "patched sql_metadata_drift on daily_revenue before review" in text


def test_codex_view_is_labelled_saved_and_hides_the_temporary_workspace_path() -> None:
    out, buffer = _out()
    assert demo.show_codex(EXAMPLE, "codex-matched", out=out) == 0
    text = buffer.getvalue()
    assert "SAVED RUN, NOT LIVE" in text
    assert "$ cat input.diff" in text
    assert "add project/catalog/overrides.json" in text
    assert "/var/folders/" not in text


def test_compare_shows_both_actions_and_the_codex_catalog_edit(demo_root: Path) -> None:
    out, buffer = _out()
    assert demo.compare(EXAMPLE, "codex-matched", out=out) == 0
    text = buffer.getvalue()
    assert "PROPOSE (request_review)" in text
    assert "PATCH (update_catalog_field) daily_revenue.description" in text
    assert "wrote catalog/overrides.json before any review:" in text
