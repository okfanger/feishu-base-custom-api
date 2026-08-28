from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from feishu_base_agent.agent_runner import AgentError, generate_text
from feishu_base_agent.models_store import parse_ref
from feishu_base_agent.schemas import TextRequest

router = APIRouter(prefix="/api", tags=["text"])


@router.post("/text")
async def run_text(payload: TextRequest, request: Request):
    store = request.app.state.store
    try:
        provider_id, _ = parse_ref(payload.model_ref)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    model = store.get_pi_model(payload.model_ref)
    if model is None:
        raise HTTPException(404, f"未知模型: {payload.model_ref}")
    key, _src = store.api_key_for(provider_id)
    if not key:
        raise HTTPException(400, f"模型 {payload.model_ref} 未配置 API Key")
    images = [{"b64": img.b64, "mime": img.mime} for img in payload.images]
    try:
        result = await generate_text(
            model=model,
            api_key=key,
            prompt=payload.prompt,
            images=images,
            system_prompt=payload.system_prompt,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
    except AgentError as e:
        raise HTTPException(502, str(e)) from e
    return result
