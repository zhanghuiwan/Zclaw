"""
P4 End-to-End Validation - Memory module.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_memory_types():
    print("=" * 60)
    print("1. Testing Memory Types")
    print("=" * 60)
    from src.memory.types import Memory, MemoryType

    m1 = Memory(content="Project uses Python 3.12", type=MemoryType.FACT, tags=["python", "config"])
    assert m1.type == MemoryType.FACT
    assert m1.content == "Project uses Python 3.12"
    print("  OK Memory creation")

    m1.touch()
    assert m1.access_count == 1
    assert m1.last_accessed != ""
    print("  OK touch() updates access")

    d = m1.to_dict()
    assert d["type"] == "fact"
    assert "python" in d["tags"]
    print("  OK to_dict()")

    m2 = Memory.from_dict(d)
    assert m2.content == m1.content
    assert m2.type == MemoryType.FACT
    print("  OK from_dict()")

    # All types
    for mt in MemoryType:
        m = Memory(content=f"Test {mt.value}", type=mt)
        assert m.type == mt
    print("  OK All memory types")

    print()


async def test_memory_store():
    print("=" * 60)
    print("2. Testing Memory Store")
    print("=" * 60)
    from src.memory.types import Memory, MemoryType
    from src.memory.store import MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(storage_path=tmpdir)
        assert store.count == 0

        m1 = store.add(Memory(content="Fact A", type=MemoryType.FACT))
        m2 = store.add(Memory(content="Event B", type=MemoryType.EPISODE, tags=["test"]))
        m3 = store.add(Memory(content="Preference C", type=MemoryType.PREFERENCE))
        assert store.count == 3
        print("  OK Add 3 memories")

        got = store.get(m1.id)
        assert got is not None and got.content == "Fact A"
        print("  OK Get by id")

        store.update(m1.id, content="Updated Fact A")
        updated = store.get(m1.id)
        assert updated.content == "Updated Fact A"
        print("  OK Update")

        # List with filter
        facts = store.list_all(mem_type="fact")
        assert len(facts) == 1 and facts[0].content == "Updated Fact A"
        print("  OK List by type")

        tagged = store.list_all(tag="test")
        assert len(tagged) == 1 and tagged[0].content == "Event B"
        print("  OK List by tag")

        # Search
        results = store.search("Fact")
        assert len(results) >= 1
        print(f"  OK Search: found {len(results)}")

        # Delete
        assert store.delete(m1.id)
        assert store.get(m1.id) is None
        assert store.count == 2
        print("  OK Delete")

        # Persistence
        store2 = MemoryStore(storage_path=tmpdir)
        assert store2.count == 2
        print("  OK Persistence across instances")

        # Clear
        store.clear()
        assert store.count == 0
        print("  OK Clear")

    print()


async def test_memory_retriever():
    print("=" * 60)
    print("3. Testing Memory Retriever")
    print("=" * 60)
    from src.memory.types import Memory, MemoryType
    from src.memory.store import MemoryStore
    from src.memory.retriever import MemoryRetriever

    with tempfile.TemporaryDirectory() as tmpdir:
        store = MemoryStore(storage_path=tmpdir)
        store.add(Memory(content="User prefers dark mode", type=MemoryType.PREFERENCE, tags=["ui"], importance=0.8))
        store.add(Memory(content="Project uses TypeScript", type=MemoryType.FACT, tags=["config"]))
        store.add(Memory(content="Fixed login bug yesterday", type=MemoryType.EPISODE, tags=["bug"], importance=0.6))

        retriever = MemoryRetriever(store)

        # Relevant retrieval
        results = retriever.retrieve("dark mode preference")
        assert len(results) >= 1
        assert any("dark mode" in m.content for m in results)
        print("  OK Relevant retrieval")

        # Recent
        recent = retriever.get_recent(limit=2)
        assert len(recent) == 2
        assert recent[0].created_at >= recent[1].created_at
        print("  OK Get recent")

        # By type
        facts = retriever.get_by_type("fact")
        assert len(facts) == 1 and "TypeScript" in facts[0].content
        print("  OK Get by type")

        # Format for context
        context = retriever.format_for_context(results)
        assert "## 相关记忆" in context
        assert "pref" in context or "fact" in context
        print(f"  OK Format for context:\n{context[:200]}")

    print()


async def test_memory_manager():
    print("=" * 60)
    print("4. Testing Memory Manager")
    print("=" * 60)
    from src.memory.manager import MemoryManager
    from src.config.settings import MemoryConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        config = MemoryConfig(storage_path=tmpdir)
        mgr = MemoryManager(config=config, session_id="test_p4")

        # remember
        m1 = mgr.remember("User likes Vim", mem_type="preference", tags=["editor"])
        assert m1.content == "User likes Vim"
        assert m1.type.value == "preference"
        print("  OK remember()")

        m2 = mgr.remember("Project: Zclaw", mem_type="fact", importance=0.9)
        m3 = mgr.remember("Fixed a critical bug", mem_type="episode")
        print("  OK remember() x3")

        assert mgr.store.count == 3
        print("  OK Store count")

        # recall
        results = mgr.recall("editor preference")
        assert len(results) >= 1
        print("  OK recall()")

        # get_context
        ctx = mgr.get_context("editor")
        assert "## 相关记忆" in ctx
        assert "Vim" in ctx
        print("  OK get_context()")

        # Stats
        stats = mgr.get_stats()
        assert stats["total"] == 3
        assert stats["by_type"]["preference"] == 1
        print(f"  OK Stats: {stats}")

        # forget
        assert mgr.forget(m1.id)
        assert mgr.store.count == 2
        print("  OK forget()")

        # Persistence
        mgr2 = MemoryManager(config=config, session_id="test_p4_2")
        assert mgr2.store.count == 2
        print("  OK Persistence across managers")

    print()


async def test_full_agent_p4():
    print("=" * 60)
    print("5. Testing Full Agent with Memory")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)

    with tempfile.TemporaryDirectory() as tmpdir:
        settings.memory.storage_path = tmpdir
        agent = Agent(settings)

        assert agent.memory is not None
        print(f"  OK Agent: {agent}")
        print(f"  OK Memory: {agent.memory}")

        # Use memory
        agent.memory.remember("Test session memory", tags=["session"])
        assert agent.memory.store.count == 1
        print("  OK Memory accessible from agent")

        # Reinitialize and check persistence
        agent2 = Agent(settings)
        assert agent2.memory.store.count == 1
        print("  OK Memory persists across agent instances")

    print()


async def main():
    print()
    print("=" * 60)
    print("        Zclaw P4 - Memory Module Validation")
    print("=" * 60)
    print()

    tests = [
        test_memory_types,
        test_memory_store,
        test_memory_retriever,
        test_memory_manager,
        test_full_agent_p4,
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
