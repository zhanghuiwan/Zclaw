"""
Stdio Channel - 标准输入/输出通道

将标准输入/输出封装为 Channel 接口，使 CLI 模式可以接入 Gateway。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Callable

from src.channel.channels.base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)


class StdioChannel(ChannelAdapter):
    """
    STDIO 通道 - 用于交互式 CLI 模式

    将标准输入/输出封装为 Channel 接口：
    - start() 开始监听 stdin
    - stop() 停止监听
    - send() 输出到 stdout
    - on_message() 注册消息回调
    """

    def __init__(
        self,
        prompt: str = " > ",
        input_lock: asyncio.Lock | None = None,
    ):
        super().__init__("stdio")
        self._prompt = prompt
        self._input_lock = input_lock or asyncio.Lock()

        # 消息回调
        self._message_callbacks: list[Callable[[ChannelMessage], None]] = []

        # 运行时状态
        self._running = False
        self._input_task: asyncio.Task | None = None

        # 用于非异步环境（如 main.py 同步调用）
        self._pending_messages: asyncio.Queue[str] | None = None

    def set_enabled(self, enabled: bool) -> None:
        """设置是否启用"""
        self._enabled = enabled
        if not enabled:
            self._running = False

    async def start(self) -> None:
        """启动 STDIO 监听"""
        if self._running:
            logger.warning("StdioChannel 已在运行")
            return

        self._running = True
        logger.info("StdioChannel 已启动")

    async def stop(self) -> None:
        """停止 STDIO 监听"""
        self._running = False

        if self._input_task:
            self._input_task.cancel()
            self._input_task = None

        logger.info("StdioChannel 已停止")

    async def send(self, message: str, recipient: str | None = None, **kwargs) -> bool:
        """
        发送消息到标准输出。

        Args:
            message: 消息内容
            recipient: 接收者（CLI 模式下为 None）
            **kwargs: 额外参数

        Returns:
            bool: 是否发送成功
        """
        if not self._running:
            return False

        try:
            print(message, flush=True)
            return True
        except Exception as e:
            logger.error(f"StdioChannel 发送失败: {e}")
            return False

    def on_message(self, callback: Callable[[ChannelMessage], None]) -> None:
        """
        注册消息回调。

        Args:
            callback: 消息回调函数，签名为 (ChannelMessage) -> None
        """
        self._message_callbacks.append(callback)

    def unregister_message_callback(self, callback: Callable[[ChannelMessage], None]) -> bool:
        """注销消息回调"""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)
            return True
        return False

    async def read_line(self, prompt: str | None = None) -> str | None:
        """
        读取一行输入（异步方式）。

        Args:
            prompt: 提示符

        Returns:
            str | None: 用户输入或 None（如果取消）
        """
        if not self._running:
            return None

        prompt_str = prompt or self._prompt

        try:
            # 在事件循环中读取输入
            loop = asyncio.get_event_loop()
            line = await loop.run_in_executor(
                None,
                lambda: input(prompt_str)
            )
            return line
        except (EOFError, KeyboardInterrupt):
            return None
        except Exception as e:
            logger.error(f"StdioChannel 读取失败: {e}")
            return None

    async def process_input(self, user_input: str) -> None:
        """
        处理用户输入，触发回调。

        Args:
            user_input: 用户输入的文本
        """
        if not user_input.strip():
            return

        channel_msg = ChannelMessage(
            text=user_input.strip(),
            sender_id="cli_user",
            sender_name="user",
            channel=self._channel_name,
            channel_specific={},
            metadata={},
        )

        # 触发回调
        for callback in self._message_callbacks:
            try:
                result = callback(channel_msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"StdioChannel 消息回调失败: {e}")

    # ==================== 同步接口（兼容 REPL）====================

    def send_sync(self, message: str) -> bool:
        """
        同步发送消息到标准输出（不添加换行）。

        用于 REPL 风格的流式输出。
        """
        try:
            sys.stdout.write(message)
            sys.stdout.flush()
            return True
        except Exception as e:
            logger.error(f"StdioChannel 同步发送失败: {e}")
            return False

    def print(self, *args, **kwargs) -> None:
        """打印消息到标准输出（添加换行）"""
        try:
            print(*args, **kwargs)
        except Exception as e:
            logger.error(f"StdioChannel 打印失败: {e}")

    async def read_input_async(self) -> str | None:
        """
        异步读取用户输入（带提示符）。

        Returns:
            str | None: 用户输入
        """
        return await self.read_line()

    def normalize_message(self, raw_message: dict[str, Any]) -> ChannelMessage | None:
        """
        将原始消息归一化为 ChannelMessage。

        对于 STDIO 通道，raw_message 应该是 {"text": "...", "sender_id": "..."}
        """
        text = raw_message.get("text", "") if isinstance(raw_message, dict) else str(raw_message)
        if not text:
            return None

        return ChannelMessage(
            text=text,
            sender_id=raw_message.get("sender_id", "cli_user") if isinstance(raw_message, dict) else "cli_user",
            sender_name=raw_message.get("sender_name", "user") if isinstance(raw_message, dict) else "user",
            channel=self._channel_name,
            channel_specific={},
            metadata=raw_message if isinstance(raw_message, dict) else {},
        )

    def __repr__(self) -> str:
        return f"StdioChannel(running={self._running}, callbacks={len(self._message_callbacks)})"