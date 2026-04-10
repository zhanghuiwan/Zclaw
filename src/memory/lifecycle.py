"""
记忆分层生命周期管理

管理记忆的分层存储、自动归档、淘汰和容量控制。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from src.memory.types import Memory, MemoryType

logger = logging.getLogger(__name__)


class MemoryTier(str):
    """记忆层级"""
    WORKING = "working"        # 工作记忆：当前会话产生的临时记忆
    RECENT = "recent"          # 近期记忆：7 天内的高频记忆
    LONG_TERM = "long_term"    # 长期记忆：重要且持久的记忆
    ARCHIVE = "archive"        # 归档记忆：低活跃度，压缩存储


# 默认配置
DEFAULT_CONFIG = {
    "recent_max_age_days": 7,
    "long_term_importance_threshold": 0.7,
    "archive_min_age_days": 30,
    "archive_min_importance": 0.3,
    "delete_min_age_days": 90,
    "delete_min_importance": 0.2,
    "max_total_memories": 1000,
    "working_clear_after_rounds": 3,  # 对话结束后 N 轮自动清理工作记忆
}


class MemoryLifecycleManager:
    """
    记忆生命周期管理器。

    职责：
    1. 为新记忆分配层级
    2. 定期升级/降级记忆层级
    3. 自动淘汰过期低价值记忆
    4. 控制总记忆数量
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = {**DEFAULT_CONFIG, **(config or {})}

    def assign_tier(self, memory: Memory) -> MemoryTier:
        """为新记忆分配初始层级。"""
        now = datetime.now()
        created = self._parse_time(memory.created_at)

        # 根据 importance 和类型分配
        if memory.importance >= self._config["long_term_importance_threshold"]:
            return MemoryTier.LONG_TERM
        elif memory.type in (MemoryType.PREFERENCE, MemoryType.SKILL):
            # 偏好和技能直接进入长期
            return MemoryTier.LONG_TERM
        else:
            return MemoryTier.RECENT

    def classify_all(self, memories: list[Memory]) -> dict[MemoryTier, list[Memory]]:
        """
        将所有记忆分类到各个层级。

        Returns:
            {tier: [memories]}
        """
        now = datetime.now()
        tiers: dict[MemoryTier, list[Memory]] = {
            MemoryTier.WORKING: [],
            MemoryTier.RECENT: [],
            MemoryTier.LONG_TERM: [],
            MemoryTier.ARCHIVE: [],
        }

        for mem in memories:
            created = self._parse_time(mem.created_at)
            age_days = (now - created).total_seconds() / 86400 if created else 0

            # 已有 tier 元数据则直接用
            if mem.metadata.get("tier"):
                try:
                    tier = MemoryTier(mem.metadata["tier"])
                    tiers[tier].append(mem)
                    continue
                except ValueError:
                    pass

            # 根据规则分类
            if age_days > self._config["delete_min_age_days"] and mem.importance < self._config["delete_min_importance"]:
                tiers[MemoryTier.ARCHIVE].append(mem)
            elif mem.importance >= self._config["long_term_importance_threshold"]:
                tiers[MemoryTier.LONG_TERM].append(mem)
            elif mem.type in (MemoryType.PREFERENCE, MemoryType.SKILL):
                tiers[MemoryTier.LONG_TERM].append(mem)
            elif age_days <= self._config["recent_max_age_days"]:
                tiers[MemoryTier.RECENT].append(mem)
            else:
                tiers[MemoryTier.ARCHIVE].append(mem)

        return tiers

    def get_deletable(self, memories: list[Memory]) -> list[Memory]:
        """获取应被删除的记忆列表。"""
        now = datetime.now()
        deletable = []

        for mem in memories:
            created = self._parse_time(mem.created_at)
            age_days = (now - created).total_seconds() / 86400 if created else 0

            if (age_days > self._config["delete_min_age_days"]
                    and mem.importance < self._config["delete_min_importance"]
                    and mem.access_count < 3):
                deletable.append(mem)

        return deletable

    def get_overflow_deletable(
        self,
        memories: list[Memory],
        target_count: int | None = None,
    ) -> list[Memory]:
        """
        当记忆总数超过上限时，返回需要淘汰的记忆。

        淘汰策略：
        1. 先删除 Archive 层的
        2. 按综合得分（importance * 时间衰减）排序，淘汰最低的
        """
        limit = target_count or self._config["max_total_memories"]
        if len(memories) <= limit:
            return []

        # 综合得分：importance × (1 / (1 + age_days/30))
        now = datetime.now()
        scored = []
        for mem in memories:
            created = self._parse_time(mem.created_at)
            age_days = (now - created).total_seconds() / 86400 if created else 0
            time_factor = 1.0 / (1.0 + age_days / 30.0)
            score = mem.importance * time_factor
            scored.append((mem, score))

        scored.sort(key=lambda x: x[1])
        excess = len(memories) - limit
        return [item[0] for item in scored[:excess]]

    def update_memory_tier(self, memory: Memory) -> MemoryTier:
        """更新单条记忆的层级。"""
        tier = self.assign_tier(memory)
        memory.metadata["tier"] = tier  # MemoryTier 是 str 子类，直接赋值
        return tier

    def merge_similar_memories(
        self,
        memories: list[Memory],
        similarity_threshold: float = 0.85,
    ) -> list[tuple[Memory, Memory]]:
        """
        找出可能重复的记忆对（简单字符相似度）。

        Returns:
            [(旧记忆, 新记忆)] 建议合并的对
        """
        from difflib import SequenceMatcher

        pairs = []
        # 只比较同类型的
        by_type: dict[str, list[Memory]] = {}
        for m in memories:
            by_type.setdefault(m.type.value, []).append(m)

        for mtype, group in by_type.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    ratio = SequenceMatcher(
                        None,
                        group[i].content,
                        group[j].content,
                    ).ratio()
                    if ratio >= similarity_threshold:
                        # 保留较新的
                        if group[i].created_at >= group[j].created_at:
                            pairs.append((group[j], group[i]))
                        else:
                            pairs.append((group[i], group[j]))

        return pairs

    @staticmethod
    def _parse_time(time_str: str) -> datetime | None:
        """安全解析时间字符串。"""
        try:
            return datetime.fromisoformat(time_str)
        except (ValueError, TypeError):
            return None
