from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolate_crawl4ai_home(tmp_path_factory: pytest.TempPathFactory) -> None:
    d = tmp_path_factory.mktemp("c4a")
    os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(d))
    Path(os.environ["CRAWL4_AI_BASE_DIRECTORY"]).mkdir(parents=True, exist_ok=True)
