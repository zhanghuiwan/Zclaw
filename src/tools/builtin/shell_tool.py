"""
Shell 工具

提供命令行执行功能。
"""

from __future__ import annotations

import re
import shlex

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult
from src.sandbox.runner import CommandRunner


class ShellTool(BaseTool):
    name = "shell"
    description = "执行 Shell 命令。用于运行测试、构建、查看信息等操作。"
    parameters = [
        ToolParameter(name="command", type="string", description="要执行的 Shell 命令", required=True),
        ToolParameter(name="timeout", type="integer", description="超时秒数", required=False, default=120),
        ToolParameter(name="workdir", type="string", description="工作目录", required=False, default="."),
    ]
    metadata = ToolMetadata(category="system", danger_level=DangerLevel.CONFIRM, timeout_seconds=120)

    # 危险命令关键词
    _DANGEROUS_PATTERNS = [
        r"\brm\s+-rf\s+/", r"\brm\s+-rf\s+\*", r"\bsudo\s+", r"\bmkfs\b",
        r"\bdd\s+if=", r":\(\)\{\s*:\|", r"\bchmod\s+777\s+/", r"\bshutdown\b",
        r"\breboot\b", r"\binit\s+0\b",
    ]

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs["command"]
        timeout = kwargs.get("timeout", 120)
        workdir = kwargs.get("workdir", ".")

        # 危险等级检测（仅提示，不阻止，由权限系统决定）
        danger = self._detect_danger(command)
        if danger:
            self.metadata = ToolMetadata(
                category="system",
                danger_level=DangerLevel.DANGEROUS,
                timeout_seconds=timeout,
            )

        runner = CommandRunner(timeout=timeout, workdir=workdir)
        result = runner.run(command)
        return result

    def _detect_danger(self, command: str) -> str | None:
        """检测命令是否包含危险模式。"""
        for pattern in self._DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return f"匹配到危险模式: {pattern}"
        return None


SHELL_TOOLS = [ShellTool()]
