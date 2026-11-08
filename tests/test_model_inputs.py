"""Model-visible inputs must not leak labels and must be byte-stable across runs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from catalog_steward.config import REPO_ROOT
from catalog_steward.episodes import load_manifest, reset_episode, workspace_token
from catalog_steward.evaluation import generic_tools, load_config, run_evaluation
from catalog_steward.evidence import EvidenceStore
from catalog_steward.llm import ScriptedLM
from catalog_steward.protocol import ToolCall, format_final
from catalog_steward.tools import ToolRegistry

LEAK_EPISODES = [
    "rem_daily_revenue_filter_drift",
    "rem_legacy_model_lifecycle",
    "change_rename_without_lifecycle",
    "clean_daily_revenue_metric",
]
STABLE_EPISODE = "change_rename_without_lifecycle"
CLEAN_PLAN = format_final(
    json.dumps({"summary": "No finding.", "findings": [], "unresolved_questions": []})
)


def _capture(tmp_path: Path, name: str, episode_ids: list[str]) -> dict[tuple[str, str], list[dict]]:
    """Run both model conditions with a scripted model; return each first model input."""

    models: dict[tuple[str, str], ScriptedLM] = {}

    def factory(condition: str, episode_id: str) -> ScriptedLM:
        models[(episode_id, condition)] = ScriptedLM([CLEAN_PLAN])
        return models[(episode_id, condition)]

    run_evaluation(
        config=load_config(),
        output_dir=tmp_path / name / "results",
        conditions=["generic", "steward"],
        episode_ids=episode_ids,
        model_factory=factory,
        workspace_root=tmp_path / name / "workspaces",
    )
    return {key: model.calls[0] for key, model in models.items()}


@pytest.fixture(scope="module")
def first_inputs(tmp_path_factory: pytest.TempPathFactory) -> dict[tuple[str, str], list[dict]]:
    return _capture(tmp_path_factory.mktemp("leak"), "run", LEAK_EPISODES)


def _forbidden_strings() -> list[str]:
    manifest = load_manifest()
    forbidden: list[str] = []
    for episode in manifest["episodes"]:
        forbidden.append(episode["id"])
        forbidden.append(episode["description"])
        for key in ("acceptable_actions", "unsafe_actions", "postconditions"):
            forbidden.extend(episode.get(key, []))
        for key in ("setup_overlay", "change_overlay"):
            if episode["fixture"].get(key):
                forbidden.append(episode["fixture"][key])
        for condition in ("generic", "steward", "static"):
            forbidden.append(workspace_token(episode["id"], condition))
    forbidden.extend(["overlays/", "expected_findings", "acceptable_actions", "unsafe_actions"])
    return forbidden


def test_initial_prompts_contain_no_episode_labels(first_inputs) -> None:
    assert set(first_inputs) == {(e, c) for e in LEAK_EPISODES for c in ("generic", "steward")}
    forbidden = _forbidden_strings()
    for key, messages in first_inputs.items():
        text = "\n".join(message["content"] for message in messages)
        leaked = [item for item in forbidden if item in text]
        assert not leaked, f"{key} leaks {leaked}"
        # Workspace paths are replaced by a stable placeholder, never the real directory.
        for real_root in {tempfile.gettempdir(), str(Path(tempfile.gettempdir()).resolve()), str(REPO_ROOT)}:
            assert real_root not in text


def test_generic_listing_has_no_labels_and_shows_target_files(first_inputs) -> None:
    for episode_id in LEAK_EPISODES:
        prompt = json.loads(first_inputs[(episode_id, "generic")][-1]["content"])
        listing = prompt["project_listing"]
        paths = [entry["path"] for entry in listing["content"]["files"]]
        assert "target/manifest.json" in paths
        assert ".user.yml" not in paths
        serialized = json.dumps(listing)
        assert not [item for item in _forbidden_strings() if item in serialized]


def test_fresh_resets_produce_byte_identical_model_inputs(tmp_path: Path, first_inputs) -> None:
    # A second, independent run under a different, differently sized root.
    second = _capture(tmp_path, "a-much-longer-second-run-directory", [STABLE_EPISODE])
    for condition in ("generic", "steward"):
        first_bytes = json.dumps(first_inputs[(STABLE_EPISODE, condition)]).encode("utf-8")
        second_bytes = json.dumps(second[(STABLE_EPISODE, condition)]).encode("utf-8")
        assert first_bytes == second_bytes, condition


def test_tool_results_redact_paths_and_volatile_dbt_fields(tmp_path: Path) -> None:
    episode_id = "rem_daily_revenue_filter_drift"
    workspace = reset_episode(
        episode_id,
        destination=tmp_path / workspace_token(episode_id, "generic"),
        build=True,
    )
    registry = ToolRegistry(generic_tools(EvidenceStore(workspace)))

    run_results = registry.execute(ToolCall("read_file", {"path": "target/run_results.json"}))
    seed_sql = registry.execute(
        ToolCall("read_file", {"path": "target/run/catalog_steward_fixture/seeds/raw_orders.csv"})
    )
    for result in (run_results, seed_sql):
        assert result.status == "ok"
        assert str(tmp_path) not in result.content
        assert workspace_token(episode_id, "generic") not in result.content
        assert "/workspace/project" in result.content
    document = json.loads(json.loads(run_results.content)["content"]["text"])
    assert document["metadata"]["invocation_id"] == "<normalized>"
    assert document["results"][0]["execution_time"] == "<normalized>"

    missing = registry.execute(ToolCall("read_file", {"path": "missing.sql"}))
    assert missing.status == "error" and missing.content.startswith("FileNotFoundError")


def test_raw_sql_cannot_read_files_outside_the_warehouse(tmp_path: Path) -> None:
    workspace = reset_episode(
        "clean_daily_revenue_metric",
        destination=tmp_path / "ws",
        build=True,
    )
    registry = ToolRegistry(generic_tools(EvidenceStore(workspace)))

    ok = registry.execute(ToolCall("query_sql", {"sql": "select count(*) from raw_orders", "max_rows": 1}))
    blocked = registry.execute(
        ToolCall(
            "query_sql",
            {"sql": "select * from read_text('data/episodes/manifest.yaml')", "max_rows": 1},
        )
    )

    assert ok.status == "ok"
    assert blocked.status == "error"
    assert "rem_" not in blocked.content
