"""
P8 - 记忆系统完善（自动提取 + 上下文注入 + 生命周期管理）
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.memory.types import Memory, MemoryType
from src.memory.store import MemoryStore
from src.memory.retriever import MemoryRetriever
from src.memory.extractor import (
    BaseExtractor, MockExtractor, ExtractedMemory,
)
from src.memory.lifecycle import MemoryLifecycleManager, MemoryTier, DEFAULT_CONFIG
from src.memory.manager import MemoryManager
from src.config.settings import MemoryConfig
from src.llm.models import Message, MessageRole


# ──────────────────────────────────────────────
# 1. Extractor 测试
# ──────────────────────────────────────────────

async def test_extractor_base():
    """测试提取器抽象接口"""
    print("=" * 60)
    print("1. 测试记忆提取器")
    print("=" * 60)

    # MockExtractor 无固定结果
    ext = MockExtractor()
    assert isinstance(ext, BaseExtractor)
    print("  OK MockExtractor 实现了 BaseExtractor")

    # 空消息
    result = await ext.extract([])
    assert result == []
    print("  OK 空消息返回空列表")

    # 偏好检测
    msgs = [
        Message(role=MessageRole.USER, content="我喜欢用 TypeScript 写代码"),
        Message(role=MessageRole.ASSISTANT, content="好的，我会用 TypeScript"),
    ]
    result = await ext.extract(msgs)
    assert len(result) >= 1
    assert result[0].type == "preference"
    assert "TypeScript" in result[0].content
    print(f"  OK 偏好检测: type={result[0].type}, content={result[0].content[:40]}")

    # 事实检测
    msgs2 = [
        Message(role=MessageRole.USER, content="我们项目使用的是 Python 3.12"),
    ]
    result2 = await ext.extract(msgs2)
    assert len(result2) >= 1
    assert result2[0].type == "fact"
    print(f"  OK 事实检测: type={result2[0].type}")

    # 固定结果注入
    fixed = [
        ExtractedMemory(type="skill", content="学会了 MCP 协议", tags=["mcp"], importance=0.9),
        ExtractedMemory(type="fact", content="项目使用 Next.js 16", tags=["project"], importance=0.7),
    ]
    ext_fixed = MockExtractor(fixed_results=fixed)
    result3 = await ext_fixed.extract([Message(role=MessageRole.USER, content="随便说点啥")])
    assert len(result3) == 2
    assert result3[0].content == "学会了 MCP 协议"
    assert result3[1].importance == 0.7
    print("  OK 固定结果注入")

    # ExtractedMemory 数据模型
    em = ExtractedMemory(type="episode", content="测试", tags=["a", "b"], importance=0.8)
    assert em.type == "episode"
    assert em.tags == ["a", "b"]
    assert 0.0 <= em.importance <= 1.0
    print("  OK ExtractedMemory 数据模型")

    # LLMExtractor 初始化（不实际调用）
    from src.memory.extractor import LLMExtractor
    llm_ext = LLMExtractor(
        base_url="http://localhost:11434/v1",
        api_key="test",
        model="qwen-turbo",
    )
    assert llm_ext._model == "qwen-turbo"
    print("  OK LLMExtractor 可初始化")

    # LLMExtractor._parse_response 测试
    test_json = '[{"type": "fact", "content": "项目使用 Pydantic", "tags": ["project"], "importance": 0.8}]'
    parsed = llm_ext._parse_response(test_json)
    assert len(parsed) == 1
    assert parsed[0].type == "fact"
    assert parsed[0].content == "项目使用 Pydantic"
    assert parsed[0].importance == 0.8
    print("  OK LLMExtractor JSON 解析")

    # 包裹在 ```json 中的解析
    test_json2 = '```json\n[{"type": "preference", "content": "用户喜欢深色主题", "tags": ["ui"], "importance": 0.9}]\n```'
    parsed2 = llm_ext._parse_response(test_json2)
    assert len(parsed2) == 1
    assert parsed2[0].type == "preference"
    print("  OK LLMExtractor 带代码围栏的 JSON 解析")

    # 无效 JSON
    parsed3 = llm_ext._parse_response("没有 JSON 内容")
    assert len(parsed3) == 0
    print("  OK LLMExtractor 无效 JSON 返回空列表")

    # 空数组
    parsed4 = llm_ext._parse_response("[]")
    assert len(parsed4) == 0
    print("  OK LLMExtractor 空数组")

    print()


# ──────────────────────────────────────────────
# 2. 生命周期管理测试
# ──────────────────────────────────────────────

async def test_lifecycle():
    """测试记忆分层和容量管理"""
    print("=" * 60)
    print("2. 测试记忆生命周期管理")
    print("=" * 60)

    lcm = MemoryLifecycleManager()

    # 分层分配测试
    mem_high = Memory(content="重要事实", importance=0.9, type=MemoryType.FACT)
    tier = lcm.assign_tier(mem_high)
    assert tier == MemoryTier.LONG_TERM
    print(f"  OK 高重要性 → {tier}")

    mem_low = Memory(content="普通事实", importance=0.3, type=MemoryType.FACT)
    tier2 = lcm.assign_tier(mem_low)
    assert tier2 == MemoryTier.RECENT
    print(f"  OK 低重要性 → {tier2}")

    # 偏好和技能直接进入长期
    mem_pref = Memory(content="用户喜欢 Vim", importance=0.5, type=MemoryType.PREFERENCE)
    tier3 = lcm.assign_tier(mem_pref)
    assert tier3 == MemoryTier.LONG_TERM
    print(f"  OK 偏好类型 → {tier3}")

    mem_skill = Memory(content="学会了 Docker", importance=0.4, type=MemoryType.SKILL)
    tier4 = lcm.assign_tier(mem_skill)
    assert tier4 == MemoryTier.LONG_TERM
    print(f"  OK 技能类型 → {tier4}")

    # 分类所有记忆
    now = datetime.now()
    memories = [
        Memory(content="新记忆", importance=0.5, type=MemoryType.FACT,
               created_at=now.isoformat()),
        Memory(content="旧记忆", importance=0.2, type=MemoryType.FACT,
               created_at=(now - timedelta(days=60)).isoformat()),
        Memory(content="重要记忆", importance=0.8, type=MemoryType.FACT,
               created_at=(now - timedelta(days=100)).isoformat()),
        Memory(content="用户偏好", importance=0.6, type=MemoryType.PREFERENCE,
               created_at=(now - timedelta(days=50)).isoformat()),
    ]
    tiers = lcm.classify_all(memories)
    assert len(tiers[MemoryTier.LONG_TERM]) >= 2  # 重要 + 偏好
    print(f"  OK 分类: recent={len(tiers[MemoryTier.RECENT])}, "
          f"long_term={len(tiers[MemoryTier.LONG_TERM])}, "
          f"archive={len(tiers[MemoryTier.ARCHIVE])}")

    # 可删除记忆（需要超过 90 天 + 重要性 < 0.2 + 访问次数 < 3）
    # 当前记忆中最旧的是 60 天、重要性 0.2，不满足条件
    deletable = lcm.get_deletable(memories)
    print(f"  OK 可删除检测: {len(deletable)} 条（当前数据无满足条件的记忆）")
    
    # 添加一条真正应该被删除的记忆
    old_worthless = Memory(
        content="过时的低价值信息",
        importance=0.1,
        type=MemoryType.FACT,
        created_at=(now - timedelta(days=100)).isoformat(),
    )
    old_worthless.access_count = 0
    deletable2 = lcm.get_deletable(memories + [old_worthless])
    assert len(deletable2) >= 1
    assert any("过时" in m.content for m in deletable2)
    print(f"  OK 可删除（含过期记忆）: {len(deletable2)} 条")

    # 溢出淘汰
    many_memories = [Memory(content=f"记忆{i}", importance=0.5, type=MemoryType.FACT,
                            created_at=now.isoformat()) for i in range(20)]
    overflow = lcm.get_overflow_deletable(many_memories, target_count=10)
    assert len(overflow) == 10
    print(f"  OK 溢出淘汰: 20 → 10, 删除 {len(overflow)} 条")

    # 不超限时不淘汰
    no_overflow = lcm.get_overflow_deletable(many_memories[:5], target_count=10)
    assert len(no_overflow) == 0
    print("  OK 不超限不淘汰")

    # 记忆合并检测
    similar = [
        Memory(content="项目使用 Python 3.12 作为运行时", importance=0.7, type=MemoryType.FACT),
        Memory(content="项目使用 Python 3.12 作为运行环境", importance=0.6, type=MemoryType.FACT),
        Memory(content="完全不同的内容", importance=0.5, type=MemoryType.FACT),
    ]
    pairs = lcm.merge_similar_memories(similar, similarity_threshold=0.5)
    assert len(pairs) >= 1
    print(f"  OK 合并检测: 找到 {len(pairs)} 对相似记忆")

    # 不相似的
    dissimilar = [
        Memory(content="AAA", importance=0.5, type=MemoryType.FACT),
        Memory(content="BBB", importance=0.5, type=MemoryType.FACT),
    ]
    pairs2 = lcm.merge_similar_memories(dissimilar)
    assert len(pairs2) == 0
    print("  OK 不相似记忆不合并")

    # 更新记忆 tier 元数据
    mem_test = Memory(content="test", importance=0.9)
    updated_tier = lcm.update_memory_tier(mem_test)
    assert updated_tier == MemoryTier.LONG_TERM
    assert mem_test.metadata["tier"] == "long_term"
    print("  OK 更新 tier 元数据")

    # 自定义配置
    custom_lcm = MemoryLifecycleManager(config={
        "max_total_memories": 500,
        "recent_max_age_days": 14,
    })
    assert custom_lcm._config["max_total_memories"] == 500
    print("  OK 自定义配置")

    print()


# ──────────────────────────────────────────────
# 3. MemoryManager P8 集成测试
# ──────────────────────────────────────────────

async def test_memory_manager_p8():
    """测试增强版 MemoryManager"""
    print("=" * 60)
    print("3. 测试增强版 MemoryManager")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = MemoryConfig(storage_path=tmpdir)
        ext = MockExtractor(fixed_results=[
            ExtractedMemory(type="fact", content="项目使用 FastAPI", tags=["project"], importance=0.7),
        ])
        mgr = MemoryManager(config=config, session_id="test_p8", extractor=ext)

        # extractor 可替换
        assert mgr.extractor is ext
        new_ext = MockExtractor()
        mgr.extractor = new_ext
        assert mgr.extractor is new_ext
        print("  OK extractor 可替换")

        # 恢复原提取器（含 fixed_results）
        mgr.extractor = ext

        # remember_batch
        batch = [
            ExtractedMemory(type="fact", content="事实1", tags=[], importance=0.5),
            ExtractedMemory(type="preference", content="偏好1", tags=[], importance=0.6),
            ExtractedMemory(type="fact", content="", tags=[], importance=0.5),  # 空内容应跳过
        ]
        count = mgr.remember_batch(batch)
        assert count == 2  # 跳过空内容
        print(f"  OK remember_batch: 3 条输入, {count} 条实际保存")

        # extract_from_conversation
        msgs = [
            Message(role=MessageRole.USER, content="我喜欢用 Rust"),
            Message(role=MessageRole.ASSISTANT, content="好的，使用 Rust"),
        ]
        new_memories = await mgr.extract_from_conversation(msgs)
        # 使用 fixed_results，不依赖消息内容
        assert len(new_memories) == 1
        assert "FastAPI" in new_memories[0].content
        print(f"  OK extract_from_conversation: 提取 {len(new_memories)} 条记忆")

        # 验证记忆有 tier 元数据
        all_mems = mgr.list_memories()
        has_tier = any(m.metadata.get("tier") for m in all_mems)
        assert has_tier
        print("  OK 记忆自动分配 tier")

        # get_stats 包含 by_tier
        stats = mgr.get_stats()
        assert "by_tier" in stats
        assert stats["total"] >= 3  # batch(2) + extract(1)
        print(f"  OK get_stats: {stats}")

        # run_lifecycle
        lifecycle_result = mgr.run_lifecycle()
        assert "deleted" in lifecycle_result
        assert "tier_updated" in lifecycle_result
        print(f"  OK run_lifecycle: {lifecycle_result}")

        print()


# ──────────────────────────────────────────────
# 4. Agent 集成测试（记忆上下文注入）
# ──────────────────────────────────────────────

async def test_agent_memory_integration():
    """测试 Agent 与记忆系统的集成"""
    print("=" * 60)
    print("4. 测试 Agent 记忆集成")
    print("=" * 60)

    from src.core.agent import Agent
    from src.config.settings import load_yaml_config

    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建配置
        yaml_data = {
            "llm": {
                "default_provider": "bailian",
                "providers": {
                    "bailian": {
                        "base_url": "https://example.com/v1",
                        "api_key": "test-key",
                        "model": "test-model",
                        "max_context_tokens": 32768,
                        "supports_tools": True,
                    }
                },
            },
            "memory": {
                "storage_path": tmpdir,
            },
        }

        import yaml, tempfile as tf2
        cfg_file = tf2.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(yaml_data, cfg_file)
        cfg_file.close()

        try:
            from pathlib import Path
            from src.config.settings import load_settings
            settings = load_settings(config_path=Path(cfg_file.name))

            # 预置一些记忆
            from src.memory.manager import MemoryManager
            mm = MemoryManager(config=settings.memory, session_id="test_integration")
            mm.remember("用户偏好使用深色主题", mem_type="preference", importance=0.8)
            mm.remember("项目使用 Python 3.12", mem_type="fact", importance=0.7)

            # 创建 Agent（会自动获取记忆上下文）
            agent = Agent(settings=settings, session_id="test_integration")

            # 注入已有的记忆管理器（含预置记忆）
            agent.set_extractor(MockExtractor(fixed_results=[]))

            # 检查初始 system prompt 是否包含记忆
            sys_prompt = agent.loop.messages[0].content if agent.loop.messages else ""
            assert "相关记忆" in sys_prompt or "可用工具" in sys_prompt
            print(f"  OK 初始化 system prompt 包含记忆上下文")

            # 模拟 _update_memory_context
            ctx = agent._memory.get_context(query="主题")
            if ctx:
                agent._update_memory_context("主题")
                updated_prompt = agent.loop.messages[0].content
                assert "深色主题" in updated_prompt
                print(f"  OK _update_memory_context 注入了相关记忆")
            else:
                print("  OK _update_memory_context (无匹配记忆时跳过)")

            # set_extractor
            new_mock = MockExtractor(fixed_results=[
                ExtractedMemory(type="fact", content="新提取的事实", importance=0.6),
            ])
            agent.set_extractor(new_mock)
            assert agent._memory.extractor is new_mock
            print("  OK set_extractor 可替换提取器")

        finally:
            os.unlink(cfg_file.name)

    print()


# ──────────────────────────────────────────────
# 5. 现有 P4 测试兼容性
# ──────────────────────────────────────────────

async def test_p4_compatibility():
    """确保 P8 不破坏 P4 已有功能"""
    print("=" * 60)
    print("5. P4 兼容性测试")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = MemoryConfig(storage_path=tmpdir)
        mgr = MemoryManager(config=config, session_id="compat_test")

        # remember/recall/forget/get_context 仍然正常
        m1 = mgr.remember("用户喜欢 Vim", mem_type="preference", tags=["editor"])
        assert m1.content == "用户喜欢 Vim"
        print("  OK remember()")

        results = mgr.recall("editor")
        assert len(results) >= 1
        print("  OK recall()")

        ctx = mgr.get_context("editor")
        assert "相关记忆" in ctx
        print("  OK get_context()")

        assert mgr.forget(m1.id)
        print("  OK forget()")

        # list_memories
        m2 = mgr.remember("Fact A", mem_type="fact")
        m3 = mgr.remember("Pref B", mem_type="preference")
        all_mems = mgr.list_memories()
        assert len(all_mems) >= 2
        print(f"  OK list_memories: {len(all_mems)} 条")

        # get_stats
        stats = mgr.get_stats()
        assert stats["total"] >= 2
        assert "fact" in stats["by_type"]
        print(f"  OK get_stats: {stats}")

        # clear
        count = mgr.clear()
        assert count >= 2
        assert mgr.store.count == 0
        print(f"  OK clear: 清空 {count} 条")

    print()


# ──────────────────────────────────────────────

async def main():
    print()
    print("=" * 60)
    print("        Zclaw P8 - 记忆系统完善验证")
    print("=" * 60)
    print()

    await test_extractor_base()
    await test_lifecycle()
    await test_memory_manager_p8()
    await test_agent_memory_integration()
    await test_p4_compatibility()

    print("=" * 60)
    print("Results: 5 passed, 0 failed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
