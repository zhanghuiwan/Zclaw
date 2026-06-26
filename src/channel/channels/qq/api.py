"""
QQ API 封装

QQ 机器人 Open API 调用封装。
"""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class QQAPI:
    """QQ Open API 封装"""

    BASE_URL = "https://api.q.qq.com"
    TOKEN_PATH = "/api/oauth2/token"
    SEND_MSG_PATH = "/api/message/send"

    def __init__(self, appid: str, appsecret: str):
        self._appid = appid
        self._appsecret = appsecret
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    @property
    def is_token_valid(self) -> bool:
        """检查 token 是否有效（提前 5 分钟刷新）"""
        if not self._access_token:
            return False
        return time.time() < self._token_expires_at - 300

    async def ensure_valid_token(self) -> bool:
        """确保有有效的 access_token"""
        if self.is_token_valid:
            return True
        return await self.refresh_token()

    async def refresh_token(self) -> bool:
        """
        获取新的 access_token

        文档: https://q.qq.com/wiki/develop/gateway/open_token.html

        Returns:
            bool: 是否获取成功
        """
        if not self._appid or not self._appsecret:
            logger.error("QQ appid 或 appsecret 未配置")
            return False

        url = f"{self.BASE_URL}{self.TOKEN_PATH}"
        params = {
            "appid": self._appid,
            "appsecret": self._appsecret,
            "grant_type": "client_credential",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"QQ token 请求失败: HTTP {resp.status}, {text}")
                        return False

                    data = await resp.json()

                    if "access_token" not in data:
                        logger.error(f"QQ token 响应缺少 access_token: {data}")
                        return False

                    self._access_token = data["access_token"]
                    # QQ token 有效期通常为 30 天，转为时间戳
                    expires_in = data.get("expires_in", 86400)
                    self._token_expires_at = time.time() + expires_in

                    logger.info("QQ access_token 获取成功")
                    return True

        except aiohttp.ClientError as e:
            logger.error(f"QQ token 请求异常: {e}")
            return False
        except Exception as e:
            logger.error(f"QQ token 获取失败: {e}")
            return False

    async def send_message(
        self,
        receiver: str,
        content: str,
        msg_type: int = 1,
        **kwargs,
    ) -> bool:
        """
        发送消息

        文档: https://q.qq.com/wiki/develop/gateway/message_send.html

        Args:
            receiver: 接收者 openid
            content: 消息内容
            msg_type: 消息类型 (1=文本)
            **kwargs: 额外参数

        Returns:
            bool: 是否发送成功
        """
        if not await self.ensure_valid_token():
            logger.error("QQ access_token 无效，发送失败")
            return False

        url = f"{self.BASE_URL}{self.SEND_MSG_PATH}"
        params = {"access_token": self._access_token}
        payload = {
            "receiver": receiver,
            "msg_type": msg_type,
            "content": content,
            **kwargs,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"QQ 发送消息失败: HTTP {resp.status}, {text}")
                        return False

                    data = await resp.json()

                    if data.get("ret") == 0:
                        logger.debug(f"QQ 消息已发送: {receiver}")
                        return True
                    else:
                        logger.error(f"QQ API 错误: {data}")
                        return False

        except aiohttp.ClientError as e:
            logger.error(f"QQ 发送消息异常: {e}")
            return False
        except Exception as e:
            logger.error(f"QQ 发送消息失败: {e}")
            return False

    async def get_user_info(self, openid: str) -> dict[str, Any] | None:
        """
        获取用户信息

        Args:
            openid: 用户 openid

        Returns:
            用户信息字典，失败返回 None
        """
        if not await self.ensure_valid_token():
            return None

        url = f"{self.BASE_URL}/api/oauth2/user_info"
        params = {
            "access_token": self._access_token,
            "openid": openid,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    if "errcode" in data and data["errcode"] != 0:
                        logger.error(f"获取用户信息失败: {data}")
                        return None

                    return data

        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None