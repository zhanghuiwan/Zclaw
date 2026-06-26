"""
Zclaw - Gateway 管理与客户端

使用方式:
    启动 Gateway: python main.py start
    停止 Gateway: python main.py stop
    查看状态:    python main.py status
    连接对话:    python main.py

Gateway 必须先启动才能连接。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def main():
    """主入口函数。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="Zclaw Chat",
        description="Zclaw - Gateway 管理与客户端",
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # start 命令
    start_parser = sub.add_parser("start", help="启动 Gateway")
    start_parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="后台守护进程模式",
    )

    # stop 命令
    sub.add_parser("stop", help="停止 Gateway")

    # restart 命令
    sub.add_parser("restart", help="重启 Gateway")

    # status 命令
    sub.add_parser("status", help="查看 Gateway 状态")

    # REPL 模式（无子命令时默认）
    parser.set_defaults(command=None)

    # 向后兼容参数
    parser.add_argument(
        "--env", "-e",
        type=str,
        default=None,
        help="指定 .env 文件路径",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="开启详细日志",
    )
    parser.add_argument(
        "--gateway",
        action="store_true",
        help="启动 Gateway（兼容旧参数）",
    )
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="启动 Gateway STDIO 模式（兼容旧参数）",
    )
    parser.add_argument(
        "--agents-dir",
        type=str,
        default="agents",
        help="Agent 配置目录 (默认: agents)",
    )
    parser.add_argument(
        "--storage",
        type=str,
        default=".Zclaw",
        help="存储路径 (默认: .Zclaw)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Gateway 监听地址 (默认: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Gateway 监听端口 (默认: 8080)",
    )

    args = parser.parse_args()

    # 导入 GatewayManager
    from src.channel.gateway_manager import GatewayManager
    from src.channel.gateway_client import run_repl

    manager = GatewayManager()

    # 处理命令
    if args.command == "start":
        success = manager.start(daemon=args.daemon)
        sys.exit(0 if success else 1)

    elif args.command == "stop":
        success = manager.stop()
        sys.exit(0 if success else 1)

    elif args.command == "restart":
        success = manager.restart()
        sys.exit(0 if success else 1)

    elif args.command == "status":
        manager.print_status()
        sys.exit(0)

    # 向后兼容：处理 --gateway 和 --stdio
    elif args.gateway or args.stdio:
        asyncio.run(_run_gateway_mode(args))
        return

    # 默认：连接 Gateway REPL
    if not manager.is_running():
        print("错误: Gateway 未运行")
        print()
        print("请先启动 Gateway:")
        print("  python main.py start")
        print("或")
        print("  zclaw start")
        sys.exit(1)

    # 检查端口
    if not manager._is_port_open():
        print("错误: Gateway 端口未开放")
        print("  请尝试重启: python main.py restart")
        sys.exit(1)

    # 运行 REPL
    asyncio.run(run_repl(
        host=manager.host,
        port=manager.port,
    ))


async def _run_gateway_mode(args) -> None:
    """运行 Gateway 模式。"""
    import logging
    from src.web.gateway_server import (
        start_gateway_server,
        start_gateway_stdio,
    )

    # 日志配置
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # 加载配置
    from src.config.settings import load_settings
    settings = load_settings(use_env=True)
    logger.info(f"QQ 配置: enabled={settings.qq.enabled}, appid={settings.qq.appid[:6] if settings.qq.appid else 'N/A'}...")

    if args.stdio:
        # STDIO 模式
        print("=" * 60)
        print("Zclaw Gateway - STDIO 模式")
        print("=" * 60)
        print(f"Agents 目录: {args.agents_dir}")
        print(f"存储路径: {args.storage}")
        print("输入 /quit 退出")
        print("=" * 60)

        await start_gateway_stdio(
            agents_dir=args.agents_dir,
            storage_path=args.storage,
            settings=settings,
        )
    else:
        # WebSocket/HTTP 模式
        print("=" * 60)
        print("Zclaw Gateway - WebSocket/HTTP 模式")
        print("=" * 60)
        print(f"Agents 目录: {args.agents_dir}")
        print(f"存储路径: {args.storage}")
        print(f"监听地址: {args.host}:{args.port}")
        print(f"WebSocket: ws://{args.host}:{args.port}/api/ws/gateway")
        if settings.qq.enabled:
            print(f"QQ: 已启用 (appid={settings.qq.appid})")
        else:
            print("QQ: 未启用")
        print("=" * 60)

        await start_gateway_server(
            agents_dir=args.agents_dir,
            storage_path=args.storage,
            host=args.host,
            port=args.port,
            settings=settings,
        )


if __name__ == "__main__":
    main()
