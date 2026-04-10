"""
记忆数据类型

定义不同类型的记忆：事实、事件、偏好。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryType(str, Enum):
    """记忆类型"""
    FACT = "fact"               # 事实性知识（如：项目使用 Python 3.12）
    EPISODE = "episode"         # 事件记忆（如：用户让我修复了 bug X）
    PREFERENCE = "preference"   # 用户偏好（如：用户喜欢用 TypeScript）
    SKILL = "skill"             # Agent 掌握的技能/模式（如：学会了使用某 API）


@dataclass
class Memory:
    """单条记忆"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: MemoryType = MemoryType.FACT
    content: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    last_accessed: str = ""
    importance: float = 0.5  # 0.0 ~ 1.0

    def touch(self) -> None:
        """更新访问时间和计数。"""
        self.access_count += 1
        self.last_accessed = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        data = dict(data)
        if "type" in data and isinstance(data["type"], str):
            data["type"] = MemoryType(data["type"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def __repr__(self) -> str:
        return f"Memory(id={self.id}, type={self.type.value}, content={self.content[:40]}...)"
