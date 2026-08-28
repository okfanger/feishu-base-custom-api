"""uvicorn 入口。必须在 import crawl4ai 之前设置 CRAWL4_AI_BASE_DIRECTORY。"""

from __future__ import annotations

import argparse

from feishu_base_agent.paths import ensure_agent_dir, ensure_crawl4ai_env


def main(argv: list[str] | None = None) -> None:
    ensure_agent_dir()
    ensure_crawl4ai_env()
    parser = argparse.ArgumentParser(prog="feishu-base-agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)
    import uvicorn

    uvicorn.run(
        "feishu_base_agent.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
