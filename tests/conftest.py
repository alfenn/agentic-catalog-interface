from __future__ import annotations

import re

import pytest

from catalog_steward.config import load_settings
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
    settings = load_settings()
    if not settings.openrouter_api_key:
        pytest.skip("OPENROUTER_API_KEY is not set; live tests need a key")
    return LM(settings=settings, tag=_tag(request))

