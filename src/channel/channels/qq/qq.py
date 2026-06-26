"""
QQ Channel Adapter - QQ 通道适配器

使用 QQ 机器人官方 Python SDK (botpy) 实现消息收发。
"""

from __future__ import annotations

import logging
from typing import Any

import botpy
from botpy import logging as botpy_logging
from botpy.message import C2CMessage, GroupMessage

from src.channel.channels.base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)
_log = botpy_logging.get_logger()


class QQChannel(ChannelAdapter):
    """
    QQ 通道适配器（使用 botpy SDK）

    通过继承 botpy.Client 实现消息接收和发送。
    """

    def __init__(
        self,
        appid: str = "",
        appsecret: str = "",
    ):
        """
        初始化 QQ 通道

        Args:
            appid: QQ 应用 ID
            appsecret: QQ 应用密钥
        """
        super().__init__("qq")
        self._appid = appid
        self._appsecret = appsecret

        # 消息回调
        self._message_callbacks: list[Any] = []

        # botpy 客户端（在 start 时创建）
        self._client: _QQClient | None = None

    # ==================== 公开接口 ====================

    async def start(self) -> None:
        """启动 QQ 通道"""
        if not self._appid or not self._appsecret:
            logger.warning("QQ appid 或 appsecret 未配置，跳过启动")
            return

        self._enabled = True

        # 创建 botpy 客户端
        intents = botpy.Intents(public_messages=True)
        self._client = _QQClient(
            intents=intents,
            channel=self,
        )

        # 启动 botpy（使用 appid 和 secret）
        import asyncio
        asyncio.create_task(self._run_client())

        logger.info("QQ 通道已启动")

    async def _run_client(self) -> None:
        """运行 botpy 客户端"""
        if self._client:
            try:
                await self._client.start(appid=self._appid, secret=self._appsecret)
            except Exception as e:
                logger.error(f"QQ botpy 客户端错误: {e}")

    async def stop(self) -> None:
        """停止 QQ 通道"""
        self._enabled = False
        if self._client:
            self._client = None
        logger.info("QQ 通道已停止")

    async def send(
        self,
        message: str,
        recipient: str | None = None,
        **kwargs,
    ) -> bool:
        """
        发送消息（被动回复方式）

        Args:
            message: 消息内容
            recipient: 接收者 openid（私聊时使用）
            **kwargs: 额外参数 (group_openid, msg_id, api)

        Returns:
            bool: 是否发送成功
        """
        api = kwargs.get("api")
        group_openid = kwargs.get("group_openid", "")
        msg_id = kwargs.get("msg_id", "")
        msg_seq = kwargs.get("msg_seq", 1)

        if not api:
            logger.warning("QQ 发送失败: 缺少 api 实例")
            return False

        try:
            if group_openid:
                # 群聊消息 - 使用 post_group_message
                await api.post_group_message(
                    group_openid=group_openid,
                    msg_type=0,  # 0=文本
                    msg_id=msg_id,
                    msg_seq=msg_seq,
                    content=message,
                )
            else:
                # 私聊消息 - 使用 post_c2c_message
                await api.post_c2c_message(
                    openid=recipient,
                    msg_type=0,
                    msg_id=msg_id,
                    msg_seq=msg_seq,
                    content=message,
                )
            return True
        except Exception as e:
            logger.error(f"QQ 发送消息失败: {e}")
            return False

    def register_message_callback(self, callback: Any) -> None:
        """注册消息回调"""
        self._message_callbacks.append(callback)

    def unregister_message_callback(self, callback: Any) -> bool:
        """注销消息回调"""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)
            return True
        return False

    async def _dispatch_message(self, channel_msg: ChannelMessage, api: Any = None) -> None:
        """分发消息到回调"""
        # 将 api 保存到 metadata 中，以便后续 send 使用
        if api:
            channel_msg.metadata["api"] = api

        for callback in self._message_callbacks:
            try:
                result = callback(channel_msg)
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.error(f"QQ 消息回调失败: {e}")

    def normalize_message(self, raw_message: dict[str, Any]) -> ChannelMessage | None:
        """实现基类方法（暂不使用）"""
        return None


class _QQClient(botpy.Client):
    """
    QQ 机器人客户端

    继承 botpy.Client 实现消息处理。
    """

    def __init__(self, intents: Any, channel: QQChannel):
        super().__init__(intents=intents)
        self._channel = channel

    async def on_ready(self):
        """机器人上线回调"""
        _log.info(f"机器人 「{self.robot.name}」 已上线！")
        logger.info(f"QQ 机器人登录成功: {self.robot.name}")

    async def on_c2c_message_create(self, message: C2CMessage):
        """
        单聊消息回调

        Args:
            message: C2CMessage 对象，包含:
                - author.user_openid: 发送者 openid
                - content: 消息内容
                - id: 消息 ID
        """
        _log.info(
            f"收到单聊消息：openid={message.author.user_openid}, "
            f"content={message.content}, id={message.id}"
        )

        # 构建 ChannelMessage
        channel_msg = ChannelMessage(
            text=message.content,
            sender_id=message.author.user_openid,
            sender_name="",
            channel="qq",
            channel_specific={
                "msg_type": "C2C",
                "msg_id": message.id,
                "msg_seq": message.msg_seq or 1,
                "openid": message.author.user_openid,
            },
            metadata={},
        )

        # 派发消息到回调处理（回调会调用 Gateway 并回复）
        await self._channel._dispatch_message(channel_msg, message._api)

    async def on_group_at_message_create(self, message: GroupMessage):
        """
        群@消息回调

        Args:
            message: GroupMessage 对象，包含:
                - group_openid: 群号
                - author.member_openid: 发送者
                - content: 消息内容
                - id: 消息 ID
        """
        _log.info(
            f"收到群@消息：group_openid={message.group_openid}, "
            f"member_openid={message.author.member_openid}, "
            f"content={message.content}, id={message.id}"
        )

        # 构建 ChannelMessage（content 可能包含 @机器人的前缀空格，需要strip）
        content = message.content.strip()

        channel_msg = ChannelMessage(
            text=content,
            sender_id=message.author.member_openid,
            sender_name="",
            channel="qq",
            channel_specific={
                "msg_type": "GROUP",
                "msg_id": message.id,
                "msg_seq": message.msg_seq or 1,
                "group_openid": message.group_openid,
                "member_openid": message.author.member_openid,
            },
            metadata={},
        )

        # 派发消息到回调处理（回调会调用 Gateway 并回复）
        await self._channel._dispatch_message(channel_msg, message._api)