from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Sequence, TypeVar

FIXTURES = Path(__file__).parent / "fixtures"
T = TypeVar("T")


def load_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def eval_slice(items: Sequence[T]) -> list[T]:
    limit = os.environ.get("CATALOG_STEWARD_EVAL_SLICE")
    return list(items[: int(limit)]) if limit else list(items)


def events(transcript: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [event for event in transcript if event.get("type") == event_type]

