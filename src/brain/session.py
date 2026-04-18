"""
Session 管理器

管理 Agent 会话的生命周期，包括创建、归档、恢复和休眠。
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """会话状态"""
    ACTIVE = "active"      # 活跃
    IDLE = "idle"          # 空闲
    DORMANT = "dormant"    # 休眠（序列化到磁盘）
    ARCHIVED = "archived"  # 归档（长期存储）


@dataclass
class SessionMessage:
    """会话消息"""
    role: str       # user / assistant / system / tool
    content: str
    tool_call_id: str = ""
    tool_name: str = ""
    timestamp: str = ""


@dataclass
class Session:
    """会话对象"""
    session_id: str
    agent_id: str
    channel: str
    sender_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: str = ""
    last_active: str = ""
    idle_timeout: int = 1800  # 30分钟空闲后休眠
    message_history: list[SessionMessage] = field(default_factory=list)
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_active:
            self.last_active = self.created_at

    def add_message(self, role: str, content: str) -> None:
        """添加消息到历史"""
        self.message_history.append(SessionMessage(
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
        ))
        self.last_active = datetime.now().isoformat()

    def is_idle(self) -> bool:
        """检查会话是否空闲"""
        last_active_time = datetime.fromisoformat(self.last_active)
        elapsed = (datetime.now() - last_active_time).total_seconds()
        return elapsed > self.idle_timeout

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "channel": self.channel,
            "sender_id": self.sender_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "idle_timeout": self.idle_timeout,
            "message_history": [asdict(m) for m in self.message_history],
            "context_snapshot": self.context_snapshot,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """从字典反序列化"""
        data = dict(data)
        if "status" in data and isinstance(data["status"], str):
            data["status"] = SessionStatus(data["status"])
        if "message_history" in data:
            data["message_history"] = [
                SessionMessage(**m) if isinstance(m, dict) else m
                for m in data["message_history"]
            ]
        return cls(**data)


class SessionManager:
    """
    Session 管理器

    负责会话的创建、存储、归档、恢复和休眠。
    """

    def __init__(self, storage_path: str = ".Zclaw/sessions"):
        self._storage_path = Path(storage_path).expanduser().resolve()
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._active_sessions: dict[str, Session] = {}
        logger.info(f"SessionManager 初始化，存储路径: {self._storage_path}")

    def create_session(
        self,
        agent_id: str,
        channel: str,
        sender_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """
        创建新会话。

        Args:
            agent_id: Agent ID
            channel: 渠道
            sender_id: 发送者 ID
            metadata: 元数据

        Returns:
            Session: 新创建的会话
        """
        session_id = f"{agent_id}_{channel}_{sender_id}_{int(time.time())}"
        session = Session(
            session_id=session_id,
            agent_id=agent_id,
            channel=channel,
            sender_id=sender_id,
            metadata=metadata or {},
        )
        self._active_sessions[session_id] = session
        logger.info(f"创建会话: {session_id}")
        return session

    def get_session(self, session_id: str) -> Session | None:
        """获取会话"""
        return self._active_sessions.get(session_id)

    def get_or_create_session(
        self,
        agent_id: str,
        channel: str,
        sender_id: str,
    ) -> Session:
        """
        获取现有会话或创建新会话。

        如果存在相同 channel + sender_id 的活跃会话，则返回该会话。
        """
        # 查找现有会话
        for session in self._active_sessions.values():
            if (session.channel == channel and
                session.sender_id == sender_id and
                session.status in (SessionStatus.ACTIVE, SessionStatus.IDLE)):
                # 更新为新的 agent_id（可能路由规则变了）
                if session.agent_id != agent_id:
                    logger.info(f"会话 {session.session_id} 路由到新 Agent: {agent_id}")
                    session.agent_id = agent_id
                return session

        # 创建新会话
        return self.create_session(agent_id, channel, sender_id)

    def archive_session(self, session_id: str) -> bool:
        """
        将会话归档到磁盘。

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否成功
        """
        session = self._active_sessions.get(session_id)
        if not session:
            logger.warning(f"归档失败，未找到会话: {session_id}")
            return False

        # 保存到磁盘
        file_path = self._storage_path / f"{session_id}.json"
        try:
            data = session.to_dict()
            data["status"] = SessionStatus.ARCHIVED.value
            file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            session.status = SessionStatus.ARCHIVED
            logger.info(f"会话已归档: {session_id} -> {file_path}")
            return True
        except Exception as e:
            logger.error(f"归档会话失败: {e}")
            return False

    def restore_session(self, session_id: str) -> Session | None:
        """
        从磁盘恢复会话。

        Args:
            session_id: 会话 ID

        Returns:
            Session | None: 恢复的会话或 None
        """
        # 检查是否已在内存中
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]

        # 从磁盘加载
        file_path = self._storage_path / f"{session_id}.json"
        if not file_path.exists():
            logger.warning(f"恢复失败，文件不存在: {file_path}")
            return None

        try:
            data = json.loads(file_path.read_text())
            session = Session.from_dict(data)
            session.status = SessionStatus.IDLE
            self._active_sessions[session_id] = session
            logger.info(f"会话已恢复: {session_id}")
            return session
        except Exception as e:
            logger.error(f"恢复会话失败: {e}")
            return None

    def hibernate_session(self, session_id: str) -> bool:
        """
        休眠会话（释放内存但保留在内存中）。

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否成功
        """
        session = self._active_sessions.get(session_id)
        if not session:
            return False

        # 保存上下文快照
        session.context_snapshot = {
            "message_history": [asdict(m) for m in session.message_history],
            "last_active": session.last_active,
        }
        # 释放内存
        session.message_history = []
        session.status = SessionStatus.DORMANT
        logger.info(f"会话已休眠: {session_id}")
        return True

    def wakeup_session(self, session_id: str) -> bool:
        """
        唤醒休眠的会话。

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否成功
        """
        session = self._active_sessions.get(session_id)
        if not session or session.status != SessionStatus.DORMANT:
            return False

        # 恢复消息历史
        if session.context_snapshot.get("message_history"):
            session.message_history = [
                SessionMessage(**m) for m in session.context_snapshot["message_history"]
            ]
        session.last_active = datetime.now().isoformat()
        session.status = SessionStatus.ACTIVE
        logger.info(f"会话已唤醒: {session_id}")
        return True

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]

        file_path = self._storage_path / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"会话已删除: {session_id}")
            return True
        return False

    def list_sessions(self) -> list[dict[str, Any]]:
        """列出所有会话"""
        sessions = []

        # 内存中的会话
        for session in self._active_sessions.values():
            sessions.append({
                "session_id": session.session_id,
                "agent_id": session.agent_id,
                "channel": session.channel,
                "sender_id": session.sender_id,
                "status": session.status.value,
                "created_at": session.created_at,
                "last_active": session.last_active,
                "message_count": len(session.message_history),
            })

        # 磁盘上的会话
        for file_path in self._storage_path.glob("*.json"):
            session_id = file_path.stem
            if session_id not in [s.session_id for s in self._active_sessions.values()]:
                try:
                    data = json.loads(file_path.read_text())
                    sessions.append({
                        "session_id": data.get("session_id", session_id),
                        "agent_id": data.get("agent_id", ""),
                        "channel": data.get("channel", ""),
                        "sender_id": data.get("sender_id", ""),
                        "status": data.get("status", "archived"),
                        "created_at": data.get("created_at", ""),
                        "last_active": data.get("last_active", ""),
                        "message_count": len(data.get("message_history", [])),
                    })
                except Exception:
                    pass

        return sessions

    def cleanup_idle_sessions(self, idle_threshold: int = 1800) -> int:
        """
        清理空闲会话。

        Args:
            idle_threshold: 空闲阈值（秒）

        Returns:
            int: 清理的会话数量
        """
        cleaned = 0
        for session_id, session in list(self._active_sessions.items()):
            if session.status == SessionStatus.ACTIVE and session.is_idle():
                session.status = SessionStatus.IDLE
                cleaned += 1

        if cleaned > 0:
            logger.info(f"清理了 {cleaned} 个空闲会话")

        return cleaned

    def get_active_count(self) -> int:
        """获取活跃会话数量"""
        return sum(
            1 for s in self._active_sessions.values()
            if s.status == SessionStatus.ACTIVE
        )
