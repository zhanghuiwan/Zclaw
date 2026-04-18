"""
Telegram Channel Adapter - Telegram 通道适配器

使用 Telegram Bot API 实现消息收发。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from src.channel.channels.base import ChannelAdapter, ChannelMessage

logger = logging.getLogger(__name__)


class TelegramChannel(ChannelAdapter):
    """
    Telegram 通道适配器

    支持：
    - Webhook 模式接收消息
    - 使用 Telegram Bot API 发送消息
    - 处理 /start, /help 等命令
    - 处理回调查询（Callback Query）
    """

    def __init__(
        self,
        bot_token: str = "",
        webhook_secret: str = "",
        webhook_path: str = "/webhook/telegram",
    ):
        super().__init__("telegram")
        self._bot_token = bot_token
        self._webhook_secret = webhook_secret
        self._webhook_path = webhook_path
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

        # 消息回调
        self._message_callbacks: list[Callable[[ChannelMessage], Any]] = []

        # 运行时状态
        self._enabled = False
        self._update_offset = 0
        self._polling_task: asyncio.Task | None = None

    def set_enabled(self, enabled: bool) -> None:
        """设置是否启用"""
        self._enabled = enabled

    async def start(self) -> None:
        """启动 Telegram 通道"""
        if not self._bot_token:
            logger.warning("Telegram bot token 未配置，跳过启动")
            return

        self._enabled = True
        logger.info(f"Telegram 通道已启动 (webhook_path={self._webhook_path})")

    async def stop(self) -> None:
        """停止 Telegram 通道"""
        self._enabled = False
        if self._polling_task:
            self._polling_task.cancel()
            self._polling_task = None
        logger.info("Telegram 通道已停止")

    async def send(
        self,
        message: str,
        recipient: str | None = None,
        **kwargs,
    ) -> bool:
        """
        发送消息到 Telegram。

        Args:
            message: 消息内容
            recipient: 接收者 ID（chat_id）
            **kwargs: 额外参数（parse_mode, reply_markup 等）

        Returns:
            bool: 是否发送成功
        """
        if not recipient:
            logger.error("Telegram 发送失败: 缺少 chat_id")
            return False

        import aiohttp

        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": recipient,
            "text": message,
            "parse_mode": kwargs.get("parse_mode", "Markdown"),
        }

        # 添加回复标记（可选）
        if kwargs.get("reply_to_message_id"):
            payload["reply_to_message_id"] = kwargs["reply_to_message_id"]

        # 添加键盘（可选）
        if kwargs.get("reply_markup"):
            payload["reply_markup"] = kwargs["reply_markup"]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        logger.debug(f"Telegram 消息已发送: {recipient}")
                        return True
                    else:
                        logger.error(f"Telegram API 错误: {result}")
                        return False
        except Exception as e:
            logger.error(f"Telegram 发送失败: {e}")
            return False

    async def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        caption: str = "",
        **kwargs,
    ) -> bool:
        """发送图片"""
        import aiohttp

        url = f"{self._base_url}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
            "parse_mode": kwargs.get("parse_mode", "Markdown"),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    result = await resp.json()
                    return result.get("ok", False)
        except Exception as e:
            logger.error(f"Telegram 发送图片失败: {e}")
            return False

    async def send_document(
        self,
        chat_id: str,
        document_url: str,
        caption: str = "",
        **kwargs,
    ) -> bool:
        """发送文件"""
        import aiohttp

        url = f"{self._base_url}/sendDocument"
        payload = {
            "chat_id": chat_id,
            "document": document_url,
            "caption": caption,
            "parse_mode": kwargs.get("parse_mode", "Markdown"),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    result = await resp.json()
                    return result.get("ok", False)
        except Exception as e:
            logger.error(f"Telegram 发送文件失败: {e}")
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

    async def handle_webhook(self, payload: dict[str, Any]) -> ChannelMessage | None:
        """
        处理 Telegram Webhook 请求。

        Args:
            payload: Telegram 发送的 webhook payload

        Returns:
            ChannelMessage | None: 归一化的消息
        """
        # 处理回调查询（Inline Keyboard 点击等）
        if "callback_query" in payload:
            return await self._handle_callback_query(payload["callback_query"])

        # 处理消息
        if "message" in payload:
            return await self._handle_message(payload["message"])

        # 处理编辑的消息
        if "edited_message" in payload:
            return await self._handle_message(payload["edited_message"])

        # 处理频道帖子
        if "channel_post" in payload:
            return await self._handle_message(payload["channel_post"])

        return None

    async def _handle_message(self, msg: dict[str, Any]) -> ChannelMessage | None:
        """处理普通消息"""
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = msg.get("text", "")

        # 处理命令
        if text.startswith("/"):
            command = text.split()[0].lower()
            if command in ("/start", "/help"):
                # 发送欢迎消息
                await self.send(
                    chat_id=chat_id,
                    text=self._get_welcome_message(),
                )
                return None  # 不作为对话消息处理

        # 忽略空消息
        if not text:
            return None

        channel_msg = ChannelMessage(
            text=text,
            sender_id=chat_id,
            sender_name=chat.get("username", ""),
            channel=self._channel_name,
            channel_specific={
                "chat_id": chat_id,
                "message_id": msg.get("message_id"),
                "date": msg.get("date"),
            },
            metadata={
                "raw_message": msg,
                "msg_type": "text",
            },
        )

        # 触发回调
        for callback in self._message_callbacks:
            try:
                result = callback(channel_msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Telegram 消息回调失败: {e}")

        return channel_msg

    async def _handle_callback_query(self, query: dict[str, Any]) -> ChannelMessage | None:
        """处理回调查询"""
        from uuid import uuid4

        chat_id = str(query.get("message", {}).get("chat", {}).get("id", ""))
        data = query.get("data", "")

        if not data:
            return None

        # 回答回调（避免超时）
        asyncio.create_task(self._answer_callback_query(query.get("id", "")))

        channel_msg = ChannelMessage(
            text=data,  # callback data 通常是命令
            sender_id=chat_id,
            sender_name="",
            channel=self._channel_name,
            channel_specific={
                "chat_id": chat_id,
                "callback_query_id": query.get("id"),
            },
            metadata={
                "raw_message": query,
                "msg_type": "callback_query",
            },
        )

        for callback in self._message_callbacks:
            try:
                result = callback(channel_msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Telegram 回调处理失败: {e}")

        return channel_msg

    async def _answer_callback_query(self, callback_query_id: str) -> None:
        """回答回调查询"""
        import aiohttp

        url = f"{self._base_url}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    pass  # 忽略响应
        except Exception as e:
            logger.error(f"回答回调查询失败: {e}")

    def _get_welcome_message(self) -> str:
        """获取欢迎消息"""
        return """
🤖 *Zclaw Bot 已启动*

欢迎使用 Zclaw 自主运行助手！

*可用命令：*
/start - 显示此欢迎消息
/help - 获取帮助信息
/status - 查看运行状态

直接发送消息即可与我对话。
""".strip()

    async def set_webhook(self, webhook_url: str) -> bool:
        """
        设置 Webhook URL。

        Args:
            webhook_url: 完整的 webhook URL（如 https://yourdomain.com/webhook/telegram）

        Returns:
            bool: 是否设置成功
        """
        import aiohttp

        url = f"{self._base_url}/setWebhook"
        payload = {
            "url": webhook_url,
            "secret_token": self._webhook_secret,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        logger.info(f"Telegram Webhook 已设置: {webhook_url}")
                        return True
                    logger.error(f"设置 Webhook 失败: {result}")
                    return False
        except Exception as e:
            logger.error(f"设置 Webhook 失败: {e}")
            return False

    async def delete_webhook(self) -> bool:
        """删除 Webhook"""
        import aiohttp

        url = f"{self._base_url}/deleteWebhook"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    result = await resp.json()
                    return result.get("ok", False)
        except Exception as e:
            logger.error(f"删除 Webhook 失败: {e}")
            return False

    async def get_me(self) -> dict[str, Any] | None:
        """获取 Bot 信息"""
        import aiohttp

        url = f"{self._base_url}/getMe"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    result = await resp.json()
                    if result.get("ok"):
                        return result.get("result")
                    return None
        except Exception as e:
            logger.error(f"获取 Bot 信息失败: {e}")
            return None

    def normalize_message(self, raw_message: dict[str, Any]) -> ChannelMessage | None:
        """实现基类方法"""
        return None  # 使用 handle_webhook 代替
