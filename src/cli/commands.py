"""
Zclaw CLI 命令入口

统一管理 zclaw 命令的子命令：
- zclaw start     : 启动 Gateway
- zclaw stop      : 停止 Gateway
- zclaw status    : 查看状态
- zclaw (无参数)  : 连接 Gateway REPL
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """CLI 主入口"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="zclaw",
        description="Zclaw - AI Agent 编程助手",
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

    args = parser.parse_args()

    # 延迟导入避免循环依赖
    from src.channel.gateway_manager import GatewayManager
    from src.channel.gateway_client import run_repl

    manager = GatewayManager()

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

    else:
        # 默认：连接 Gateway REPL
        if not manager.is_running():
            print("错误: Gateway 未运行")
            print()
            print("请先启动 Gateway:")
            print("  zclaw start")
            print("或")
            print("  python main.py start")
            sys.exit(1)

        # 检查端口
        if not manager._is_port_open():
            print("错误: Gateway 端口未开放")
            print("  请尝试重启: zclaw restart")
            sys.exit(1)

        # 运行 REPL
        asyncio.run(run_repl(
            host=manager.host,
            port=manager.port,
        ))


if __name__ == "__main__":
    main()