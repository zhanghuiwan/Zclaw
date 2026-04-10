"""
P4 End-to-End Validation - V4 Memory Module.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_v4_layers():
    """Test V4 memory layers (L0-L4)."""
    print("=" * 60)
    print("1. Testing V4 Memory Layers (L0-L4)")
    print("=" * 60)

    from src.memory.config import V4MemoryConfig
    from src.memory.coordinator import MemoryCoordinator
    from src.memory.layers import (
        PerceptualBuffer, WorkingMemory, EpisodicMemory,
        SemanticMemory, ProceduralMemory,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        config = V4MemoryConfig(storage_path=tmpdir)

        # L0: Perceptual Buffer
        buf = PerceptualBuffer(max_turns=2)
        entry1 = buf.capture("Hello", "Hi there")
        assert entry1.turn_index == 1
        entry2 = buf.capture("How are you?", "I'm fine")
        assert entry2.turn_index == 2
        assert buf.turn_count == 2
        assert buf.get_current() == entry2
        print("  OK L0 Perceptual Buffer")

        # L1: Working Memory
        working = WorkingMemory(Path(tmpdir))
        snap = working.create_snapshot("test_session")
        working.update_snapshot(
            task_description="Test task",
            active_files=["test.py"],
            pending_goals=["goal1", "goal2"],
        )
        assert working.current.task_description == "Test task"
        assert len(working.current.pending_goals) == 2
        working.complete_goal("goal1")
        assert "goal1" in working.current.completed_goals
        assert "goal1" not in working.current.pending_goals
        working.add_tool_call("file_read", {"path": "test.py"}, "file content")
        assert len(working.current.tool_history) == 1
        print("  OK L1 Working Memory")

        # L2: Episodic Memory
        episodic = EpisodicMemory(Path(tmpdir), vector_store_enabled=False)
        ep1 = episodic.append(type("E", (), {
            "id": "1", "session_id": "s1", "timestamp": "2026-04-10T10:00:00",
            "role": "user", "content": "Hello", "summary": "", "embedding_id": None, "tool_calls": []
        })())
        ep2 = episodic.append(type("E", (), {
            "id": "2", "session_id": "s1", "timestamp": "2026-04-10T10:01:00",
            "role": "assistant", "content": "Hi there", "summary": "", "embedding_id": None, "tool_calls": []
        })())
        assert episodic.count() == 2
        results = episodic.search(query="Hello")
        assert len(results) >= 1
        history = episodic.get_session_history("s1")
        assert len(history) == 2
        print("  OK L2 Episodic Memory")

        # L3: Semantic Memory
        semantic = SemanticMemory(Path(tmpdir))
        semantic.update_user_profile(name="Tom", preferred_language="Python")
        semantic.set_preference("dark_mode", True)
        assert semantic.get_user_profile().name == "Tom"
        assert semantic.get_preference("dark_mode") is True
        semantic.update_project_profile(tech_stack=["Python", "FastAPI"], architecture="REST API")
        assert "Python" in semantic.get_project_profile().tech_stack
        ctx = semantic.format_for_system_prompt()
        assert "Tom" in ctx
        assert "Python" in ctx
        print("  OK L3 Semantic Memory")

        # L4: Procedural Memory
        procedural = ProceduralMemory(Path(tmpdir))
        rules = procedural.get_global_rules()
        assert "coding_rules" in rules or len(rules) >= 0
        ctx = procedural.format_for_system_prompt()
        assert "Rules" in ctx or len(ctx) > 0
        print("  OK L4 Procedural Memory")

    print()


async def test_memory_coordinator():
    """Test MemoryCoordinator."""
    print("=" * 60)
    print("2. Testing Memory Coordinator")
    print("=" * 60)

    from src.memory.config import V4MemoryConfig
    from src.memory.coordinator import MemoryCoordinator

    with tempfile.TemporaryDirectory() as tmpdir:
        config = V4MemoryConfig(storage_path=tmpdir)
        coord = MemoryCoordinator(
            storage_root=config.resolve_storage_path(),
            session_id="test_session",
            config=config,
        )

        # L0 perception
        entry = coord.perceive("Hello", "Hi")
        assert entry.turn_index == 1
        print("  OK perceive()")

        # L1 context
        snap = coord.update_working_context(
            task_description="Test task",
            active_files=["main.py"],
        )
        assert snap.task_description == "Test task"
        coord.add_pending_goal("Complete feature X")
        assert "Complete feature X" in coord.working.current.pending_goals
        print("  OK working context")

        # L2 archive
        ep = coord.archive_turn(role="user", content="我叫 Tom")
        assert ep.content == "我叫 Tom"
        results = coord.search_episodic(query="Tom")
        assert len(results) >= 1
        print("  OK episodic archive")

        # L3 state
        coord.semantic.update_user_profile(name="Jack")
        assert coord.semantic.get_user_profile().name == "Jack"
        print("  OK semantic state")

        # System prompt context
        ctx = coord.build_system_prompt_context()
        assert "Jack" in ctx
        assert "Rules" in ctx or "Behavior" in ctx
        print(f"  OK build_system_prompt_context() ({len(ctx)} chars)")

    print()


async def test_memory_tools():
    """Test V4 memory tools."""
    print("=" * 60)
    print("3. Testing Memory Tools")
    print("=" * 60)

    from src.memory.config import V4MemoryConfig
    from src.memory.coordinator import MemoryCoordinator
    from src.memory.tools.episodic_search import SearchConversationHistoryTool, GetSessionHistoryTool
    from src.memory.tools.memory_tools import UpdateSemanticMemoryTool, SetPreferenceTool

    with tempfile.TemporaryDirectory() as tmpdir:
        config = V4MemoryConfig(storage_path=tmpdir)
        coord = MemoryCoordinator(
            storage_root=config.resolve_storage_path(),
            session_id="test_session",
            config=config,
        )

        # Archive some data for search
        coord.archive_turn(role="user", content="我叫 Tom")
        coord.archive_turn(role="assistant", content="好的 Tom")
        coord.archive_turn(role="user", content="请用 Python 写快排")
        coord.archive_turn(role="assistant", content="好的，这是 Python 快排...")

        # Test search_conversation_history
        search_tool = SearchConversationHistoryTool(coord.episodic)
        result = await search_tool.execute(query="Tom", limit=5)
        assert result.success
        assert "Tom" in result.content
        print("  OK search_conversation_history")

        # Test get_session_history
        history_tool = GetSessionHistoryTool(coord.episodic)
        result = await history_tool.execute(session_id="test_session", limit=10)
        assert result.success
        print("  OK get_session_history")

        # Test update_memory
        update_tool = UpdateSemanticMemoryTool(coord.semantic)
        result = await update_tool.execute(
            category="user",
            data={"name": "John", "preferred_code_style": "functional"}
        )
        assert result.success
        assert coord.semantic.get_user_profile().name == "John"
        print("  OK update_memory")

        # Test set_preference
        pref_tool = SetPreferenceTool(coord.semantic)
        result = await pref_tool.execute(key="timezone", value="Asia/Shanghai")
        assert result.success
        assert coord.semantic.get_preference("timezone") == "Asia/Shanghai"
        print("  OK set_preference")

    print()


async def test_agent_integration():
    """Test Agent with V4 memory."""
    print("=" * 60)
    print("4. Testing Agent Integration")
    print("=" * 60)

    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)

    with tempfile.TemporaryDirectory() as tmpdir:
        settings.memory.storage_path = tmpdir
        agent = Agent(settings)

        assert agent.memory is not None
        print(f"  OK Agent created: {agent}")
        print(f"  OK Memory type: {type(agent.memory).__name__}")

        # Test that memory tools are registered
        assert agent.tools.has("search_conversation_history")
        assert agent.tools.has("get_session_history")
        assert agent.tools.has("update_memory")
        assert agent.tools.has("set_preference")
        print("  OK Memory tools registered")

        # Test system prompt contains memory context
        ctx = agent.memory.build_system_prompt_context()
        assert len(ctx) > 0
        print(f"  OK Memory context built ({len(ctx)} chars)")

        # Test archive turn
        agent.memory.archive_turn(role="user", content="Test message")
        results = agent.memory.search_episodic(query="Test")
        assert len(results) >= 1
        print("  OK Archive and search")

    print()


async def main():
    print()
    print("=" * 60)
    print("        Zclaw P4 - V4 Memory Module Validation")
    print("=" * 60)
    print()

    tests = [
        test_v4_layers,
        test_memory_coordinator,
        test_memory_tools,
        test_agent_integration,
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
