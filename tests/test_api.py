from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from feishu_base_agent.models_store import reset_store


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FEISHU_BASE_AGENT_DIR", str(tmp_path))
    monkeypatch.setenv("SKIP_CRAWLER", "1")
    reset_store()
    from feishu_base_agent.app import create_app

    with TestClient(create_app()) as c:
        yield c
    reset_store()


def test_list_models_hides_keys(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret-do-not-leak")
    r = client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    assert "sk-secret-do-not-leak" not in r.text
    refs = [m["ref"] for m in body]
    assert "deepseek/deepseek-chat" in refs
    ds = next(m for m in body if m["ref"] == "deepseek/deepseek-chat")
    assert ds["has_key"] is True
    assert ds["api"] == "openai-completions"


def test_providers_crud_roundtrip(client: TestClient) -> None:
    payload = {
        "id": "acme",
        "name": "Acme",
        "api": "openai-completions",
        "base_url": "https://acme.example/v1",
        "api_key": "sk-hidden",
        "models": [{"id": "fast", "name": "Fast", "input": ["text"]}],
    }
    r = client.post("/api/providers", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["id"] == "acme"
    assert "sk-hidden" not in r.text
    assert created["has_key"] is True

    listed = client.get("/api/providers").json()
    assert any(p["id"] == "acme" for p in listed)

    payload["name"] = "Acme 2"
    payload["api_key"] = ""
    r2 = client.put("/api/providers/acme", json=payload)
    assert r2.status_code == 200
    assert r2.json()["name"] == "Acme 2"
    assert r2.json()["has_key"] is True

    bad = dict(payload)
    bad["id"] = "other"
    assert client.put("/api/providers/acme", json=bad).status_code == 400

    unsupported = dict(payload)
    unsupported["id"] = "x"
    unsupported["api"] = "openai-responses"
    # pydantic 会在 schema 层拒绝
    assert client.post("/api/providers", json=unsupported).status_code == 422

    assert client.delete("/api/providers/acme").status_code == 200
    refs = [m["ref"] for m in client.get("/api/models").json()]
    assert "acme/fast" not in refs


def test_text_unknown_model_404(client: TestClient) -> None:
    r = client.post("/api/text", json={"model_ref": "nope/none", "prompt": "hi"})
    assert r.status_code == 404


def test_text_missing_key_400(client: TestClient) -> None:
    r = client.post("/api/text", json={"model_ref": "openai/gpt-4o-mini", "prompt": "hi"})
    assert r.status_code == 400
    assert "API Key" in r.json()["detail"]


def test_text_success_monkeypatched(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate_text(**kwargs):
        assert kwargs["prompt"] == "写一句口号"
        return {"text": "搞定", "usage": {"input": 1, "output": 2, "total_tokens": 3, "cost": 0.0}, "stop_reason": "stop"}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("feishu_base_agent.api.text.generate_text", fake_generate_text)
    # store 已在启动时加载，热重载应看到新 env
    r = client.post("/api/text", json={"model_ref": "openai/gpt-4o-mini", "prompt": "写一句口号"})
    assert r.status_code == 200, r.text
    assert r.json()["text"] == "搞定"


def test_crawl_unavailable_when_skipped(client: TestClient) -> None:
    r = client.post("/api/crawl", json={"url": "https://example.com"})
    assert r.status_code == 503


def test_index_served(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "任务类型" in r.text
    assert "网页爬取" in r.text
    js = client.get("/js/app.js")
    assert js.status_code == 200
    assert "TASK" in js.text or "guardedRun" in js.text or "callText" in js.text
    sdk = client.get("/lark-sdk.js")
    assert sdk.status_code == 200
