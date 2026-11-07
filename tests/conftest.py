from __future__ import annotations

import re

import pytest

from catalog_steward.llm import LM, ScriptedLM


def _tag(request: pytest.FixtureRequest) -> str:
    node = request.node.nodeid.replace("tests/", "").replace(".py::", "/")
    return re.sub(r"\[.*\]$", "", node)


@pytest.fixture
def scripted():
    def make(script, *, repeat_last: bool = False) -> ScriptedLM:
        return ScriptedLM(script, repeat_last=repeat_last)

    return make


@pytest.fixture
def live_lm(request: pytest.FixtureRequest) -> LM:
    return LM(tag=_tag(request))

