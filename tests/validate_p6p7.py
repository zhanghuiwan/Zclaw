"""
P6 End-to-End Validation - Prompt Engineering + Planner.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


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


async def main():
    print()
    print("=" * 60)
    print("        Zclaw P6+P7 - Prompt/Planner/Plugins Validation")
    print("=" * 60)
    print()

    tests = [
        test_plan_structures,
        test_planner,
        test_prompt_builder,
        test_full_agent_p6,
        test_full_agent_p7,
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
