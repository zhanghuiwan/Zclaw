"""
Diff 预览工具

提供文件内容比较、变更预览、回滚等功能。
"""

from __future__ import annotations

import difflib
import hashlib
from pathlib import Path
from datetime import datetime

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class DiffTool(BaseTool):
    name = "diff"
    description = (
        "比较两个文本或文件之间的差异。支持以下比较模式：\n"
        "- file: 比较两个文件之间的差异\n"
        "- text: 比较两段文本之间的差异\n"
        "- snapshot: 比较文件当前内容与之前的快照"
    )
    parameters = [
        ToolParameter(
            name="mode",
            type="string",
            description="比较模式: file（比较文件）、text（比较文本）、snapshot（与快照比较）",
            required=True,
            enum=["file", "text", "snapshot"],
        ),
        ToolParameter(
            name="path",
            type="string",
            description="文件路径（file/snapshot 模式需要）",
            required=False,
        ),
        ToolParameter(
            name="path2",
            type="string",
            description="第二个文件路径（仅 file 模式需要）",
            required=False,
        ),
        ToolParameter(
            name="old_text",
            type="string",
            description="旧文本（text 模式需要）",
            required=False,
        ),
        ToolParameter(
            name="new_text",
            type="string",
            description="新文本（text 模式需要）",
            required=False,
        ),
        ToolParameter(
            name="context_lines",
            type="integer",
            description="显示差异的上下文行数（默认 3）",
            required=False,
            default=3,
        ),
        ToolParameter(
            name="format",
            type="string",
            description="输出格式: unified（统一格式）、side_by_side（并排格式，适合终端）",
            required=False,
            default="unified",
            enum=["unified", "side_by_side"],
        ),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    # 快照存储目录
    _SNAPSHOT_DIR = None

    @classmethod
    def _get_snapshot_dir(cls) -> Path:
        if cls._SNAPSHOT_DIR is None:
            from src.config.settings import _get_zclaw_dir
            cls._SNAPSHOT_DIR = _get_zclaw_dir() / "snapshots"
            cls._SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        return cls._SNAPSHOT_DIR

    async def execute(self, **kwargs) -> ToolResult:
        mode = kwargs["mode"]
        context_lines = kwargs.get("context_lines", 3)
        output_format = kwargs.get("format", "unified")

        try:
            if mode == "file":
                return self._diff_files(kwargs, context_lines, output_format)
            elif mode == "text":
                return self._diff_text(kwargs, context_lines, output_format)
            elif mode == "snapshot":
                return self._diff_snapshot(kwargs, context_lines, output_format)
            else:
                return ToolResult.fail(f"不支持的模式: {mode}")
        except Exception as e:
            return ToolResult.fail(str(e))

    def _diff_files(self, kwargs: dict, context_lines: int, output_format: str) -> ToolResult:
        path1 = kwargs.get("path")
        path2 = kwargs.get("path2")

        if not path1 or not path2:
            return ToolResult.fail("file 模式需要 path 和 path2 参数")

        p1 = Path(path1).expanduser()
        p2 = Path(path2).expanduser()

        if not p1.exists():
            return ToolResult.fail(f"文件未找到: {path1}")
        if not p2.exists():
            return ToolResult.fail(f"文件未找到: {path2}")

        with open(p1, "r", encoding="utf-8", errors="replace") as f:
            old_lines = f.readlines()
        with open(p2, "r", encoding="utf-8", errors="replace") as f:
            new_lines = f.readlines()

        diff_text = self._generate_diff(
            old_lines, new_lines,
            from_file=str(p1),
            to_file=str(p2),
            context_lines=context_lines,
            output_format=output_format,
        )

        # 统计变更
        stats = self._diff_stats(old_lines, new_lines)

        return ToolResult.ok(
            f"比较: {path1} vs {path2}\n"
            f"{stats}\n"
            f"{'=' * 60}\n"
            f"{diff_text}"
        )

    def _diff_text(self, kwargs: dict, context_lines: int, output_format: str) -> ToolResult:
        old_text = kwargs.get("old_text", "")
        new_text = kwargs.get("new_text", "")

        if not old_text and not new_text:
            return ToolResult.fail("text 模式需要 old_text 和/或 new_text 参数")

        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)

        diff_text = self._generate_diff(
            old_lines, new_lines,
            from_file="旧文本",
            to_file="新文本",
            context_lines=context_lines,
            output_format=output_format,
        )

        stats = self._diff_stats(old_lines, new_lines)

        return ToolResult.ok(
            f"文本比较\n{stats}\n{'=' * 60}\n{diff_text}"
        )

    def _diff_snapshot(self, kwargs: dict, context_lines: int, output_format: str) -> ToolResult:
        path = kwargs.get("path")
        if not path:
            return ToolResult.fail("snapshot 模式需要 path 参数")

        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult.fail(f"文件未找到: {path}")

        # 查找最新的快照
        snapshot_dir = self._get_snapshot_dir()
        file_hash = hashlib.md5(str(p.resolve()).encode()).hexdigest()[:12]
        snapshots = sorted(snapshot_dir.glob(f"{file_hash}_*.snapshot"), reverse=True)

        if not snapshots:
            return ToolResult.fail(f"未找到 {path} 的快照记录。请先使用 file_write 或 file_edit 操作该文件。")

        # 使用最新的快照
        latest_snapshot = snapshots[0]
        with open(latest_snapshot, "r", encoding="utf-8", errors="replace") as f:
            old_lines = f.readlines()

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            new_lines = f.readlines()

        snapshot_time = latest_snapshot.stem.split("_", 1)[1].replace("_", ":")

        diff_text = self._generate_diff(
            old_lines, new_lines,
            from_file=f"快照 ({snapshot_time})",
            to_file=f"当前 ({path})",
            context_lines=context_lines,
            output_format=output_format,
        )

        stats = self._diff_stats(old_lines, new_lines)

        return ToolResult.ok(
            f"快照比较: {path}\n"
            f"快照时间: {snapshot_time}\n"
            f"{stats}\n"
            f"{'=' * 60}\n"
            f"{diff_text}"
        )

    def _generate_diff(
        self,
        old_lines: list[str],
        new_lines: list[str],
        from_file: str = "",
        to_file: str = "",
        context_lines: int = 3,
        output_format: str = "unified",
    ) -> str:
        if output_format == "side_by_side":
            return self._side_by_side_diff(old_lines, new_lines, from_file, to_file)

        # Unified diff
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=from_file,
            tofile=to_file,
            n=context_lines,
        )
        return "".join(diff)

    def _side_by_side_diff(
        self,
        old_lines: list[str],
        new_lines: list[str],
        from_file: str,
        to_file: str,
    ) -> str:
        """生成并排对比格式的 diff。"""
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        max_line_len = 60

        left_lines = []
        right_lines = []

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i1, i2):
                    left_lines.append(f"  {old_lines[k].rstrip()[:max_line_len]}")
                    right_lines.append(f"  {new_lines[j1 + (k - i1)].rstrip()[:max_line_len]}")
            elif tag == "replace":
                max_len = max(i2 - i1, j2 - j1)
                for k in range(max_len):
                    old_idx = i1 + k if k < (i2 - i1) else None
                    new_idx = j1 + k if k < (j2 - j1) else None
                    left = f"- {old_lines[old_idx].rstrip()[:max_line_len]}" if old_idx is not None else ""
                    right = f"+ {new_lines[new_idx].rstrip()[:max_line_len]}" if new_idx is not None else ""
                    left_lines.append(left)
                    right_lines.append(right)
            elif tag == "delete":
                for k in range(i1, i2):
                    left_lines.append(f"- {old_lines[k].rstrip()[:max_line_len]}")
                    right_lines.append("")
            elif tag == "insert":
                for k in range(j1, j2):
                    left_lines.append("")
                    right_lines.append(f"+ {new_lines[k].rstrip()[:max_line_len]}")

        # 格式化并排输出
        header = f"{'─' * max_line_len} {from_file}  │  {to_file} {'─' * max_line_len}\n"
        separator = f"{'─' * max_line_len} ├────────────────────────────────┤ {'─' * max_line_len}\n"

        max_left_width = max((len(l) for l in left_lines), default=0)
        max_right_width = max((len(r) for r in right_lines), default=0)

        lines = [header]
        for left, right in zip(left_lines, right_lines):
            left_padded = left.ljust(max_left_width)
            right_padded = right.ljust(max_right_width)
            lines.append(f"{left_padded} │ {right_padded}")

        return "\n".join(lines)

    def _diff_stats(self, old_lines: list[str], new_lines: list[str]) -> str:
        """统计差异行数。"""
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        added = 0
        removed = 0
        modified = 0

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace":
                added += j2 - j1
                removed += i2 - i1
                modified += min(i2 - i1, j2 - j1)
            elif tag == "delete":
                removed += i2 - i1
            elif tag == "insert":
                added += j2 - j1

        return (
            f"统计: +{added} 行新增, -{removed} 行删除, ~{modified} 行修改"
        )


class SnapshotTool(BaseTool):
    name = "snapshot"
    description = "创建或管理文件快照，用于编辑前的备份和回滚。"
    parameters = [
        ToolParameter(
            name="action",
            type="string",
            description="操作: save（保存快照）、list（列出快照）、restore（恢复快照）、delete（删除快照）",
            required=True,
            enum=["save", "list", "restore", "delete"],
        ),
        ToolParameter(
            name="path",
            type="string",
            description="文件路径（save/restore/delete 需要）",
            required=False,
        ),
        ToolParameter(
            name="snapshot_id",
            type="string",
            description="快照标识（restore/delete 需要，不提供则使用最新快照）",
            required=False,
        ),
    ]
    metadata = ToolMetadata(category="file", danger_level=DangerLevel.CONFIRM, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs["action"]
        path = kwargs.get("path")
        snapshot_id = kwargs.get("snapshot_id")

        try:
            snapshot_dir = DiffTool._get_snapshot_dir()

            if action == "save":
                if not path:
                    return ToolResult.fail("save 操作需要 path 参数")
                return self._save_snapshot(path, snapshot_dir)
            elif action == "list":
                return self._list_snapshots(snapshot_dir, path)
            elif action == "restore":
                if not path:
                    return ToolResult.fail("restore 操作需要 path 参数")
                return self._restore_snapshot(path, snapshot_id, snapshot_dir)
            elif action == "delete":
                if not path:
                    return ToolResult.fail("delete 操作需要 path 参数")
                return self._delete_snapshot(path, snapshot_id, snapshot_dir)
            else:
                return ToolResult.fail(f"不支持的操作: {action}")

        except Exception as e:
            return ToolResult.fail(str(e))

    def _save_snapshot(self, path: str, snapshot_dir: Path) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult.fail(f"文件未找到: {path}")

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        file_hash = hashlib.md5(str(p.resolve()).encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        snapshot_path = snapshot_dir / f"{file_hash}_{timestamp}.snapshot"

        with open(snapshot_path, "w", encoding="utf-8") as f:
            f.write(content)

        return ToolResult.ok(
            f"✅ 快照已保存\n"
            f"文件: {path}\n"
            f"快照 ID: {file_hash}_{timestamp}\n"
            f"大小: {len(content)} 字符"
        )

    def _list_snapshots(self, snapshot_dir: Path, path: str | None) -> ToolResult:
        snapshots = sorted(snapshot_dir.glob("*.snapshot"), reverse=True)

        if not snapshots:
            return ToolResult.ok("暂无快照记录")

        if path:
            file_hash = hashlib.md5(
                str(Path(path).expanduser().resolve()).encode()
            ).hexdigest()[:12]
            snapshots = [s for s in snapshots if s.name.startswith(f"{file_hash}_")]

        if not snapshots:
            return ToolResult.ok(f"未找到 {'文件 ' + path + ' 的' if path else ''}快照记录")

        lines = [f"共 {len(snapshots)} 个快照:\n"]
        for s in snapshots[:20]:  # 最多显示 20 个
            size = s.stat().st_size
            name = s.stem
            lines.append(f"  📸 {name}  ({size} 字节)")

        if len(snapshots) > 20:
            lines.append(f"  ... 还有 {len(snapshots) - 20} 个快照")

        return ToolResult.ok("\n".join(lines))

    def _restore_snapshot(self, path: str, snapshot_id: str | None, snapshot_dir: Path) -> ToolResult:
        p = Path(path).expanduser()
        file_hash = hashlib.md5(str(p.resolve()).encode()).hexdigest()[:12]

        # 查找快照
        if snapshot_id:
            snapshot_path = snapshot_dir / f"{snapshot_id}.snapshot"
        else:
            # 使用最新快照
            snapshots = sorted(snapshot_dir.glob(f"{file_hash}_*.snapshot"), reverse=True)
            if not snapshots:
                return ToolResult.fail(f"未找到 {path} 的快照记录")
            snapshot_path = snapshots[0]

        if not snapshot_path.exists():
            return ToolResult.fail(f"快照不存在: {snapshot_id}")

        # 读取快照内容
        with open(snapshot_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # 恢复文件
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

        return ToolResult.ok(
            f"✅ 已从快照恢复\n"
            f"文件: {path}\n"
            f"快照: {snapshot_path.stem}\n"
            f"大小: {len(content)} 字符"
        )

    def _delete_snapshot(self, path: str, snapshot_id: str | None, snapshot_dir: Path) -> ToolResult:
        p = Path(path).expanduser()
        file_hash = hashlib.md5(str(p.resolve()).encode()).hexdigest()[:12]

        if snapshot_id:
            snapshot_path = snapshot_dir / f"{snapshot_id}.snapshot"
            if not snapshot_path.exists():
                return ToolResult.fail(f"快照不存在: {snapshot_id}")
            snapshot_path.unlink()
            return ToolResult.ok(f"✅ 已删除快照: {snapshot_id}")
        else:
            # 删除该文件的所有快照
            snapshots = sorted(snapshot_dir.glob(f"{file_hash}_*.snapshot"), reverse=False)
            if not snapshots:
                return ToolResult.fail(f"未找到 {path} 的快照记录")
            for s in snapshots:
                s.unlink()
            return ToolResult.ok(f"✅ 已删除 {len(snapshots)} 个快照")


DIFF_TOOLS = [DiffTool(), SnapshotTool()]
