#!/usr/bin/env python3
"""
Zclaw Gateway 启动脚本

用法:
    python scripts/start_gateway.py [agents_dir] [port]

示例:
    python scripts/start_gateway.py agents 8080
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description="启动 Zclaw Gateway")
    parser.add_argument(
        "agents_dir",
        nargs="?",
        default="agents",
        help="Agent 配置目录 (默认: agents)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="监听端口 (默认: 8080)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址 (默认: 0.0.0.0)",
    )
    parser.add_argument(
        "--storage",
        default=".Zclaw",
        help="存储路径 (默认: .Zclaw)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 配置日志
    import logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from src.web.gateway_server import start_gateway_server

    print(f"""
╔══════════════════════════════════════════════════════════╗
║              Zclaw Gateway - 24/7 Autonomous Agent       ║
╠══════════════════════════════════════════════════════════╣
║  Agents: {args.agents_dir:<47} ║
║  Storage: {args.storage:<47} ║
║  Server: http://{args.host}:{args.port:<31} ║
║  WebSocket: ws://{args.host}:{args.port}/api/ws/gateway           ║
╚══════════════════════════════════════════════════════════╝
    """)

    try:
        asyncio.run(start_gateway_server(
            agents_dir=args.agents_dir,
            storage_path=args.storage,
            host=args.host,
            port=args.port,
        ))
    except KeyboardInterrupt:
        print("\nGateway 已关闭")


if __name__ == "__main__":
    main()
