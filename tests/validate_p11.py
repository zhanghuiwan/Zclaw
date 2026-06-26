"""
P11 验证测试 - 高级编辑能力

测试 P11 新增的所有工具：
1. 行号级编辑工具 (line_edit_tool.py) - line_edit, line_read
2. Diff 预览工具 (diff_tool.py) - diff, snapshot
3. Git 集成工具 (git_tool.py) - git_diff, git_commit, git_log, git_status, git_branch, git_show, git_blame
4. 语法感知编辑 (ast_tool.py) - code_structure, symbol_find, symbol_edit, import_analyze

运行方式: python -m pytest tests/validate_p11.py -v
         或: python tests/validate_p11.py
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

passed = 0
failed = 0
errors = []


def run_test(name, func):
    """运行单个测试并记录结果。"""
    global passed, failed, errors
    try:
        func()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


def run_async_test(name, func):
    """运行异步测试。"""
    global passed, failed, errors
    try:
        asyncio.run(func())
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


# ============================================================
# Test 1: 行号级编辑工具 (line_edit_tool.py)
# ============================================================

async def test_line_edit_replace():
    """测试行号替换操作。"""
    from src.tools.builtin.line_edit_tool import LineEditTool

    tool = LineEditTool()

    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("line1\nline2\nline3\nline4\nline5\n")
        tmp_path = f.name

    try:
        # 替换第 2-3 行
        result = await tool.execute(path=tmp_path, mode="replace", start_line=2, end_line=3, content="new_line")
        assert result.success, f"替换失败: {result.error}"
        assert "替换第 2-3 行" in result.content

        with open(tmp_path, "r") as f:
            content = f.read()
        assert content == "line1\nnew_line\nline4\nline5\n"
    finally:
        os.unlink(tmp_path)


async def test_line_edit_insert():
    """测试行号插入操作。"""
    from src.tools.builtin.line_edit_tool import LineEditTool

    tool = LineEditTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("aaa\nccc\n")
        tmp_path = f.name

    try:
        result = await tool.execute(path=tmp_path, mode="insert", start_line=2, content="bbb")
        assert result.success, f"插入失败: {result.error}"

        with open(tmp_path, "r") as f:
            content = f.read()
        assert content == "aaa\nbbb\nccc\n"
    finally:
        os.unlink(tmp_path)


async def test_line_edit_delete():
    """测试行号删除操作。"""
    from src.tools.builtin.line_edit_tool import LineEditTool

    tool = LineEditTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("aaa\nbbb\nccc\n")
        tmp_path = f.name

    try:
        result = await tool.execute(path=tmp_path, mode="delete", start_line=2, end_line=2)
        assert result.success, f"删除失败: {result.error}"

        with open(tmp_path, "r") as f:
            content = f.read()
        assert content == "aaa\nccc\n"
    finally:
        os.unlink(tmp_path)


async def test_line_edit_validation():
    """测试行号越界检查。"""
    from src.tools.builtin.line_edit_tool import LineEditTool

    tool = LineEditTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("line1\nline2\n")
        tmp_path = f.name

    try:
        # 起始行号超出范围
        result = await tool.execute(path=tmp_path, mode="replace", start_line=10, end_line=10, content="x")
        assert not result.success
        assert "超出范围" in result.error

        # 结束行号小于起始行号
        result = await tool.execute(path=tmp_path, mode="delete", start_line=3, end_line=2)
        assert not result.success
        assert "小于" in result.error
    finally:
        os.unlink(tmp_path)


async def test_line_read():
    """测试按行号读取。"""
    from src.tools.builtin.line_edit_tool import LineReadTool

    tool = LineReadTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("line1\nline2\nline3\nline4\nline5\n")
        tmp_path = f.name

    try:
        # 读取第 2-4 行
        result = await tool.execute(path=tmp_path, start_line=2, end_line=4, show_line_numbers=True)
        assert result.success
        assert "2 | line2" in result.content
        assert "3 | line3" in result.content
        assert "4 | line4" in result.content
        assert "line1" not in result.content  # 不包含第 1 行
        assert "共 5 行" in result.content

        # 不显示行号
        result = await tool.execute(path=tmp_path, start_line=1, end_line=2, show_line_numbers=False)
        assert result.success
        assert "line1" in result.content
        assert "|" not in result.content
    finally:
        os.unlink(tmp_path)


# ============================================================
# Test 2: Diff 预览工具 (diff_tool.py)
# ============================================================

def test_diff_text():
    """测试文本比较。"""
    from src.tools.builtin.diff_tool import DiffTool

    tool = DiffTool()

    # 需要异步执行
    async def _run():
        result = await tool.execute(
            mode="text",
            old_text="hello\nworld\n",
            new_text="hello\npython\n",
            format="unified",
        )
        assert result.success
        assert "+python" in result.content or "-world" in result.content
        assert "统计" in result.content

    asyncio.run(_run())


def test_diff_file():
    """测试文件比较。"""
    from src.tools.builtin.diff_tool import DiffTool

    tool = DiffTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f1:
        f1.write("aaa\nbbb\nccc\n")
        path1 = f1.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f2:
        f2.write("aaa\nxxx\nccc\n")
        path2 = f2.name

    try:
        async def _run():
            result = await tool.execute(
                mode="file",
                path=path1,
                path2=path2,
                format="unified",
            )
            assert result.success
            assert "bbb" in result.content or "xxx" in result.content

        asyncio.run(_run())
    finally:
        os.unlink(path1)
        os.unlink(path2)


def test_diff_side_by_side():
    """测试并排对比格式。"""
    from src.tools.builtin.diff_tool import DiffTool

    tool = DiffTool()

    async def _run():
        result = await tool.execute(
            mode="text",
            old_text="aaa\nbbb\n",
            new_text="aaa\nccc\n",
            format="side_by_side",
        )
        assert result.success
        assert "│" in result.content  # 并排格式使用 │ 分隔

    asyncio.run(_run())


def test_snapshot_save_and_restore():
    """测试快照保存和恢复。"""
    from src.tools.builtin.diff_tool import SnapshotTool

    tool = SnapshotTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("original content\n")
        tmp_path = f.name

    try:
        async def _run():
            # 保存快照
            save_result = await tool.execute(action="save", path=tmp_path)
            assert save_result.success
            assert "快照已保存" in save_result.content
            snapshot_id = None
            for line in save_result.content.split("\n"):
                if "快照 ID:" in line:
                    snapshot_id = line.split("快照 ID:")[1].strip()
            assert snapshot_id is not None

            # 修改文件
            with open(tmp_path, "w") as f:
                f.write("modified content\n")

            # 恢复快照
            restore_result = await tool.execute(action="restore", path=tmp_path, snapshot_id=snapshot_id)
            assert restore_result.success
            assert "已从快照恢复" in restore_result.content

            # 验证内容已恢复
            with open(tmp_path, "r") as f:
                assert f.read() == "original content\n"

            # 删除快照
            delete_result = await tool.execute(action="delete", path=tmp_path, snapshot_id=snapshot_id)
            assert delete_result.success

        asyncio.run(_run())
    finally:
        os.unlink(tmp_path)


def test_snapshot_list():
    """测试快照列表。"""
    from src.tools.builtin.diff_tool import SnapshotTool

    tool = SnapshotTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write("test\n")
        tmp_path = f.name

    try:
        async def _run():
            # 保存两个快照
            await tool.execute(action="save", path=tmp_path)
            await tool.execute(action="save", path=tmp_path)

            # 列出
            result = await tool.execute(action="list", path=tmp_path)
            assert result.success
            assert "2 个快照" in result.content

            # 删除全部
            result = await tool.execute(action="delete", path=tmp_path)
            assert result.success
            assert "2" in result.content

        asyncio.run(_run())
    finally:
        os.unlink(tmp_path)


# ============================================================
# Test 3: Git 集成工具 (git_tool.py)
# ============================================================

def test_git_tools_import():
    """测试 Git 工具可以正确导入。"""
    from src.tools.builtin.git_tool import (
        GitDiffTool, GitCommitTool, GitLogTool,
        GitStatusTool, GitBranchTool, GitShowTool, GitBlameTool,
        GIT_TOOLS,
    )
    assert len(GIT_TOOLS) == 7
    assert GIT_TOOLS[0].name == "git_diff"
    assert GIT_TOOLS[1].name == "git_commit"
    assert GIT_TOOLS[2].name == "git_log"
    assert GIT_TOOLS[3].name == "git_status"
    assert GIT_TOOLS[4].name == "git_branch"
    assert GIT_TOOLS[5].name == "git_show"
    assert GIT_TOOLS[6].name == "git_blame"


def test_git_diff_tool_properties():
    """测试 GitDiffTool 属性。"""
    from src.tools.builtin.git_tool import GitDiffTool
    from src.tools.base import DangerLevel

    tool = GitDiffTool()
    assert tool.name == "git_diff"
    assert tool.danger_level == DangerLevel.SAFE
    assert tool.category == "git"
    assert len(tool.parameters) == 5

    # 验证参数定义
    param_names = [p.name for p in tool.parameters]
    assert "mode" in param_names
    assert "file_path" in param_names
    assert "commit_range" in param_names


def test_git_commit_tool_properties():
    """测试 GitCommitTool 属性。"""
    from src.tools.builtin.git_tool import GitCommitTool
    from src.tools.base import DangerLevel

    tool = GitCommitTool()
    assert tool.name == "git_commit"
    assert tool.danger_level == DangerLevel.CONFIRM

    param_names = [p.name for p in tool.parameters]
    assert "message" in param_names
    assert "files" in param_names
    assert "amend" in param_names


def test_git_log_tool_properties():
    """测试 GitLogTool 属性。"""
    from src.tools.builtin.git_tool import GitLogTool

    tool = GitLogTool()
    assert tool.name == "git_log"
    param_names = [p.name for p in tool.parameters]
    assert "count" in param_names
    assert "author" in param_names
    assert "since" in param_names


def test_git_status_tool_properties():
    """测试 GitStatusTool 属性。"""
    from src.tools.builtin.git_tool import GitStatusTool

    tool = GitStatusTool()
    assert tool.name == "git_status"
    assert len(tool.parameters) == 2


def test_git_branch_tool_properties():
    """测试 GitBranchTool 属性。"""
    from src.tools.builtin.git_tool import GitBranchTool
    from src.tools.base import DangerLevel

    tool = GitBranchTool()
    assert tool.name == "git_branch"
    assert tool.danger_level == DangerLevel.CONFIRM


def test_git_operations():
    """测试 Git 操作（在临时仓库中）。"""
    from src.tools.builtin.git_tool import (
        GitStatusTool, GitCommitTool, GitLogTool, GitDiffTool,
    )

    import subprocess

    # 创建临时 Git 仓库
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, "w") as f:
            f.write("print('hello')\n")

        async def _run():
            # git status
            status_tool = GitStatusTool()
            result = await status_tool.execute(repo_path=tmpdir)
            assert result.success, f"git status 失败: {result.error}"
            assert "test.py" in result.content

            # git commit
            commit_tool = GitCommitTool()
            result = await commit_tool.execute(
                message="initial commit",
                files=".",
                repo_path=tmpdir,
            )
            assert result.success, f"git commit 失败: {result.error}"
            assert "提交成功" in result.content

            # git log
            log_tool = GitLogTool()
            result = await log_tool.execute(count=5, repo_path=tmpdir)
            assert result.success
            assert "initial commit" in result.content

            # git diff (应该没有差异)
            diff_tool = GitDiffTool()
            result = await diff_tool.execute(mode="unstaged", repo_path=tmpdir)
            assert result.success
            assert "没有差异" in result.content

        asyncio.run(_run())


def test_git_show_tool():
    """测试 git_show 工具。"""
    from src.tools.builtin.git_tool import GitShowTool

    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, "w") as f:
            f.write("hello\n")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "test commit"], cwd=tmpdir, capture_output=True)

        async def _run():
            tool = GitShowTool()
            result = await tool.execute(commit="HEAD", stat=True, repo_path=tmpdir)
            assert result.success
            assert "test commit" in result.content

        asyncio.run(_run())


def test_git_blame_tool():
    """测试 git_blame 工具。"""
    from src.tools.builtin.git_tool import GitBlameTool

    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

        test_file = os.path.join(tmpdir, "blame_test.py")
        with open(test_file, "w") as f:
            f.write("line1\nline2\nline3\n")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "blame test"], cwd=tmpdir, capture_output=True)

        async def _run():
            tool = GitBlameTool()
            result = await tool.execute(file_path="blame_test.py", repo_path=tmpdir)
            assert result.success

        asyncio.run(_run())


def test_git_branch_tool():
    """测试 git_branch 工具。"""
    from src.tools.builtin.git_tool import GitBranchTool

    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmpdir, capture_output=True)

        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, "w") as f:
            f.write("init\n")
        subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmpdir, capture_output=True)

        async def _run():
            tool = GitBranchTool()

            # 列出分支
            result = await tool.execute(repo_path=tmpdir)
            assert result.success
            assert "当前分支" in result.content

            # 创建并切换分支
            result = await tool.execute(branch="feature-test", create=True, repo_path=tmpdir)
            assert result.success
            assert "feature-test" in result.content

        asyncio.run(_run())


# ============================================================
# Test 4: 语法感知编辑 (ast_tool.py)
# ============================================================

def test_code_structure():
    """测试代码结构分析。"""
    from src.tools.builtin.ast_tool import CodeStructureTool

    tool = CodeStructureTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write('''
"""Module docstring."""

import os
from typing import List

class MyClass:
    """A class."""
    
    def method1(self):
        pass
    
    async def method2(self):
        pass

def my_function(x: int, y: str = "default") -> str:
    """A function."""
    return f"{x} {y}"
''')
        tmp_path = f.name

    try:
        async def _run():
            # normal detail
            result = await tool.execute(path=tmp_path, detail="normal")
            assert result.success, f"分析失败: {result.error}"
            assert "MyClass" in result.content
            assert "method1" in result.content
            assert "method2" in result.content
            assert "my_function" in result.content
            assert "import os" in result.content

            # brief detail
            result = await tool.execute(path=tmp_path, detail="brief")
            assert result.success
            assert "MyClass" in result.content

            # full detail (含文档字符串)
            result = await tool.execute(path=tmp_path, detail="full")
            assert result.success
            assert "A class." in result.content or "A function." in result.content

        asyncio.run(_run())
    finally:
        os.unlink(tmp_path)


def test_symbol_find():
    """测试符号查找。"""
    from src.tools.builtin.ast_tool import SymbolFindTool

    tool = SymbolFindTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write('''
def hello():
    """Say hello."""
    return "hello"

def world():
    return "world"
''')
        tmp_path = f.name

    try:
        async def _run():
            # 查找存在的符号
            result = await tool.execute(path=tmp_path, symbol="hello", include_body=True)
            assert result.success, f"查找失败: {result.error}"
            assert "def hello" in result.content
            assert "Say hello" in result.content

            # 查找不存在的符号
            result = await tool.execute(path=tmp_path, symbol="nonexistent")
            assert not result.success
            assert "未找到" in result.error

        asyncio.run(_run())
    finally:
        os.unlink(tmp_path)


def test_symbol_edit():
    """测试符号替换。"""
    from src.tools.builtin.ast_tool import SymbolEditTool

    tool = SymbolEditTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write('def old_func():\n    return "old"\n\ndef other_func():\n    return "other"\n')
        tmp_path = f.name

    try:
        async def _run():
            new_code = 'def new_func():\n    """New function."""\n    return "new"'
            result = await tool.execute(
                path=tmp_path,
                symbol="old_func",
                new_code=new_code,
            )
            assert result.success, f"替换失败: {result.error}"
            assert "符号替换成功" in result.content

            with open(tmp_path, "r") as f:
                content = f.read()
            assert "def new_func" in content
            assert "old_func" not in content
            assert "def other_func" in content  # 其他函数不受影响

        asyncio.run(_run())
    finally:
        os.unlink(tmp_path)


def test_import_analyze():
    """测试导入分析。"""
    from src.tools.builtin.ast_tool import ImportAnalyzerTool

    tool = ImportAnalyzerTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write('''
import os
import sys
from pathlib import Path
from typing import List, Dict
import json  # unused

def my_func():
    pass
''')
        tmp_path = f.name

    try:
        async def _run():
            result = await tool.execute(path=tmp_path, check_unused=True)
            assert result.success, f"分析失败: {result.error}"
            assert "标准库" in result.content
            assert "json" in result.content
            assert "统计" in result.content

        asyncio.run(_run())
    finally:
        os.unlink(tmp_path)


def test_ast_tool_properties():
    """测试 AST 工具属性。"""
    from src.tools.builtin.ast_tool import (
        CodeStructureTool, SymbolFindTool, SymbolEditTool,
        ImportAnalyzerTool, AST_TOOLS,
    )
    from src.tools.base import DangerLevel

    assert len(AST_TOOLS) == 4

    # code_structure
    t = CodeStructureTool()
    assert t.name == "code_structure"
    assert t.danger_level == DangerLevel.SAFE
    assert t.category == "analysis"

    # symbol_find
    t = SymbolFindTool()
    assert t.name == "symbol_find"
    assert t.danger_level == DangerLevel.SAFE

    # symbol_edit
    t = SymbolEditTool()
    assert t.name == "symbol_edit"
    assert t.danger_level == DangerLevel.CONFIRM

    # import_analyze
    t = ImportAnalyzerTool()
    assert t.name == "import_analyze"
    assert t.danger_level == DangerLevel.SAFE


def test_code_structure_non_python():
    """测试非 Python 文件的处理。"""
    from src.tools.builtin.ast_tool import CodeStructureTool

    tool = CodeStructureTool()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("not python\n")
        tmp_path = f.name

    try:
        async def _run():
            result = await tool.execute(path=tmp_path)
            assert not result.success
            assert "Python" in result.error

        asyncio.run(_run())
    finally:
        os.unlink(tmp_path)


# ============================================================
# Test 5: Agent 集成
# ============================================================

def test_agent_tool_registration():
    """测试所有 P11 工具已注册到 Agent。"""
    from src.tools.builtin.line_edit_tool import LINE_EDIT_TOOLS
    from src.tools.builtin.diff_tool import DIFF_TOOLS
    from src.tools.builtin.git_tool import GIT_TOOLS
    from src.tools.builtin.ast_tool import AST_TOOLS

    p11_tools = LINE_EDIT_TOOLS + DIFF_TOOLS + GIT_TOOLS + AST_TOOLS
    p11_names = [t.name for t in p11_tools]

    expected_names = [
        "line_edit", "line_read",
        "diff", "snapshot",
        "git_diff", "git_commit", "git_log", "git_status",
        "git_branch", "git_show", "git_blame",
        "code_structure", "symbol_find", "symbol_edit", "import_analyze",
    ]

    assert len(p11_tools) == 15, f"预期 15 个工具，实际 {len(p11_tools)}"
    for name in expected_names:
        assert name in p11_names, f"缺少工具: {name}"


def test_diff_tool_stats():
    """测试 diff 统计功能。"""
    from src.tools.builtin.diff_tool import DiffTool

    tool = DiffTool()
    old_lines = ["a\n", "b\n", "c\n", "d\n"]
    new_lines = ["a\n", "x\n", "c\n", "d\n", "e\n", "f\n"]

    stats = tool._diff_stats(old_lines, new_lines)
    assert "统计" in stats
    assert "+" in stats or "-" in stats


def test_get_zclaw_dir():
    """测试 _get_zclaw_dir 函数。"""
    from src.config.settings import _get_zclaw_dir

    d = _get_zclaw_dir()
    assert d.exists()
    assert d.name == ".Zclaw"


# ============================================================
# 运行所有测试
# ============================================================

def main():
    print("=" * 60)
    print("P11 验证测试 - 高级编辑能力")
    print("=" * 60)

    print("\n📝 1. 行号级编辑工具 (line_edit_tool.py)")
    run_async_test("行号替换 (replace)", test_line_edit_replace)
    run_async_test("行号插入 (insert)", test_line_edit_insert)
    run_async_test("行号删除 (delete)", test_line_edit_delete)
    run_async_test("行号越界检查", test_line_edit_validation)
    run_async_test("按行号读取 (line_read)", test_line_read)

    print("\n🔍 2. Diff 预览工具 (diff_tool.py)")
    run_test("文本比较", test_diff_text)
    run_test("文件比较", test_diff_file)
    run_test("并排对比格式", test_diff_side_by_side)
    run_test("快照保存和恢复", test_snapshot_save_and_restore)
    run_test("快照列表", test_snapshot_list)

    print("\n🐙 3. Git 集成工具 (git_tool.py)")
    run_test("Git 工具导入", test_git_tools_import)
    run_test("GitDiffTool 属性", test_git_diff_tool_properties)
    run_test("GitCommitTool 属性", test_git_commit_tool_properties)
    run_test("GitLogTool 属性", test_git_log_tool_properties)
    run_test("GitStatusTool 属性", test_git_status_tool_properties)
    run_test("GitBranchTool 属性", test_git_branch_tool_properties)
    run_test("Git 操作 (status/commit/log/diff)", test_git_operations)
    run_test("git_show", test_git_show_tool)
    run_test("git_blame", test_git_blame_tool)
    run_test("git_branch", test_git_branch_tool)

    print("\n🧠 4. 语法感知编辑 (ast_tool.py)")
    run_test("代码结构分析", test_code_structure)
    run_test("符号查找", test_symbol_find)
    run_test("符号替换", test_symbol_edit)
    run_test("导入分析", test_import_analyze)
    run_test("AST 工具属性", test_ast_tool_properties)
    run_test("非 Python 文件处理", test_code_structure_non_python)

    print("\n🔗 5. Agent 集成")
    run_test("P11 工具注册", test_agent_tool_registration)
    run_test("Diff 统计功能", test_diff_tool_stats)
    run_test("_get_zclaw_dir 函数", test_get_zclaw_dir)

    # 汇总
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"结果: {passed}/{total} 通过, {failed} 失败")
    print("=" * 60)

    if errors:
        print("\n失败详情:")
        for name, err in errors:
            print(f"  - {name}: {err}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
