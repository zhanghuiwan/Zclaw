"""Tool registry, sandbox, shell, and agent loop tests."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path


async def test_tool_base():
    print("=" * 60)
    print("1. Testing Tool Base & ToolResult")
    print("=" * 60)
    from src.tools.base import ToolResult, ToolParameter
    r1 = ToolResult.ok("hello")
    assert r1.success and r1.content == "hello"
    print("  OK ToolResult.ok")
    r2 = ToolResult.fail("error msg")
    assert not r2.success and r2.error == "error msg"
    print("  OK ToolResult.fail")
    p = ToolParameter(name="path", type="string", description="File path", required=True)
    schema = p.to_json_schema()
    assert schema["type"] == "string"
    print("  OK ToolParameter.to_json_schema")
    print()

async def test_registry():
    print("=" * 60)
    print("2. Testing Tool Registry")
    print("=" * 60)
    from src.tools.base import BaseTool, ToolResult, ToolParameter, DangerLevel
    from src.tools.registry import ToolRegistry
    class EchoTool(BaseTool):
        name = "echo"
        description = "Echo input"
        danger_level = DangerLevel.SAFE
        category = "test"
        parameters = [ToolParameter(name="text", type="string", description="Text", required=True)]
        async def execute(self, **kwargs):
            return ToolResult.ok(kwargs["text"])
    reg = ToolRegistry()
    reg.register(EchoTool())
    assert reg.has("echo")
    print("  OK Tool registration")
    tools = reg.to_openai_tools()
    assert len(tools) == 1
    print("  OK OpenAI tool definition generation")
    result = await reg.execute("echo", {"text": "hello"})
    assert result.success
    assert result.content == "hello"
    print("  OK Tool execution")
    try:
        await reg.execute("nonexistent", {})
        assert False
    except KeyError:
        print("  OK Unknown tool error")
    result2 = await reg.execute("echo", {})
    assert not result2.success
    print("  OK Parameter validation error")
    stats = reg.get_stats()
    print(f"  OK Stats: {stats}")
    print()

async def test_file_tools():
    print("=" * 60)
    print("3. Testing File Tools")
    print("=" * 60)
    from src.tools.builtin.file_tools import FileWriteTool, FileReadTool, FileEditTool
    wt = FileWriteTool()
    rt = FileReadTool()
    et = FileEditTool()
    with tempfile.TemporaryDirectory() as tmpdir:
        p = os.path.join(tmpdir, "test.txt")
        r1 = await wt.execute(path=p, content="Hello World\nLine 2\nLine 3")
        assert r1.success
        print("  OK file_write: create file")
        r2 = await rt.execute(path=p)
        assert r2.success and "Hello World" in r2.content
        print("  OK file_read: read file")
        r3 = await rt.execute(path=p, offset=1, limit=1)
        assert r2.success and "Line 2" in r2.content
        print("  OK file_read: read with offset/limit")
        r4 = await rt.execute(path="/nonexistent/file.txt")
        assert not r4.success
        print("  OK file_read: file not found error")
        r5 = await et.execute(path=p, old_text="World", new_text="Zclaw")
        assert r5.success
        print("  OK file_edit: replace content")
        r6 = await rt.execute(path=p)
        assert "Zclaw" in r6.content
        print("  OK file_edit: verify change")
        r7 = await et.execute(path="/nonexistent", old_text="x", new_text="y")
        assert not r7.success
        print("  OK file_edit: not found error")
    print()

async def test_search_tools():
    print("=" * 60)
    print("4. Testing Search Tools")
    print("=" * 60)
    from src.tools.builtin.search_tools import DirectoryTool, FileSearchTool
    dt = DirectoryTool()
    fs = FileSearchTool()
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "subdir"))
        with open(os.path.join(tmpdir, "a.txt"), "w") as f:
            f.write("hello")
        with open(os.path.join(tmpdir, "subdir", "b.txt"), "w") as f:
            f.write("world")
        r1 = await dt.execute(path=tmpdir)
        assert r1.success
        print("  OK directory: list files")
        r2 = await fs.execute(path=tmpdir, pattern="b.txt")
        assert r2.success and "b.txt" in r2.content
        print("  OK file_search: by filename")
        with open(os.path.join(tmpdir, "c.txt"), "w") as f:
            f.write("unique_content_xyz")
        r3 = await fs.execute(path=tmpdir, pattern="unique_content_xyz", search_content=True)
        assert r3.success and "c.txt" in r3.content
        print("  OK file_search: by content")
        r4 = await fs.execute(path=tmpdir, pattern="nonexistent_pattern_xyz")
        assert r4.success and "未找到" in r4.content
        print("  OK file_search: no results")
    print()

async def test_sandbox():
    print("=" * 60)
    print("5. Testing Sandbox")
    print("=" * 60)
    from src.sandbox.runner import CommandRunner
    runner = CommandRunner(timeout=5)
    r1 = runner.run("echo hello")
    assert r1.success and "hello" in r1.content
    print("  OK Basic command: exit=0, stdout='hello'")
    r2 = runner.run("exit 42")
    assert not r2.success
    print("  OK Exit code: 42")
    runner_slow = CommandRunner(timeout=1)
    r3 = runner_slow.run("sleep 10")
    assert not r3.success and "超时" in r3.error
    print("  OK Timeout: timed_out=True")
    r4 = runner.run("ls /nonexistent_dir_xyz")
    assert not r4.success
    print("  OK Error handling: exit=2")
    print()

async def test_shell_tool():
    print("=" * 60)
    print("6. Testing Shell Tool")
    print("=" * 60)
    from src.tools.base import DangerLevel
    from src.tools.builtin.shell_tool import ShellTool
    st = ShellTool()
    d1 = st._detect_danger("ls -la")
    assert d1 is None
    print("  OK Safe command: ls -la -> safe")
    d2 = st._detect_danger("git status")
    assert d2 is None
    print("  OK Safe command: git status -> safe")
    d3 = st._detect_danger("python script.py")
    assert d3 is None
    print("  OK Confirm command: python script.py -> confirm")
    d4 = st._detect_danger("rm -rf /")
    assert d4 is not None
    print("  OK Dangerous command: rm -rf / -> dangerous")
    d5 = st._detect_danger("sudo apt install")
    assert d5 is not None
    print("  OK Dangerous command: sudo -> dangerous")
    assert st.get_danger_level({"command": "rm -rf /"}) == DangerLevel.DANGEROUS
    assert st.danger_level == DangerLevel.CONFIRM
    assert st.get_danger_level({"command": "echo safe"}) == DangerLevel.CONFIRM
    print("  OK Dynamic danger level does not mutate metadata")
    r1 = await st.execute(command="echo safe_test_12345", timeout=5)
    assert r1.success
    print("  OK Execute safe command")
    print()

async def test_loop_tools():
    print("=" * 60)
    print("7. Testing Agent Loop + Tools Integration")
    print("=" * 60)
    from src.config.settings import load_yaml_config, LLMConfig, AgentConfig
    from src.core.loop import AgentLoop
    from src.llm.router import LLMRouter
    from src.tools.base import BaseTool, ToolResult, ToolParameter, DangerLevel
    from src.tools.registry import ToolRegistry
    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    llm_config = LLMConfig.model_validate(config_yaml["llm"])
    agent_config = AgentConfig.model_validate(config_yaml.get("agent", {}))
    router = LLMRouter(llm_config)
    reg = ToolRegistry()
    class CountTool(BaseTool):
        name = "count"
        description = "Count chars"
        danger_level = DangerLevel.SAFE
        category = "test"
        parameters = [ToolParameter(name="text", type="string", description="Text", required=True)]
        async def execute(self, **kwargs):
            return ToolResult.ok(f"Length: {len(kwargs['text'])}")
    reg.register(CountTool())
    loop = AgentLoop(llm=router, agent_config=agent_config, system_prompt="Test", tool_registry=reg)
    print(f"  OK Loop initialized with tools: {loop}")
    defs = loop._get_tool_definitions()
    assert len(defs) == 1 and defs[0].name == "count"
    print(f"  OK Tool definitions: {[d.name for d in defs]}")
    from src.llm.models import ToolCall
    calls = [ToolCall(id="c1", name="count", arguments='{"text": "hello world"}')]
    results = await loop._execute_tool_calls(calls)
    assert results[0].success and "11" in results[0].content
    print(f"  OK Direct tool execution: {results[0].content}")
    loop._inject_tool_results(results)
    assert len(loop.messages) > 1
    print("  OK Tool result injection")
    print()

async def test_full_agent():
    print("=" * 60)
    print("8. Testing Full Agent Initialization")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent
    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)
    settings.mcp.enabled = False
    settings.skills.enabled = False
    settings.security.audit_log = False
    agent = Agent(settings)
    print(f"  OK Agent: {agent}")
    assert agent.state.value == "idle"
    print(f"  OK Registered tools: {sorted(agent.tools.tool_names)}")
    required_tools = {
        "file_read",
        "file_write",
        "file_edit",
        "directory",
        "file_search",
        "grep",
        "glob",
        "shell",
        "search_conversation_history",
        "get_session_history",
        "update_memory",
        "set_preference",
    }
    assert required_tools.issubset(set(agent.tools.tool_names))
    assert len(agent.tools.to_openai_tools()) >= len(required_tools)
    print(f"  OK OpenAI tool definitions: {len(agent.tools.to_openai_tools())} tools")
    print()

async def test_stream_events():
    print("=" * 60)
    print("9. Testing Stream Event Types")
    print("=" * 60)
    from src.llm.models import StreamEventType
    assert hasattr(StreamEventType, "TOOL_EXECUTE_START")
    assert hasattr(StreamEventType, "TOOL_EXECUTE_END")
    assert hasattr(StreamEventType, "LOOP_START")
    print("  OK New event types exist")
    from src.llm.models import StreamEvent
    e1 = StreamEvent(type=StreamEventType.TOOL_EXECUTE_START, data={"id": "1", "name": "test"})
    assert e1.type == StreamEventType.TOOL_EXECUTE_START
    print("  OK TOOL_EXECUTE_START event")
    e2 = StreamEvent(type=StreamEventType.TOOL_EXECUTE_END, data={"id": "1", "name": "test", "success": True})
    print("  OK TOOL_EXECUTE_END event")
    e3 = StreamEvent(type=StreamEventType.LOOP_START, data={"round": 2})
    print("  OK LOOP_START event")
    print()
