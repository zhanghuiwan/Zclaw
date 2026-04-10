"""
Glob 工具

使用 glob 模式匹配查找文件。
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class GlobTool(BaseTool):
    name = "glob"
    description = (
        "使用 glob 模式查找文件。例如: **/*.py 查找所有 Python 文件，"
        "src/**/*.ts 查找 src 下所有 TypeScript 文件。"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="搜索根目录", required=False, default="."),
        ToolParameter(name="pattern", type="string", description="Glob 模式（如 **/*.py, src/**/*.ts）", required=True),
        ToolParameter(name="exclude_hidden", type="boolean", description="是否排除隐藏文件/目录（默认是）", required=False, default=True),
        ToolParameter(name="max_results", type="integer", description="最大结果数", required=False, default=100),
    ]
    metadata = ToolMetadata(category="search", danger_level=DangerLevel.SAFE, timeout_seconds=15)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        pattern = kwargs["pattern"]
        exclude_hidden = kwargs.get("exclude_hidden", True)
        max_results = kwargs.get("max_results", 100)

        root = Path(path).expanduser()
        if not root.exists():
            return ToolResult.fail(f"路径未找到: {path}")
        if not root.is_dir():
            return ToolResult.fail(f"不是目录: {path}")

        try:
            matched = sorted(root.glob(pattern))
        except (ValueError, NotImplementedError) as e:
            return ToolResult.fail(f"无效的 glob 模式: {e}")

        results = []
        for item in matched:
            if len(results) >= max_results:
                break
            if not item.is_file():
                continue
            rel = str(item.relative_to(root))

            # 排除隐藏文件
            if exclude_hidden:
                parts = Path(rel).parts
                if any(part.startswith(".") for part in parts):
                    continue

            results.append(rel)

        if not results:
            return ToolResult.ok(f"没有文件匹配模式: {pattern}")

        total_matched = sum(1 for m in matched if m.is_file())
        header = f"找到 {len(results)} 个文件匹配: {pattern}"
        if len(results) < total_matched:
            header += f"（仅显示前 {max_results} 个）"
        return ToolResult.ok(header + "\n" + "\n".join(results))


GLOB_TOOL = [GlobTool()]
