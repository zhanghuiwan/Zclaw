"""
记忆管理器

提供记忆的统一管理接口，整合存储、检索、提取和生命周期管理。
"""

from __future__ import annotations

import logging
from typing import Any

from src.config.settings import MemoryConfig
from src.memory.types import Memory, MemoryType
from src.memory.store import MemoryStore
from src.memory.retriever import MemoryRetriever
from src.memory.extractor import BaseExtractor, ExtractedMemory
from src.memory.lifecycle import MemoryLifecycleManager, MemoryTier

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器。

    高层 API:
    - remember: 保存一条记忆
    - recall: 检索相关记忆
    - forget: 删除记忆
    - get_context: 获取格式化的记忆上下文
    - extract_from_conversation: 从对话中自动提取记忆
    - run_lifecycle: 执行生命周期管理（归档/淘汰）
    """

    def __init__(
        self,
        config: MemoryConfig,
        session_id: str = "",
        extractor: BaseExtractor | None = None,
    ):
        self._config = config
        self._session_id = session_id
        self._store = MemoryStore(storage_path=config.storage_path)
        self._retriever = MemoryRetriever(self._store)
        self._lifecycle = MemoryLifecycleManager()
        # 提取器
        self._extractor = extractor
        # 维护计数器：每N次对话后运行一次生命周期管理
        self._conversation_count = 0
        self._MAINTENANCE_INTERVAL = 10  # 每10次对话后维护一次

    @property
    def extractor(self) -> BaseExtractor:
        return self._extractor

    @extractor.setter
    def extractor(self, value: BaseExtractor) -> None:
        self._extractor = value

    @property
    def lifecycle(self) -> MemoryLifecycleManager:
        return self._lifecycle

    def remember(
        self,
        content: str,
        mem_type: str = "fact",
        tags: list[str] | None = None,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        """保存一条记忆。"""
        try:
            mtype = MemoryType(mem_type)
        except ValueError:
            mtype = MemoryType.FACT
            logger.warning(f"未知的记忆类型 '{mem_type}'，默认使用 'fact'")

        mem = Memory(
            content=content,
            type=mtype,
            tags=tags or [],
            importance=importance,
            metadata=metadata or {},
        )
        if self._session_id:
            mem.metadata["session_id"] = self._session_id

        # 分配层级
        tier = self._lifecycle.update_memory_tier(mem)

        self._store.add(mem)
        logger.debug(f"已保存记忆: {mem.id} ({mtype.value}/{tier}): {content[:50]}")
        return mem

    def remember_batch(self, extracted: list[ExtractedMemory]) -> int:
        """批量保存提取出的记忆，返回实际保存数量。"""
        count = 0
        for em in extracted:
            if not em.content.strip():
                continue
            self.remember(
                content=em.content,
                mem_type=em.type,
                tags=["auto_extracted"] + em.tags,
                importance=em.importance,
            )
            count += 1

        # 合并相似记忆
        if count > 0:
            self._merge_similar()

        return count

    def _merge_similar(self, similarity_threshold: float = 0.85) -> int:
        """合并相似记忆，返回合并的记忆对数。"""
        all_memories = self._store.list_all()
        pairs = self._lifecycle.merge_similar_memories(all_memories, similarity_threshold)

        merged_count = 0
        for old_mem, new_mem in pairs:
            # 保留较新的记忆，更新其 access_count
            new_mem.access_count = max(new_mem.access_count, old_mem.access_count)
            new_mem.touch()
            # 删除旧的
            self._store.delete(old_mem.id)
            merged_count += 1
            logger.debug(f"合并相似记忆: {old_mem.id} -> {new_mem.id}")

        if merged_count > 0:
            logger.info(f"合并了 {merged_count} 对相似记忆")
        return merged_count

    async def extract_from_conversation(self, messages: list) -> list[Memory]:
        """
        从对话中自动提取记忆并保存。

        Args:
            messages: 对话消息列表

        Returns:
            新保存的记忆列表
        """
        if self._extractor is None:
            logger.warning("没有配置记忆提取器")
            return []

        try:
            extracted = await self._extractor.extract(messages)
        except Exception as e:
            logger.error(f"记忆提取失败: {e}")
            return []

        new_memories = []
        for em in extracted:
            if not em.content.strip():
                continue
            mem = self.remember(
                content=em.content,
                mem_type=em.type,
                tags=["auto_extracted"] + em.tags,
                importance=em.importance,
            )
            new_memories.append(mem)

        if new_memories:
            logger.info(f"自动提取并保存了 {len(new_memories)} 条记忆")

        # 维护计数器递增，周期性运行生命周期管理
        self._conversation_count += 1
        if self._conversation_count % self._MAINTENANCE_INTERVAL == 0:
            logger.info(f"触发定期维护（已对话 {self._conversation_count} 次）")
            self.run_lifecycle()

        return new_memories

    def recall(self, query: str, limit: int = 10) -> list[Memory]:
        """检索相关记忆。"""
        return self._retriever.retrieve(query, limit=limit)

    def forget(self, memory_id: str) -> bool:
        """删除一条记忆。"""
        return self._store.delete(memory_id)

    def get_context(self, query: str = "", limit: int = 10) -> str:
        """
        获取格式化的记忆上下文，用于注入 system prompt。

        Args:
            query: 当前用户输入（用于检索相关记忆）
            limit: 最大记忆数

        Returns:
            格式化的记忆文本，空字符串表示无记忆
        """
        if query:
            memories = self.recall(query, limit=limit)
        else:
            memories = self._retriever.get_recent(limit=limit)

        return self._retriever.format_for_context(memories)

    def list_memories(self, mem_type: str | None = None) -> list[Memory]:
        """列出所有记忆。"""
        return self._store.list_all(mem_type=mem_type)

    def get_stats(self) -> dict[str, Any]:
        """获取记忆统计。"""
        all_mems = self._store.list_all()
        type_counts = {}
        tier_counts = {}
        for mem in all_mems:
            t = mem.type.value
            type_counts[t] = type_counts.get(t, 0) + 1
            tier = mem.metadata.get("tier", "unknown")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        return {
            "total": self._store.count,
            "by_type": type_counts,
            "by_tier": tier_counts,
        }

    def run_lifecycle(self) -> dict[str, Any]:
        """
        执行一次完整的生命周期管理。

        Returns:
            操作统计
        """
        all_memories = self._store.list_all()
        stats = {"deleted": 0, "tier_updated": 0}

        # 1. 删除过期低价值记忆
        deletable = self._lifecycle.get_deletable(all_memories)
        for mem in deletable:
            self._store.delete(mem.id)
            stats["deleted"] += 1

        # 2. 溢出淘汰
        remaining = self._store.list_all()
        overflow = self._lifecycle.get_overflow_deletable(remaining)
        for mem in overflow:
            self._store.delete(mem.id)
            stats["deleted"] += 1

        # 3. 更新层级
        remaining = self._store.list_all()
        for mem in remaining:
            old_tier = mem.metadata.get("tier")
            new_tier = self._lifecycle.update_memory_tier(mem)
            if old_tier != new_tier:  # MemoryTier 是 str 子类，直接比较
                stats["tier_updated"] += 1

        # 保存更新
        if stats["tier_updated"] > 0:
            self._store._save()

        if stats["deleted"] > 0 or stats["tier_updated"] > 0:
            logger.info(f"生命周期管理: 删除 {stats['deleted']} 条, 更新 {stats['tier_updated']} 条层级")

        return stats

    def clear(self) -> int:
        """清空所有记忆。"""
        count = self._store.clear()
        logger.info(f"已清空 {count} 条记忆")
        return count

    @property
    def store(self) -> MemoryStore:
        return self._store

    @property
    def retriever(self) -> MemoryRetriever:
        return self._retriever

    def __repr__(self) -> str:
        return f"MemoryManager(count={self._store.count}, session={self._session_id})"
