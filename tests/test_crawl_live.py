from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from feishu_base_agent.models_store import reset_store


def _playwright_ready() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return bool(p.chromium.executable_path)
    except Exception:
        return False


@pytest.mark.skipif(os.environ.get("SKIP_LIVE_CRAWL") == "1", reason="explicitly skipped")
@pytest.mark.skipif(not _playwright_ready(), reason="playwright chromium not installed")
def test_crawl_example_com(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FEISHU_BASE_AGENT_DIR", str(tmp_path))
    monkeypatch.delenv("SKIP_CRAWLER", raising=False)
    reset_store()
    from feishu_base_agent.app import create_app

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/crawl",
            json={
                "url": "https://example.com",
                "run": {"cache_mode": "bypass", "page_timeout": 30000, "verbose": False},
                "markdown": {"content_filter": "pruning"},
                "text_format": "raw_markdown",
                "file_formats": ["md"],
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert "Example" in (data.get("text") or "") or "example" in (data.get("text") or "").lower()
        assert data["files"]
    reset_store()
