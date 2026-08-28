from __future__ import annotations

import base64

from feishu_base_agent.crawler_format import format_one, merge_results, pick_text


class _MD:
    raw_markdown = "# Hello"
    fit_markdown = "Hello"
    markdown_with_citations = "Hello⟨1⟩"
    fit_html = "<p>Hello</p>"


class _Result:
    url = "https://example.com/page"
    success = True
    status_code = 200
    html = "<html><body>raw</body></html>"
    cleaned_html = "<p>clean</p>"
    markdown = _MD()
    extracted_content = '[{"name": "x"}]'
    links = {"internal": [{"href": "/a"}], "external": [{"href": "https://x"}]}
    media = {"images": [{"src": "a.png"}], "videos": [], "audios": []}
    metadata = {"title": "Example"}
    screenshot = base64.b64encode(b"\x89PNG").decode("ascii")
    pdf = b"%PDF-1.4"
    mhtml = "From: <Saved by Crawl>\n"
    error_message = None
    tables = []


def test_pick_text_formats() -> None:
    r = _Result()
    assert pick_text(r, "raw_markdown") == "# Hello"
    assert pick_text(r, "fit_markdown") == "Hello"
    assert "⟨1⟩" in pick_text(r, "markdown_with_citations")
    assert pick_text(r, "cleaned_html") == "<p>clean</p>"
    assert "raw" in pick_text(r, "html")
    assert '"name": "x"' in pick_text(r, "extracted_content")
    assert "/a" in pick_text(r, "links")
    assert "Example" in pick_text(r, "metadata")


def test_format_one_files_include_requested() -> None:
    out = format_one(_Result(), "raw_markdown", ["md", "html", "json", "png", "pdf", "mhtml"])
    assert out["ok"] is True
    assert out["text"] == "# Hello"
    names = {f["name"] for f in out["files"]}
    assert any(n.endswith(".md") for n in names)
    assert any(n.endswith(".png") for n in names)
    assert any(n.endswith(".pdf") for n in names)
    assert out["meta"]["title"] == "Example"
    assert out["meta"]["links"] == 2
    assert out["meta"]["images"] == 1
    png = next(f for f in out["files"] if f["name"].endswith(".png"))
    assert base64.b64decode(png["b64"]).startswith(b"\x89PNG")


def test_failed_result_has_error_no_files() -> None:
    class Fail:
        url = "https://x"
        success = False
        status_code = 403
        error_message = "blocked"
        markdown = None
        html = ""
        cleaned_html = None
        links = {}
        media = {}
        metadata = {}
        extracted_content = None
        screenshot = None
        pdf = None
        mhtml = None

    out = format_one(Fail(), "raw_markdown", ["md"])
    assert out["ok"] is False
    assert out["error"] == "blocked"
    assert out["files"] == []
    assert out["text"] == ""


def test_merge_deep_results_concatenates_and_renames_files() -> None:
    a, b = _Result(), _Result()
    b.url = "https://example.com/other"
    out = merge_results([a, b], "fit_markdown", ["md"])
    assert out["ok"] is True
    assert "## [1]" in out["text"]
    assert "## [2]" in out["text"]
    assert len(out["files"]) == 2
    assert out["files"][0]["name"] != out["files"][1]["name"]
