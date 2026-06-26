"""
Channel Adapters - 通道适配器

各渠道（WebSocket、Telegram、WhatsApp、Slack、QQ）的消息适配器。
"""

from src.channel.channels.base import ChannelAdapter, ChannelMessage
from src.channel.channels.web import WebSocketChannel

from src.channel.channels.qq import QQChannel

__all__ = ["ChannelAdapter", "ChannelMessage", "WebSocketChannel", "QQChannel"]
