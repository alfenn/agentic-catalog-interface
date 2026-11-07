"""Environment-backed settings and a safe configuration doctor."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def _optional_int(value: str | None, *, name: str) -> int | None:
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _positive_int(value: str, *, name: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _positive_float(value: str, *, name: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _path(root: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else root / candidate


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings; secrets are excluded from reports and reprs."""

    model: str
    reasoning_effort: str
    budget_usd: float
    eval_slice: int | None
    eval_concurrency: int
    cache_dir: Path
    results_dir: Path
    dbt_project_dir: Path
    warehouse_path: Path
    openrouter_api_key: str | None = field(default=None, repr=False)

    @classmethod
    def from_mapping(cls, env: Mapping[str, str], *, root: Path = REPO_ROOT) -> "Settings":
        return cls(
            model=env.get("CATALOG_STEWARD_MODEL", "openai/gpt-6-luna"),
            reasoning_effort=env.get("CATALOG_STEWARD_REASONING_EFFORT", "low"),
            budget_usd=_positive_float(
                env.get("CATALOG_STEWARD_BUDGET_USD", "10"),
                name="CATALOG_STEWARD_BUDGET_USD",
            ),
            eval_slice=_optional_int(
                env.get("CATALOG_STEWARD_EVAL_SLICE"),
                name="CATALOG_STEWARD_EVAL_SLICE",
            ),
            eval_concurrency=_positive_int(
                env.get("CATALOG_STEWARD_EVAL_CONCURRENCY", "2"),
                name="CATALOG_STEWARD_EVAL_CONCURRENCY",
            ),
            cache_dir=_path(root, env.get("CATALOG_STEWARD_CACHE_DIR", ".lm_cache")),
            results_dir=_path(root, env.get("CATALOG_STEWARD_RESULTS_DIR", "experiments/results")),
            dbt_project_dir=_path(
                root,
                env.get("CATALOG_STEWARD_DBT_PROJECT_DIR", "data/fixtures/dbt_catalog"),
            ),
            warehouse_path=_path(
                root,
                env.get("CATALOG_STEWARD_WAREHOUSE_PATH", ".artifacts/catalog.duckdb"),
            ),
            openrouter_api_key=env.get("OPENROUTER_API_KEY") or None,
        )

    def validate(self, *, require_live: bool = False) -> None:
        if not self.model.strip():
            raise ValueError("CATALOG_STEWARD_MODEL cannot be empty")
        if not self.reasoning_effort.strip():
            raise ValueError("CATALOG_STEWARD_REASONING_EFFORT cannot be empty")
        if require_live and not self.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required for live tests; copy .env.example to .env and set it"
            )

    def report(self) -> dict[str, object]:
        """Return a diagnostic report that never exposes the API key."""

        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "budget_usd": self.budget_usd,
            "eval_slice": self.eval_slice,
            "eval_concurrency": self.eval_concurrency,
            "cache_dir": str(self.cache_dir),
            "results_dir": str(self.results_dir),
            "dbt_project_dir": str(self.dbt_project_dir),
            "warehouse_path": str(self.warehouse_path),
            "openrouter_api_key_configured": bool(self.openrouter_api_key),
        }


def load_settings(*, dotenv_path: Path | None = None) -> Settings:
    load_dotenv(dotenv_path or REPO_ROOT / ".env", override=False)
    return Settings.from_mapping(os.environ)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate catalog-steward configuration")
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="also require credentials used by paid/external tests",
    )
    args = parser.parse_args(argv)
    settings = load_settings()
    settings.validate(require_live=args.require_live)
    print(json.dumps(settings.report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

