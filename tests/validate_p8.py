"""
P8 - V4 记忆系统验证

覆盖：
1. 记忆提取器
2. L0-L4 分层和 MemoryCoordinator
3. 记忆工具
4. extract_and_store 分发逻辑
5. Agent 集成

运行方式: python -m pytest tests/validate_p8.py -v
         或: python tests/validate_p8.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.models import Message, MessageRole, StreamEvent, StreamEventType
from src.memory.extractor import BaseExtractor, ExtractedMemory, LLMExtractor, MockExtractor


async def test_extractor_base():
    print("=" * 60)
    print("1. 测试记忆提取器")
    print("=" * 60)

    ext = MockExtractor()
    assert isinstance(ext, BaseExtractor)
    assert await ext.extract([]) == []
    print("  OK MockExtractor 基础行为")

    preference_msgs = [
        Message(role=MessageRole.USER, content="我喜欢用 TypeScript 写代码"),
        Message(role=MessageRole.ASSISTANT, content="好的，我会用 TypeScript"),
    ]
    preference_result = await ext.extract(preference_msgs)
    assert preference_result
    assert preference_result[0].type == "preference"
    assert "TypeScript" in preference_result[0].content
    print("  OK 偏好提取")

    fact_msgs = [Message(role=MessageRole.USER, content="我们项目使用的是 Python 3.12")]
    fact_result = await ext.extract(fact_msgs)
    assert fact_result
    assert fact_result[0].type == "fact"
    print("  OK 事实提取")

    fixed = [
        ExtractedMemory(type="skill", content="学会了 MCP 协议", tags=["mcp"], importance=0.9),
        ExtractedMemory(type="episode", content="修复过 Web 权限确认", tags=["web"], importance=0.7),
    ]
    fixed_ext = MockExtractor(fixed_results=fixed)
    assert await fixed_ext.extract(fact_msgs) == fixed
    print("  OK 固定结果注入")

    llm_ext = LLMExtractor(base_url="http://localhost:11434/v1", api_key="test", model="qwen-turbo")
    parsed = llm_ext._parse_response(
        '```json\n[{"type":"fact","content":"项目使用 FastAPI","tags":["project"],"importance":0.8}]\n```'
    )
    assert len(parsed) == 1
    assert parsed[0].type == "fact"
    assert parsed[0].content == "项目使用 FastAPI"
    assert llm_ext._parse_response("无 JSON") == []
    print("  OK LLMExtractor JSON 解析")
    print()


async def test_memory_coordinator_layers():
    print("=" * 60)
    print("2. 测试 V4 MemoryCoordinator L0-L4")
    print("=" * 60)

    from src.memory.config import V4MemoryConfig
    from src.memory.coordinator import MemoryCoordinator

    with tempfile.TemporaryDirectory() as tmpdir:
        config = V4MemoryConfig(storage_path=tmpdir, vector_store_enabled=False)
        coord = MemoryCoordinator(
            storage_root=config.resolve_storage_path(),
            session_id="p8_layers",
            config=config,
        )

        entry = coord.perceive("你好", "你好呀")
        assert entry.turn_index == 1
        assert coord.perceptual.get_current().user_input == "你好"
        print("  OK L0 perceptual")

        snap = coord.update_working_context(
            task_description="梳理项目",
            active_files=["src/core/agent.py"],
            pending_goals=["阅读入口"],
        )
        assert snap.task_description == "梳理项目"
        coord.complete_goal("阅读入口")
        assert "阅读入口" in coord.working.current.completed_goals
        print("  OK L1 working")

        coord.archive_turn(role="user", content="用户提到 FastAPI")
        coord.archive_turn(role="assistant", content="记录 FastAPI 项目事实")
        results = coord.search_episodic(query="FastAPI", limit=5)
        assert len(results) == 2
        history = coord.get_session_history("p8_layers")
        assert len(history) == 2
        print("  OK L2 episodic")

        coord.semantic.update_user_profile(name="Tom", preferred_language="zh-CN")
        coord.semantic.update_project_profile(name="Zclaw", tech_stack=["Python", "FastAPI"])
        coord.semantic.set_preference("editor", "Vim")
        semantic_ctx = coord.semantic.format_for_system_prompt()
        assert "Tom" in semantic_ctx
        assert "Zclaw" in semantic_ctx
        assert "Vim" in semantic_ctx
        print("  OK L3 semantic")

        procedural_ctx = coord.procedural.format_for_system_prompt()
        assert "Behavior Rules" in procedural_ctx
        print("  OK L4 procedural")

        system_ctx = coord.build_system_prompt_context()
        assert "Behavior Rules" in system_ctx
        assert "Tom" in system_ctx
        assert "Current Task" in system_ctx
        print("  OK system prompt context")
    print()


async def test_memory_tools():
    print("=" * 60)
    print("3. 测试 V4 记忆工具")
    print("=" * 60)

    from src.memory.config import V4MemoryConfig
    from src.memory.coordinator import MemoryCoordinator
    from src.memory.tools.episodic_search import GetSessionHistoryTool, SearchConversationHistoryTool
    from src.memory.tools.memory_tools import SetPreferenceTool, UpdateSemanticMemoryTool

    with tempfile.TemporaryDirectory() as tmpdir:
        config = V4MemoryConfig(storage_path=tmpdir, vector_store_enabled=False)
        coord = MemoryCoordinator(
            storage_root=config.resolve_storage_path(),
            session_id="p8_tools",
            config=config,
        )
        coord.archive_turn(role="user", content="我喜欢深色主题")
        coord.archive_turn(role="assistant", content="已记录深色主题偏好")

        search_result = await SearchConversationHistoryTool(coord.episodic).execute(query="深色", limit=5)
        assert search_result.success
        assert "深色" in search_result.content
        print("  OK search_conversation_history")

        history_result = await GetSessionHistoryTool(coord.episodic).execute(session_id="p8_tools", limit=10)
        assert history_result.success
        assert "p8_tools" in history_result.content
        print("  OK get_session_history")

        update_result = await UpdateSemanticMemoryTool(coord.semantic).execute(
            category="project",
            data={"name": "Zclaw", "architecture": "local agent runtime"},
        )
        assert update_result.success
        assert coord.semantic.get_project_profile().name == "Zclaw"
        print("  OK update_memory")

        pref_result = await SetPreferenceTool(coord.semantic).execute(key="theme", value="dark")
        assert pref_result.success
        assert coord.semantic.get_preference("theme") == "dark"
        print("  OK set_preference")
    print()


async def test_extract_and_store():
    print("=" * 60)
    print("4. 测试 extract_and_store 分发")
    print("=" * 60)

    from src.memory.config import V4MemoryConfig
    from src.memory.coordinator import MemoryCoordinator

    extracted = [
        ExtractedMemory(type="preference", content="用户喜欢 Vim", tags=["editor"], importance=0.8),
        ExtractedMemory(type="fact", content="项目使用 FastAPI", tags=["project"], importance=0.7),
        ExtractedMemory(type="episode", content="修复了 Web 权限回调", tags=["web"], importance=0.6),
        ExtractedMemory(type="skill", content="掌握 V4 记忆分层", tags=["memory"], importance=0.6),
    ]
    extractor = MockExtractor(fixed_results=extracted)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = V4MemoryConfig(storage_path=tmpdir, vector_store_enabled=False)
        coord = MemoryCoordinator(
            storage_root=config.resolve_storage_path(),
            session_id="p8_extract",
            config=config,
        )

        stored = await coord.extract_and_store(
            [
                Message(role=MessageRole.USER, content="请记住这些内容"),
                Message(role=MessageRole.ASSISTANT, content="好的"),
            ],
            extractor,
        )

        assert len(stored) == 4
        assert coord.semantic.get_user_profile().preferences
        assert "项目使用 FastAPI" in coord.working.current.extracted_facts
        assert any("[skill] 掌握 V4 记忆分层" == fact for fact in coord.working.current.extracted_facts)
        assert coord.episodic.search(query="Web 权限", limit=5)
        print("  OK extracted memories routed to L1/L2/L3")
    print()


async def test_agent_memory_integration():
    print("=" * 60)
    print("5. 测试 Agent 记忆集成")
    print("=" * 60)

    from src.config.settings import ProviderConfig, Settings
    from src.core.agent import Agent

    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings()
        settings.llm.providers = {
            "test": ProviderConfig(
                base_url="http://localhost:11434/v1",
                api_key="test",
                model="test-model",
                supports_tools=True,
            )
        }
        settings.llm.default_provider = "test"
        settings.memory.storage_path = tmpdir
        settings.mcp.enabled = False
        settings.skills.enabled = False
        settings.security.audit_log = False

        agent = Agent(settings)
        assert agent.memory is not None
        assert agent.tools.has("search_conversation_history")
        assert agent.tools.has("get_session_history")
        assert agent.tools.has("update_memory")
        assert agent.tools.has("set_preference")
        assert agent.memory.build_system_prompt_context()
        print("  OK Agent 注册 V4 记忆与工具")
    print()


async def test_agent_stream_memory_extraction_background():
    print("=" * 60)
    print("6. 测试流式记忆后台提取")
    print("=" * 60)

    from src.config.settings import ProviderConfig, Settings
    from src.core.agent import Agent

    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings()
        settings.llm.providers = {
            "test": ProviderConfig(
                base_url="http://localhost:11434/v1",
                api_key="test",
                model="test-model",
                supports_tools=True,
            )
        }
        settings.llm.default_provider = "test"
        settings.memory.storage_path = tmpdir
        settings.mcp.enabled = False
        settings.skills.enabled = False
        settings.security.audit_log = False

        agent = Agent(settings)
        extract_started = asyncio.Event()
        extract_continue = asyncio.Event()
        extract_finished = asyncio.Event()

        async def slow_extract_and_store(messages, extractor):
            extract_started.set()
            await extract_continue.wait()
            extract_finished.set()
            return []

        async def fake_run_stream(user_input):
            yield StreamEvent(type=StreamEventType.CONTENT_DELTA, data="好的")
            yield StreamEvent(type=StreamEventType.DONE, data=None)

        agent.memory.extractor = object()
        agent.memory.extract_and_store = AsyncMock(side_effect=slow_extract_and_store)
        agent.loop.run_stream = MagicMock(side_effect=fake_run_stream)

        events = []
        async for event in agent.chat_stream("测试后台记忆"):
            events.append(event.type)

        assert events == [StreamEventType.CONTENT_DELTA, StreamEventType.DONE]
        await asyncio.wait_for(extract_started.wait(), timeout=1)
        assert not extract_finished.is_set()

        extract_continue.set()
        await asyncio.wait_for(extract_finished.wait(), timeout=1)
        assert agent.memory.extract_and_store.await_count == 1
        print("  OK chat_stream 不等待记忆提取完成")
    print()


async def main():
    tests = [
        test_extractor_base,
        test_memory_coordinator_layers,
        test_memory_tools,
        test_extract_and_store,
        test_agent_memory_integration,
        test_agent_stream_memory_extraction_background,
    ]
    passed = 0
    failed = 0
    failures = []
    print("=" * 60)
    print("        Zclaw P8 - V4 记忆系统验证")
    print("=" * 60)
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as exc:
            failed += 1
            failures.append((test.__name__, str(exc)))
            print(f"  FAILED {test.__name__}: {exc}")

    print("=" * 60)
    print(f"结果: {passed}/{len(tests)} 通过, {failed} 失败")
    print("=" * 60)
    if failures:
        for name, error in failures:
            print(f"  - {name}: {error}")
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
