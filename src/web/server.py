"""
Web Server - FastAPI 应用入口

创建和配置 FastAPI 应用，挂载路由和静态文件。
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# 静态文件目录（相对于本文件）
_STATIC_DIR = Path(__file__).parent / "static"


def create_app(agent=None, settings=None) -> FastAPI:
    """
    创建 FastAPI 应用实例。

    Args:
        agent: Agent 实例（可选，也可后续通过 set_agent 设置）
        settings: Settings 实例

    Returns:
        配置好的 FastAPI 应用
    """
    app = FastAPI(
        title="Zclaw Web UI",
        description="Claude Code 风格 AI 编程助手 - Web 界面",
        version="0.6.1",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS 中间件
    cors_origins = ["*"]
    if settings and settings.web.cors_origins:
        cors_origins = settings.web.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 设置 Agent 和 Settings 引用
    if agent:
        from src.web.routes import set_agent
        set_agent(agent)
    if settings:
        from src.web.routes import set_settings
        set_settings(settings)

    # 挂载 API 路由
    from src.web.routes import router
    app.include_router(router)

    # 挂载静态文件
    if _STATIC_DIR.exists():
        app.mount("/", _create_static_app(_STATIC_DIR), name="static")

    logger.info("Web 应用已创建")

    return app


def _create_static_app(static_dir: Path):
    """
    创建一个简单的静态文件服务应用。

    用于挂载到 FastAPI 主应用上，提供前端页面。
    """
    from starlette.responses import FileResponse, HTMLResponse
    from starlette.routing import Route, Mount
    from starlette.applications import Starlette
    import os

    async def serve_index(request):
        """服务 index.html"""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse("<h1>Zclaw Web UI - 页面未找到</h1>", status_code=404)

    async def serve_static(request):
        """服务静态文件（CSS/JS/图片等）"""
        file_path = request.path_params.get("path", "")
        full_path = static_dir / file_path

        # 防止路径穿越
        try:
            full_path.resolve().relative_to(static_dir.resolve())
        except ValueError:
            return HTMLResponse("Forbidden", status_code=403)

        if full_path.exists() and full_path.is_file():
            return FileResponse(full_path)
        return HTMLResponse("Not Found", status_code=404)

    routes = [
        Mount("/static", app=Starlette(routes=[
            Route("/{path:path}", serve_static),
        ])),
        Route("/{path:path}", serve_index),
    ]

    return Starlette(routes=routes)


async def start_web_server(agent, settings, host: str = "0.0.0.0", port: int = 8080):
    """
    启动 Web 服务器。

    Args:
        agent: Agent 实例
        settings: Settings 实例
        host: 监听地址
        port: 监听端口
    """
    import uvicorn

    app = create_app(agent=agent, settings=settings)

    logger.info(f"启动 Web 服务器: http://{host}:{port}")

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        ws_ping_interval=30,
        ws_ping_timeout=60,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import asyncio
    from src.config.settings import load_settings_from_env
    from src.core.agent import Agent

    async def main():
        settings = load_settings_from_env()
        agent = Agent(settings)
        await start_web_server(agent, settings)

    asyncio.run(main())
