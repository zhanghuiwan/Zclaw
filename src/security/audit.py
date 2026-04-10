"""
审计日志

记录所有工具调用的完整信息，用于审计和调试。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """单条审计记录"""
    timestamp: str
    session_id: str = ""
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    danger_level: str = ""
    permission_decision: str = ""
    permission_auto: bool = False
    execution_success: bool | None = None
    execution_error: str | None = None
    duration_ms: int = 0
    user_message_context: str = ""


class AuditLogger:
    """
    审计日志记录器。

    将工具调用的完整信息追加写入 JSONL 格式的日志文件。
    """

    def __init__(
        self,
        enabled: bool = True,
        log_dir: str = ".Zclaw/audit/",
        session_id: str = "",
    ):
        self._enabled = enabled
        # 相对路径解析为项目根目录
        path = Path(log_dir)
        if not path.is_absolute() and not str(path).startswith("~"):
            src_dir = Path(__file__).resolve().parent
            project_root = src_dir.parent.parent
            self._log_dir = project_root / path
        else:
            self._log_dir = path.expanduser().resolve()
        self._session_id = session_id

        if self._enabled:
            try:
                self._log_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"无法创建审计日志目录: {e}")
                self._enabled = False

        self._stats = {
            "total_entries": 0,
            "allowed": 0,
            "denied": 0,
            "failed": 0,
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def log_file(self) -> Path:
        if not self._session_id:
            return self._log_dir / "audit.jsonl"
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self._log_dir / f"{date_str}_{self._session_id[:8]}.jsonl"

    def log(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        danger_level: str = "",
        permission_decision: str = "",
        permission_auto: bool = False,
        execution_success: bool | None = None,
        execution_error: str | None = None,
        duration_ms: int = 0,
        user_message_context: str = "",
    ) -> None:
        if not self._enabled:
            return

        self._stats["total_entries"] += 1
        if permission_decision == "allow":
            self._stats["allowed"] += 1
        elif permission_decision == "deny":
            self._stats["denied"] += 1
        if execution_success is False:
            self._stats["failed"] += 1

        safe_args = self._redact_arguments(arguments)
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            session_id=self._session_id,
            tool_name=tool_name,
            arguments=safe_args,
            danger_level=danger_level,
            permission_decision=permission_decision,
            permission_auto=permission_auto,
            execution_success=execution_success,
            execution_error=execution_error,
            duration_ms=duration_ms,
            user_message_context=user_message_context[:200] if user_message_context else "",
        )

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning(f"写入审计日志失败: {e}")

    def _redact_arguments(self, args: dict[str, Any]) -> dict[str, Any]:
        sensitive_keys = {"password", "passwd", "secret", "token", "api_key", "apikey", "private_key"}
        safe = {}
        for key, value in args.items():
            if any(sk in key.lower() for sk in sensitive_keys):
                safe[key] = "***REDACTED***"
            elif isinstance(value, str) and len(value) > 500:
                safe[key] = value[:500] + f"...（已截断，共 {len(value)} 个字符）"
            else:
                safe[key] = value
        return safe

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def read_entries(self, limit: int = 100) -> list[dict]:
        if not self.log_file.exists():
            return []
        entries = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                    if len(entries) >= limit:
                        break
        except OSError:
            return []
        return list(reversed(entries))

    def __repr__(self) -> str:
        return (
            f"AuditLogger(enabled={self._enabled}, "
            f"entries={self._stats['total_entries']})"
        )
