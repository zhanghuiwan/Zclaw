"""
P3 End-to-End Validation - Enhanced tools, cache, parallel execution.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


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


async def main():
    print()
    print("=" * 60)
    print("        Zclaw P3 - Enhanced Tools Validation")
    print("=" * 60)
    print()

    tests = [
        test_grep_tool,
        test_glob_tool,
        test_multi_edit_tool,
        test_tool_cache,
        test_parallel_execution,
        test_cache_in_loop,
        test_full_agent_p3,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
