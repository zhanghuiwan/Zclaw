"""
对话历史压缩器
"""
from __future__ import annotations
import logging
from src.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)


class ContextCompressor:
    """对话历史压缩器"""

    def __init__(self, keep_recent_rounds: int = 4, max_summary_length: int = 2000):
        self._keep_recent = keep_recent_rounds
        self._max_summary_length = max_summary_length

    def compress(self, messages: list[Message]) -> list[Message]:
        """压缩消息列表：保留 system + 最近 N 轮 + 历史摘要。"""
        if len(messages) <= self._keep_recent * 2 + 1:
            return messages

        system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
        non_system = [m for m in messages if m.role != MessageRole.SYSTEM]

        # 分离旧消息和最近消息
        cutoff = self._keep_recent * 2
        old_msgs = non_system[:-cutoff]
        recent_msgs = non_system[-cutoff:]

        # 创建旧消息摘要
        summary = self._summarize(old_msgs)
        if summary:
            summary_msg = Message(
                role=MessageRole.USER,
                content=f"[之前的对话摘要]\n{summary}",
            )
            assistant_ack = Message(
                role=MessageRole.ASSISTANT,
                content="好的，我已经获取了之前对话的上下文。",
            )
            return system_msgs + [summary_msg, assistant_ack] + recent_msgs

        return system_msgs + recent_msgs

    def _summarize(self, messages: list[Message]) -> str:
        """从消息列表提取摘要。"""
        parts = []
        char_count = 0
        for msg in messages:
            if msg.content and msg.role in (MessageRole.USER, MessageRole.ASSISTANT):
                snippet = msg.content[:200]
                parts.append(f"[{msg.role.value}]: {snippet}")
                char_count += len(snippet)
                if char_count >= self._max_summary_length:
                    break
        if not parts:
            return ""
        # 保留最近的条目以获得最新上下文
        parts = parts[-10:]
        return "\n".join(parts)
