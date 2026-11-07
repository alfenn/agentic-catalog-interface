from __future__ import annotations

import pytest

from catalog_steward.protocol import (
    format_final,
    format_tool_call,
    parse_response,
    render_tools,
)


def test_tool_call_round_trip_preserves_nested_arguments() -> None:
    arguments = {
        "text": "quotes \" and unicode café",
        "nested": {"items": [1, True, None, {"closing": "}"}]},
    }
    parsed = parse_response(format_tool_call("echo", arguments))

    assert parsed.error is None
    assert parsed.tool_call is not None
    assert parsed.tool_call.name == "echo"
    assert parsed.tool_call.arguments == arguments


def test_final_round_trip() -> None:
    parsed = parse_response(format_final("Verified repair."))

    assert parsed.kind == "final"
    assert parsed.content == "Verified repair."


def test_json_fence_is_accepted_but_surrounding_prose_is_not() -> None:
    payload = format_final("done")

    assert parse_response(f"```json\n{payload}\n```").content == "done"
    assert parse_response(f"Here is the result: {payload}").error


@pytest.mark.parametrize(
    "reply",
    ["", "{", "[]", "{}", "null", '{"type":"tool","name":"x"}', '{"type":"final","content":3}'],
)
def test_malformed_responses_never_raise(reply: str) -> None:
    parsed = parse_response(reply)

    assert parsed.error
    assert parsed.tool_call is None


def test_render_tools_contains_names_schemas_and_output_contract() -> None:
    rendered = render_tools(
        [
            {
                "name": "inspect_model",
                "description": "Inspect a model.",
                "parameters": {"type": "object", "properties": {}},
                "read_only": True,
            }
        ]
    )

    assert "inspect_model" in rendered
    assert "arguments" in rendered
    assert "final" in rendered

