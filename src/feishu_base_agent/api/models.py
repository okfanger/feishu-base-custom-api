from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from feishu_base_agent.models_store import ModelsStore, get_store
from feishu_base_agent.schemas import ProviderUpsert

router = APIRouter(prefix="/api", tags=["models"])


def _store(request: Request) -> ModelsStore:
    return getattr(request.app.state, "store", None) or get_store()


@router.get("/models")
def list_models(request: Request):
    return _store(request).list_models()


@router.get("/providers")
def list_providers(request: Request):
    return _store(request).list_providers()


@router.post("/providers")
def create_provider(payload: ProviderUpsert, request: Request):
    store = _store(request)
    if any(p["id"] == payload.id for p in store.list_providers()):
        raise HTTPException(409, f"供应商已存在: {payload.id}")
    try:
        return store.upsert_provider(payload.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.put("/providers/{provider_id}")
def update_provider(provider_id: str, payload: ProviderUpsert, request: Request):
    if payload.id != provider_id:
        raise HTTPException(400, "路径 id 与 body.id 不一致")
    store = _store(request)
    if not any(p["id"] == provider_id for p in store.list_providers()):
        raise HTTPException(404, f"供应商不存在: {provider_id}")
    try:
        return store.upsert_provider(payload.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: str, request: Request):
    store = _store(request)
    try:
        store.delete_provider(provider_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True}


@router.post("/models/{provider_id}/{model_id}/test")
async def test_model(provider_id: str, model_id: str, request: Request):
    from feishu_base_agent.agent_runner import AgentError, generate_text

    store = _store(request)
    ref = f"{provider_id}/{model_id}"
    model = store.get_pi_model(ref)
    if model is None:
        raise HTTPException(404, f"未知模型: {ref}")
    key, _src = store.api_key_for(provider_id)
    if not key:
        raise HTTPException(400, f"模型 {ref} 未配置 API Key（检查 models.yaml 或环境变量）")
    import time

    t0 = time.perf_counter()
    try:
        result = await generate_text(model=model, api_key=key, prompt="你好")
    except AgentError as e:
        raise HTTPException(502, str(e)) from e
    ms = int((time.perf_counter() - t0) * 1000)
    return {"ok": True, "latency_ms": ms, **result}
