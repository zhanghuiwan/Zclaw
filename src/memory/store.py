"""
记忆持久化存储

使用 JSON 文件存储记忆数据。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.memory.types import Memory

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    记忆持久化存储。

    使用 JSON 文件存储所有记忆，支持 CRUD 操作。
    """

    def __init__(self, storage_path: str = "~/.Zclaw/memory"):
        # 如果是相对路径，解析为相对于项目根目录（src/ 的上级目录）
        path = Path(storage_path)
        if not path.is_absolute() and not str(path).startswith("~"):
            # 找到项目根目录（src/memory/store.py → src/ → 项目根目录）
            src_dir = Path(__file__).resolve().parent
            project_root = src_dir.parent.parent
            self._dir = project_root / path
        else:
            self._dir = path.expanduser().resolve()
        self._path = self._dir / "memories.json"
        self._memories: dict[str, Memory] = {}
        self._load()

    def _load(self) -> None:
        """从磁盘加载记忆。"""
        self._memories.clear()
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    mem = Memory.from_dict(item)
                    self._memories[mem.id] = mem
            logger.debug(f"从 {self._path} 加载了 {len(self._memories)} 条记忆")
        except Exception as e:
            logger.error(f"加载记忆失败: {e}")

    def _save(self) -> None:
        """保存记忆到磁盘。"""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = [m.to_dict() for m in self._memories.values()]
            self._path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")

    def add(self, memory: Memory) -> Memory:
        """添加一条记忆。"""
        self._memories[memory.id] = memory
        self._save()
        return memory

    def get(self, memory_id: str) -> Memory | None:
        """获取一条记忆。"""
        return self._memories.get(memory_id)

    def update(self, memory_id: str, **updates) -> Memory | None:
        """更新记忆字段。"""
        mem = self._memories.get(memory_id)
        if mem is None:
            return None
        for key, value in updates.items():
            if hasattr(mem, key):
                setattr(mem, key, value)
        mem.touch()
        self._save()
        return mem

    def delete(self, memory_id: str) -> bool:
        """删除一条记忆。"""
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save()
            return True
        return False

    def list_all(self, mem_type: str | None = None, tag: str | None = None) -> list[Memory]:
        """列出记忆，可按类型和标签过滤。"""
        results = list(self._memories.values())
        if mem_type:
            results = [m for m in results if m.type.value == mem_type]
        if tag:
            results = [m for m in results if tag in m.tags]
        return sorted(results, key=lambda m: m.created_at, reverse=True)

    def search(self, query: str, limit: int = 20) -> list[Memory]:
        """简单关键词搜索。"""
        query_lower = query.lower()
        scored = []
        for mem in self._memories.values():
            score = 0.0
            if query_lower in mem.content.lower():
                score += 1.0
            if query_lower in " ".join(mem.tags).lower():
                score += 0.5
            if query_lower in mem.type.value:
                score += 0.3
            if score > 0:
                scored.append((mem, score))
                mem.touch()

        scored.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in scored[:limit]]

    @property
    def count(self) -> int:
        return len(self._memories)

    def clear(self) -> int:
        count = len(self._memories)
        self._memories.clear()
        self._save()
        return count

    def __repr__(self) -> str:
        return f"MemoryStore(count={self.count}, path={self._path})"
