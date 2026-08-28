from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from feishu_base_agent.schemas import CrawlRequest

router = APIRouter(prefix="/api", tags=["crawl"])


@router.post("/crawl")
async def run_crawl(payload: CrawlRequest, request: Request):
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(400, "url 必填")
    crawler = getattr(request.app.state, "crawler", None)
    if crawler is None or not crawler.ready:
        msg = getattr(request.app.state, "crawler_error", None) or (
            crawler.error if crawler else "crawler 未启动"
        )
        raise HTTPException(503, f"爬虫不可用: {msg}")
    try:
        return await crawler.crawl(payload, request.app.state.store)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"爬取失败: {e}") from e
