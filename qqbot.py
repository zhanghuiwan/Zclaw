# -*- coding: utf-8 -*-
import os

import botpy
from botpy import logging
from botpy.message import C2CMessage, GroupMessage

_log = logging.get_logger()


class MyClient(botpy.Client):
    """自定义机器人客户端"""

    async def on_ready(self):
        _log.info(f"机器人 「{self.robot.name}」 已上线！")

    # ---------- 单聊消息：C2C_MESSAGE_CREATE ----------
    async def on_c2c_message_create(self, message: C2CMessage):
        """
        用户在单聊给机器人发消息时触发
        """
        _log.info(
            f"收到单聊消息：openid={message.author.user_openid}, "
            f"content={message.content}, id={message.id}"
        )

        # 被动回复：调用 post_c2c_message
        await message._api.post_c2c_message(
            openid=message.author.user_openid,
            msg_type=0,  # 0=文本
            msg_id=message.id,
            content=f"我收到了你的消息：{message.content}",
        )

    # ---------- 群聊 @机器人消息：GROUP_AT_MESSAGE_CREATE ----------
    async def on_group_at_message_create(self, message: GroupMessage):
        """
        用户在群内 @机器人 发消息时触发
        """
        _log.info(
            f"收到群@消息：group_openid={message.group_openid}, "
            f"member_openid={message.author.member_openid}, "
            f"content={message.content}, id={message.id}"
        )

        # 被动回复：调用 post_group_message
        await message._api.post_group_message(
            group_openid=message.group_openid,
            msg_type=0,
            msg_id=message.id,
            content=f"群聊收到：{message.content}",
        )


if __name__ == "__main__":
    # 1. 配置 Intents：只打开需要的公域事件（群/C2C）
    intents = botpy.Intents(public_messages=True)

    # 2. 创建客户端并启动
    client = MyClient(intents=intents)

    # 3. 从环境变量读取 AppID 和 AppSecret
    #    在 .env 中配置 QQ_APPID 和 QQ_APPSECRET,或在运行前 export
    APP_ID = os.environ.get("QQ_APPID", "")
    APP_SECRET = os.environ.get("QQ_APPSECRET", "")

    if not APP_ID or not APP_SECRET:
        raise SystemExit(
            "缺少 QQ_APPID / QQ_APPSECRET 环境变量。"
            "请在 .env 中配置或在运行前 export。"
        )

    client.run(appid=APP_ID, secret=APP_SECRET)