"""
Inter-Agent Messenger - Agent 间消息传递

支持不同 Agent 之间的消息传递和协作。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """消息优先级"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class InterAgentMessage:
    """Agent 间消息"""
    msg_id: str
    from_agent: str                 # 发送者 Agent ID
    to_agent: str                   # 接收者 Agent ID
    content: dict[str, Any]        # 消息内容
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    reply_to: str = ""             # 回复的消息 ID
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
            "metadata": self.metadata,
        }


class InterAgentMessenger:
    """
    Agent 间消息传递器

    支持：
    - 点对点消息发送
    - 广播消息
    - 消息收件箱
    """

    def __init__(self):
        self._inboxes: dict[str, list[InterAgentMessage]] = {}  # agent_id -> 收件箱
        self._sent_messages: list[InterAgentMessage] = []       # 已发送消息
        self._message_counter = 0

    def _generate_msg_id(self) -> str:
        """生成消息 ID"""
        import uuid
        self._message_counter += 1
        return f"msg_{uuid.uuid4().hex[:8]}_{self._message_counter}"

    async def send(
        self,
        from_agent: str,
        to_agent: str,
        content: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: str = "",
    ) -> str:
        """
        发送消息给另一个 Agent。

        Args:
            from_agent: 发送者 Agent ID
            to_agent: 接收者 Agent ID
            content: 消息内容
            priority: 优先级
            reply_to: 回复的消息 ID

        Returns:
            str: 消息 ID
        """
        msg_id = self._generate_msg_id()

        message = InterAgentMessage(
            msg_id=msg_id,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            priority=priority,
            reply_to=reply_to,
        )

        # 添加到接收者的收件箱
        if to_agent not in self._inboxes:
            self._inboxes[to_agent] = []
        self._inboxes[to_agent].append(message)

        # 记录已发送消息
        self._sent_messages.append(message)

        logger.info(f"Agent 间消息: {from_agent} -> {to_agent} ({msg_id})")
        return msg_id

    async def broadcast(
        self,
        from_agent: str,
        content: dict[str, Any],
        exclude_agents: list[str] | None = None,
    ) -> list[str]:
        """
        广播消息给所有 Agent。

        Args:
            from_agent: 发送者 Agent ID
            content: 消息内容
            exclude_agents: 要排除的 Agent 列表

        Returns:
            list[str]: 发送到的 Agent ID 列表
        """
        exclude_set = set(exclude_agents or [])
        target_agents = [
            agent_id
            for agent_id in self._inboxes.keys()
            if agent_id not in exclude_set
        ]

        msg_ids = []
        for agent_id in target_agents:
            msg_id = await self.send(
                from_agent=from_agent,
                to_agent=agent_id,
                content=content,
            )
            msg_ids.append(msg_id)

        logger.info(f"广播消息: {from_agent} -> {target_agents} ({len(msg_ids)} 个)")
        return target_agents

    def get_inbox(self, agent_id: str) -> list[InterAgentMessage]:
        """
        获取 Agent 的收件箱。

        Args:
            agent_id: Agent ID

        Returns:
            list: 消息列表（按时间排序）
        """
        messages = self._inboxes.get(agent_id, [])
        return sorted(messages, key=lambda m: m.timestamp, reverse=True)

    def get_inbox_count(self, agent_id: str) -> int:
        """获取收件箱未读消息数量"""
        return len(self._inboxes.get(agent_id, []))

    def peek_inbox(
        self,
        agent_id: str,
        count: int = 10,
        priority: MessagePriority | None = None,
    ) -> list[InterAgentMessage]:
        """
        查看收件箱消息（不标记为已读）。

        Args:
            agent_id: Agent ID
            count: 返回数量
            priority: 按优先级过滤

        Returns:
            list: 消息列表
        """
        messages = self.get_inbox(agent_id)

        if priority:
            messages = [m for m in messages if m.priority == priority]

        return messages[:count]

    def pop_message(self, agent_id: str, msg_id: str) -> InterAgentMessage | None:
        """
        取出并移除消息。

        Args:
            agent_id: Agent ID
            msg_id: 消息 ID

        Returns:
            InterAgentMessage | None: 消息或 None
        """
        inbox = self._inboxes.get(agent_id, [])
        for i, msg in enumerate(inbox):
            if msg.msg_id == msg_id:
                return inbox.pop(i)

        return None

    def mark_read(self, agent_id: str, msg_id: str) -> bool:
        """
        标记消息为已读。

        Args:
            agent_id: Agent ID
            msg_id: 消息 ID

        Returns:
            bool: 是否成功
        """
        inbox = self._inboxes.get(agent_id, [])
        for msg in inbox:
            if msg.msg_id == msg_id:
                msg.metadata["read"] = True
                return True
        return False

    def delete_message(self, agent_id: str, msg_id: str) -> bool:
        """
        删除消息。

        Args:
            agent_id: Agent ID
            msg_id: 消息 ID

        Returns:
            bool: 是否成功
        """
        msg = self.pop_message(agent_id, msg_id)
        return msg is not None

    def clear_inbox(self, agent_id: str) -> int:
        """
        清空收件箱。

        Args:
            agent_id: Agent ID

        Returns:
            int: 删除的消息数量
        """
        count = len(self._inboxes.get(agent_id, []))
        self._inboxes[agent_id] = []
        return count

    def get_sent_messages(
        self,
        from_agent: str | None = None,
        to_agent: str | None = None,
    ) -> list[InterAgentMessage]:
        """
        获取已发送消息历史。

        Args:
            from_agent: 按发送者过滤
            to_agent: 按接收者过滤

        Returns:
            list: 消息列表
        """
        messages = self._sent_messages

        if from_agent:
            messages = [m for m in messages if m.from_agent == from_agent]

        if to_agent:
            messages = [m for m in messages if m.to_agent == to_agent]

        return sorted(messages, key=lambda m: m.timestamp, reverse=True)

    def get_status(self) -> dict[str, Any]:
        """获取消息传递器状态"""
        return {
            "inbox_count": len(self._inboxes),
            "total_messages": len(self._sent_messages),
            "agents_with_messages": [
                {
                    "agent_id": agent_id,
                    "count": len(messages),
                }
                for agent_id, messages in self._inboxes.items()
                if messages
            ],
        }
