"""
记忆模块 V4

提供跨会话的持久化记忆系统，基于分层架构。
L0: Perceptual Buffer (RingBuffer)
L1: Working Memory (会话快照)
L2: Episodic Memory (不可变档案, SQLite-VSS)
L3: Semantic Memory (当前状态, JSON)
L4: Procedural Memory (YAML规则)
"""

from src.memory.config import V4MemoryConfig
from src.memory.coordinator import MemoryCoordinator
from src.memory.layers import (
    PerceptualBuffer,
    PerceptualEntry,
    WorkingMemory,
    SessionSnapshot,
    EpisodicMemory,
    EpisodicEntry,
    SemanticMemory,
    UserProfile,
    ProjectProfile,
    ProceduralMemory,
)

__all__ = [
    "V4MemoryConfig",
    "MemoryCoordinator",
    # Layers
    "PerceptualBuffer",
    "PerceptualEntry",
    "WorkingMemory",
    "SessionSnapshot",
    "EpisodicMemory",
    "EpisodicEntry",
    "SemanticMemory",
    "UserProfile",
    "ProjectProfile",
    "ProceduralMemory",
]
