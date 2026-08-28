from __future__ import annotations

import pytest
from pi_ai.providers.faux import FAUX_MODEL, FauxScript, clear_scripts, push_script

from feishu_base_agent.agent_runner import AgentError, generate_text


@pytest.fixture(autouse=True)
def _clear_faux() -> None:
    clear_scripts()
    yield
    clear_scripts()


@pytest.mark.asyncio
async def test_generate_text_uses_agent_and_returns_usage() -> None:
    push_script(FauxScript(text="你好世界"))
    result = await generate_text(model=FAUX_MODEL, api_key="unused", prompt="hi")
    assert result["text"] == "你好世界"
    assert result["stop_reason"] in ("stop", "length")
    assert "input" in result["usage"]
    assert "output" in result["usage"]


@pytest.mark.asyncio
async def test_generate_text_error_script_raises() -> None:
    push_script(FauxScript(error="upstream boom"))
    with pytest.raises(AgentError, match="boom"):
        await generate_text(model=FAUX_MODEL, api_key="x", prompt="hi")


@pytest.mark.asyncio
async def test_generate_text_requires_key_and_content() -> None:
    with pytest.raises(AgentError, match="API Key"):
        await generate_text(model=FAUX_MODEL, api_key="", prompt="hi")
    with pytest.raises(AgentError, match="不能同时为空"):
        await generate_text(model=FAUX_MODEL, api_key="x", prompt="")
