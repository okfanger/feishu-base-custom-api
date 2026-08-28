from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from feishu_base_agent.models_store import (
    ModelsStore,
    resolve_secret,
    SUPPORTED_APIS,
)


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModelsStore:
    monkeypatch.setenv("FEISHU_BASE_AGENT_DIR", str(tmp_path))
    return ModelsStore()


def test_resolve_secret_env_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOO_KEY", "sk-from-env")
    assert resolve_secret("${FOO_KEY}") == ("sk-from-env", "env")
    assert resolve_secret("env:FOO_KEY") == ("sk-from-env", "env")


def test_resolve_secret_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_KEY", raising=False)
    value, source = resolve_secret("${MISSING_KEY}")
    assert value is None
    assert source == "missing"


def test_resolve_secret_plain() -> None:
    assert resolve_secret("sk-plain") == ("sk-plain", "plain")
    assert resolve_secret("") == (None, "missing")
    assert resolve_secret(None) == (None, "missing")


def test_first_load_writes_default_template(store: ModelsStore) -> None:
    data = store.load()
    assert store.yaml_path.is_file()
    assert data["version"] == 1
    ids = [p["id"] for p in data["providers"]]
    assert "openai" in ids
    assert "anthropic" in ids
    assert "deepseek" in ids
    text = store.yaml_path.read_text(encoding="utf-8")
    assert "${OPENAI_API_KEY}" in text


def test_load_builds_pi_models_with_required_fields(store: ModelsStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    store.reload(force=True)
    model = store.get_pi_model("deepseek/deepseek-chat")
    assert model is not None
    assert model.id == "deepseek-chat"
    assert model.name == "DeepSeek Chat"
    assert model.api == "openai-completions"
    assert model.provider == "deepseek"
    assert model.base_url == "https://api.deepseek.com/v1"
    assert "text" in model.input


def test_list_models_never_returns_plaintext_key(store: ModelsStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-super-secret")
    items = store.list_models()
    blob = str(items)
    assert "sk-super-secret" not in blob
    ds = next(m for m in items if m["ref"] == "deepseek/deepseek-chat")
    assert ds["has_key"] is True
    assert ds["key_source"] == "env"
    assert ds["api"] == "openai-completions"


def test_missing_key_marked_not_has_key(store: ModelsStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    items = store.list_models()
    oa = next(m for m in items if m["ref"] == "openai/gpt-4o-mini")
    assert oa["has_key"] is False
    assert oa["key_source"] == "missing"


def test_hot_reload_picks_up_yaml_change(store: ModelsStore) -> None:
    store.load()
    data = yaml.safe_load(store.yaml_path.read_text(encoding="utf-8"))
    data["providers"].append(
        {
            "id": "local",
            "name": "Local",
            "api": "openai-completions",
            "base_url": "http://127.0.0.1:8000/v1",
            "api_key": "sk-local",
            "models": [{"id": "qwen", "name": "Qwen", "input": ["text"]}],
        }
    )
    store.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    items = store.list_models()
    assert any(m["ref"] == "local/qwen" for m in items)
    model = store.get_pi_model("local/qwen")
    assert model is not None
    assert model.base_url == "http://127.0.0.1:8000/v1"
    assert model.name == "Qwen"


def test_save_provider_roundtrip_does_not_leak_key_in_list(store: ModelsStore) -> None:
    store.upsert_provider(
        {
            "id": "acme",
            "name": "Acme",
            "api": "anthropic-messages",
            "base_url": "https://api.anthropic.com",
            "api_key": "sk-keep-secret",
            "models": [{"id": "claude", "name": "Claude", "input": ["text", "image"]}],
        }
    )
    listed = store.list_providers()
    acme = next(p for p in listed if p["id"] == "acme")
    assert "sk-keep-secret" not in str(acme)
    assert acme["has_key"] is True
    assert acme["key_source"] == "plain"
    assert acme["api"] == "anthropic-messages"
    # 再 upsert 不传 key 应保留原 key
    store.upsert_provider(
        {
            "id": "acme",
            "name": "Acme Renamed",
            "api": "anthropic-messages",
            "base_url": "https://api.anthropic.com",
            "models": [{"id": "claude", "name": "Claude", "input": ["text"]}],
        }
    )
    key, source = store.api_key_for("acme")
    assert key == "sk-keep-secret"
    assert source == "plain"
    acme2 = next(p for p in store.list_providers() if p["id"] == "acme")
    assert acme2["name"] == "Acme Renamed"


def test_delete_provider(store: ModelsStore) -> None:
    store.load()
    store.delete_provider("openai")
    refs = [m["ref"] for m in store.list_models()]
    assert not any(r.startswith("openai/") for r in refs)


def test_unsupported_api_rejected(store: ModelsStore) -> None:
    with pytest.raises(ValueError, match="api"):
        store.upsert_provider(
            {
                "id": "bad",
                "name": "Bad",
                "api": "openai-responses",
                "base_url": "https://example.com",
                "models": [{"id": "x", "name": "X"}],
            }
        )
    assert "openai-completions" in SUPPORTED_APIS
    assert "anthropic-messages" in SUPPORTED_APIS
