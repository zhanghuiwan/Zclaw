"""
V4 Memory Configuration

Configuration classes for the V4 layered memory architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class V4MemoryConfig:
    """V4 记忆系统配置"""

    # 存储根路径
    storage_path: str = ".Zclaw/memory"

    # L0 Perceptual Buffer 配置
    perceptual_max_turns: int = 1  # RingBuffer 大小

    # L1 Working Memory 配置
    working_memory_max_tokens: int = 30000

    # L2 Episodic Memory 配置
    episodic_max_age_days: int = 90
    episodic_max_entries: int = 10000
    vector_store_enabled: bool = True

    # L3/L4 存储配置
    rules_path: str = ".Zclaw/memory/L4_procedural"

    # 路径解析：相对路径转绝对路径
    def resolve_storage_path(self) -> Path:
        """解析存储根路径为绝对路径"""
        path = Path(self.storage_path)
        if not path.is_absolute() and not str(path).startswith("~"):
            # 相对路径：从项目根目录解析
            src_dir = Path(__file__).resolve().parent
            project_root = src_dir.parent.parent
            return project_root / path
        return path.expanduser().resolve()

    def resolve_rules_path(self) -> Path:
        """解析规则路径为绝对路径"""
        path = Path(self.rules_path)
        if not path.is_absolute() and not str(path).startswith("~"):
            src_dir = Path(__file__).resolve().parent
            project_root = src_dir.parent.parent
            return project_root / path
        return path.expanduser().resolve()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> V4MemoryConfig:
        """从字典创建配置"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "storage_path": self.storage_path,
            "perceptual_max_turns": self.perceptual_max_turns,
            "working_memory_max_tokens": self.working_memory_max_tokens,
            "episodic_max_age_days": self.episodic_max_age_days,
            "episodic_max_entries": self.episodic_max_entries,
            "vector_store_enabled": self.vector_store_enabled,
            "rules_path": self.rules_path,
        }
