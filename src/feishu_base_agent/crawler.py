"""crawl4ai 封装：进程内复用单个 AsyncWebCrawler。"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from feishu_base_agent.crawler_format import as_result_list, merge_results
from feishu_base_agent.models_store import ModelsStore, parse_ref
from feishu_base_agent.paths import ensure_crawl4ai_env
from feishu_base_agent.schemas import CrawlRequest


def _cache_mode(name: str) -> Any:
    from crawl4ai import CacheMode

    mapping = {
        "enabled": CacheMode.ENABLED,
        "disabled": CacheMode.DISABLED,
        "read_only": CacheMode.READ_ONLY,
        "write_only": CacheMode.WRITE_ONLY,
        "bypass": CacheMode.BYPASS,
    }
    return mapping.get(name, CacheMode.BYPASS)


def build_run_config(req: CrawlRequest, store: ModelsStore | None = None) -> Any:
    from crawl4ai import (
        BM25ContentFilter,
        DefaultMarkdownGenerator,
        JsonCssExtractionStrategy,
        LLMConfig,
        LLMExtractionStrategy,
        PruningContentFilter,
        CrawlerRunConfig,
    )

    run = req.run.model_dump(exclude_none=True)
    run["cache_mode"] = _cache_mode(req.run.cache_mode)
    run["verbose"] = bool(req.run.verbose)

    wanted = set(req.file_formats or [])
    if "png" in wanted:
        run["screenshot"] = True
    if "pdf" in wanted:
        run["pdf"] = True
    if "mhtml" in wanted:
        run["capture_mhtml"] = True

    md = req.markdown
    content_filter = None
    if md.content_filter == "pruning":
        kwargs: dict[str, Any] = {
            "threshold": md.pruning_threshold,
            "threshold_type": md.pruning_threshold_type,
        }
        if md.pruning_min_word_threshold is not None:
            kwargs["min_word_threshold"] = md.pruning_min_word_threshold
        content_filter = PruningContentFilter(**kwargs)
    elif md.content_filter == "bm25":
        content_filter = BM25ContentFilter(
            user_query=md.bm25_query,
            bm25_threshold=md.bm25_threshold,
        )
    run["markdown_generator"] = DefaultMarkdownGenerator(
        content_filter=content_filter,
        options={
            "ignore_links": md.ignore_links,
            "ignore_images": md.ignore_images,
            "body_width": md.body_width,
        },
    )

    ext = req.extraction
    if ext.kind == "json_css":
        if not ext.json_css_schema:
            raise ValueError("json_css 抽取需要 json_css_schema")
        run["extraction_strategy"] = JsonCssExtractionStrategy(ext.json_css_schema)
    elif ext.kind == "llm":
        if store is None or not ext.model_ref:
            raise ValueError("llm 抽取需要 model_ref")
        model = store.get_pi_model(ext.model_ref)
        if model is None:
            raise ValueError(f"未知模型: {ext.model_ref}")
        provider_id, _ = parse_ref(ext.model_ref)
        key, _src = store.api_key_for(provider_id)
        if not key:
            raise ValueError(f"模型 {ext.model_ref} 未配置 API Key")
        if model.api == "anthropic-messages":
            litellm_provider = f"anthropic/{model.id}"
        else:
            litellm_provider = f"openai/{model.id}"
        llm_config = LLMConfig(provider=litellm_provider, api_token=key, base_url=model.base_url)
        schema = ext.schema_
        run["extraction_strategy"] = LLMExtractionStrategy(
            llm_config=llm_config,
            instruction=ext.instruction,
            schema=schema,
            extraction_type=ext.extraction_type,
            chunk_token_threshold=ext.chunk_token_threshold,
            apply_chunking=ext.apply_chunking,
            input_format=ext.input_format,
        )

    if req.deep.enabled:
        from crawl4ai import BestFirstCrawlingStrategy, BFSDeepCrawlStrategy, DFSDeepCrawlStrategy

        cls = {
            "BFS": BFSDeepCrawlStrategy,
            "DFS": DFSDeepCrawlStrategy,
            "BestFirst": BestFirstCrawlingStrategy,
        }[req.deep.strategy]
        run["deep_crawl_strategy"] = cls(
            max_depth=req.deep.max_depth,
            max_pages=req.deep.max_pages,
            include_external=req.deep.include_external,
        )

    # 丢掉空列表/空字符串以免覆盖默认
    cleaned = {k: v for k, v in run.items() if v not in (None, "", [])}
    return CrawlerRunConfig.from_kwargs(cleaned)


class CrawlerService:
    def __init__(self, concurrency: int | None = None) -> None:
        n = concurrency if concurrency is not None else int(os.environ.get("CRAWL_CONCURRENCY", "3"))
        self._sem = asyncio.Semaphore(max(1, n))
        self._crawler: Any = None
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self._crawler is not None

    async def start(self) -> None:
        ensure_crawl4ai_env()
        from crawl4ai import AsyncWebCrawler, BrowserConfig

        cfg = BrowserConfig(
            headless=True,
            verbose=False,
            light_mode=True,
            memory_saving_mode=True,
            max_pages_before_recycle=50,
        )
        crawler = AsyncWebCrawler(config=cfg)
        await crawler.start()
        self._crawler = crawler
        self.error = None

    async def close(self) -> None:
        if self._crawler is not None:
            try:
                await self._crawler.close()
            except Exception:
                pass
            self._crawler = None

    async def crawl(self, req: CrawlRequest, store: ModelsStore) -> dict[str, Any]:
        if self._crawler is None:
            raise RuntimeError(self.error or "crawler 未启动")
        config = build_run_config(req, store)
        async with self._sem:
            raw = await self._crawler.arun(url=req.url, config=config)
        results = as_result_list(raw)
        return merge_results(results, req.text_format, list(req.file_formats), req.md_variant)
