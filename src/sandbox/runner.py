"""
命令运行器

在受控环境中执行 Shell 命令。
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import time
from pathlib import Path

from src.tools.base import ToolResult

logger = logging.getLogger(__name__)

# ANSI 转义码清理
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


class CommandRunner:
    """
    命令运行器。

    支持：
    - 超时控制
    - 输出截断
    - 工作目录
    - ANSI 清理
    """

    def __init__(
        self,
        timeout: int = 120,
        workdir: str = ".",
        max_output_chars: int = 100_000,
    ):
        self._timeout = timeout
        self._workdir = Path(workdir).expanduser().resolve()
        self._max_output_chars = max_output_chars

    def run(self, command: str) -> ToolResult:
        """同步执行命令。"""
        try:
            cwd = str(self._workdir) if self._workdir.exists() else None
            start = time.monotonic()
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=cwd,
                env={**os.environ},
            )
            duration_ms = int((time.monotonic() - start) * 1000)

            stdout = self._clean_output(result.stdout)
            stderr = self._clean_output(result.stderr)

            output_parts = []
            if stdout:
                output_parts.append(stdout)
            if stderr:
                output_parts.append(f"[stderr]\n{stderr}")

            content = "\n".join(output_parts) if output_parts else "(无输出)"

            if result.returncode != 0:
                return ToolResult.fail(
                    error=f"命令以退出码 {result.returncode} 结束",
                    content=content,
                    duration_ms=duration_ms,
                )

            return ToolResult.ok(content, duration_ms=duration_ms)

        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                error=f"命令超时 ({self._timeout}秒)",
                content="(进程已终止)",
                timed_out=True,
            )
        except Exception as e:
            return ToolResult.fail(str(e))

    def _clean_output(self, text: str) -> str:
        """清理输出文本。"""
        text = _ANSI_RE.sub("", text)
        if len(text) > self._max_output_chars:
            text = text[:self._max_output_chars] + f"\n... (在 {self._max_output_chars} 字符处截断)"
        return text.strip()
