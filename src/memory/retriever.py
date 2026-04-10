"""
记忆检索器

根据上下文检索相关记忆，支持时序衰减和重要性加权。
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from src.memory.types import Memory, MemoryType
from src.memory.store import MemoryStore


class MemoryRetriever:
    """
    记忆检索器。

    检索策略：
    1. 关键词匹配得分
    2. 时序衰减（近期记忆权重更高）
    3. 重要性加权
    4. 访问频率加权
    """

    def __init__(self, store: MemoryStore):
        self._store = store

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.1,
    ) -> list[Memory]:
        """
        检索与查询相关的记忆。

        Args:
            query: 查询文本
            limit: 最大返回数
            min_score: 最低分数阈值

        Returns:
            按相关性排序的记忆列表
        """
        query_lower = query.lower()
        query_tokens = set(query_lower.split())
        now = datetime.now()

        scored = []
        for mem in self._store.list_all():
            # 1. 关键词匹配得分 (0~1)
            content_lower = mem.content.lower()
            token_match = sum(1 for t in query_tokens if t in content_lower)
            keyword_score = token_match / max(len(query_tokens), 1)

            # 标签匹配
            tags_lower = " ".join(mem.tags).lower()
            tag_match = sum(1 for t in query_tokens if t in tags_lower)
            tag_score = min(tag_match * 0.3, 0.3)

            relevance = min(keyword_score + tag_score, 1.0)

            if relevance < min_score:
                continue

            # 2. 时序衰减（指数衰减，半衰期 7 天）
            try:
                created = datetime.fromisoformat(mem.created_at)
                age_days = (now - created).total_seconds() / 86400
                time_decay = math.exp(-0.1 * age_days)
            except (ValueError, TypeError):
                time_decay = 0.5

            # 3. 重要性
            importance = mem.importance

            # 4. 访问频率
            access_score = min(mem.access_count / 10.0, 1.0)

            # 综合得分
            final_score = (
                relevance * 0.4 +
                time_decay * 0.2 +
                importance * 0.2 +
                access_score * 0.2
            )

            scored.append((mem, final_score))
            mem.touch()

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:limit]]

    def get_recent(self, limit: int = 10) -> list[Memory]:
        """获取最近创建的记忆。"""
        all_mems = self._store.list_all()
        return all_mems[:limit]

    def get_by_type(self, mem_type: str, limit: int = 10) -> list[Memory]:
        """按类型获取记忆。"""
        return self._store.list_all(mem_type=mem_type)[:limit]

    def format_for_context(self, memories: list[Memory]) -> str:
        """将记忆格式化为注入 system prompt 的文本。"""
        if not memories:
            return ""
        lines = ["## 相关记忆\n"]
        type_icons = {
            MemoryType.FACT: "fact",
            MemoryType.EPISODE: "event",
            MemoryType.PREFERENCE: "pref",
            MemoryType.SKILL: "skill",
        }
        for mem in memories:
            icon = type_icons.get(mem.type, mem.type.value)
            lines.append(f"- [{icon}] {mem.content}")
            if mem.tags:
                lines.append(f"  （标签: {', '.join(mem.tags)})")
        return "\n".join(lines)
