"""~/.feishu-base-agent/models.yaml 读写，并注册到 pi_ai 模型表。"""

from __future__ import annotations

import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pi_ai import Model, ModelCost, register_model

from feishu_base_agent.paths import ensure_agent_dir, models_yaml_path

SUPPORTED_APIS = ("openai-completions", "anthropic-messages")
ENV_PLACEHOLDER = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")

DEFAULT_YAML = """\
# 飞书多维表格插件 · 模型/供应商配置
# 路径: ~/.feishu-base-agent/models.yaml
# api 目前支持: openai-completions / anthropic-messages
# api_key 支持明文、${ENV_VAR} 或 env:ENV_VAR
version: 1
providers:
  - id: openai
    name: OpenAI
    api: openai-completions
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
    models:
      - id: gpt-4o-mini
        name: GPT-4o mini
        input: [text, image]
        context_window: 128000
        max_tokens: 16384
      - id: gpt-4o
        name: GPT-4o
        input: [text, image]
        context_window: 128000
        max_tokens: 16384
  - id: anthropic
    name: Anthropic
    api: anthropic-messages
    base_url: https://api.anthropic.com
    api_key: ${ANTHROPIC_API_KEY}
    models:
      - id: claude-sonnet-4-5
        name: Claude Sonnet 4.5
        input: [text, image]
        context_window: 200000
        max_tokens: 8192
      - id: claude-haiku-4-5
        name: Claude Haiku 4.5
        input: [text, image]
        context_window: 200000
        max_tokens: 8192
  - id: deepseek
    name: DeepSeek
    api: openai-completions
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
    models:
      - id: deepseek-chat
        name: DeepSeek Chat
        input: [text]
        context_window: 64000
        max_tokens: 8192
        cost: { input: 0.14, output: 0.28, cache_read: 0.014 }
"""


def resolve_secret(raw: str | None) -> tuple[str | None, str]:
    """返回 (resolved_or_none, source) ，source 为 env / plain / missing。"""
    if raw is None:
        return None, "missing"
    text = str(raw).strip()
    if not text:
        return None, "missing"
    m = ENV_PLACEHOLDER.match(text)
    if m:
        val = os.environ.get(m.group(1), "")
        return (val, "env") if val else (None, "missing")
    if text.startswith("env:"):
        name = text[4:].strip()
        val = os.environ.get(name, "")
        return (val, "env") if val else (None, "missing")
    return text, "plain"


def parse_ref(ref: str) -> tuple[str, str]:
    if "/" not in ref:
        raise ValueError(f"模型引用须为 provider/id，收到: {ref!r}")
    provider, model_id = ref.split("/", 1)
    if not provider or not model_id:
        raise ValueError(f"模型引用须为 provider/id，收到: {ref!r}")
    return provider, model_id


def _cost_from_dict(raw: Any) -> ModelCost:
    if not raw or not isinstance(raw, dict):
        return ModelCost()
    kwargs: dict[str, Any] = {}
    for k in ("input", "output", "cache_read", "cacheRead", "cache_write", "cacheWrite"):
        if k in raw:
            kwargs[k] = raw[k]
    return ModelCost(**kwargs)


def _model_name(mid: str, spec: dict[str, Any]) -> str:
    return str(spec.get("name") or mid)


def _build_pi_model(provider: dict[str, Any], spec: dict[str, Any]) -> Model:
    mid = str(spec["id"])
    input_kinds = spec.get("input") or ["text"]
    cost = _cost_from_dict(spec.get("cost"))
    kwargs: dict[str, Any] = {
        "id": mid,
        "name": _model_name(mid, spec),
        "api": provider["api"],
        "provider": provider["id"],
        "base_url": provider["base_url"],
        "input": list(input_kinds),
        "cost": cost,
        "reasoning": bool(spec.get("reasoning", False)),
        "context_window": int(spec.get("context_window") or spec.get("contextWindow") or 0),
        "max_tokens": int(spec.get("max_tokens") or spec.get("maxTokens") or 0),
    }
    if spec.get("sampling_params") or spec.get("samplingParams"):
        kwargs["sampling_params"] = spec.get("sampling_params") or spec.get("samplingParams")
    headers = spec.get("headers") or provider.get("headers")
    if headers:
        kwargs["headers"] = dict(headers)
    if spec.get("compat"):
        kwargs["compat"] = dict(spec["compat"])
    return Model(**kwargs)


class ModelsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.yaml_path = path or models_yaml_path()
        self._mtime: float | None = None
        self._data: dict[str, Any] = {"version": 1, "providers": []}
        self._pi: dict[str, Model] = {}

    def load(self) -> dict[str, Any]:
        ensure_agent_dir()
        if not self.yaml_path.exists():
            self.yaml_path.write_text(DEFAULT_YAML, encoding="utf-8")
        return self.reload(force=True)

    def reload(self, force: bool = False) -> dict[str, Any]:
        if not self.yaml_path.exists():
            return self.load()
        mtime = self.yaml_path.stat().st_mtime
        if not force and self._mtime is not None and mtime == self._mtime:
            return self._data
        raw = yaml.safe_load(self.yaml_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("models.yaml 根节点必须是 mapping")
        providers = raw.get("providers") or []
        if not isinstance(providers, list):
            raise ValueError("providers 必须是列表")
        self._data = {"version": raw.get("version", 1), "providers": providers}
        self._mtime = mtime
        self._rebuild_pi()
        return self._data

    def ensure_fresh(self) -> dict[str, Any]:
        if not self.yaml_path.exists():
            return self.load()
        mtime = self.yaml_path.stat().st_mtime
        if self._mtime is None or mtime != self._mtime:
            return self.reload(force=True)
        return self._data

    def _rebuild_pi(self) -> None:
        self._pi = {}
        for provider in self._data.get("providers") or []:
            if not isinstance(provider, dict) or not provider.get("id"):
                continue
            api = provider.get("api")
            if api not in SUPPORTED_APIS:
                continue
            if not provider.get("base_url"):
                continue
            for spec in provider.get("models") or []:
                if not isinstance(spec, dict) or not spec.get("id"):
                    continue
                try:
                    model = _build_pi_model(provider, spec)
                except Exception:
                    continue
                register_model(model)
                self._pi[f"{provider['id']}/{spec['id']}"] = model

    def _provider(self, provider_id: str) -> dict[str, Any] | None:
        for p in self._data.get("providers") or []:
            if isinstance(p, dict) and p.get("id") == provider_id:
                return p
        return None

    def get_pi_model(self, ref: str) -> Model | None:
        self.ensure_fresh()
        return self._pi.get(ref)

    def api_key_for(self, provider_id: str) -> tuple[str | None, str]:
        self.ensure_fresh()
        p = self._provider(provider_id)
        if p is None:
            return None, "missing"
        return resolve_secret(p.get("api_key"))

    def key_meta(self, provider: dict[str, Any]) -> dict[str, Any]:
        raw = provider.get("api_key")
        value, source = resolve_secret(raw)
        hint = None
        if isinstance(raw, str) and raw.strip():
            text = raw.strip()
            if ENV_PLACEHOLDER.match(text) or text.startswith("env:"):
                hint = text
        return {
            "has_key": bool(value),
            "key_source": source,
            "key_hint": hint,
        }

    def list_models(self) -> list[dict[str, Any]]:
        self.ensure_fresh()
        out: list[dict[str, Any]] = []
        for provider in self._data.get("providers") or []:
            if not isinstance(provider, dict):
                continue
            meta = self.key_meta(provider)
            for spec in provider.get("models") or []:
                if not isinstance(spec, dict) or not spec.get("id"):
                    continue
                mid = spec["id"]
                out.append(
                    {
                        "ref": f"{provider.get('id')}/{mid}",
                        "provider_id": provider.get("id"),
                        "provider_name": provider.get("name") or provider.get("id"),
                        "id": mid,
                        "name": _model_name(mid, spec),
                        "api": provider.get("api"),
                        "base_url": provider.get("base_url"),
                        "input": list(spec.get("input") or ["text"]),
                        "context_window": spec.get("context_window") or spec.get("contextWindow") or 0,
                        "max_tokens": spec.get("max_tokens") or spec.get("maxTokens") or 0,
                        **meta,
                    }
                )
        return out

    def list_providers(self) -> list[dict[str, Any]]:
        self.ensure_fresh()
        out: list[dict[str, Any]] = []
        for provider in self._data.get("providers") or []:
            if not isinstance(provider, dict):
                continue
            meta = self.key_meta(provider)
            models = []
            for spec in provider.get("models") or []:
                if not isinstance(spec, dict) or not spec.get("id"):
                    continue
                models.append(
                    {
                        "id": spec["id"],
                        "name": _model_name(spec["id"], spec),
                        "input": list(spec.get("input") or ["text"]),
                        "context_window": spec.get("context_window") or spec.get("contextWindow") or 0,
                        "max_tokens": spec.get("max_tokens") or spec.get("maxTokens") or 0,
                        "reasoning": bool(spec.get("reasoning", False)),
                        "cost": spec.get("cost") or {},
                    }
                )
            out.append(
                {
                    "id": provider.get("id"),
                    "name": provider.get("name") or provider.get("id"),
                    "api": provider.get("api"),
                    "base_url": provider.get("base_url"),
                    "headers": provider.get("headers") or {},
                    "models": models,
                    **meta,
                }
            )
        return out

    def _write(self, data: dict[str, Any]) -> None:
        ensure_agent_dir()
        payload = {"version": data.get("version", 1), "providers": data.get("providers") or []}
        text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        header = (
            "# 飞书多维表格插件 · 模型/供应商配置\n"
            "# api 目前支持: openai-completions / anthropic-messages\n"
            "# api_key 支持明文、${ENV_VAR} 或 env:ENV_VAR\n"
        )
        self.yaml_path.write_text(header + text, encoding="utf-8")
        self.reload(force=True)

    def upsert_provider(self, spec: dict[str, Any]) -> dict[str, Any]:
        self.ensure_fresh()
        pid = str(spec.get("id") or "").strip()
        if not pid:
            raise ValueError("供应商 id 必填")
        api = spec.get("api")
        if api not in SUPPORTED_APIS:
            raise ValueError(f"不支持的 api: {api!r}，可选 {SUPPORTED_APIS}")
        base_url = str(spec.get("base_url") or "").strip()
        if not base_url:
            raise ValueError("base_url 必填")
        models = spec.get("models") or []
        if not isinstance(models, list):
            raise ValueError("models 必须是列表")
        for m in models:
            if not isinstance(m, dict) or not m.get("id"):
                raise ValueError("每个模型必须有 id")
        data = deepcopy(self._data)
        existing = None
        for i, p in enumerate(data.get("providers") or []):
            if isinstance(p, dict) and p.get("id") == pid:
                existing = p
                idx = i
                break
        saved_key = existing.get("api_key") if existing else None
        incoming_key = spec.get("api_key")
        if incoming_key is None or str(incoming_key).strip() == "":
            api_key = saved_key
        else:
            api_key = incoming_key
        record = {
            "id": pid,
            "name": spec.get("name") or pid,
            "api": api,
            "base_url": base_url,
            "api_key": api_key or "",
            "models": models,
        }
        if spec.get("headers"):
            record["headers"] = spec["headers"]
        elif existing and existing.get("headers"):
            record["headers"] = existing["headers"]
        providers = list(data.get("providers") or [])
        if existing is not None:
            providers[idx] = record
        else:
            providers.append(record)
        data["providers"] = providers
        self._write(data)
        return next(p for p in self.list_providers() if p["id"] == pid)

    def delete_provider(self, provider_id: str) -> None:
        self.ensure_fresh()
        data = deepcopy(self._data)
        before = data.get("providers") or []
        after = [p for p in before if not (isinstance(p, dict) and p.get("id") == provider_id)]
        if len(after) == len(before):
            raise KeyError(f"供应商不存在: {provider_id}")
        data["providers"] = after
        self._write(data)


_STORE: ModelsStore | None = None


def get_store() -> ModelsStore:
    global _STORE
    if _STORE is None:
        _STORE = ModelsStore()
        _STORE.load()
    return _STORE


def reset_store() -> None:
    global _STORE
    _STORE = None
