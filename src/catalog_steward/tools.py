"""Schema-checked tool definitions and execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import jsonschema

from catalog_steward.protocol import ToolCall


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    read_only: bool = True

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "read_only": self.read_only,
        }


@dataclass(frozen=True)
class ToolResult:
    name: str
    status: str
    content: str


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolSpec]) -> None:
        self._tools: dict[str, ToolSpec] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"duplicate tool name: {tool.name}")
            jsonschema.Draft202012Validator.check_schema(tool.parameters)
            self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, call: ToolCall, *, allow_writes: bool = False) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return ToolResult(call.name, "unknown_tool", f"unknown tool: {call.name}")
        try:
            jsonschema.validate(call.arguments, tool.parameters)
        except jsonschema.ValidationError as exc:
            return ToolResult(call.name, "invalid_args", exc.message)
        if not tool.read_only and not allow_writes:
            return ToolResult(call.name, "denied", "write-capable tools are disabled for this run")
        try:
            value = tool.handler(**call.arguments)
        except Exception as exc:  # tool failures become evidence for the next model turn
            display_type = getattr(exc, "display_type", type(exc).__name__)
            return ToolResult(call.name, "error", f"{display_type}: {exc}")
        content = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
        return ToolResult(call.name, "ok", content)

