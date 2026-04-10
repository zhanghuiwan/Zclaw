"""
搜索工具

提供目录浏览和文件搜索功能。
"""

from __future__ import annotations

import os
from pathlib import Path

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class DirectoryTool(BaseTool):
    name = "directory"
    description = "浏览目录结构，列出指定路径下的文件和子目录。"
    parameters = [
        ToolParameter(name="path", type="string", description="目录路径（默认当前目录）", required=False, default="."),
    ]
    metadata = ToolMetadata(category="search", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"目录未找到: {path}")
            if not p.is_dir():
                return ToolResult.fail(f"不是目录: {path}")
            entries = []
            for item in sorted(p.iterdir()):
                if item.name.startswith("."):
                    continue
                prefix = "📁 " if item.is_dir() else "📄 "
                entries.append(f"{prefix}{item.name}")
            if not entries:
                return ToolResult.ok("（空目录）")
            return ToolResult.ok("\n".join(entries))
        except Exception as e:
            return ToolResult.fail(str(e))


class FileSearchTool(BaseTool):
    name = "file_search"
    description = "按文件名或内容搜索文件。"
    parameters = [
        ToolParameter(name="path", type="string", description="搜索根目录", required=False, default="."),
        ToolParameter(name="pattern", type="string", description="搜索模式（文件名或内容关键词）", required=True),
        ToolParameter(name="search_content", type="boolean", description="是否搜索文件内容（默认只搜索文件名）", required=False, default=False),
        ToolParameter(name="max_results", type="integer", description="最大结果数", required=False, default=20),
    ]
    metadata = ToolMetadata(category="search", danger_level=DangerLevel.SAFE, timeout_seconds=30)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        pattern = kwargs["pattern"]
        search_content = kwargs.get("search_content", False)
        max_results = kwargs.get("max_results", 20)
        try:
            root = Path(path).expanduser()
            if not root.exists():
                return ToolResult.fail(f"路径未找到: {path}")
            results = []
            if search_content:
                for item in root.rglob("*"):
                    if len(results) >= max_results:
                        break
                    if item.is_file() and item.stat().st_size < 1_000_000:
                        try:
                            text = item.read_text(encoding="utf-8", errors="replace")
                            for i, line in enumerate(text.splitlines(), 1):
                                if pattern.lower() in line.lower():
                                    results.append(f"{item}:{i}: {line.strip()[:200]}")
                                    if len(results) >= max_results:
                                        break
                        except Exception:
                            continue
            else:
                for item in root.rglob("*"):
                    if len(results) >= max_results:
                        break
                    if pattern.lower() in item.name.lower():
                        results.append(str(item))
            if not results:
                return ToolResult.ok(f"未找到与 '{pattern}' 匹配的结果")
            return ToolResult.ok("\n".join(results))
        except Exception as e:
            return ToolResult.fail(str(e))


SEARCH_TOOLS = [DirectoryTool(), FileSearchTool()]
