"""
Channel Layer - 消息通道层

负责接收来自不同渠道的消息（WebSocket、Telegram、Slack 等），
进行归一化处理后路由到对应的 Agent。
"""

from src.channel.gateway import Gateway
from src.channel.router import MessageRouter
from src.channel.normalizer import MessageNormalizer, UnifiedMessage

__all__ = ["Gateway", "MessageRouter", "MessageNormalizer", "UnifiedMessage"]
