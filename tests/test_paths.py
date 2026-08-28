from __future__ import annotations

import os
from pathlib import Path

import pytest

from feishu_base_agent.paths import (
    ENV_CRAWL4AI,
    ENV_DIR,
    agent_dir,
    crawl4ai_dir,
    ensure_agent_dir,
    ensure_crawl4ai_env,
    models_yaml_path,
)


def test_agent_dir_respects_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DIR, str(tmp_path / "custom"))
    assert agent_dir() == (tmp_path / "custom").resolve()
    assert models_yaml_path() == (tmp_path / "custom" / "models.yaml").resolve()
    assert crawl4ai_dir() == (tmp_path / "custom" / "crawl4ai").resolve()


def test_agent_dir_defaults_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_DIR, raising=False)
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    # Path.home() uses HOME
    assert agent_dir() == Path("/tmp/fake-home/.feishu-base-agent").resolve()


def test_ensure_agent_dir_creates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "agent"
    monkeypatch.setenv(ENV_DIR, str(target))
    got = ensure_agent_dir()
    assert got.is_dir()
    assert got == target.resolve()


def test_ensure_crawl4ai_env_sets_var_before_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_DIR, str(tmp_path))
    monkeypatch.delenv(ENV_CRAWL4AI, raising=False)
    d = ensure_crawl4ai_env()
    assert d.is_dir()
    assert os.environ[ENV_CRAWL4AI] == str(d)
    assert d == (tmp_path / "crawl4ai").resolve()


def test_ensure_crawl4ai_env_keeps_existing_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    other = tmp_path / "other-c4a"
    monkeypatch.setenv(ENV_CRAWL4AI, str(other))
    d = ensure_crawl4ai_env()
    assert d == other.resolve()
    assert other.is_dir()
