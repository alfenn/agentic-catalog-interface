from __future__ import annotations

import pytest

from catalog_steward.agent import AgentConfig, AgentSession


@pytest.mark.live
def test_live_model_obeys_final_response_protocol(live_lm) -> None:
    session = AgentSession(
        live_lm,
        [],
        AgentConfig(
            max_turns=3,
            system_prompt="Answer the arithmetic request using the required JSON response protocol.",
        ),
    )

    result = session.send("What is 20 + 22? Answer briefly.")

    assert result.status == "done"
    assert "42" in result.text

