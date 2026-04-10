"""
Git 集成工具

提供 git_diff, git_commit, git_log, git_status, git_branch 等功能。
"""

from __future__ import annotations

import os
from pathlib import Path

from src.sandbox.runner import CommandRunner
from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


def _run_git_command(cmd: str, workdir: str, timeout: int = 30) -> ToolResult:
    """执行 Git 命令的统一辅助函数。"""
    runner = CommandRunner(timeout=timeout, workdir=workdir)
    return runner.run(cmd)


def _is_git_success(result: ToolResult) -> bool:
    """判断 Git 命令是否成功执行。"""
    return result.success


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = (
        "查看 Git 差异。支持以下模式：\n"
        "- unstaged: 查看未暂存的修改（默认）\n"
        "- staged: 查看已暂存但未提交的修改\n"
        "- commit: 查看指定提交之间的差异\n"
        "- file: 查看特定文件的修改"
    )
    parameters = [
        ToolParameter(
            name="mode",
            type="string",
            description="差异模式: unstaged（未暂存）、staged（已暂存）、commit（提交间）、file（文件）",
            required=False,
            default="unstaged",
            enum=["unstaged", "staged", "commit", "file"],
        ),
        ToolParameter(
            name="file_path",
            type="string",
            description="文件路径（file 模式需要）",
            required=False,
        ),
        ToolParameter(
            name="commit_range",
            type="string",
            description="提交范围（commit 模式，如 'HEAD~3..HEAD' 或 'abc123..def456'）",
            required=False,
        ),
        ToolParameter(
            name="repo_path",
            type="string",
            description="Git 仓库路径（默认为当前目录）",
            required=False,
        ),
        ToolParameter(
            name="stat",
            type="boolean",
            description="是否只显示统计摘要（默认 false）",
            required=False,
            default=False,
        ),
    ]
    metadata = ToolMetadata(category="git", danger_level=DangerLevel.SAFE, timeout_seconds=30)

    async def execute(self, **kwargs) -> ToolResult:
        mode = kwargs.get("mode", "unstaged")
        repo_path = kwargs.get("repo_path", ".")
        stat = kwargs.get("stat", False)

        try:
            p = Path(repo_path).expanduser().resolve()

            if mode == "unstaged":
                cmd = "git diff"
            elif mode == "staged":
                cmd = "git diff --cached"
            elif mode == "commit":
                commit_range = kwargs.get("commit_range", "HEAD~1..HEAD")
                cmd = f"git diff {commit_range}"
            elif mode == "file":
                file_path = kwargs.get("file_path")
                if not file_path:
                    return ToolResult.fail("file 模式需要 file_path 参数")
                cmd = f"git diff -- {file_path}"
            else:
                return ToolResult.fail(f"不支持的模式: {mode}")

            if stat:
                cmd += " --stat"

            result = _run_git_command(cmd, str(p), timeout=30)

            if result.metadata.get("timed_out"):
                return ToolResult.fail("git diff 命令超时")

            if not result.success:
                return ToolResult.fail(f"git diff 失败: {result.error}")

            if not result.content.strip() or result.content.strip() == "(无输出)":
                return ToolResult.ok("没有差异" if not stat else "没有变更")

            return ToolResult.ok(result.content)

        except Exception as e:
            return ToolResult.fail(str(e))


class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "暂存并提交文件到 Git 仓库。"
    parameters = [
        ToolParameter(
            name="message",
            type="string",
            description="提交信息",
            required=True,
        ),
        ToolParameter(
            name="files",
            type="string",
            description="要提交的文件路径（多个文件用空格分隔，'.' 表示全部，默认为 '.'）",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="repo_path",
            type="string",
            description="Git 仓库路径（默认为当前目录）",
            required=False,
        ),
        ToolParameter(
            name="amend",
            type="boolean",
            description="是否修改上一次提交（默认 false）",
            required=False,
            default=False,
        ),
    ]
    metadata = ToolMetadata(category="git", danger_level=DangerLevel.CONFIRM, timeout_seconds=30)

    async def execute(self, **kwargs) -> ToolResult:
        message = kwargs["message"]
        files = kwargs.get("files", ".")
        repo_path = kwargs.get("repo_path", ".")
        amend = kwargs.get("amend", False)

        try:
            p = Path(repo_path).expanduser().resolve()

            # 检查是否是 git 仓库
            check = _run_git_command("git rev-parse --is-inside-work-tree", str(p), timeout=5)
            if not _is_git_success(check):
                return ToolResult.fail(f"不是 Git 仓库: {repo_path}")

            # git add
            add_cmd = f"git add {files}"
            add_result = _run_git_command(add_cmd, str(p), timeout=15)
            if not _is_git_success(add_result):
                return ToolResult.fail(f"git add 失败: {add_result.error or add_result.content}")

            # git commit
            amend_flag = "--amend" if amend else ""
            commit_cmd = f'git commit {amend_flag} -m {self._shell_quote(message)}'
            commit_result = _run_git_command(commit_cmd, str(p), timeout=15)

            if not _is_git_success(commit_result):
                error_msg = commit_result.error or commit_result.content
                if error_msg and "nothing to commit" in error_msg:
                    return ToolResult.ok("没有需要提交的变更")
                return ToolResult.fail(f"git commit 失败: {error_msg}")

            # 获取提交 hash
            hash_result = _run_git_command("git rev-parse --short HEAD", str(p), timeout=5)
            short_hash = hash_result.content.strip() if hash_result.success else "unknown"

            return ToolResult.ok(
                f"✅ 提交成功\n"
                f"Commit: {short_hash}\n"
                f"Message: {message}\n"
                f"Files: {files}"
            )

        except Exception as e:
            return ToolResult.fail(str(e))

    @staticmethod
    def _shell_quote(s: str) -> str:
        """简单地将字符串用单引号包裹（替换内部的单引号）。"""
        return "'" + s.replace("'", "'\\''") + "'"


class GitLogTool(BaseTool):
    name = "git_log"
    description = "查看 Git 提交历史。"
    parameters = [
        ToolParameter(
            name="count",
            type="integer",
            description="显示最近 N 条提交（默认 10）",
            required=False,
            default=10,
        ),
        ToolParameter(
            name="author",
            type="string",
            description="按作者过滤",
            required=False,
        ),
        ToolParameter(
            name="since",
            type="string",
            description="起始日期（如 '2024-01-01' 或 '1 week ago'）",
            required=False,
        ),
        ToolParameter(
            name="branch",
            type="string",
            description="指定分支",
            required=False,
        ),
        ToolParameter(
            name="oneline",
            type="boolean",
            description="是否使用单行格式（默认 true）",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="repo_path",
            type="string",
            description="Git 仓库路径（默认为当前目录）",
            required=False,
        ),
    ]
    metadata = ToolMetadata(category="git", danger_level=DangerLevel.SAFE, timeout_seconds=15)

    async def execute(self, **kwargs) -> ToolResult:
        count = kwargs.get("count", 10)
        repo_path = kwargs.get("repo_path", ".")
        author = kwargs.get("author")
        since = kwargs.get("since")
        branch = kwargs.get("branch")
        oneline = kwargs.get("oneline", True)

        try:
            p = Path(repo_path).expanduser().resolve()

            # 构建命令
            parts = ["git", "log"]

            if oneline:
                parts.append("--oneline")
            else:
                parts.extend(["--pretty=format:%h %an %ai %s"])

            parts.append(f"-{min(count, 100)}")

            if author:
                parts.append(f"--author={author}")
            if since:
                parts.append(f"--since={since}")
            if branch:
                parts.append(branch)

            cmd = " ".join(parts)
            result = _run_git_command(cmd, str(p), timeout=15)

            if not _is_git_success(result):
                return ToolResult.fail(f"git log 失败: {result.error}")

            if not result.content.strip() or result.content.strip() == "(无输出)":
                return ToolResult.ok("没有提交记录")

            return ToolResult.ok(result.content)

        except Exception as e:
            return ToolResult.fail(str(e))


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "查看 Git 仓库当前状态（修改、暂存、未跟踪文件等）。"
    parameters = [
        ToolParameter(
            name="repo_path",
            type="string",
            description="Git 仓库路径（默认为当前目录）",
            required=False,
        ),
        ToolParameter(
            name="short",
            type="boolean",
            description="是否使用简短格式（默认 true）",
            required=False,
            default=True,
        ),
    ]
    metadata = ToolMetadata(category="git", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        repo_path = kwargs.get("repo_path", ".")
        short = kwargs.get("short", True)

        try:
            p = Path(repo_path).expanduser().resolve()
            short_flag = "--short" if short else ""
            cmd = f"git status {short_flag}"
            result = _run_git_command(cmd, str(p), timeout=10)

            if not _is_git_success(result):
                return ToolResult.fail(f"git status 失败: {result.error}")

            return ToolResult.ok(result.content)

        except Exception as e:
            return ToolResult.fail(str(e))


class GitBranchTool(BaseTool):
    name = "git_branch"
    description = (
        "查看、创建或切换 Git 分支。\n"
        "不提供 branch 参数时列出所有分支，提供则切换到该分支。"
    )
    parameters = [
        ToolParameter(
            name="branch",
            type="string",
            description="分支名称。提供此参数时切换到该分支（不提供则列出所有分支）",
            required=False,
        ),
        ToolParameter(
            name="create",
            type="boolean",
            description="是否创建新分支（默认 false）",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="repo_path",
            type="string",
            description="Git 仓库路径（默认为当前目录）",
            required=False,
        ),
    ]
    metadata = ToolMetadata(category="git", danger_level=DangerLevel.CONFIRM, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        branch = kwargs.get("branch")
        create = kwargs.get("create", False)
        repo_path = kwargs.get("repo_path", ".")

        try:
            p = Path(repo_path).expanduser().resolve()

            if not branch:
                # 列出所有分支
                result = _run_git_command("git branch -a", str(p), timeout=10)
                if not _is_git_success(result):
                    return ToolResult.fail(f"git branch 失败: {result.error}")

                # 标记当前分支
                content = result.content
                lines = []
                for line in content.strip().split("\n"):
                    if line.startswith("* "):
                        lines.append(f"  * {line[2:]}  ← 当前分支")
                    else:
                        lines.append(f"    {line.strip()}")
                return ToolResult.ok(f"所有分支:\n" + "\n".join(lines))
            else:
                if create:
                    cmd = f"git checkout -b {branch}"
                else:
                    cmd = f"git checkout {branch}"

                result = _run_git_command(cmd, str(p), timeout=10)
                if not _is_git_success(result):
                    return ToolResult.fail(
                        f"切换分支失败: {result.error or result.content}"
                    )

                action = "创建并切换" if create else "切换"
                return ToolResult.ok(f"✅ 已{action}到分支: {branch}")

        except Exception as e:
            return ToolResult.fail(str(e))


class GitShowTool(BaseTool):
    name = "git_show"
    description = "查看指定提交的详细信息，包括修改内容。"
    parameters = [
        ToolParameter(
            name="commit",
            type="string",
            description="提交 hash（如 'HEAD', 'HEAD~1', 'abc123'）",
            required=True,
        ),
        ToolParameter(
            name="stat",
            type="boolean",
            description="是否只显示统计信息（默认 false）",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="repo_path",
            type="string",
            description="Git 仓库路径（默认为当前目录）",
            required=False,
        ),
    ]
    metadata = ToolMetadata(category="git", danger_level=DangerLevel.SAFE, timeout_seconds=15)

    async def execute(self, **kwargs) -> ToolResult:
        commit = kwargs["commit"]
        stat = kwargs.get("stat", False)
        repo_path = kwargs.get("repo_path", ".")

        try:
            p = Path(repo_path).expanduser().resolve()
            stat_flag = "--stat" if stat else ""
            cmd = f"git show {stat_flag} {commit}"
            result = _run_git_command(cmd, str(p), timeout=15)

            if not _is_git_success(result):
                return ToolResult.fail(
                    f"git show 失败: {result.error or result.content}"
                )

            return ToolResult.ok(result.content)

        except Exception as e:
            return ToolResult.fail(str(e))


class GitBlameTool(BaseTool):
    name = "git_blame"
    description = "查看文件每一行最后修改的提交信息。"
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="文件路径",
            required=True,
        ),
        ToolParameter(
            name="line_range",
            type="string",
            description="行号范围（如 '10,20' 或 '10,+5'，可选）",
            required=False,
        ),
        ToolParameter(
            name="repo_path",
            type="string",
            description="Git 仓库路径（默认为当前目录）",
            required=False,
        ),
    ]
    metadata = ToolMetadata(category="git", danger_level=DangerLevel.SAFE, timeout_seconds=15)

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs["file_path"]
        line_range = kwargs.get("line_range")
        repo_path = kwargs.get("repo_path", ".")

        try:
            p = Path(repo_path).expanduser().resolve()
            range_flag = f"-L {line_range}" if line_range else ""
            cmd = f"git blame {range_flag} {file_path}"
            result = _run_git_command(cmd, str(p), timeout=15)

            if not _is_git_success(result):
                return ToolResult.fail(
                    f"git blame 失败: {result.error or result.content}"
                )

            return ToolResult.ok(result.content)

        except Exception as e:
            return ToolResult.fail(str(e))


GIT_TOOLS = [
    GitDiffTool(),
    GitCommitTool(),
    GitLogTool(),
    GitStatusTool(),
    GitBranchTool(),
    GitShowTool(),
    GitBlameTool(),
]
