"""
Grep 工具

使用正则表达式搜索文件内容，支持行号、上下文行、glob 过滤。
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class GrepTool(BaseTool):
    name = "grep"
    description = (
        "在文件中搜索匹配正则表达式的内容。"
        "支持行号显示、上下文行、include/exclude glob 过滤。"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="搜索根目录", required=False, default="."),
        ToolParameter(name="pattern", type="string", description="正则表达式", required=True),
        ToolParameter(name="include", type="string", description="只搜索匹配此 glob 的文件（如 *.py）", required=False, default=""),
        ToolParameter(name="exclude", type="string", description="排除匹配此 glob 的文件（如 *.min.js）", required=False, default=""),
        ToolParameter(name="context", type="integer", description="显示匹配行前后各 N 行上下文", required=False, default=0),
        ToolParameter(name="max_results", type="integer", description="最大匹配数", required=False, default=50),
    ]
    metadata = ToolMetadata(category="search", danger_level=DangerLevel.SAFE, timeout_seconds=30)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        pattern = kwargs["pattern"]
        include = kwargs.get("include", "")
        exclude = kwargs.get("exclude", "")
        context = kwargs.get("context", 0)
        max_results = kwargs.get("max_results", 50)

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return ToolResult.fail(f"无效的正则表达式: {e}")

        root = Path(path).expanduser()
        if not root.exists():
            return ToolResult.fail(f"路径未找到: {path}")
        if not root.is_dir():
            return ToolResult.fail(f"不是目录: {path}")

        results = []
        try:
            for item in root.rglob("*"):
                if len(results) >= max_results:
                    break
                if not item.is_file():
                    continue
                if item.stat().st_size > 1_000_000:
                    continue

                rel = item.relative_to(root)
                rel_str = str(rel)

                # include 过滤
                if include and not fnmatch.fnmatch(rel_str, include) and not fnmatch.fnmatch(item.name, include):
                    continue
                # exclude 过滤
                if exclude and (fnmatch.fnmatch(rel_str, exclude) or fnmatch.fnmatch(item.name, exclude)):
                    continue

                try:
                    lines = item.read_text(encoding="utf-8", errors="replace").splitlines()
                except Exception:
                    continue

                match_indices = []
                for i, line in enumerate(lines):
                    if regex.search(line):
                        match_indices.append(i)
                        if len(results) + len(match_indices) >= max_results:
                            break

                for idx in match_indices:
                    if len(results) >= max_results:
                        break
                    line_no = idx + 1
                    line_content = lines[idx].rstrip()

                    # 构建上下文行
                    context_lines = []
                    start = max(0, idx - context)
                    end = min(len(lines), idx + context + 1)
                    for ci in range(start, end):
                        prefix = "  " if ci != idx else ">>"
                        context_lines.append(f"  {prefix} {ci + 1}: {lines[ci].rstrip()}")

                    if context > 0:
                        results.append(f"{rel_str}:{line_no}\n" + "\n".join(context_lines))
                    else:
                        results.append(f"{rel_str}:{line_no}: {line_content}")

        except Exception as e:
            return ToolResult.fail(str(e))

        if not results:
            return ToolResult.ok(f"未找到与模式匹配的内容: {pattern}")

        header = f"找到 {len(results)} 个匹配项: {pattern}"
        if include:
            header += f"（包含: {include}）"
        if exclude:
            header += f"（排除: {exclude}）"
        return ToolResult.ok(header + "\n" + "\n".join(results))


GREP_TOOL = [GrepTool()]
