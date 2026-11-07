"""Strict JSON protocol used between a model and the steward tool loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ParsedResponse:
    kind: str | None = None
    content: str = ""
    tool_call: ToolCall | None = None
    error: str | None = None


def format_tool_call(name: str, arguments: dict[str, Any]) -> str:
    return json.dumps({"type": "tool", "name": name, "arguments": arguments}, sort_keys=True)


def format_final(content: str) -> str:
    return json.dumps({"type": "final", "content": content}, sort_keys=True)


def _unwrap_fence(reply: str) -> str:
    stripped = reply.strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        return stripped[len("```json") : -3].strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped[3:-3].strip()
    return stripped


def parse_response(reply: str) -> ParsedResponse:
    """Parse one exact response object; malformed model text never raises."""

    if not isinstance(reply, str) or not reply.strip():
        return ParsedResponse(error="response is empty")
    try:
        payload = json.loads(_unwrap_fence(reply))
    except (json.JSONDecodeError, TypeError) as exc:
        return ParsedResponse(error=f"response is not one valid JSON object: {exc}")
    if not isinstance(payload, dict):
        return ParsedResponse(error="response must be a JSON object")
    response_type = payload.get("type")
    if response_type == "final":
        if set(payload) != {"type", "content"} or not isinstance(payload.get("content"), str):
            return ParsedResponse(error="final response requires exactly type and string content")
        return ParsedResponse(kind="final", content=payload["content"])
    if response_type == "tool":
        if set(payload) != {"type", "name", "arguments"}:
            return ParsedResponse(error="tool response requires exactly type, name, and arguments")
        if not isinstance(payload.get("name"), str) or not payload["name"].strip():
            return ParsedResponse(error="tool name must be a non-empty string")
        if not isinstance(payload.get("arguments"), dict):
            return ParsedResponse(error="tool arguments must be an object")
        return ParsedResponse(
            kind="tool",
            tool_call=ToolCall(name=payload["name"], arguments=payload["arguments"]),
        )
    return ParsedResponse(error="response type must be 'tool' or 'final'")


def render_tools(schemas: Iterable[dict[str, Any]]) -> str:
    tools = list(schemas)
    contract = {
        "tool_call": {"type": "tool", "name": "tool_name", "arguments": {}},
        "final_answer": {"type": "final", "content": "answer"},
    }
    return (
        "Available tools:\n"
        + json.dumps(tools, indent=2, sort_keys=True)
        + "\n\nReturn exactly one JSON object using one of these shapes:\n"
        + json.dumps(contract, indent=2, sort_keys=True)
    )

