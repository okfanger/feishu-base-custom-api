from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from feishu_base_agent.crawler import CrawlerService
from feishu_base_agent.models_store import ModelsStore, get_store
from feishu_base_agent.paths import ensure_agent_dir, ensure_crawl4ai_env


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_agent_dir()
    ensure_crawl4ai_env()
    store: ModelsStore = get_store()
    store.load()
    app.state.store = store
    crawler = CrawlerService()
    app.state.crawler = crawler
    app.state.crawler_error = None
    if os.environ.get("SKIP_CRAWLER") == "1":
        app.state.crawler_error = "SKIP_CRAWLER=1"
    else:
        try:
            await crawler.start()
        except Exception as e:  # noqa: BLE001 — 启动失败仍提供文本/模型 API
            app.state.crawler_error = str(e)
            crawler.error = str(e)
    yield
    await crawler.close()


def create_app() -> FastAPI:
    app = FastAPI(title="feishu-base-agent", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    from feishu_base_agent.api.crawl import router as crawl_router
    from feishu_base_agent.api.models import router as models_router
    from feishu_base_agent.api.text import router as text_router

    app.include_router(models_router)
    app.include_router(text_router)
    app.include_router(crawl_router)

    static = _static_dir()
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="static")
    return app


# 允许 `uvicorn feishu_base_agent.app:app`
app = create_app()
