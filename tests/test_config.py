from __future__ import annotations

from pathlib import Path

import pytest

from catalog_steward.config import Settings


def test_defaults_are_local_and_non_live(tmp_path: Path) -> None:
    settings = Settings.from_mapping({}, root=tmp_path)

    settings.validate()

    assert settings.model == "openai/gpt-6-luna"
    assert settings.cache_dir == tmp_path / ".lm_cache"
    assert settings.dbt_project_dir == tmp_path / "data/fixtures/dbt_catalog"
    assert settings.openrouter_api_key is None
    assert settings.report()["openrouter_api_key_configured"] is False
    assert "openrouter_api_key" not in settings.report()


def test_relative_and_absolute_paths_are_resolved(tmp_path: Path) -> None:
    absolute_results = tmp_path / "elsewhere"
    settings = Settings.from_mapping(
        {
            "CATALOG_STEWARD_CACHE_DIR": "local-cache",
            "CATALOG_STEWARD_RESULTS_DIR": str(absolute_results),
        },
        root=tmp_path,
    )

    assert settings.cache_dir == tmp_path / "local-cache"
    assert settings.results_dir == absolute_results


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CATALOG_STEWARD_BUDGET_USD", "0"),
        ("CATALOG_STEWARD_EVAL_SLICE", "-1"),
        ("CATALOG_STEWARD_EVAL_CONCURRENCY", "0"),
    ],
)
def test_positive_bounds_are_enforced(tmp_path: Path, name: str, value: str) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        Settings.from_mapping({name: value}, root=tmp_path)


def test_live_validation_requires_api_key(tmp_path: Path) -> None:
    settings = Settings.from_mapping({}, root=tmp_path)

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        settings.validate(require_live=True)

    live = Settings.from_mapping({"OPENROUTER_API_KEY": "test-key"}, root=tmp_path)
    live.validate(require_live=True)

