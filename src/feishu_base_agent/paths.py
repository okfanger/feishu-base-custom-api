"""本机配置目录解析。优先 ``FEISHU_BASE_AGENT_DIR``，否则 ``~/.feishu-base-agent``。"""

from __future__ import annotations

import os
from pathlib import Path

ENV_DIR = "FEISHU_BASE_AGENT_DIR"
ENV_CRAWL4AI = "CRAWL4_AI_BASE_DIRECTORY"


def agent_dir() -> Path:
    override = os.environ.get(ENV_DIR)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".feishu-base-agent").resolve()


def models_yaml_path() -> Path:
    return agent_dir() / "models.yaml"


def crawl4ai_dir() -> Path:
    return agent_dir() / "crawl4ai"


def ensure_agent_dir() -> Path:
    d = agent_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_crawl4ai_env() -> Path:
    """在 import crawl4ai 之前调用：crawl4ai 会在导入时于该目录建 SQLite。"""
    target = Path(os.environ.get(ENV_CRAWL4AI) or crawl4ai_dir()).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    os.environ[ENV_CRAWL4AI] = str(target)
    return target
