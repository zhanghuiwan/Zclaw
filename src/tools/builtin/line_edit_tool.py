"""
行号级编辑工具

支持按行号范围替换、插入、删除文件内容。
"""

from __future__ import annotations

from pathlib import Path

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class LineEditTool(BaseTool):
    name = "line_edit"
    description = (
        "按行号范围编辑文件内容。支持三种操作模式：\n"
        "- replace: 替换指定行范围为新内容\n"
        "- insert: 在指定行前插入新内容\n"
        "- delete: 删除指定行范围的内容"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="文件路径", required=True),
        ToolParameter(
            name="mode",
            type="string",
            description="操作模式: replace（替换）、insert（插入）、delete（删除）",
            required=True,
            enum=["replace", "insert", "delete"],
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="起始行号（从 1 开始）",
            required=True,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="结束行号（从 1 开始，包含此行）。仅 replace/delete 模式需要",
            required=False,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="新内容（replace/insert 模式需要）",
            required=False,
        ),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.CONFIRM, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        mode = kwargs["mode"]
        start_line = kwargs["start_line"]
        end_line = kwargs.get("end_line", start_line)
        content = kwargs.get("content", "")

        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")
            if not p.is_file():
                return ToolResult.fail(f"不是文件: {path}")

            with open(p, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # 转换为 0-based 索引
            start_idx = start_line - 1
            end_idx = end_line  # slice 是 exclusive，所以不需要 -1

            # 边界检查
            if start_line < 1 or start_idx > total_lines:
                return ToolResult.fail(
                    f"起始行号 {start_line} 超出范围（文件共 {total_lines} 行）"
                )
            if mode in ("replace", "delete") and end_line > total_lines:
                return ToolResult.fail(
                    f"结束行号 {end_line} 超出范围（文件共 {total_lines} 行）"
                )
            if mode in ("replace", "delete") and end_line < start_line:
                return ToolResult.fail(
                    f"结束行号 {end_line} 小于起始行号 {start_line}"
                )

            # 生成 diff 预览
            old_lines = lines[start_idx:end_idx]
            old_text = "".join(old_lines)

            if mode == "replace":
                new_lines = lines[:start_idx] + [content + "\n" if not content.endswith("\n") else content] + lines[end_idx:]
                action = f"替换第 {start_line}-{end_line} 行"
            elif mode == "insert":
                insert_text = content + "\n" if not content.endswith("\n") else content
                new_lines = lines[:start_idx] + [insert_text] + lines[start_idx:]
                action = f"在第 {start_line} 行前插入"
                old_text = ""  # insert 没有旧文本
            elif mode == "delete":
                new_lines = lines[:start_idx] + lines[end_idx:]
                action = f"删除第 {start_line}-{end_line} 行"
            else:
                return ToolResult.fail(f"不支持的模式: {mode}")

            # 写入文件
            with open(p, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            # 生成摘要
            new_count = len(new_lines)
            changed = len(new_lines) - total_lines

            result_parts = [
                f"✅ 成功 {action}",
                f"文件: {path}",
                f"行数变化: {total_lines} → {new_count} ({changed:+d})",
            ]

            return ToolResult.ok("\n".join(result_parts))

        except Exception as e:
            return ToolResult.fail(str(e))


class LineReadTool(BaseTool):
    name = "line_read"
    description = "按行号范围读取文件内容。支持显示行号。"
    parameters = [
        ToolParameter(name="path", type="string", description="文件路径", required=True),
        ToolParameter(
            name="start_line",
            type="integer",
            description="起始行号（从 1 开始，默认为 1）",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="结束行号（从 1 开始，包含此行，默认到文件末尾）",
            required=False,
        ),
        ToolParameter(
            name="show_line_numbers",
            type="boolean",
            description="是否显示行号（默认为 true）",
            required=False,
            default=True,
        ),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        start_line = kwargs.get("start_line", 1)
        end_line = kwargs.get("end_line")
        show_line_numbers = kwargs.get("show_line_numbers", True)

        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")
            if not p.is_file():
                return ToolResult.fail(f"不是文件: {path}")

            with open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total = len(lines)

            # 边界检查
            if start_line < 1 or start_line > total:
                return ToolResult.fail(
                    f"起始行号 {start_line} 超出范围（文件共 {total} 行）"
                )

            actual_end = min(end_line or total, total)
            selected = lines[start_line - 1:actual_end]

            # 格式化输出
            if show_line_numbers:
                # 计算行号最大宽度
                max_width = len(str(actual_end))
                formatted = []
                for i, line in enumerate(selected, start=start_line):
                    line_text = line.rstrip("\n")
                    formatted.append(f"{i:>{max_width}} | {line_text}")
                content = "\n".join(formatted)
            else:
                content = "".join(selected)

            header = f"文件: {path}（共 {total} 行）\n"
            if start_line > 1 or actual_end < total:
                header += f"显示第 {start_line}-{actual_end} 行\n"

            return ToolResult.ok(header + content)

        except Exception as e:
            return ToolResult.fail(str(e))


LINE_EDIT_TOOLS = [LineEditTool(), LineReadTool()]
