from __future__ import annotations

from feishu_base_agent.crawler import build_run_config
from feishu_base_agent.schemas import CrawlRequest, ExtractionConfig, MarkdownConfig


def test_build_run_config_sets_cache_mode_and_markdown_filter() -> None:
    req = CrawlRequest(
        url="https://example.com",
        markdown=MarkdownConfig(content_filter="pruning", pruning_threshold=0.4),
        file_formats=["png", "pdf"],
    )
    cfg = build_run_config(req, store=None)
    assert cfg.screenshot is True
    assert cfg.pdf is True
    assert cfg.verbose is False
    assert cfg.markdown_generator is not None
    assert cfg.markdown_generator.content_filter is not None


def test_build_run_config_json_css_requires_schema() -> None:
    req = CrawlRequest(
        url="https://example.com",
        extraction=ExtractionConfig(kind="json_css"),
    )
    try:
        build_run_config(req, store=None)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "json_css_schema" in str(e)
