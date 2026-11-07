from __future__ import annotations

from pathlib import Path

import pytest

from catalog_steward.episodes import (
    MARKER,
    build_fixture,
    episode_by_id,
    load_manifest,
    reset_episode,
    validate_episodes,
)


def test_manifest_has_balanced_audited_episode_set() -> None:
    manifest = load_manifest()
    episodes = manifest["episodes"]

    assert len(episodes) == 10
    assert sum(episode["mode"] == "remediation" for episode in episodes) == 4
    assert sum(episode["mode"] == "change_review" for episode in episodes) == 6
    assert sum(not episode["expected_findings"] for episode in episodes) == 2
    assert sorted(episode.get("demo_step") for episode in episodes if episode.get("demo_step")) == [1, 2]


def test_remediation_reset_applies_setup_without_change_diff(tmp_path: Path) -> None:
    workspace = reset_episode(
        "rem_daily_revenue_filter_drift",
        destination=tmp_path / "episode",
    )

    override = workspace.project_dir / "catalog/overrides.json"
    assert "Revenue from all orders" in override.read_text(encoding="utf-8")
    assert workspace.diff_path.read_text(encoding="utf-8") == ""
    assert (workspace.root / MARKER).read_text(encoding="utf-8").strip() == workspace.episode_id


def test_change_reset_generates_diff_and_applies_deletion(tmp_path: Path) -> None:
    workspace = reset_episode(
        "change_rename_without_lifecycle",
        destination=tmp_path / "episode",
    )

    diff = workspace.diff_path.read_text(encoding="utf-8")
    assert "a/models/daily_revenue.sql" in diff
    assert "b/models/revenue_daily.sql" in diff
    assert not (workspace.project_dir / "models/daily_revenue.sql").exists()


def test_reset_refuses_to_replace_unmarked_directory(tmp_path: Path) -> None:
    destination = tmp_path / "not-an-episode"
    destination.mkdir()
    (destination / "important.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="unmarked"):
        reset_episode("rem_daily_revenue_filter_drift", destination=destination)

    assert (destination / "important.txt").read_text(encoding="utf-8") == "keep"


def test_clean_fixture_builds_and_emits_manifest(tmp_path: Path) -> None:
    workspace = reset_episode(
        "clean_new_model_documented",
        destination=tmp_path / "episode",
    )

    build_fixture(workspace)

    assert workspace.warehouse_path.exists()
    assert (workspace.project_dir / "target/manifest.json").exists()
    assert "$ dbt seed" in workspace.build_log_path.read_text(encoding="utf-8")


def test_unknown_episode_is_rejected() -> None:
    with pytest.raises(KeyError, match="unknown episode"):
        episode_by_id(load_manifest(), "does_not_exist")


def test_all_episodes_reset_without_building() -> None:
    manifest = load_manifest()

    validated = validate_episodes(manifest)

    assert validated == [episode["id"] for episode in manifest["episodes"]]

