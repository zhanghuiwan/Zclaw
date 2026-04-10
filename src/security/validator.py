"""
输入/输出安全校验器

提供工具参数和输出的安全检查。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PATH_TRAVERSAL_RE = re.compile(r'(\.\./|\.\.\\)')

_SENSITIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(?:api[_-]?key|apikey|secret|token|password|passwd)\s*[=:]\s*["\']?[\w\-]{20,}', re.IGNORECASE), "***REDACTED***"),
    (re.compile(r'Bearer\s+[\w\-\.]{20,}', re.IGNORECASE), "Bearer ***REDACTED***"),
    (re.compile(r'(?:AKIA|ASIA)[A-Z0-9]{16}'), "***AWS_KEY***"),
]


class InputValidator:
    """输入安全校验器。"""

    def __init__(self):
        pass

    def validate_path(self, path_str: str, allow_absolute: bool = True) -> tuple[bool, str]:
        if not path_str:
            return False, "路径为空"
        if _PATH_TRAVERSAL_RE.search(path_str):
            return False, f"检测到路径穿越: {path_str}"
        try:
            resolved = Path(path_str).expanduser().resolve()
        except (OSError, ValueError) as e:
            return False, f"无效的路径: {e}"
        if not allow_absolute and resolved.is_absolute() and not path_str.startswith("~"):
            return False, f"不允许使用绝对路径: {resolved}"
        return True, ""

    def validate_command(self, command: str) -> tuple[bool, str]:
        if not command or not command.strip():
            return False, "命令为空"
        stripped = command.strip()
        if ";" in stripped and not stripped.startswith("export "):
            parts = stripped.split(";")
            if len(parts) > 3:
                return False, f"链式命令过多（{len(parts)} 个），可能存在注入风险"
        return True, ""

    def validate_length(self, value: str, max_length: int, name: str = "value") -> tuple[bool, str]:
        if len(value) > max_length:
            return False, f"{name} 超过最大长度（{len(value)} > {max_length}）"
        return True, ""

    def validate_file_size(
        self, content: str, max_bytes: int = 1_000_000, name: str = "content"
    ) -> tuple[bool, str]:
        size = len(content.encode('utf-8'))
        if size > max_bytes:
            return False, f"{name} 过大（{size:,} 字节 > {max_bytes:,} 字节限制）"
        return True, ""


class OutputSanitizer:
    """输出安全处理器。"""

    def __init__(self):
        pass

    def redact_sensitive(self, text: str) -> str:
        result = text
        for pattern, replacement in _SENSITIVE_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    def clean_control_chars(self, text: str) -> str:
        result = []
        for ch in text:
            if ch in '\n\r\t':
                result.append(ch)
            elif ord(ch) < 32:
                result.append(' ')
            else:
                result.append(ch)
        return ''.join(result)

    def truncate(self, text: str, max_length: int = 50_000) -> str:
        if len(text) <= max_length:
            return text
        return text[:max_length] + f"\n\n[输出已截断，最大 {max_length:,} 个字符]"

    def sanitize(self, text: str) -> str:
        text = self.clean_control_chars(text)
        text = self.redact_sensitive(text)
        text = self.truncate(text)
        return text
