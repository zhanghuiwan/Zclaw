"""Context, prompt builder, planner, and plugin integration tests."""

import asyncio
import sys
from pathlib import Path


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

async def test_plan_structures():
    print("=" * 60)
    print("1. Testing Plan Data Structures")
    print("=" * 60)
    from src.core.plan import Plan, PlanStep, PlanStepStatus

    step1 = PlanStep(index=0, description="Read the file")
    step2 = PlanStep(index=1, description="Modify the file")
    step3 = PlanStep(index=2, description="Test the changes")
    plan = Plan(goal="Implement feature X", steps=[step1, step2, step3])

    assert plan.goal == "Implement feature X"
    assert len(plan.steps) == 3
    assert plan.current_step_index == 0
    assert plan.progress == 0.0
    print("  OK Plan creation")

    # Advance
    plan.advance()  # Step 0 -> DONE, activate Step 1
    assert plan.steps[0].status == PlanStepStatus.DONE
    assert plan.steps[1].status == PlanStepStatus.IN_PROGRESS
    assert plan.current_step_index == 1
    print(f"  OK Advance: progress={plan.progress:.0%}")

    plan.advance()  # Step 1 -> DONE, activate Step 2
    assert plan.steps[1].status == PlanStepStatus.DONE
    assert plan.steps[2].status == PlanStepStatus.IN_PROGRESS
    assert plan.progress == 2 / 3
    print(f"  OK Advance: progress={plan.progress:.0%}")

    # Complete
    plan.advance()
    assert plan.progress == 1.0
    print("  OK All steps done")

    # Fail
    plan2 = Plan(goal="Test fail", steps=[PlanStep(index=0, description="A"), PlanStep(index=1, description="B")])
    plan2.advance()  # A in_progress
    plan2.fail_current("Some error")
    assert plan2.steps[0].status == PlanStepStatus.DONE
    assert plan2.steps[1].status == PlanStepStatus.FAILED
    assert plan2.steps[1].error == "Some error"
    print("  OK Fail current")

    # Serialization
    d = plan.to_dict()
    assert d["goal"] == "Implement feature X"
    assert len(d["steps"]) == 3
    plan_restored = Plan.from_dict(d)
    assert plan_restored.goal == plan.goal
    print("  OK Serialization round-trip")

    # Format
    status = plan.format_status()
    assert "计划:" in status
    assert "[+]" in status  # Done step
    print(f"  OK Format:\n{status}")

    print()

async def test_planner():
    print("=" * 60)
    print("2. Testing Planner")
    print("=" * 60)
    from src.core.planner import Planner

    pl = Planner()

    # Create from steps
    plan = pl.create_plan_from_steps(
        "Build a web app",
        [{"description": "Set up project structure"}, {"description": "Write main.py"}, {"description": "Test"}],
    )
    assert pl.has_plan
    assert plan.goal == "Build a web app"
    print("  OK create_plan_from_steps")

    # Parse from text
    text = '[{"description": "Analyze"}, {"description": "Implement"}, {"description": "Test"}]'
    parsed = pl.parse_plan_from_text("Analyze and implement", text)
    assert parsed is not None
    assert parsed.goal == "Analyze and implement"
    assert len(parsed.steps) == 3
    print("  OK parse_plan_from_text")

    # Parse invalid
    invalid = pl.parse_plan_from_text("Goal", "not json")
    assert invalid is None
    print("  OK parse_plan_from_text: invalid returns None")

    # Get context
    ctx = pl.get_context()
    assert "计划:" in ctx
    print("  OK get_context")

    # Clear
    pl.clear_plan()
    assert not pl.has_plan
    print("  OK clear_plan")

    print()

async def test_prompt_builder():
    print("=" * 60)
    print("3. Testing Prompt Builder")
    print("=" * 60)
    from src.prompt.builder import PromptBuilder
    from src.prompt.templates import DEFAULT_PERSONA, COMPACT_PERSONA

    pb = PromptBuilder()
    prompt = pb.build()
    assert DEFAULT_PERSONA in prompt
    assert "可用工具" in prompt
    print("  OK Build with tools")

    prompt2 = pb.build(tool_names=["file_read", "shell"])
    assert "file_read" in prompt2
    assert "shell" in prompt2
    print("  OK Build with specific tools")

    prompt3 = pb.build(memory_context="## Memories\n- User likes Vim")
    assert "User likes Vim" in prompt3
    print("  OK Build with memory context")

    prompt4 = pb.build_compact()
    assert COMPACT_PERSONA in prompt4
    print("  OK Build compact")

    # Add sections
    pb.add_section("Project Rules", "Always use type hints.")
    prompt5 = pb.build()
    assert "Project Rules" in prompt5
    assert "Always use type hints" in prompt5
    print("  OK Add sections")

    print()

async def test_full_agent_p6():
    print("=" * 60)
    print("4. Testing Full Agent with P6")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)
    agent = Agent(settings)

    assert agent.planner is not None
    assert agent.prompt_builder is not None
    print(f"  OK Agent: planner={agent.planner}, builder={agent.prompt_builder}")

    # Agent should use dynamic prompt
    sys_prompt = agent.loop.messages[0].content if agent.loop.messages else ""
    assert "可用工具" in sys_prompt
    assert "file_read" in sys_prompt
    print("  OK Dynamic system prompt in loop")

    print()

async def test_full_agent_p7():
    print("=" * 60)
    print("5. Testing Full Agent with P7")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent

    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)
    agent = Agent(settings)

    assert agent.plugin_loader is not None
    assert agent.session_manager is not None
    print(f"  OK Agent: plugins={agent.plugin_loader}, sessions={agent.session_manager}")

    # Cost tracker
    from src.cli.cost_tracker import CostTracker
    ct = CostTracker()
    ct.record_round(100, 200)
    ct.record_round(50, 300)
    assert ct.total_rounds == 2
    assert ct.get_total() == 650
    summary = ct.get_summary()
    assert "650" in summary
    print(f"  OK CostTracker:\n{summary}")

    # Plugin loader
    plugins = agent.plugin_loader.scan()
    assert isinstance(plugins, list)
    print(f"  OK Plugin scan: {len(plugins)} plugin(s)")

    # Session manager
    sessions = agent.session_manager.list_sessions()
    assert isinstance(sessions, list)
    print(f"  OK Session list: {len(sessions)} session(s)")

    print()
