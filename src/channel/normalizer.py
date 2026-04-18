"""
消息归一化模块

将来自不同渠道的消息统一为内部标准格式（UnifiedMessage），
抹平平台差异。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UnifiedMessage:
    """统一消息格式"""
    text: str                           # 消息文本内容
    channel: str                        # 来源渠道（websocket/telegram/whatsapp/slack）
    sender_id: str = ""                 # 发送者 ID
    sender_name: str = ""               # 发送者名称
    channelSpecific: dict[str, Any] = field(default_factory=dict)  # 渠道特定数据
    metadata: dict[str, Any] = field(default_factory=dict)         # 元数据

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "channel": self.channel,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "channelSpecific": self.channelSpecific,
            "metadata": self.metadata,
        }


class MessageNormalizer:
    """
    消息归一化器

    将不同渠道的消息格式统一转换为 UnifiedMessage。
    """

    def normalize(self, raw_message: dict[str, Any], channel: str) -> UnifiedMessage:
        """
        将原始消息归一化。

        Args:
            raw_message: 原始消息字典
            channel: 消息来源渠道

        Returns:
            UnifiedMessage: 统一格式的消息
        """
        if channel == "websocket":
            return self._normalize_websocket(raw_message)
        elif channel == "telegram":
            return self._normalize_telegram(raw_message)
        elif channel == "whatsapp":
            return self._normalize_whatsapp(raw_message)
        elif channel == "slack":
            return self._normalize_slack(raw_message)
        else:
            return self._normalize_generic(raw_message, channel)

    def _normalize_websocket(self, msg: dict[str, Any]) -> UnifiedMessage:
        """归一化 WebSocket 消息"""
        data = msg.get("data", {})
        return UnifiedMessage(
            text=data.get("message", ""),
            channel="websocket",
            sender_id=data.get("sender_id", "anonymous"),
            sender_name=data.get("sender_name", ""),
            channelSpecific=data,
            metadata={"raw_type": msg.get("type", "unknown")},
        )

    def _normalize_telegram(self, msg: dict[str, Any]) -> UnifiedMessage:
        """归一化 Telegram 消息"""
        message = msg.get("message", {})
        from_user = message.get("from", {})

        # 处理文本消息
        text = message.get("text", "")
        # 处理回调查询（按钮点击）
        if not text and msg.get("callback_query"):
            callback_query = msg["callback_query"]
            text = callback_query.get("data", "")
            from_user = callback_query.get("from", {})

        return UnifiedMessage(
            text=text,
            channel="telegram",
            sender_id=str(from_user.get("id", "")),
            sender_name=from_user.get("first_name", ""),
            channelSpecific={
                "chat_id": message.get("chat", {}).get("id"),
                "message_id": message.get("message_id"),
            },
            metadata={
                "raw": msg,
            },
        )

    def _normalize_whatsapp(self, msg: dict[str, Any]) -> UnifiedMessage:
        """归一化 WhatsApp 消息"""
        # WhatsApp Cloud API 格式
        entry = msg.get("entry", [])
        if entry:
            changes = entry[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                if messages:
                    wa_msg = messages[0]
                    return UnifiedMessage(
                        text=wa_msg.get("text", {}).get("body", ""),
                        channel="whatsapp",
                        sender_id=wa_msg.get("from", ""),
                        sender_name="",  # WhatsApp 不直接提供名称
                        channelSpecific={
                            "wa_id": value.get("metadata", {}).get("phone_number_id"),
                            "timestamp": wa_msg.get("timestamp"),
                        },
                        metadata={"raw": msg},
                    )

        # 备用：简单格式
        return UnifiedMessage(
            text=msg.get("text", msg.get("body", "")),
            channel="whatsapp",
            sender_id=msg.get("from", ""),
            sender_name="",
            metadata={"raw": msg},
        )

    def _normalize_slack(self, msg: dict[str, Any]) -> UnifiedMessage:
        """归一化 Slack 消息"""
        # Slack Events API 格式
        if msg.get("type") == "event_callback":
            event = msg.get("event", {})
            channel = event.get("channel", "")
            user = event.get("user", "")

            # 处理消息删除等事件
            if event.get("type") in ("message", "app_mention"):
                return UnifiedMessage(
                    text=event.get("text", ""),
                    channel="slack",
                    sender_id=user,
                    sender_name="",
                    channelSpecific={
                        "channel_id": channel,
                        "ts": event.get("ts"),
                        "thread_ts": event.get("thread_ts"),
                    },
                    metadata={"raw": msg},
                )

        # 处理斜杠命令
        if msg.get("type") == "shortcut":
            return UnifiedMessage(
                text=msg.get("payload", {}).get("command", ""),
                channel="slack",
                sender_id=msg.get("payload", {}).get("user_id", ""),
                channelSpecific={"trigger_id": msg.get("trigger_id")},
                metadata={"raw": msg},
            )

        return UnifiedMessage(
            text=msg.get("text", ""),
            channel="slack",
            sender_id=msg.get("user", ""),
            metadata={"raw": msg},
        )

    def _normalize_generic(self, msg: dict[str, Any], channel: str) -> UnifiedMessage:
        """通用归一化（兜底）"""
        return UnifiedMessage(
            text=msg.get("text", msg.get("message", str(msg))),
            channel=channel,
            sender_id=msg.get("sender_id", msg.get("user_id", "")),
            sender_name=msg.get("sender_name", ""),
            channelSpecific=msg,
            metadata={},
        )
