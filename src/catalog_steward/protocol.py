"""Strict JSON protocol used between a model and the steward tool loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

# Wrapper keys a model may copy from documentation instead of returning the inner object.
_WRAPPER_HINTS = {"tool_call", "final_answer", "tool", "final", "response", "answer", "reply"}


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


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _unwrap_fence(reply: str) -> str:
    stripped = reply.strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        return stripped[len("```json") : -3].strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped[3:-3].strip()
    return stripped


def _keys(payload: dict[str, Any]) -> list[str]:
    return sorted(str(key) for key in payload)


def parse_response(reply: str) -> ParsedResponse:
    """Parse one exact response object; malformed model text never raises.

    Error messages state what was received and what to send instead, so a model can
    correct its format on the next turn.
    """

    if not isinstance(reply, str) or not reply.strip():
        return ParsedResponse(
            error='response is empty; reply with one JSON object such as {"type": "tool", ...} '
            'or {"type": "final", ...}'
        )
    try:
        payload = json.loads(_unwrap_fence(reply))
    except (json.JSONDecodeError, TypeError) as exc:
        return ParsedResponse(
            error=f"response is not one valid JSON object ({exc}); reply with only the JSON object, "
            "no surrounding prose"
        )
    if not isinstance(payload, dict):
        return ParsedResponse(
            error=f"response must be a JSON object, got a JSON {type(payload).__name__}; reply with "
            'one object whose "type" is "tool" or "final"'
        )
    response_type = payload.get("type")
    if response_type == "final":
        if set(payload) != {"type", "content"}:
            return ParsedResponse(
                error=f"final response requires exactly the keys type and content; got keys {_keys(payload)}"
            )
        content = payload["content"]
        if isinstance(content, (dict, list)):
            # A structured answer sent as an object is unambiguous; serialize it canonically.
            content = canonical_json(content)
        if not isinstance(content, str):
            return ParsedResponse(
                error=f"final content must be a string (or a JSON object), got {type(content).__name__}"
            )
        return ParsedResponse(kind="final", content=content)
    if response_type == "tool":
        if set(payload) != {"type", "name", "arguments"}:
            return ParsedResponse(
                error=f"tool response requires exactly the keys type, name, and arguments; "
                f"got keys {_keys(payload)}"
            )
        if not isinstance(payload.get("name"), str) or not payload["name"].strip():
            return ParsedResponse(error="tool name must be a non-empty string naming an available tool")
        if not isinstance(payload.get("arguments"), dict):
            return ParsedResponse(
                error=f"tool arguments must be a JSON object, got {type(payload['arguments']).__name__}; "
                "use {} for a tool without arguments"
            )
        return ParsedResponse(
            kind="tool",
            tool_call=ToolCall(name=payload["name"], arguments=payload["arguments"]),
        )
    if "type" not in payload:
        inner = [
            key
            for key, value in payload.items()
            if isinstance(value, dict) and value.get("type") in {"tool", "final"}
        ]
        if len(payload) == 1 and (inner or set(payload) & _WRAPPER_HINTS):
            return ParsedResponse(
                error=f"top-level keys were {_keys(payload)}; return the inner object "
                '(for example {"type": "tool", "name": ..., "arguments": {...}} or '
                '{"type": "final", "content": ...}) without a wrapper key'
            )
        return ParsedResponse(
            error=f'response has no "type" key; top-level keys were {_keys(payload)}. Reply with '
            '{"type": "tool", "name": ..., "arguments": {...}} or {"type": "final", "content": ...}'
        )
    return ParsedResponse(
        error=f'response type must be "tool" or "final", got {json.dumps(response_type)}'
    )


def render_tools(schemas: Iterable[dict[str, Any]]) -> str:
    tools = list(schemas)
    tool_example = {"type": "tool", "name": "tool_name", "arguments": {}}
    final_example = {"type": "final", "content": "<answer as a string>"}
    return (
        "Available tools:\n"
        + json.dumps(tools, indent=2, sort_keys=True)
        + "\n\nEach reply must be exactly one JSON object, with no prose and no wrapper key. "
        "The object itself is the reply: its top-level keys are exactly the ones shown below.\n\n"
        "To call a tool, reply with an object like this (arguments must match the tool's "
        "parameters; use {} when it takes none):\n"
        + json.dumps(tool_example, sort_keys=True)
        + "\n\nTo finish, reply with an object like this. content must be a string holding your "
        "complete answer; when the task asks for a JSON answer, content is that JSON document "
        "serialized as a string:\n"
        + json.dumps(final_example, sort_keys=True)
    )
