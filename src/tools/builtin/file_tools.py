"""
文件操作工具

提供文件读取、写入、编辑功能。
"""

from __future__ import annotations

import os
from pathlib import Path

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class FileReadTool(BaseTool):
    name = "file_read"
    description = "读取文件内容。支持大文件的分段读取。"
    parameters = [
        ToolParameter(name="path", type="string", description="文件路径", required=True),
        ToolParameter(name="offset", type="integer", description="起始行号（从 0 开始）", required=False, default=0),
        ToolParameter(name="limit", type="integer", description="读取行数", required=False, default=1000),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 1000)
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")
            if not p.is_file():
                return ToolResult.fail(f"不是文件: {path}")
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            total = len(lines)
            selected = lines[offset:offset + limit]
            content = "".join(selected)
            header = f"文件: {path}（共 {total} 行）\n"
            if offset > 0 or offset + limit < total:
                header += f"显示第 {offset + 1}-{min(offset + limit, total)} 行，共 {total} 行\n"
            return ToolResult.ok(header + content)
        except Exception as e:
            return ToolResult.fail(str(e))


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "创建新文件或完全覆盖已有文件的内容。"
    parameters = [
        ToolParameter(name="path", type="string", description="文件路径", required=True),
        ToolParameter(name="content", type="string", description="要写入的完整内容", required=True),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.CONFIRM, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        content = kwargs["content"]
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult.ok(f"成功写入 {len(content)} 个字符到 {path}")
        except Exception as e:
            return ToolResult.fail(str(e))


class FileEditTool(BaseTool):
    name = "file_edit"
    description = "精确修改文件的部分内容（推荐用于局部修改）。替换文件中匹配的旧文本为新文本。"
    parameters = [
        ToolParameter(name="path", type="string", description="文件路径", required=True),
        ToolParameter(name="old_text", type="string", description="要被替换的旧文本", required=True),
        ToolParameter(name="new_text", type="string", description="替换后的新文本", required=True),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.CONFIRM, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        old_text = kwargs["old_text"]
        new_text = kwargs["new_text"]
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            if old_text not in content:
                return ToolResult.fail(f"在 {path} 中未找到旧文本")
            new_content = content.replace(old_text, new_text, 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write(new_content)
            return ToolResult.ok(f"成功编辑 {path}")
        except Exception as e:
            return ToolResult.fail(str(e))


FILE_TOOLS = [FileReadTool(), FileWriteTool(), FileEditTool()]
