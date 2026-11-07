"""Cached language-model access with deterministic test doubles and cost limits."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from catalog_steward.config import Settings, load_settings

Message = dict[str, str]
VALID_ROLES = {"system", "user", "assistant"}
OPENROUTER_URL = "https://openrouter.ai/api/v1"

# USD per million tokens: input, cached input, output. OpenRouter's reported
# request cost is preferred; this table is the fallback and a guard against
# accidentally running an unpriced model.
MODEL_PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-6-sol": (2.00, 0.20, 10.00),
    "gpt-6-astra": (10.00, 1.00, 50.00),
}


class ChatModel(Protocol):
    def __call__(self, messages: Sequence[Message]) -> str: ...


class BudgetExceeded(RuntimeError):
    """Raised before a call that would begin after the configured spend cap."""


class ScriptExhausted(RuntimeError):
    """Raised when deterministic code makes an unexpected model call."""


class OutputTruncated(RuntimeError):
    """Raised when the provider stops because max output tokens were reached."""

    def __init__(self, text: str, *, max_tokens: int) -> None:
        self.text = text
        self.max_tokens = max_tokens
        super().__init__(f"model output stopped at max_tokens={max_tokens}")


def validate_messages(messages: Sequence[Message]) -> None:
    if not isinstance(messages, (list, tuple)) or not messages:
        raise ValueError("messages must be a non-empty list")
    for message in messages:
        if not isinstance(message, dict) or set(message) != {"role", "content"}:
            raise ValueError("each message must contain exactly role and content")
        if message["role"] not in VALID_ROLES:
            raise ValueError(f"unsupported message role: {message['role']!r}")
        if not isinstance(message["content"], str):
            raise ValueError("message content must be a string")


def _short_model(model: str) -> str:
    return model.rsplit("/", 1)[-1]


def _price(model: str) -> tuple[float, float, float]:
    short = _short_model(model)
    matches = [
        (name, price)
        for name, price in MODEL_PRICES.items()
        if short == name or short.startswith(name + "-20")
    ]
    if not matches:
        raise KeyError(f"No fallback token price is configured for model {model!r}")
    return max(matches, key=lambda item: len(item[0]))[1]


def estimated_cost(
    model: str,
    *,
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
) -> float:
    input_price, cached_price, output_price = _price(model)
    fresh_tokens = max(input_tokens - cached_tokens, 0)
    return (
        fresh_tokens * input_price
        + cached_tokens * cached_price
        + output_tokens * output_price
    ) / 1_000_000


def read_ledger(cache_dir: Path) -> list[dict[str, Any]]:
    path = cache_dir / "ledger.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def total_spend(cache_dir: Path) -> float:
    return sum(float(row.get("cost_usd", 0.0)) for row in read_ledger(cache_dir))


_LEDGER_LOCK = threading.Lock()


def _append_ledger(cache_dir: Path, row: Mapping[str, Any]) -> None:
    path = cache_dir / "ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LEDGER_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


class LM:
    """OpenRouter chat model with content-addressed caching and a cost ledger."""

    def __init__(
        self,
        model: str | None = None,
        *,
        settings: Settings | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tag: str = "",
        cache: bool = True,
        salt: str = "",
        cache_dir: Path | None = None,
        budget_usd: float | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.model = model or self.settings.model
        _price(self.model)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tag = tag
        self.cache = cache
        self.salt = salt
        self.cache_dir = cache_dir or self.settings.cache_dir
        self.budget_usd = budget_usd if budget_usd is not None else self.settings.budget_usd
        self.calls = 0
        self.cached_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.seconds = 0.0
        self._client: Any = None

    def __call__(self, messages: Sequence[Message]) -> str:
        validate_messages(messages)
        copied = copy.deepcopy(list(messages))
        key = self._key(copied)
        path = self.cache_dir / key[:2] / f"{key}.json"
        self.calls += 1
        if self.cache and path.exists():
            self.cached_calls += 1
            return str(json.loads(path.read_text(encoding="utf-8"))["text"])

        spent = total_spend(self.cache_dir)
        if spent >= self.budget_usd:
            raise BudgetExceeded(
                f"Recorded spend ${spent:.4f} reached the ${self.budget_usd:.4f} budget"
            )

        started = time.time()
        text, usage = self._complete(copied)
        seconds = time.time() - started
        cost = usage.get("cost_usd")
        if cost is None:
            cost = estimated_cost(
                self.model,
                input_tokens=int(usage.get("input_tokens", 0)),
                cached_tokens=int(usage.get("cached_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            )
        row = {
            "ts": round(started, 3),
            "model": self.model,
            "tag": self.tag,
            "input_tokens": int(usage.get("input_tokens", 0)),
            "cached_tokens": int(usage.get("cached_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "cost_usd": float(cost),
            "seconds": round(seconds, 3),
            "finish_reason": usage.get("finish_reason"),
        }
        _append_ledger(self.cache_dir, row)
        self.input_tokens += row["input_tokens"]
        self.output_tokens += row["output_tokens"]
        self.cost_usd += row["cost_usd"]
        self.seconds += seconds

        if row["finish_reason"] == "length":
            raise OutputTruncated(text, max_tokens=self.max_tokens)
        if self.cache and text.strip():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            temporary.write_text(
                json.dumps({"model": self.model, "text": text}),
                encoding="utf-8",
            )
            temporary.replace(path)
        return text

    def _key(self, messages: list[Message]) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "reasoning_effort": self.settings.reasoning_effort,
                "salt": self.salt,
                "messages": messages,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _complete(self, messages: list[Message]) -> tuple[str, dict[str, Any]]:
        if self._client is None:
            if not self.settings.openrouter_api_key:
                raise RuntimeError("OPENROUTER_API_KEY is required for a live model call")
            from openai import OpenAI

            self._client = OpenAI(
                base_url=OPENROUTER_URL,
                api_key=self.settings.openrouter_api_key,
                max_retries=4,
                timeout=120,
                default_headers={"X-Title": "Catalog Steward"},
            )
        extra_body: dict[str, Any] = {"usage": {"include": True}}
        if self.settings.reasoning_effort:
            extra_body["reasoning"] = {"effort": self.settings.reasoning_effort}
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body=extra_body,
        )
        choice = response.choices[0]
        provider_usage = response.usage
        prompt_details = getattr(provider_usage, "prompt_tokens_details", None)
        usage = {
            "input_tokens": int(getattr(provider_usage, "prompt_tokens", 0) or 0),
            "cached_tokens": int(getattr(prompt_details, "cached_tokens", 0) or 0),
            "output_tokens": int(getattr(provider_usage, "completion_tokens", 0) or 0),
            "finish_reason": getattr(choice, "finish_reason", None),
        }
        provider_cost = getattr(provider_usage, "cost", None)
        if isinstance(provider_cost, (float, int)):
            usage["cost_usd"] = float(provider_cost)
        return choice.message.content or "", usage

    def usage(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "calls": self.calls,
            "cached_calls": self.cached_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "seconds": self.seconds,
        }


class ScriptedLM:
    """Network-free model that replays fixed replies and records every call."""

    model = "scripted"

    def __init__(
        self,
        script: Sequence[str | Callable[[list[Message]], str]],
        *,
        repeat_last: bool = False,
    ) -> None:
        self.script = list(script)
        self.repeat_last = repeat_last
        self.calls: list[list[Message]] = []
        self.replies: list[str] = []

    def __call__(self, messages: Sequence[Message]) -> str:
        validate_messages(messages)
        self.calls.append(copy.deepcopy(list(messages)))
        index = len(self.calls) - 1
        if index >= len(self.script):
            if not self.repeat_last or not self.script:
                raise ScriptExhausted(
                    f"call {index + 1} exceeded a script of {len(self.script)} replies"
                )
            index = len(self.script) - 1
        entry = self.script[index]
        reply = entry(self.calls[-1]) if callable(entry) else entry
        self.replies.append(reply)
        return reply

    @property
    def remaining(self) -> int:
        return max(len(self.script) - len(self.calls), 0)

    def usage(self) -> dict[str, Any]:
        return {"model": self.model, "calls": len(self.calls), "cost_usd": 0.0}


def spending_report(rows: list[dict[str, Any]] | None = None, *, cache_dir: Path | None = None) -> str:
    if rows is None:
        rows = read_ledger(cache_dir or load_settings().cache_dir)
    if not rows:
        return "No LLM calls recorded yet."
    calls = len(rows)
    input_tokens = sum(int(row.get("input_tokens", 0)) for row in rows)
    output_tokens = sum(int(row.get("output_tokens", 0)) for row in rows)
    cost = sum(float(row.get("cost_usd", 0.0)) for row in rows)
    seconds = sum(float(row.get("seconds", 0.0)) for row in rows)
    return (
        f"{calls} calls | {input_tokens} input tokens | {output_tokens} output tokens | "
        f"${cost:.4f} | {seconds:.1f}s"
    )


if __name__ == "__main__":
    print(spending_report())

