"""API / 内部共用的 pydantic schema。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CacheModeName = Literal["enabled", "disabled", "read_only", "write_only", "bypass"]
TextFormat = Literal[
    "raw_markdown",
    "fit_markdown",
    "markdown_with_citations",
    "cleaned_html",
    "html",
    "extracted_content",
    "links",
    "metadata",
]
FileFormat = Literal["md", "html", "json", "png", "pdf", "mhtml"]
ApiName = Literal["openai-completions", "anthropic-messages"]


class ModelSpec(BaseModel):
    id: str
    name: str | None = None
    input: list[str] = Field(default_factory=lambda: ["text"])
    context_window: int = 0
    max_tokens: int = 0
    reasoning: bool = False
    cost: dict[str, Any] = Field(default_factory=dict)


class ProviderUpsert(BaseModel):
    id: str
    name: str | None = None
    api: ApiName
    base_url: str
    api_key: str | None = None
    headers: dict[str, str] | None = None
    models: list[ModelSpec] = Field(default_factory=list)


class ImageInput(BaseModel):
    b64: str
    mime: str = "image/png"


class TextRequest(BaseModel):
    model_ref: str
    prompt: str = ""
    system_prompt: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    max_tokens: int | None = None
    temperature: float | None = None


class CrawlRunConfig(BaseModel):
    word_count_threshold: int = 1
    css_selector: str | None = None
    target_elements: list[str] = Field(default_factory=list)
    excluded_tags: list[str] = Field(default_factory=list)
    excluded_selector: str = ""
    only_text: bool = False
    remove_forms: bool = False
    keep_data_attributes: bool = False
    cache_mode: CacheModeName = "bypass"
    wait_until: str = "domcontentloaded"
    wait_for: str | None = None
    wait_for_timeout: int | None = None
    page_timeout: int = 60000
    delay_before_return_html: float = 0.1
    js_code: str | list[str] | None = None
    scan_full_page: bool = False
    scroll_delay: float = 0.2
    max_scroll_steps: int | None = None
    process_iframes: bool = False
    remove_overlay_elements: bool = False
    remove_consent_popups: bool = False
    simulate_user: bool = False
    override_navigator: bool = False
    magic: bool = False
    flatten_shadow_dom: bool = False
    screenshot: bool = False
    pdf: bool = False
    capture_mhtml: bool = False
    exclude_external_images: bool = False
    exclude_external_links: bool = False
    exclude_social_media_links: bool = False
    exclude_domains: list[str] = Field(default_factory=list)
    check_robots_txt: bool = False
    verbose: bool = False


class MarkdownConfig(BaseModel):
    content_filter: Literal["none", "pruning", "bm25"] = "none"
    pruning_threshold: float = 0.48
    pruning_threshold_type: Literal["fixed", "dynamic"] = "dynamic"
    pruning_min_word_threshold: int | None = None
    bm25_query: str | None = None
    bm25_threshold: float = 1.0
    ignore_links: bool = False
    ignore_images: bool = False
    body_width: int = 0


class ExtractionConfig(BaseModel):
    kind: Literal["none", "json_css", "llm"] = "none"
    json_css_schema: dict[str, Any] | None = None
    model_ref: str | None = None
    instruction: str | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    extraction_type: Literal["schema", "block"] = "schema"
    chunk_token_threshold: int = 2048
    apply_chunking: bool = True
    input_format: Literal["markdown", "html", "fit_markdown"] = "markdown"

    model_config = {"populate_by_name": True}


class DeepConfig(BaseModel):
    enabled: bool = False
    strategy: Literal["BFS", "DFS", "BestFirst"] = "BFS"
    max_depth: int = 1
    max_pages: int = 10
    include_external: bool = False


class CrawlRequest(BaseModel):
    url: str
    run: CrawlRunConfig = Field(default_factory=CrawlRunConfig)
    markdown: MarkdownConfig = Field(default_factory=MarkdownConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    deep: DeepConfig = Field(default_factory=DeepConfig)
    text_format: TextFormat = "raw_markdown"
    file_formats: list[FileFormat] = Field(default_factory=list)
    md_variant: Literal["raw", "fit"] = "raw"
