"""pi-py Agent 封装：统一文本（含视觉输入）生成。"""

from __future__ import annotations

from typing import Any

from pi_agent_core import Agent, AgentOptions
from pi_ai import (
    AssistantMessage,
    ImageContent,
    SimpleStreamOptions,
    TextContent,
    UserMessage,
    stream_simple,
)
from pi_ai.types import Model


class AgentError(RuntimeError):
    """上游模型调用失败。"""


def _make_stream_fn(max_tokens: int | None, temperature: float | None):
    def stream_fn(model, context, options=None):
        kwargs: dict[str, Any] = {}
        if options is not None:
            try:
                kwargs.update(options.model_dump(exclude_none=True))
            except Exception:
                pass
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        return stream_simple(model, context, SimpleStreamOptions(**kwargs) if kwargs else options)

    return stream_fn


def _last_assistant(messages: list[Any]) -> AssistantMessage | None:
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage) or getattr(msg, "role", None) == "assistant":
            return msg
    return None


def extract_text(message: AssistantMessage | None) -> str:
    if message is None:
        return ""
    parts: list[str] = []
    for block in message.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts).strip()


async def generate_text(
    *,
    model: Model,
    api_key: str,
    prompt: str,
    images: list[dict[str, str]] | None = None,
    system_prompt: str = "",
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """跑一轮无工具 Agent，返回 {text, usage, stop_reason}。"""
    if not api_key:
        raise AgentError("未配置 API Key")

    blocks: list[TextContent | ImageContent] = []
    if prompt:
        blocks.append(TextContent(text=prompt))
    for img in images or []:
        b64 = img.get("b64") or img.get("data") or ""
        mime = img.get("mime") or img.get("mime_type") or "image/png"
        if b64:
            blocks.append(ImageContent(data=b64, mime_type=mime))
    if not blocks:
        raise AgentError("prompt 与 images 不能同时为空")

    agent = Agent(
        AgentOptions(
            initial_state={
                "system_prompt": system_prompt or "",
                "model": model,
                "tools": [],
            },
            get_api_key=lambda _provider: api_key,
            stream_fn=_make_stream_fn(max_tokens, temperature),
        )
    )
    await agent.prompt(UserMessage(content=blocks))
    msg = _last_assistant(agent.state.messages)
    if msg is None:
        raise AgentError("模型未返回 assistant 消息")
    stop = getattr(msg, "stop_reason", None) or "stop"
    err = getattr(msg, "error_message", None)
    if stop in ("error", "aborted"):
        raise AgentError(err or f"模型停止: {stop}")
    text = extract_text(msg)
    usage = getattr(msg, "usage", None)
    usage_out = {"input": 0, "output": 0, "total_tokens": 0, "cost": 0.0}
    if usage is not None:
        usage_out["input"] = int(getattr(usage, "input", 0) or 0)
        usage_out["output"] = int(getattr(usage, "output", 0) or 0)
        usage_out["total_tokens"] = int(getattr(usage, "total_tokens", 0) or 0)
        cost = getattr(usage, "cost", None)
        if cost is not None:
            usage_out["cost"] = float(getattr(cost, "total", 0) or getattr(cost, "input", 0) or 0)
    return {"text": text, "usage": usage_out, "stop_reason": stop}
