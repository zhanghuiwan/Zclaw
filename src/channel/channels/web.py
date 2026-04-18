"""
WebSocket Channel Adapter - WebSocket 通道适配器

适配现有的 WebSocket 消息格式。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from src.channel.channels.base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)


class WebSocketChannel(ChannelAdapter):
    """
    WebSocket 通道适配器

    与现有的 WebSocket 管理器集成。
    """

    def __init__(self):
        super().__init__("websocket")
        self._connections: dict[str, Any] = {}  # conn_id -> websocket
        self._message_callbacks: list[Callable[[ChannelMessage], Any]] = []
        self._running = False
        self._ws_manager = None

    async def start(self) -> None:
        """启动 WebSocket 服务（与现有 server 集成）"""
        self._running = True
        logger.info("WebSocket 通道已启动")

    async def stop(self) -> None:
        """停止 WebSocket 服务"""
        self._running = False
        self._connections.clear()
        logger.info("WebSocket 通道已停止")

    async def send(self, message: str, recipient: str | None = None, **kwargs) -> bool:
        """
        发送消息到 WebSocket 客户端。

        Args:
            message: 消息内容
            recipient: 连接 ID（conn_id）
            **kwargs: 额外参数（如 message_type）

        Returns:
            bool: 是否发送成功
        """
        from src.web.ws_manager import ConnectionManager

        if self._ws_manager is None:
            self._ws_manager = ConnectionManager()

        message_type = kwargs.get("type", "chat")
        conn_id = recipient or kwargs.get("conn_id")

        if conn_id:
            try:
                await self._ws_manager.send_json(conn_id, {
                    "type": message_type,
                    "data": {"content": message},
                })
                return True
            except Exception as e:
                logger.error(f"WebSocket 发送失败: {e}")
                return False
        else:
            # 广播到所有连接
            return await self._broadcast(message, message_type)

    async def _broadcast(self, message: str, message_type: str = "chat") -> bool:
        """广播消息到所有连接"""
        if self._ws_manager is None:
            return False

        try:
            for conn_id in list(self._ws_manager.active_connections.keys()):
                await self._ws_manager.send_json(conn_id, {
                    "type": message_type,
                    "data": {"content": message},
                })
            return True
        except Exception as e:
            logger.error(f"WebSocket 广播失败: {e}")
            return False

    def register_message_callback(self, callback: Callable[[ChannelMessage], Any]) -> None:
        """注册消息回调"""
        self._message_callbacks.append(callback)

    def unregister_message_callback(self, callback: Callable[[ChannelMessage], Any]) -> bool:
        """注销消息回调"""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)
            return True
        return False

    async def handle_raw_message(self, conn_id: str, raw_message: dict[str, Any]) -> ChannelMessage | None:
        """
        处理原始 WebSocket 消息。

        Args:
            conn_id: 连接 ID
            raw_message: 原始消息字典

        Returns:
            ChannelMessage | None: 归一化的消息
        """
        channel_msg = self.normalize_message(raw_message)
        if channel_msg:
            # 设置发送者 ID 为连接 ID
            if not channel_msg.sender_id:
                channel_msg.sender_id = conn_id

            # 触发回调
            for callback in self._message_callbacks:
                try:
                    result = callback(channel_msg)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"WebSocket 消息回调失败: {e}")

        return channel_msg

    def normalize_message(self, raw_message: dict[str, Any]) -> ChannelMessage | None:
        """将 WebSocket 原始消息归一化"""
        msg_type = raw_message.get("type", "")
        data = raw_message.get("data", {})

        if msg_type == "chat":
            text = data.get("message", "").strip()
            if not text:
                return None

            return ChannelMessage(
                text=text,
                sender_id=data.get("sender_id", "anonymous"),
                sender_name=data.get("sender_name", ""),
                channel=self._channel_name,
                channel_specific=data,
                metadata={"raw_type": msg_type},
            )

        return None
