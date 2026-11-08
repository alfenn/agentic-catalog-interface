from __future__ import annotations

import json
from pathlib import Path

import pytest

from catalog_steward.config import Settings
from catalog_steward.llm import (
    BudgetExceeded,
    LM,
    OutputTruncated,
    ScriptedLM,
    spending_report,
)

MESSAGES = [{"role": "user", "content": "hello"}]


class FakeLM(LM):
    def __init__(self, cache_dir: Path, *, finish_reason: str = "stop", cost: float = 0.002):
        settings = Settings.from_mapping({}, root=cache_dir.parent)
        super().__init__(settings=settings, cache_dir=cache_dir, budget_usd=1.0)
        self.completions = 0
        self.finish_reason = finish_reason
        self.fake_cost = cost

    def _complete(self, messages):
        self.completions += 1
        return "cached reply", {
            "input_tokens": 10,
            "cached_tokens": 0,
            "output_tokens": 2,
            "cost_usd": self.fake_cost,
            "finish_reason": self.finish_reason,
        }


def test_identical_call_uses_disk_cache_and_ledger_once(tmp_path: Path) -> None:
    model = FakeLM(tmp_path / "cache")

    assert model(MESSAGES) == "cached reply"
    assert model(MESSAGES) == "cached reply"

    assert model.completions == 1
    assert model.cached_calls == 1
    ledger = (tmp_path / "cache" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 1
    assert json.loads(ledger[0])["cost_usd"] == 0.002


def test_budget_stops_before_next_uncached_call(tmp_path: Path) -> None:
    model = FakeLM(tmp_path / "cache", cost=0.002)
    model.budget_usd = 0.001

    model(MESSAGES)
    with pytest.raises(BudgetExceeded):
        model([{"role": "user", "content": "different"}])


def test_truncated_output_is_charged_but_not_cached(tmp_path: Path) -> None:
    model = FakeLM(tmp_path / "cache", finish_reason="length")

    with pytest.raises(OutputTruncated):
        model(MESSAGES)
    with pytest.raises(OutputTruncated):
        model(MESSAGES)

    assert model.completions == 2


def test_scripted_model_records_deep_copied_calls() -> None:
    model = ScriptedLM(["one"])
    messages = [{"role": "user", "content": "original"}]

    assert model(messages) == "one"
    messages[0]["content"] = "mutated"

    assert model.calls[0][0]["content"] == "original"


def test_spending_report_is_compact() -> None:
    report = spending_report(
        [
            {
                "input_tokens": 10,
                "output_tokens": 5,
                "cost_usd": 0.25,
                "seconds": 1.5,
            }
        ]
    )

    assert "1 calls" in report
    assert "$0.2500" in report



def test_response_without_choices_raises_clear_error(tmp_path: Path) -> None:
    from types import SimpleNamespace

    settings = Settings.from_mapping({"OPENROUTER_API_KEY": "sk-test"}, root=tmp_path)
    model = LM(settings=settings, cache_dir=tmp_path / "cache", budget_usd=1.0)
    error_response = SimpleNamespace(choices=None, usage=None, error={"code": 502, "message": "upstream"})
    model._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: error_response))
    )

    with pytest.raises(RuntimeError, match="no choices.*upstream"):
        model(MESSAGES)


def test_results_dir_setting_controls_default_evaluation_output(tmp_path: Path, monkeypatch) -> None:
    from catalog_steward import evaluation

    captured = {}
    monkeypatch.setenv("CATALOG_STEWARD_RESULTS_DIR", str(tmp_path / "custom"))
    monkeypatch.setattr(
        evaluation,
        "run_evaluation",
        lambda **kwargs: captured.update(kwargs) or [],
    )

    assert evaluation.main(["--conditions", "static", "--episodes", "clean_daily_revenue_metric"]) == 0
    assert captured["output_dir"].parent == tmp_path / "custom"


def test_explicit_reasoning_effort_overrides_environment(tmp_path: Path) -> None:
    from types import SimpleNamespace

    settings = Settings.from_mapping(
        {"OPENROUTER_API_KEY": "sk-test", "CATALOG_STEWARD_REASONING_EFFORT": "high"},
        root=tmp_path,
    )
    requests = []
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost=0.0),
    )

    model = LM(settings=settings, reasoning_effort="low", cache_dir=tmp_path / "cache", budget_usd=1.0)
    model._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: requests.append(kwargs) or response)
        )
    )
    model(MESSAGES)

    assert requests[0]["extra_body"]["reasoning"] == {"effort": "low"}
    assert LM(settings=settings, cache_dir=tmp_path / "cache").reasoning_effort == "high"
