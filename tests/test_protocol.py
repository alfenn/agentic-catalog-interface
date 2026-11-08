from __future__ import annotations

import json

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



def test_render_tools_shows_two_separate_unwrapped_shapes() -> None:
    rendered = render_tools([])

    assert '{"arguments": {}, "name": "tool_name", "type": "tool"}' in rendered
    assert '{"content": "<answer as a string>", "type": "final"}' in rendered
    assert "no wrapper key" in rendered
    assert "tool_call" not in rendered and "final_answer" not in rendered


@pytest.mark.parametrize(
    ("reply", "wrapper"),
    [
        ('{"final_answer": {"type": "final", "content": "x"}}', "final_answer"),
        ('{"tool_call": {"name": "read_diff", "arguments": {}, "type": "tool"}}', "tool_call"),
    ],
)
def test_wrapped_reply_gets_actionable_error(reply: str, wrapper: str) -> None:
    parsed = parse_response(reply)

    assert parsed.kind is None
    assert f"top-level keys were ['{wrapper}']" in parsed.error
    assert "without a wrapper key" in parsed.error


def test_tool_error_names_received_keys() -> None:
    parsed = parse_response('{"type": "tool", "name": "x", "arguments": {}, "id": 1}')

    assert parsed.error == (
        "tool response requires exactly the keys type, name, and arguments; "
        "got keys ['arguments', 'id', 'name', 'type']"
    )


@pytest.mark.parametrize("content", [{"b": 1, "a": [1, 2]}, [{"z": None}]])
def test_object_or_array_final_content_is_serialized_canonically(content) -> None:
    parsed = parse_response(json.dumps({"type": "final", "content": content}))

    assert parsed.error is None
    assert parsed.kind == "final"
    assert parsed.content == json.dumps(content, sort_keys=True)


def test_other_strictness_rules_still_apply() -> None:
    assert parse_response('{"type": "final", "content": {"a": 1}, "extra": 1}').error
    assert parse_response('{"type": "final", "content": 3}').error
    assert parse_response('{"type": "done", "content": "x"}').error
