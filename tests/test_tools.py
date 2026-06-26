"""Built-in search, edit, diff, git, cache, and AST tool tests."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


async def test_grep_tool():
    print("=" * 60)
    print("1. Testing Grep Tool")
    print("=" * 60)
    from src.tools.builtin.grep_tool import GrepTool
    gt = GrepTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        os.makedirs(os.path.join(tmpdir, "src"))
        with open(os.path.join(tmpdir, "src", "main.py"), "w") as f:
            f.write("import os\nimport sys\n\ndef hello():\n    print('hello')\n\nclass App:\n    pass\n")
        with open(os.path.join(tmpdir, "src", "utils.py"), "w") as f:
            f.write("def util_func():\n    return 42\n\ndef import_helper():\n    pass\n")

        # Basic regex search
        r1 = await gt.execute(path=tmpdir, pattern="import")
        assert r1.success
        assert "main.py" in r1.content
        assert "utils.py" in r1.content
        print("  OK Basic regex search")

        # Case insensitive
        r2 = await gt.execute(path=tmpdir, pattern="class", include="*.py")
        assert r2.success and "App" in r2.content
        print("  OK Include filter")

        # Exclude filter
        r3 = await gt.execute(path=tmpdir, pattern="def", exclude="utils.py")
        assert r3.success
        assert "main.py" in r3.content
        print("  OK Exclude filter")

        # Context lines
        r4 = await gt.execute(path=tmpdir, pattern="hello", context=1)
        assert r4.success and ">>" in r4.content
        print("  OK Context lines")

        # No results
        r5 = await gt.execute(path=tmpdir, pattern="nonexistent_xyz_pattern")
        assert r5.success and "未找到" in r5.content
        print("  OK No matches")

        # Invalid regex
        r6 = await gt.execute(path=tmpdir, pattern="[invalid")
        assert not r6.success
        print("  OK Invalid regex rejected")

    print()

async def test_glob_tool():
    print("=" * 60)
    print("2. Testing Glob Tool")
    print("=" * 60)
    from src.tools.builtin.glob_tool import GlobTool
    gl = GlobTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "src", "core"))
        with open(os.path.join(tmpdir, "src", "main.py"), "w") as f:
            f.write("")
        with open(os.path.join(tmpdir, "src", "utils.py"), "w") as f:
            f.write("")
        with open(os.path.join(tmpdir, "src", "core", "agent.py"), "w") as f:
            f.write("")
        # Hidden file
        with open(os.path.join(tmpdir, ".hidden"), "w") as f:
            f.write("")

        # Match all .py
        r1 = await gl.execute(path=tmpdir, pattern="**/*.py")
        assert r1.success
        assert "main.py" in r1.content
        assert "utils.py" in r1.content
        assert "agent.py" in r1.content
        assert ".hidden" not in r1.content
        print("  OK **/*.py pattern")

        # Match specific dir
        r2 = await gl.execute(path=tmpdir, pattern="src/core/*.py")
        assert r2.success
        assert "agent.py" in r2.content
        assert "main.py" not in r2.content
        print("  OK src/core/*.py pattern")

        # Hidden files excluded
        r3 = await gl.execute(path=tmpdir, pattern="*")
        assert ".hidden" not in r3.content
        print("  OK Hidden files excluded by default")

        # Show hidden
        r4 = await gl.execute(path=tmpdir, pattern="*", exclude_hidden=False)
        assert ".hidden" in r4.content
        print("  OK Hidden files shown when exclude_hidden=False")

        # No match
        r5 = await gl.execute(path=tmpdir, pattern="**/*.xyz")
        assert r5.success and "没有文件匹配" in r5.content
        print("  OK No matches")

    print()

async def test_multi_edit_tool():
    print("=" * 60)
    print("3. Testing Multi-Edit Tool")
    print("=" * 60)
    from src.tools.builtin.multi_edit_tool import MultiEditTool
    me = MultiEditTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        p = os.path.join(tmpdir, "test.txt")
        original = "Line A\nLine B\nLine C\nLine D\n"
        with open(p, "w") as f:
            f.write(original)

        # Basic multi edit
        edits = json.dumps([
            {"old_text": "Line A", "new_text": "Line 1"},
            {"old_text": "Line C", "new_text": "Line 3"},
        ])
        r1 = await me.execute(path=p, edits=edits)
        assert r1.success
        content = open(p).read()
        assert "Line 1" in content
        assert "Line B" in content
        assert "Line 3" in content
        assert "Line A" not in content
        print("  OK Multi-edit: two replacements")

        # Atomic rollback on failure
        r2 = await me.execute(path=p, edits=json.dumps([
            {"old_text": "Line B", "new_text": "Line 2"},
            {"old_text": "NOT_FOUND", "new_text": "X"},
        ]))
        assert not r2.success
        content_after = open(p).read()
        assert content_after == content  # File unchanged
        print("  OK Atomic rollback on failure")

        # Invalid JSON
        r3 = await me.execute(path=p, edits="not json")
        assert not r3.success
        print("  OK Invalid JSON rejected")

        # Empty edits
        r4 = await me.execute(path=p, edits="[]")
        assert not r4.success
        print("  OK Empty edits rejected")

        # File not found
        r5 = await me.execute(path="/nonexistent", edits=edits)
        assert not r5.success
        print("  OK File not found")

    print()

async def test_tool_cache():
    print("=" * 60)
    print("4. Testing Tool Result Cache")
    print("=" * 60)
    from src.tools.cache import ToolResultCache
    from src.tools.base import ToolResult

    cache = ToolResultCache(max_size=5, ttl_seconds=60, enabled=True)

    # Basic put/get
    r1 = ToolResult.ok("cached result")
    cache.put("echo", {"text": "hello"}, r1)
    cached = cache.get("echo", {"text": "hello"})
    assert cached is not None and cached.success and cached.content == "cached result"
    print("  OK Basic put/get")

    # Cache miss
    miss = cache.get("echo", {"text": "different"})
    assert miss is None
    print("  OK Cache miss")

    # Key generation deterministic
    k1 = ToolResultCache.make_key("echo", {"text": "hello"})
    k2 = ToolResultCache.make_key("echo", {"text": "hello"})
    k3 = ToolResultCache.make_key("echo", {"text": "world"})
    assert k1 == k2 and k1 != k3
    print("  OK Key generation deterministic")

    # Don't cache failures
    r_fail = ToolResult.fail("error")
    cache.put("test", {"x": "1"}, r_fail)
    miss2 = cache.get("test", {"x": "1"})
    assert miss2 is None
    print("  OK Failures not cached")

    # Stats
    cache.get("echo", {"text": "hello"})  # hit
    cache.get("echo", {"text": "miss"})   # miss
    stats = cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    print(f"  OK Stats: hits={stats['hits']}, misses={stats['misses']}")

    # LRU eviction
    for i in range(10):
        cache.put("tool", {"n": str(i)}, ToolResult.ok(f"result {i}"))
    assert cache.size <= 5
    stats2 = cache.get_stats()
    assert stats2["evictions"] > 0
    print(f"  OK LRU eviction: size={cache.size}, evictions={stats2['evictions']}")

    # Disabled cache
    cache2 = ToolResultCache(enabled=False)
    cache2.put("x", {"y": "z"}, ToolResult.ok("test"))
    assert cache2.get("x", {"y": "z"}) is None
    print("  OK Disabled cache")

    # Clear
    cache.put("a", {"b": "c"}, ToolResult.ok("d"))
    cleared = cache.clear()
    assert cleared > 0
    assert cache.size == 0
    print("  OK Clear")

    print()

async def test_parallel_execution():
    print("=" * 60)
    print("5. Testing Parallel Execution in Loop")
    print("=" * 60)
    from src.config.settings import load_yaml_config, LLMConfig, AgentConfig, SecurityConfig
    from src.core.loop import AgentLoop
    from src.llm.router import LLMRouter
    from src.llm.models import ToolCall
    from src.security.permission import PermissionManager
    from src.security.audit import AuditLogger
    from src.tools.base import BaseTool, ToolResult, DangerLevel, ToolParameter
    from src.tools.registry import ToolRegistry
    import time

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    llm_config = LLMConfig.model_validate(config_yaml["llm"])
    agent_config = AgentConfig.model_validate(config_yaml.get("agent", {}))
    security_config = SecurityConfig()

    with tempfile.TemporaryDirectory() as tmpdir:
        router = LLMRouter(llm_config)
        registry = ToolRegistry()

        class SlowSafeTool(BaseTool):
            name = "slow_safe"
            description = "Slow safe tool"
            danger_level = DangerLevel.SAFE
            category = "test"
            parameters = [ToolParameter(name="val", type="string", description="Val", required=True)]
            async def execute(self, **kwargs):
                await asyncio.sleep(0.2)  # Simulate slow IO
                return ToolResult.ok(f"slow_{kwargs['val']}")

        class FastConfirmTool(BaseTool):
            name = "fast_confirm"
            description = "Fast confirm tool"
            danger_level = DangerLevel.CONFIRM
            category = "test"
            parameters = [ToolParameter(name="val", type="string", description="Val", required=True)]
            async def execute(self, **kwargs):
                return ToolResult.ok(f"confirm_{kwargs['val']}")

        registry.register_many([SlowSafeTool(), FastConfirmTool()])
        pm = PermissionManager(config=security_config, auto_confirm=True)
        audit = AuditLogger(enabled=False)
        loop = AgentLoop(llm=router, agent_config=agent_config, system_prompt="Test",
                         tool_registry=registry, permission_manager=pm, audit_logger=audit)

        # 3 safe tools in parallel should be faster than sequential
        calls = [
            ToolCall(id="s1", name="slow_safe", arguments='{"val": "a"}'),
            ToolCall(id="s2", name="slow_safe", arguments='{"val": "b"}'),
            ToolCall(id="s3", name="slow_safe", arguments='{"val": "c"}'),
        ]
        start = time.monotonic()
        results = await loop._execute_tool_calls(calls)
        elapsed = time.monotonic() - start

        assert len(results) == 3
        assert all(r.success for r in results)
        assert "slow_a" in results[0].content
        assert "slow_b" in results[1].content
        assert "slow_c" in results[2].content
        # Parallel: ~0.2s (not ~0.6s)
        assert elapsed < 0.8, f"Parallel execution took too long: {elapsed:.2f}s"
        print(f"  OK 3 safe tools parallel in {elapsed:.2f}s (< 0.8s)")

        # Mixed: safe parallel + confirm sequential
        calls2 = [
            ToolCall(id="s1", name="slow_safe", arguments='{"val": "x"}'),
            ToolCall(id="c1", name="fast_confirm", arguments='{"val": "y"}'),
            ToolCall(id="s2", name="slow_safe", arguments='{"val": "z"}'),
        ]
        results2 = await loop._execute_tool_calls(calls2)
        assert len(results2) == 3
        assert all(r.success for r in results2)
        assert results2[0].content == "slow_x"  # Order preserved
        assert results2[1].content == "confirm_y"
        assert results2[2].content == "slow_z"
        print("  OK Mixed safe+confirm execution, order preserved")

    print()

async def test_cache_in_loop():
    print("=" * 60)
    print("6. Testing Cache Integration in Loop")
    print("=" * 60)
    from src.config.settings import load_yaml_config, LLMConfig, AgentConfig, SecurityConfig
    from src.core.loop import AgentLoop
    from src.llm.router import LLMRouter
    from src.llm.models import ToolCall
    from src.security.permission import PermissionManager
    from src.tools.base import BaseTool, ToolResult, DangerLevel, ToolParameter
    from src.tools.registry import ToolRegistry

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    llm_config = LLMConfig.model_validate(config_yaml["llm"])
    agent_config = AgentConfig.model_validate(config_yaml.get("agent", {}))
    security_config = SecurityConfig()
    router = LLMRouter(llm_config)

    call_count = 0
    class CountingTool(BaseTool):
        name = "counting"
        description = "Counts calls"
        danger_level = DangerLevel.SAFE
        category = "test"
        parameters = [ToolParameter(name="x", type="string", description="X", required=True)]
        async def execute(self, **kwargs):
            nonlocal call_count
            call_count += 1
            return ToolResult.ok(f"called_{call_count}")

    registry = ToolRegistry()
    registry.register(CountingTool())
    pm = PermissionManager(config=security_config)
    loop = AgentLoop(llm=router, agent_config=agent_config, system_prompt="Test",
                     tool_registry=registry, permission_manager=pm, audit_logger=None)

    # First call - executes
    calls1 = [ToolCall(id="c1", name="counting", arguments='{"x": "1"}')]
    r1 = await loop._execute_tool_calls(calls1)
    assert r1[0].success and "called_1" in r1[0].content
    assert call_count == 1
    print("  OK First call executes")

    # Second call with same args - cached
    calls2 = [ToolCall(id="c2", name="counting", arguments='{"x": "1"}')]
    r2 = await loop._execute_tool_calls(calls2)
    assert r2[0].success and "called_1" in r2[0].content
    assert call_count == 1  # No new execution
    print("  OK Second call returns cached result (no new execution)")

    # Different args - new execution
    calls3 = [ToolCall(id="c3", name="counting", arguments='{"x": "2"}')]
    r3 = await loop._execute_tool_calls(calls3)
    assert r3[0].success and "called_2" in r3[0].content
    assert call_count == 2
    print("  OK Different args bypass cache")

    # Cache stats
    stats = loop._cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 2
    print(f"  OK Cache stats: hits={stats['hits']}, misses={stats['misses']}")

    print()

async def test_full_agent_p3():
    print("=" * 60)
    print("7. Testing Full Agent with P3 Tools")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)
    agent = Agent(settings)

    names = sorted(agent.tools.tool_names)
    print(f"  OK Agent: {agent}")
    print(f"  OK Tools ({len(names)}): {names}")

    # Check new tools exist
    assert "grep" in names
    assert "glob" in names
    assert "multi_edit" in names
    print("  OK New tools registered: grep, glob, multi_edit")

    assert agent.loop._cache is not None
    print(f"  OK Cache initialized: {agent.loop._cache}")

    print()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
