"""
Base Channel Adapter - 通道适配器基类

定义各渠道适配器的接口。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChannelMessage:
    """通道消息"""
    text: str
    sender_id: str = ""
    sender_name: str = ""
    channel: str = ""          # 渠道名称
    channel_specific: dict[str, Any] | None = None  # 渠道特定数据
    metadata: dict[str, Any] | None = None


class ChannelAdapter(ABC):
    """
    通道适配器抽象基类

    各渠道（WebSocket、Telegram 等）需要实现此接口。
    """

    def __init__(self, channel_name: str):
        self._channel_name = channel_name
        self._enabled = True

    @property
    def channel_name(self) -> str:
        return self._channel_name

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    @abstractmethod
    async def start(self) -> None:
        """启动通道监听"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止通道监听"""
        pass

    @abstractmethod
    async def send(self, message: str, recipient: str | None = None, **kwargs) -> bool:
        """
        发送消息。

        Args:
            message: 消息内容
            recipient: 接收者标识（渠道特定）
            **kwargs: 额外的发送参数

        Returns:
            bool: 是否发送成功
        """
        pass

    def normalize_message(self, raw_message: dict[str, Any]) -> ChannelMessage | None:
        """
        将原始消息归一化为 ChannelMessage。

        Args:
            raw_message: 渠道特定的原始消息

        Returns:
            ChannelMessage | None: 归一化的消息，如果消息不需要处理则返回 None
        """
        return None
