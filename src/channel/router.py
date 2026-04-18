"""
消息路由器

根据路由规则将消息分发到对应的 Agent。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RouteRule:
    """路由规则"""
    channel: str                        # 渠道（telegram/whatsapp/slack/websocket）
    sender_id: str = ""                 # 发送者 ID（可选，精确匹配）
    channel_id: str = ""                # 频道 ID（Slack 专用）
    agent_id: str = ""                   # 目标 Agent ID
    priority: int = 0                   # 优先级（数字越大优先级越高）

    def matches(self, channel: str, sender_id: str = "", channel_id: str = "") -> bool:
        """检查消息是否匹配此规则"""
        if self.channel != channel:
            return False

        # 优先精确匹配 sender_id
        if self.sender_id:
            if self.sender_id == sender_id:
                return True
            return False

        # 然后匹配 channel_id（Slack 等）
        if self.channel_id:
            if self.channel_id == channel_id:
                return True
            return False

        # 只有 channel 匹配
        return True


class MessageRouter:
    """
    消息路由器

    根据预定义的路由规则，将消息分发到对应的 Agent。
    """

    def __init__(self, default_agent_id: str = "default"):
        self._rules: list[RouteRule] = []
        self._default_agent_id = default_agent_id

    def add_rule(
        self,
        channel: str,
        agent_id: str,
        sender_id: str = "",
        channel_id: str = "",
        priority: int = 0,
    ) -> None:
        """
        添加路由规则。

        Args:
            channel: 渠道名称
            agent_id: 目标 Agent ID
            sender_id: 发送者 ID（精确匹配）
            channel_id: 频道 ID（Slack 等）
            priority: 优先级
        """
        rule = RouteRule(
            channel=channel,
            sender_id=sender_id,
            channel_id=channel_id,
            agent_id=agent_id,
            priority=priority,
        )
        self._rules.append(rule)
        # 按优先级降序排序
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"添加路由规则: {channel}/{sender_id or channel_id} -> {agent_id}")

    def remove_rule(self, channel: str, sender_id: str = "", channel_id: str = "") -> bool:
        """移除路由规则"""
        for i, rule in enumerate(self._rules):
            if rule.channel == channel:
                if sender_id and rule.sender_id == sender_id:
                    self._rules.pop(i)
                    return True
                if channel_id and rule.channel_id == channel_id:
                    self._rules.pop(i)
                    return True
        return False

    def route(
        self,
        channel: str,
        sender_id: str = "",
        channel_id: str = "",
    ) -> str:
        """
        根据消息属性路由到对应的 Agent。

        Args:
            channel: 渠道名称
            sender_id: 发送者 ID
            channel_id: 频道 ID

        Returns:
            目标 Agent ID
        """
        for rule in self._rules:
            if rule.matches(channel, sender_id, channel_id):
                logger.debug(f"路由匹配: {channel}/{sender_id or channel_id} -> {rule.agent_id}")
                return rule.agent_id

        logger.debug(f"无匹配规则，使用默认: {self._default_agent_id}")
        return self._default_agent_id

    def get_rules(self) -> list[RouteRule]:
        """获取所有路由规则"""
        return list(self._rules)

    def clear_rules(self) -> None:
        """清空所有路由规则"""
        self._rules.clear()

    def load_rules_from_config(self, rules_config: list[dict[str, Any]]) -> None:
        """
        从配置加载路由规则。

        配置格式:
        [
            {"channel": "telegram", "sender_id": "123", "agent_id": "agent-personal"},
            {"channel": "slack", "channel_id": "C01ABCDE", "agent_id": "agent-dev"},
        ]
        """
        for rule_config in rules_config:
            self.add_rule(
                channel=rule_config["channel"],
                agent_id=rule_config["agent_id"],
                sender_id=rule_config.get("sender_id", ""),
                channel_id=rule_config.get("channel_id", ""),
                priority=rule_config.get("priority", 0),
            )
