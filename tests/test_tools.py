from __future__ import annotations

from catalog_steward.protocol import ToolCall
from catalog_steward.tools import ToolRegistry
from tests.fixture_tools import make_fixture_tools


def test_registry_validates_and_executes() -> None:
    fixtures = make_fixture_tools()
    registry = ToolRegistry(fixtures.tools)

    result = registry.execute(ToolCall("add", {"a": 17, "b": 25}))

    assert result.status == "ok"
    assert result.content == '{"sum": 42}'
    assert fixtures.calls == [("add", {"a": 17, "b": 25})]


def test_unknown_invalid_and_handler_errors_are_structured() -> None:
    registry = ToolRegistry(make_fixture_tools().tools)

    assert registry.execute(ToolCall("missing", {})).status == "unknown_tool"
    assert registry.execute(ToolCall("add", {"a": 1})).status == "invalid_args"
    failed = registry.execute(ToolCall("fail", {}))
    assert failed.status == "error"
    assert "LookupError" in failed.content


def test_write_tool_is_denied_by_default() -> None:
    fixtures = make_fixture_tools()
    registry = ToolRegistry(fixtures.tools)

    denied = registry.execute(ToolCall("write_note", {"text": "do not save"}))
    allowed = registry.execute(
        ToolCall("write_note", {"text": "save this"}),
        allow_writes=True,
    )

    assert denied.status == "denied"
    assert allowed.status == "ok"
    assert fixtures.writes == ["save this"]

