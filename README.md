<div align="center">

# 🔌 多维表格接自定义 API 插件

**飞书多维表格直连大模型 + 网页爬取：文本 / 图片 / 视频 / 爬取，一个插件全搞定。**

uv 管理的 FastAPI 应用 · pi-py 统一 Agent · crawl4ai 爬取 · 模型配置落在本机 `~/.feishu-base-agent/models.yaml`

[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e.svg)](LICENSE)
[![飞书多维表格](https://img.shields.io/badge/飞书-多维表格插件-4c8dff.svg)](#-安装到多维表格)

</div>

---

## 它解决什么问题

飞书多维表格自带的 AI 能力**没法接你自己的 API**：不能换中转站、不能指定模型、不能调用生图接口，也不能把网页正文抓回来写进表格。这个插件把后端跑在你自己的机器上：

- 📝 **文本任务**：走后端 [pi-py](https://github.com/encyc/pi-py) Agent（`openai-completions` / `anthropic-messages`），提示词模板 `【列名】` 引用单元格，结果写进文本列。附件列可作为视觉模型输入。
- 🖼 **图片任务**：浏览器直连 OpenAI 兼容生图接口，写进附件列（支持图生图）。
- 🎬 **视频任务**：浏览器直连方舟 Seedance 或中转站 `/v1/videos`，异步提交→轮询→取片，任务 ID 可落表续查。
- 🕷 **爬取任务**：后端调用 [crawl4ai](https://github.com/unclecode/crawl4ai) Python SDK，参数对齐一次 `arun()` 所需配置；写回可选文本列和/或附件（md / html / json / png / pdf / mhtml）。
- 🗂 **模型库**：供应商与模型维护在 `~/.feishu-base-agent/models.yaml`，Key 支持 `${ENV_VAR}` / `env:NAME`，接口响应不回传明文 Key。

## 要求

- Python **≥ 3.11**（推荐 3.12）
- [uv](https://docs.astral.sh/uv/)
- 首次使用爬取任务需要 Playwright Chromium（`crawl4ai-setup`）

## 安装与启动

```bash
git clone <本仓库>
cd feishu-base-custom-api
uv sync
uv run crawl4ai-setup          # 安装 Chromium，仅爬取任务需要
uv run feishu-base-agent       # 默认 http://127.0.0.1:8000
# 或
uv run python -m feishu_base_agent --host 0.0.0.0 --port 8000
```

首次启动会在 `~/.feishu-base-agent/models.yaml` 写入带注释的默认模板（openai / anthropic / deepseek）。可用环境变量覆盖配置目录：

```bash
export FEISHU_BASE_AGENT_DIR=/path/to/dir
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=...
export DEEPSEEK_API_KEY=...
```

crawl4ai 的缓存目录默认在 `~/.feishu-base-agent/crawl4ai`（通过 `CRAWL4_AI_BASE_DIRECTORY` 注入，避免污染家目录）。

## 模型配置（models.yaml）

```yaml
version: 1
providers:
  - id: deepseek
    name: DeepSeek
    api: openai-completions          # 或 anthropic-messages
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}     # 明文 / ${ENV} / env:NAME
    models:
      - id: deepseek-chat
        name: DeepSeek Chat
        input: [text]
        context_window: 64000
        max_tokens: 8192
```

也可在插件侧栏「③ 模型库」里增删改，并点「测试连通」。`openai-responses` 协议本期未实现，下拉框里是禁用项。

文本任务的 API Key **只存在后端 yaml / 环境变量**，不再随请求从浏览器上传。图片 / 视频任务仍按原设计把 Key 存在本机 localStorage，由浏览器直连上游。

## 安装到多维表格

1. 启动本服务，拿到插件 URL：
   - 本机：`http://127.0.0.1:8000/`
   - 远程部署必须 **HTTPS**（浏览器会拦截 https 页面调 http，mixed content）
2. 打开飞书多维表格 → 右上角「插件」→「自定义插件」→ 添加，粘贴 URL
3. 侧边栏打开插件，配置任务后开跑

服务**不会**设置 `X-Frame-Options: DENY`，以便被飞书 iframe 嵌入。

## 使用

**① 选模型**  
文本模式从模型库下拉选择；图片模式填 API 地址 / Key / 生图模型；视频模式用独立的方舟或中转站配置。

**② 配任务**

| 配置项 | 说明 |
|---|---|
| 任务类型 | 文本 / 图片 / 视频 / 爬取 |
| 输入列 | 点选一或多个列；附件列可作为视觉模型输入或图生图参考图 |
| 提示词模板 | 用 `【列名】` 引用输入列 |
| 输出列 | 文本任务选文本列，图片/视频选附件列；爬取可分别选文本列与附件列 |
| 并发 / 行数 / 已有内容 | 同时跑几行、最多处理几行、已填的行跳过还是覆盖 |

**③ 开跑**  
「▶ 开始」批量跑空行，或「只跑当前光标所在行」单行试效果。

### 爬取任务要点

- **URL 来源**：指定一个文本列为网址，或在提示词里写 / 用 `【列名】` 拼出 `http(s)://...`
- **写回**：只写文本、只写附件、或两者都写。文本格式包括 `raw_markdown` / `fit_markdown` / `cleaned_html` / 抽取 JSON 等
- **附件格式**：`.md` / `.html` / `.json` / 截图 `.png` / `.pdf` / `.mhtml`
- **过滤器**：中文页面请用 **pruning**（BM25 对中文分词效果差）。`fit_markdown` 只有启用过滤器后才有内容
- **缓存**：UI 必须显式选择；crawl4ai 构造默认是 `bypass`，不是文档里写的 `enabled`
- **抽取**：可选 Json CSS schema 或用模型库里的模型做 LLM 抽取
- **深度爬取**：BFS / DFS / BestFirst + max_depth / max_pages

高级参数与一次 crawl4ai `CrawlerRunConfig` 对齐（css_selector、excluded_tags、wait_for、js_code、scan_full_page、iframe、弹层、magic、shadow DOM、robots.txt 等）。

### 视频生成

视频 API 全行业都是异步任务制。方舟官方接口普遍不给浏览器开跨域，需要你自己的透传代理（形如 `http://127.0.0.1:8000/api/ark/v3`）。中转站若支持 `/v1/videos` 可直连。建议配「任务ID列」防重复扣费，中途关掉面板可点「续查」。

## 开发

```bash
uv sync --group dev
uv run pytest
uv run python -m feishu_base_agent --reload
```

目录：

```
src/feishu_base_agent/
  app.py              FastAPI（GZip + 静态站）
  models_store.py     models.yaml ↔ pi_ai.Model
  agent_runner.py     pi_agent_core.Agent
  crawler.py          复用的 AsyncWebCrawler
  static/             零构建 vanilla 前端 + 内联 Lark SDK
```

## License

[MIT](LICENSE)
