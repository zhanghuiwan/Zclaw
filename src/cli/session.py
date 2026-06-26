"""
会话管理器

支持保存和恢复对话历史。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime

from src.llm.models import Message

logger = logging.getLogger(__name__)


def deserialize_messages(messages: list[dict | Message]) -> list[Message]:
    """将会话文件中的消息字典恢复为 Message 对象。"""
    result = []
    for msg in messages:
        if isinstance(msg, Message):
            result.append(msg)
        else:
            result.append(Message.from_dict(msg))
    return result


class SessionManager:
    """会话管理器"""

    def __init__(self, sessions_dir: str = ".Zclaw/sessions"):
        # 相对路径解析为项目根目录
        path = Path(sessions_dir)
        if not path.is_absolute() and not str(path).startswith("~"):
            src_dir = Path(__file__).resolve().parent
            project_root = src_dir.parent.parent
            self._dir = project_root / path
        else:
            self._dir = path.expanduser().resolve()
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, messages: list, name: str = "", session_id: str = "") -> str:
        """保存会话到文件，返回会话 ID。"""
        if not session_id:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        if name:
            session_id = f"{name}_{session_id}"

        data = {
            "session_id": session_id,
            "saved_at": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": [
                {
                    "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                    "content": m.content or "",
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in (m.tool_calls or [])
                    ],
                }
                for m in messages
            ],
        }

        path = self._dir / f"{session_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Saved session: {session_id} ({len(messages)} messages) -> {path}")
        return session_id

    def load(self, session_id: str) -> list[dict] | None:
        """加载会话，返回消息列表（dict 格式）。"""
        # 按前缀匹配查找
        matches = list(self._dir.glob(f"*{session_id}*.json"))
        if not matches:
            return None
        # 使用最近匹配
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        path = matches[0]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.info(f"Loaded session: {data.get('session_id')} ({data.get('message_count', 0)} messages)")
            return data.get("messages", [])
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """列出所有保存的会话。"""
        sessions = []
        for path in sorted(self._dir.glob("*.json"), reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data.get("session_id", path.stem),
                    "saved_at": data.get("saved_at", ""),
                    "message_count": data.get("message_count", 0),
                    "file": path.stem,
                })
            except Exception:
                sessions.append({"session_id": path.stem, "saved_at": "?", "message_count": 0, "file": path.stem})
        return sessions

    def delete(self, session_id: str) -> bool:
        """删除一个会话。"""
        matches = list(self._dir.glob(f"*{session_id}*.json"))
        if not matches:
            return False
        matches[0].unlink()
        logger.info(f"Deleted session: {matches[0].stem}")
        return True
