from __future__ import annotations

import json

import pytest

from catalog_steward.agent import AgentConfig, AgentSession
from catalog_steward.llm import ScriptExhausted
from catalog_steward.protocol import format_final, format_tool_call
from tests.fixture_tools import make_fixture_tools
from tests.helpers import events


def test_plain_structured_answer(scripted) -> None:
    model = scripted([format_final("The model is healthy.")])
    fixtures = make_fixture_tools()

    result = AgentSession(model, fixtures.tools).send("Inspect it.")

    assert result.status == "done"
    assert result.text == "The model is healthy."
    assert result.turns == 1
    assert fixtures.calls == []


def test_tool_result_is_visible_to_next_turn(scripted) -> None:
    model = scripted([format_tool_call("add", {"a": 17, "b": 25}), format_final("The sum is 42.")])
    fixtures = make_fixture_tools()

    result = AgentSession(model, fixtures.tools).send("Add the values.")

    assert result.status == "done"
    assert fixtures.calls == [("add", {"a": 17, "b": 25})]
    assert '"sum": 42' in model.calls[1][-1]["content"]
    assert [event["type"] for event in result.transcript] == [
        "user",
        "assistant",
        "tool_call",
        "tool_result",
        "assistant",
    ]


def test_protocol_error_can_recover(scripted) -> None:
    model = scripted(["not json", format_tool_call("echo", {"text": "recovered"}), format_final("done")])
    fixtures = make_fixture_tools()

    result = AgentSession(model, fixtures.tools).send("Recover.")

    assert result.status == "done"
    assert fixtures.calls == [("echo", {"text": "recovered"})]
    assert len(events(result.transcript, "error")) == 1


def test_consecutive_protocol_errors_stop(scripted) -> None:
    model = scripted(["bad"], repeat_last=True)

    result = AgentSession(model, [], AgentConfig(max_consecutive_errors=3)).send("Stop safely.")

    assert result.status == "protocol_error"
    assert result.turns == 3


def test_unknown_tool_and_invalid_arguments_count_as_errors(scripted) -> None:
    model = scripted(
        [
            format_tool_call("missing", {}),
            format_tool_call("add", {"a": 1}),
            format_tool_call("add", {"a": 1}),
        ]
    )

    result = AgentSession(model, make_fixture_tools().tools).send("Malformed calls.")

    assert result.status == "protocol_error"
    assert [event["status"] for event in events(result.transcript, "tool_result")] == [
        "unknown_tool",
        "invalid_args",
        "invalid_args",
    ]


def test_handler_failure_is_returned_and_loop_continues(scripted) -> None:
    model = scripted([format_tool_call("fail", {}), format_final("I handled the failure.")])

    result = AgentSession(model, make_fixture_tools().tools).send("Call the failing tool.")

    assert result.status == "done"
    tool_result = events(result.transcript, "tool_result")[0]
    assert tool_result["status"] == "error"
    assert "LookupError" in model.calls[1][-1]["content"]


def test_write_tool_denied_unless_explicitly_enabled(scripted) -> None:
    fixtures = make_fixture_tools()
    model = scripted([format_tool_call("write_note", {"text": "unsafe"}), format_final("not saved")])

    result = AgentSession(model, fixtures.tools).send("Write.")

    assert result.status == "done"
    assert fixtures.writes == []
    assert events(result.transcript, "tool_result")[0]["status"] == "denied"


def test_max_turns_stops_repeating_tool_loop(scripted) -> None:
    model = scripted([format_tool_call("echo", {"text": "again"})], repeat_last=True)
    fixtures = make_fixture_tools()

    result = AgentSession(model, fixtures.tools, AgentConfig(max_turns=4)).send("Loop.")

    assert result.status == "max_turns"
    assert result.turns == 4
    assert len(model.calls) == 4


def test_unexpected_extra_model_call_is_not_swallowed(scripted) -> None:
    model = scripted([format_tool_call("echo", {"text": "once"})])

    with pytest.raises(ScriptExhausted):
        AgentSession(model, make_fixture_tools().tools).send("Call then answer.")



def test_wrapped_reply_gets_actionable_error_and_retry_succeeds(scripted) -> None:
    wrapped = json.dumps({"tool_call": {"name": "echo", "arguments": {"text": "hi"}, "type": "tool"}})
    model = scripted([wrapped, format_tool_call("echo", {"text": "hi"}), format_final("done")])
    fixtures = make_fixture_tools()

    result = AgentSession(model, fixtures.tools).send("Echo.")

    assert result.status == "done"
    feedback = json.loads(model.calls[1][-1]["content"])
    assert feedback["type"] == "protocol_error"
    assert "top-level keys were ['tool_call']" in feedback["error"]
    assert "without a wrapper key" in feedback["error"]
    assert fixtures.calls == [("echo", {"text": "hi"})]
    assert result.protocol_rejections == 1
    assert result.repair_used is False


def _reject_unless_ok(text: str):
    return None if text == "ok" else f"bad plan: {text}"


def test_repair_turn_fixes_bad_final_once(scripted) -> None:
    model = scripted([format_final("bad"), format_final("ok")])

    result = AgentSession(model, [], final_validator=_reject_unless_ok).send("Plan.")

    assert result.status == "done"
    assert result.text == "ok"
    assert result.repair_used is True
    assert result.protocol_rejections == 0
    rejection = json.loads(model.calls[1][-1]["content"])
    assert rejection["type"] == "final_answer_rejected"
    assert rejection["error"] == "bad plan: bad"
    assert [event["type"] for event in result.transcript].count("final_rejected") == 1


def test_second_bad_final_is_returned_for_caller_rejection(scripted) -> None:
    calls: list[str] = []

    def validator(text: str):
        calls.append(text)
        return _reject_unless_ok(text)

    model = scripted([format_final("bad"), format_final("still bad")])

    result = AgentSession(model, [], final_validator=validator).send("Plan.")

    # Only one repair: the second answer is handed back unvalidated and the caller rejects it.
    assert result.status == "done"
    assert result.text == "still bad"
    assert calls == ["bad"]
    assert len(model.calls) == 2


def test_repair_reply_is_allowed_after_the_last_regular_turn(scripted) -> None:
    model = scripted([format_tool_call("echo", {"text": "a"}), format_final("bad"), format_final("ok")])

    result = AgentSession(
        model, make_fixture_tools().tools, AgentConfig(max_turns=2), final_validator=_reject_unless_ok
    ).send("Plan.")

    assert result.status == "done"
    assert result.text == "ok"
    assert result.turns == 3


def test_validator_from_describes_schema_errors() -> None:
    import jsonschema

    from catalog_steward.agent import validator_from

    schema = {"type": "object", "required": ["findings"]}
    validate = validator_from(lambda text: jsonschema.validate(json.loads(text), schema))

    assert validate('{"findings": []}') is None
    assert "plan does not match the schema at <root>" in validate("{}")
    assert "not valid JSON" in validate("nope")
