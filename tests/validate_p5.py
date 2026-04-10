"""
P5 End-to-End Validation - Context Management.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_token_budget():
    print("=" * 60)
    print("1. Testing Token Budget")
    print("=" * 60)
    from src.context.budget import TokenBudget
    from src.llm.models import Message, MessageRole

    b = TokenBudget(max_context_tokens=10000, safety_margin_ratio=0.1)
    assert b.total == 10000
    assert b.available == 9000
    print("  OK Total and available")

    msgs = [
        Message(role=MessageRole.SYSTEM, content="You are a helpful assistant."),
        Message(role=MessageRole.USER, content="Hello, how are you?"),
    ]
    tokens = b.estimate_tokens(msgs)
    assert tokens > 0
    print(f"  OK Estimate: {tokens} tokens")

    ratio = b.usage_ratio(msgs)
    assert 0 < ratio < 1
    print(f"  OK Usage ratio: {ratio:.4f}")

    remaining = b.remaining(msgs)
    assert remaining > 0
    print(f"  OK Remaining: {remaining}")

    # High usage
    many_msgs = [Message(role=MessageRole.USER, content="x" * 36000)]  # ~9000 tokens
    high_ratio = b.usage_ratio(many_msgs)
    assert high_ratio > 0.9
    print(f"  OK High usage: {high_ratio:.2f}")

    print()


async def test_compressor():
    print("=" * 60)
    print("2. Testing Context Compressor")
    print("=" * 60)
    from src.context.compressor import ContextCompressor
    from src.llm.models import Message, MessageRole, ToolCall, ToolCallResult

    comp = ContextCompressor(keep_recent_rounds=2)

    # Build messages: system + 10 user/assistant pairs
    msgs = [Message(role=MessageRole.SYSTEM, content="System prompt")]
    for i in range(10):
        msgs.append(Message(role=MessageRole.USER, content=f"User message {i}"))
        msgs.append(Message(role=MessageRole.ASSISTANT, content=f"Response {i}"))

    original_len = len(msgs)
    compressed = comp.compress(msgs)

    assert compressed[0].role == MessageRole.SYSTEM
    assert len(compressed) < original_len
    # Should keep system + summary + recent 4 messages
    assert len(compressed) == 1 + 2 + 4  # system + summary_msg + assistant_ack + 4 recent
    print(f"  OK Compressed: {original_len} -> {len(compressed)} messages")

    # Summary present
    assert "[之前的对话摘要]" in compressed[1].content
    print("  OK Summary injected")

    # Short list should not compress
    short = [Message(role=MessageRole.SYSTEM, content="S"), Message(role=MessageRole.USER, content="U"), Message(role=MessageRole.ASSISTANT, content="A")]
    result = comp.compress(short)
    assert len(result) == 3  # No change
    print("  OK Short list not compressed")

    print()


async def test_context_manager():
    print("=" * 60)
    print("3. Testing Context Manager")
    print("=" * 60)
    from src.context.manager import ContextManager
    from src.config.settings import ContextConfig
    from src.llm.models import Message, MessageRole

    cfg = ContextConfig(safety_margin_ratio=0.1)
    cm = ContextManager(config=cfg, max_context_tokens=10000)

    msgs = [Message(role=MessageRole.USER, content="Hello")]
    assert not cm.should_compress(msgs)
    print("  OK should_compress: False (low usage)")

    # Force near-limit
    big = [Message(role=MessageRole.USER, content="x" * 36000)]
    assert cm.should_compress(big)
    print("  OK should_compress: True (high usage)")

    # prepare_messages with force
    msgs2 = [Message(role=MessageRole.SYSTEM, content="S")]
    for i in range(10):
        msgs2.append(Message(role=MessageRole.USER, content=f"M{i}"))
        msgs2.append(Message(role=MessageRole.ASSISTANT, content=f"R{i}"))
    prepared = cm.prepare_messages(msgs2, force_compress=True)
    assert len(prepared) < len(msgs2)
    print(f"  OK prepare_messages: {len(msgs2)} -> {len(prepared)}")

    # No compression when not needed
    msgs3 = [Message(role=MessageRole.USER, content="Hi")]
    result = cm.prepare_messages(msgs3)
    assert len(result) == 1
    print("  OK No unnecessary compression")

    # Usage info
    info = cm.get_usage_info(msgs)
    assert "used_tokens" in info
    assert "usage_ratio" in info
    assert "needs_compression" in info
    print(f"  OK get_usage_info: {info}")

    print()


async def test_loop_integration():
    print("=" * 60)
    print("4. Testing Context Manager + Loop Integration")
    print("=" * 60)
    from src.config.settings import load_yaml_config, LLMConfig, AgentConfig, ContextConfig
    from src.core.loop import AgentLoop
    from src.llm.router import LLMRouter
    from src.context.manager import ContextManager

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    llm_config = LLMConfig.model_validate(config_yaml["llm"])
    agent_config = AgentConfig.model_validate(config_yaml.get("agent", {}))
    context_config = ContextConfig()
    router = LLMRouter(llm_config)

    max_tokens = llm_config.providers["bailian"].max_context_tokens
    ctx = ContextManager(config=context_config, max_context_tokens=max_tokens)
    loop = AgentLoop(llm=router, agent_config=agent_config, system_prompt="Test", context_manager=ctx)

    assert loop._context is not None
    print(f"  OK Loop with context manager")

    info = loop._context.get_usage_info(loop.messages)
    assert info["used_tokens"] >= 0
    print(f"  OK Context info: {info}")

    print()


async def test_full_agent_p5():
    print("=" * 60)
    print("5. Testing Full Agent with Context")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)
    agent = Agent(settings)

    assert agent.context_manager is not None
    print(f"  OK Agent: {agent}")

    info = agent.context_manager.get_usage_info(agent.loop.messages)
    print(f"  OK Context info: {info}")

    print()


async def main():
    print()
    print("=" * 60)
    print("        Zclaw P5 - Context Management Validation")
    print("=" * 60)
    print()

    tests = [
        test_token_budget,
        test_compressor,
        test_context_manager,
        test_loop_integration,
        test_full_agent_p5,
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
