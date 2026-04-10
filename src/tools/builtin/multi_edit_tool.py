"""
Multi-Edit 工具

一次调用中对同一文件执行多处替换，确保原子性（全部成功或全部回滚）。
"""

from __future__ import annotations

from pathlib import Path

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class MultiEditTool(BaseTool):
    name = "multi_edit"
    description = (
        "对同一文件执行多处精确替换。所有替换原子执行：全部成功则写入，"
        "任何一个 old_text 未找到则全部回滚，不修改文件。"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="文件路径", required=True),
        ToolParameter(
            name="edits",
            type="string",
            description=(
                "JSON 数组，每项包含 old_text 和 new_text。"
                '例如: [{"old_text": "foo", "new_text": "bar"}, ...]'
            ),
            required=True,
        ),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.CONFIRM, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        edits_json = kwargs["edits"]

        import json
        try:
            edits = json.loads(edits_json) if isinstance(edits_json, str) else edits_json
        except json.JSONDecodeError as e:
            return ToolResult.fail(f"edits 的 JSON 格式无效: {e}")

        if not isinstance(edits, list) or len(edits) == 0:
            return ToolResult.fail("edits 必须是非空的 JSON 数组")

        for i, edit in enumerate(edits):
            if not isinstance(edit, dict):
                return ToolResult.fail(f"编辑 #{i + 1} 必须是包含 old_text 和 new_text 的对象")
            if "old_text" not in edit or "new_text" not in edit:
                return ToolResult.fail(f"编辑 #{i + 1} 缺少 old_text 或 new_text")
            if not isinstance(edit["old_text"], str) or not isinstance(edit["new_text"], str):
                return ToolResult.fail(f"编辑 #{i + 1}: old_text 和 new_text 必须是字符串")

        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")

            original = p.read_text(encoding="utf-8")
            new_content = original

            # 先验证所有编辑（预检）
            for i, edit in enumerate(edits):
                old_text = edit["old_text"]
                if old_text not in new_content:
                    # 对原文检查以便提供更好的错误信息
                    count_in_original = original.count(old_text)
                    if count_in_original == 0:
                        return ToolResult.fail(
                            f"编辑 #{i + 1}: 在文件中未找到 old_text。"
                            f"前 80 个字符: {old_text[:80]}"
                        )
                    else:
                        return ToolResult.fail(
                            f"编辑 #{i + 1}: old_text 在原文中找到 {count_in_original} 处，"
                            f"但之前的编辑已改变了上下文。"
                            f"请尝试调整编辑顺序或使用编辑后的文本。"
                        )

            # 应用所有编辑
            for edit in edits:
                new_content = new_content.replace(edit["old_text"], edit["new_text"], 1)

            # 安全检查：内容未变化时发出警告
            if new_content == original:
                return ToolResult.ok(
                    f"未对 {path} 做任何修改（所有替换结果与原文相同）"
                )

            # 写入文件
            p.write_text(new_content, encoding="utf-8")
            return ToolResult.ok(
                f"成功对 {path} 应用了 {len(edits)} 处编辑\n"
                f"文件大小: {len(original)} -> {len(new_content)} 个字符"
            )

        except Exception as e:
            return ToolResult.fail(str(e))


MULTI_EDIT_TOOL = [MultiEditTool()]
