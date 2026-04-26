"""
Gateway WebSocket 客户端

通过 WebSocket 连接 Gateway，实现 REPL 对话界面。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

import websockets

from src.llm.models import StreamEventType

logger = logging.getLogger(__name__)


class GatewayClient:
    """Gateway WebSocket 客户端"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        agent_id: str = "default",
    ):
        self.host = host
        self.port = port
        self.agent_id = agent_id
        self.ws_url = f"ws://{host}:{port}/api/ws/gateway"
        self._ws: websockets.WebSocketClientProtocol | None = None

    async def connect(self) -> None:
        """连接 Gateway"""
        try:
            self._ws = await websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=60,
            )
            logger.info(f"Connected to Gateway at {self.ws_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Gateway: {e}")
            raise

    async def disconnect(self) -> None:
        """断开连接"""
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def chat(self, message: str) -> AsyncGenerator[dict, None]:
        """
        发送消息并接收流式响应

        Args:
            message: 用户输入的消息

        Yields:
            事件字典，包含 type 和 data
        """
        if not self._ws:
            raise RuntimeError("Not connected to Gateway. Call connect() first.")

        # 发送聊天消息
        await self._ws.send(json.dumps({
            "type": "chat",
            "data": {
                "message": message,
                "agent_id": self.agent_id,
            },
        }))

        # 接收响应事件
        while True:
            try:
                raw = await self._ws.recv()
                event = json.loads(raw)
                yield event

                # done 事件表示响应结束
                if event.get("type") == "done":
                    break

            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection to Gateway closed")
                break

    async def cancel(self) -> None:
        """取消当前请求"""
        if not self._ws:
            return
        try:
            await self._ws.send(json.dumps({
                "type": "cancel",
                "data": {},
            }))
        except Exception as e:
            logger.warning(f"Failed to send cancel: {e}")

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._ws is not None and self._ws.open


async def run_repl(
    host: str = "127.0.0.1",
    port: int = 8080,
    agent_id: str = "default",
) -> None:
    """
    运行 REPL 对话界面

    Args:
        host: Gateway 主机
        port: Gateway 端口
        agent_id: 使用的 Agent ID
    """
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from src.cli.renderer import Renderer

    renderer = Renderer()
    client = GatewayClient(host=host, port=port, agent_id=agent_id)

    # 尝试连接
    try:
        await client.connect()
    except Exception as e:
        print(f"\n错误: 无法连接到 Gateway\n  {e}")
        print("\n请先启动 Gateway:")
        print("  zclaw start")
        print("  或")
        print("  python main.py start")
        return

    # 打印 banner
    renderer.print_banner()
    print(f"  连接到 Gateway: ws://{host}:{port}\n")

    history = InMemoryHistory()
    session = PromptSession(history=history)

    busy = False

    try:
        while True:
            try:
                # 提示符
                prompt = " ◐ " if busy else " > "
                user_input = await session.prompt_async(prompt)
            except (KeyboardInterrupt, EOFError):
                break

            if user_input is None:
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # 处理命令
            if user_input.startswith("/"):
                cmd = user_input.lower().split()[0]
                if cmd in ("/quit", "/exit", "/q"):
                    break
                elif cmd == "/help":
                    _print_help()
                    continue
                else:
                    print(f"  未知命令: {cmd}")
                    continue

            # 对话
            busy = True
            round_prompt = 0
            round_completion = 0
            assistant_started = False

            try:
                async for event in client.chat(user_input):
                    event_type = event.get("type", "")
                    data = event.get("data", {})

                    if event_type == "stream_delta":
                        if not assistant_started:
                            print("\n")
                            assistant_started = True
                        print(data.get("content", ""), end="", flush=True)

                    elif event_type == "tool_start":
                        print(f"\n  [tool] {data.get('name', '')} 执行中...", flush=True)

                    elif event_type == "tool_end":
                        success = data.get("success", False)
                        name = data.get("name", "")
                        status = "完成" if success else "失败"
                        print(f"  [tool] {name} {status}")

                    elif event_type == "usage":
                        round_prompt = data.get("prompt_tokens", 0)
                        round_completion = data.get("completion_tokens", 0)

                    elif event_type == "done":
                        total = round_prompt + round_completion
                        if total > 0:
                            print(f"\n  Tokens: {round_prompt}+{round_completion}={total}")
                        break

                    elif event_type == "error":
                        print(f"\n  错误: {data.get('message', '未知错误')}")
                        break

            except Exception as e:
                print(f"\n  错误: {e}")

            busy = False
            print()

    except KeyboardInterrupt:
        if busy:
            await client.cancel()
            print("\n  已取消")
    finally:
        await client.disconnect()
        print("\n再见!")


def _print_help():
    """打印帮助信息"""
    print("""
  可用命令:
    /help     显示帮助信息
    /quit     退出
    /exit     退出

  其他:
    直接输入消息与 Agent 对话
""")


async def main():
    """客户端入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Zclaw Gateway Client")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--agent-id", type=str, default="default")

    args = parser.parse_args()

    await run_repl(
        host=args.host,
        port=args.port,
        agent_id=args.agent_id,
    )


if __name__ == "__main__":
    asyncio.run(main())