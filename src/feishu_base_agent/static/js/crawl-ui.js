import { $ } from './dom.js';

function csvList(s) {
  return String(s || '').split(/[,，]/).map(x => x.trim()).filter(Boolean);
}

export function collectCrawlPayload(url) {
  const files = [...document.querySelectorAll('#crawlFileFormats input:checked')].map(i => i.value);
  const run = {
    cache_mode: $('crawlCache').value || 'bypass',
    word_count_threshold: parseInt($('crawlWordCount').value) || 1,
    page_timeout: parseInt($('crawlPageTimeout').value) || 60000,
    css_selector: $('crawlCss').value.trim() || null,
    excluded_tags: csvList($('crawlExcludedTags').value),
    excluded_selector: $('crawlExcludedSel').value.trim(),
    wait_for: $('crawlWaitFor').value.trim() || null,
    js_code: $('crawlJs').value.trim() || null,
    scan_full_page: $('crawlScanFull').checked,
    process_iframes: $('crawlIframes').checked,
    remove_overlay_elements: $('crawlOverlay').checked,
    remove_consent_popups: $('crawlConsent').checked,
    magic: $('crawlMagic').checked,
    flatten_shadow_dom: $('crawlShadow').checked,
    exclude_external_links: $('crawlExtLinks').checked,
    check_robots_txt: $('crawlRobots').checked,
    verbose: false,
  };
  const extraction = { kind: $('crawlExtract').value || 'none' };
  if (extraction.kind === 'json_css') {
    const raw = $('crawlCssSchema').value.trim();
    if (raw) {
      try { extraction.json_css_schema = JSON.parse(raw); }
      catch { throw new Error('Json CSS schema 不是合法 JSON'); }
    }
  }
  if (extraction.kind === 'llm') {
    extraction.model_ref = $('crawlLlmModel').value;
    extraction.instruction = $('crawlLlmInstruction').value;
  }
  const deepStrategy = $('crawlDeep').value;
  const deep = {
    enabled: !!deepStrategy,
    strategy: deepStrategy || 'BFS',
    max_depth: parseInt($('crawlDeepDepth').value) || 1,
    max_pages: parseInt($('crawlDeepPages').value) || 10,
    include_external: false,
  };
  return {
    url,
    run,
    markdown: { content_filter: $('crawlFilter').value || 'none' },
    extraction,
    deep,
    text_format: $('crawlTextFormat').value || 'raw_markdown',
    file_formats: files,
    md_variant: $('crawlMdVariant').value || 'raw',
  };
}

export function extractUrl(text) {
  const m = String(text || '').match(/https?:\/\/[^\s<>"']+/);
  return m ? m[0] : '';
}
