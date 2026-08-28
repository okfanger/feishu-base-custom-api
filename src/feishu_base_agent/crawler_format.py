"""把 crawl4ai 的结果格式化成前端可写回的 {text, files, meta}。不依赖 crawl4ai 导入。"""

from __future__ import annotations

import base64
import json
from typing import Any


def _md_attr(result: Any, name: str) -> str:
    md = getattr(result, "markdown", None)
    if md is None:
        return ""
    value = getattr(md, name, None)
    if value:
        return str(value)
    if name == "raw_markdown" and isinstance(md, str):
        return md
    return ""


def _load_json(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


def _pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def pick_text(result: Any, text_format: str) -> str:
    if text_format == "raw_markdown":
        return _md_attr(result, "raw_markdown")
    if text_format == "fit_markdown":
        return _md_attr(result, "fit_markdown") or _md_attr(result, "raw_markdown")
    if text_format == "markdown_with_citations":
        return _md_attr(result, "markdown_with_citations") or _md_attr(result, "raw_markdown")
    if text_format == "cleaned_html":
        return getattr(result, "cleaned_html", None) or ""
    if text_format == "html":
        return getattr(result, "html", None) or ""
    if text_format == "extracted_content":
        raw = getattr(result, "extracted_content", None)
        parsed = _load_json(raw)
        if parsed is None:
            return ""
        return parsed if isinstance(parsed, str) else _pretty(parsed)
    if text_format == "links":
        return _pretty(getattr(result, "links", None) or {})
    if text_format == "metadata":
        return _pretty(getattr(result, "metadata", None) or {})
    return _md_attr(result, "raw_markdown")


def _file(name: str, mime: str, data: bytes) -> dict[str, str]:
    return {
        "name": name,
        "mime": mime,
        "b64": base64.b64encode(data).decode("ascii"),
    }


def _slug(url: str) -> str:
    host = url.split("://", 1)[-1]
    host = host.split("?", 1)[0].rstrip("/").replace("/", "_")
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in host)[:80] or "page"


def build_files(result: Any, file_formats: list[str], md_variant: str = "raw") -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    slug = _slug(getattr(result, "url", "") or "page")
    wanted = set(file_formats or [])
    if "md" in wanted:
        md = _md_attr(result, "fit_markdown" if md_variant == "fit" else "raw_markdown")
        files.append(_file(f"{slug}.md", "text/markdown; charset=utf-8", md.encode("utf-8")))
    if "html" in wanted:
        html = getattr(result, "cleaned_html", None) or getattr(result, "html", None) or ""
        files.append(_file(f"{slug}.html", "text/html; charset=utf-8", str(html).encode("utf-8")))
    if "json" in wanted:
        payload = {
            "url": getattr(result, "url", None),
            "status_code": getattr(result, "status_code", None),
            "metadata": getattr(result, "metadata", None),
            "links": getattr(result, "links", None),
            "extracted_content": _load_json(getattr(result, "extracted_content", None)),
            "markdown": _md_attr(result, "raw_markdown"),
        }
        files.append(_file(f"{slug}.json", "application/json", _pretty(payload).encode("utf-8")))
    if "png" in wanted:
        shot = getattr(result, "screenshot", None)
        if shot:
            raw = base64.b64decode(shot) if isinstance(shot, str) else shot
            files.append(_file(f"{slug}.png", "image/png", raw))
    if "pdf" in wanted:
        pdf = getattr(result, "pdf", None)
        if pdf:
            raw = pdf if isinstance(pdf, (bytes, bytearray)) else base64.b64decode(pdf)
            files.append(_file(f"{slug}.pdf", "application/pdf", bytes(raw)))
    if "mhtml" in wanted:
        mhtml = getattr(result, "mhtml", None)
        if mhtml:
            data = mhtml.encode("utf-8") if isinstance(mhtml, str) else bytes(mhtml)
            files.append(_file(f"{slug}.mhtml", "multipart/related", data))
    return files


def result_meta(result: Any) -> dict[str, Any]:
    links = getattr(result, "links", None) or {}
    media = getattr(result, "media", None) or {}
    metadata = getattr(result, "metadata", None) or {}
    n_links = 0
    if isinstance(links, dict):
        n_links = len(links.get("internal") or []) + len(links.get("external") or [])
    n_images = len((media or {}).get("images") or []) if isinstance(media, dict) else 0
    return {
        "title": metadata.get("title") if isinstance(metadata, dict) else None,
        "links": n_links,
        "images": n_images,
        "status_code": getattr(result, "status_code", None),
        "url": getattr(result, "url", None),
    }


def format_one(result: Any, text_format: str, file_formats: list[str], md_variant: str = "raw") -> dict[str, Any]:
    ok = bool(getattr(result, "success", True))
    err = getattr(result, "error_message", None)
    return {
        "ok": ok,
        "url": getattr(result, "url", None),
        "status_code": getattr(result, "status_code", None),
        "error": None if ok else (err or "crawl failed"),
        "text": pick_text(result, text_format) if ok else "",
        "files": build_files(result, file_formats, md_variant) if ok else [],
        "meta": result_meta(result),
    }


def merge_results(
    results: list[Any],
    text_format: str,
    file_formats: list[str],
    md_variant: str = "raw",
) -> dict[str, Any]:
    if not results:
        return {
            "ok": False,
            "url": None,
            "status_code": None,
            "error": "empty crawl result",
            "text": "",
            "files": [],
            "meta": {"title": None, "links": 0, "images": 0},
        }
    if len(results) == 1:
        return format_one(results[0], text_format, file_formats, md_variant)
    parts: list[str] = []
    files: list[dict[str, str]] = []
    ok_any = False
    first = results[0]
    errors: list[str] = []
    for i, r in enumerate(results, 1):
        one = format_one(r, text_format, file_formats, md_variant)
        if one["ok"]:
            ok_any = True
            url = one.get("url") or ""
            parts.append(f"## [{i}] {url}\n\n{one['text']}".rstrip())
            for f in one["files"]:
                f = dict(f)
                stem, _, ext = f["name"].rpartition(".")
                f["name"] = f"{stem}_{i}.{ext}" if ext else f"{f['name']}_{i}"
                files.append(f)
        else:
            errors.append(str(one.get("error") or "fail"))
    text = "\n\n---\n\n".join(parts)
    return {
        "ok": ok_any,
        "url": getattr(first, "url", None),
        "status_code": getattr(first, "status_code", None),
        "error": None if ok_any else "; ".join(errors) or "crawl failed",
        "text": text,
        "files": files,
        "meta": result_meta(first) | {"pages": len(results)},
    }


def as_result_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    # CrawlResultContainer is sequence-like
    try:
        return list(raw)
    except TypeError:
        return [raw]
