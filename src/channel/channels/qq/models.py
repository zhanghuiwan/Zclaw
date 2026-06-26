"""
QQ 消息模型

QQ 机器人消息数据结构定义。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class QQMsgType(IntEnum):
    """QQ 消息类型"""
    TEXT = 1          # 文本消息
    IMAGE = 2         # 图片消息
    AUDIO = 3         # 语音消息
    VIDEO = 4         # 视频消息
    CARD = 5          # 卡片消息
    RICH_TEXT = 7     # 富文本消息
    MENTION = 9       # @消息
    REPLY = 10        # 回复消息


class QQMessageContent:
    """QQ 消息内容（根据 msg_type 不同，内容字段不同）"""

    def __init__(self, msg_type: int, raw: dict[str, Any]):
        self.msg_type = msg_type
        self.raw = raw

    @property
    def text(self) -> str:
        """获取文本内容（如果有）"""
        return self.raw.get("content", "")

    @property
    def image_url(self) -> str | None:
        """获取图片 URL（如果有）"""
        return self.raw.get("url") or self.raw.get("image_url")

    @property
    def audio_url(self) -> str | None:
        """获取语音 URL（如果有）"""
        return self.raw.get("audio_url")

    @property
    def file_url(self) -> str | None:
        """获取文件 URL（如果有）"""
        return self.raw.get("file_url")


@dataclass
class QQWebhookEvent:
    """
    QQ Webhook 事件

    QQ 服务器推送的事件载荷。
    """
    # 基础字段
    msg_type: int = 1              # 消息类型
    guild_id: str = ""             # 频道 ID
    channel_id: str = ""            # 子频道 ID
    openid: str = ""               # 发送者 openid
    content: str = ""              # 消息内容
    timestamp: int = 0             # 时间戳
    seq: int = 0                   # 消息序列号

    # 扩展字段（原始数据）
    raw: dict[str, Any | None] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QQWebhookEvent:
        """从字典创建事件对象"""
        return cls(
            msg_type=data.get("msg_type", 1),
            guild_id=data.get("guild_id", ""),
            channel_id=data.get("channel_id", ""),
            openid=data.get("openid", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", 0),
            seq=data.get("seq", 0),
            raw=data,
        )

    def is_text_message(self) -> bool:
        """是否为文本消息"""
        return self.msg_type == QQMsgType.TEXT

    def is_mention(self) -> bool:
        """是否为 @消息"""
        return self.msg_type == QQMsgType.MENTION