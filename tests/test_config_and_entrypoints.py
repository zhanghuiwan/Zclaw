"""Configuration, entrypoint, LLM model, and agent bootstrap tests."""

import asyncio
import sys
from pathlib import Path


async def test_config_module():
    print("=" * 60)
    print("1. Testing Config Module")
    print("=" * 60)
    from src.config.settings import Settings, load_settings, load_yaml_config, _resolve_env_vars
    s = Settings()
    assert s.llm.default_provider == "bailian"
    assert s.agent.max_loop_rounds == 50
    print("  OK Default settings loaded")
    import os
    os.environ["TEST_VAR"] = "hello_world"
    result = _resolve_env_vars({"key": "${TEST_VAR}"})
    assert result["key"] == "hello_world"
    print("  OK Env var resolution works")
    config = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    assert config is not None and "llm" in config
    print("  OK Example YAML config parsed")
    s2 = Settings.model_validate(config)
    assert s2.llm.providers["bailian"].model == "qwen-plus"
    print("  OK Settings built from YAML config")
    print()

async def test_llm_models():
    print("=" * 60)
    print("2. Testing LLM Models")
    print("=" * 60)
    from src.llm.models import (
        Message, MessageRole, ToolCall, ToolDefinition,
        Response, Usage, StreamEvent, StreamEventType,
    )
    msg = Message(role=MessageRole.USER, content="Hello")
    assert msg.to_openai_dict()["role"] == "user"
    print("  OK Message creation and serialization")
    tc = ToolCall(id="call_1", name="read_file", arguments='{"path": "/tmp"}')
    msg2 = Message(role=MessageRole.ASSISTANT, content="", tool_calls=[tc])
    assert msg2.to_openai_dict()["tool_calls"][0]["id"] == "call_1"
    print("  OK Message with tool calls")
    td = ToolDefinition(name="read_file", description="Read a file", parameters={"type": "object", "properties": {"path": {"type": "string"}}})
    assert td.to_openai_dict()["type"] == "function"
    print("  OK Tool definition serialization")
    u1 = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    u2 = Usage(prompt_tokens=200, completion_tokens=80, total_tokens=280)
    u3 = u1 + u2
    assert u3.total_tokens == 430
    print("  OK Usage addition")
    r = Response(content="Hi there", usage=u1, finish_reason="stop")
    assert r.content == "Hi there"
    print("  OK Response model")
    se = StreamEvent(type=StreamEventType.CONTENT_DELTA, data="chunk")
    assert se.type == StreamEventType.CONTENT_DELTA
    print("  OK Stream event model")
    print()

async def test_llm_router():
    print("=" * 60)
    print("3. Testing LLM Router")
    print("=" * 60)
    from src.config.settings import load_yaml_config, LLMConfig
    from src.llm.router import LLMRouter, create_provider
    from src.llm.base import BaseProvider
    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    llm_config = LLMConfig.model_validate(config_yaml["llm"])
    router = LLMRouter(llm_config)
    print(f"  OK Router created: {router}")
    assert router.default_provider.name == "bailian"
    assert router.default_provider.model == "qwen-plus"
    print("  OK Default provider")
    ollama = router.get_provider("ollama")
    assert ollama.model == "qwen2.5:latest"
    print("  OK Ollama provider")
    router._config.default_provider = "bailian"
    chain = router._get_fallback_chain("bailian")
    assert len(chain) == 2
    print(f"  OK Fallback chain: {[p.name for p in chain]}")
    from src.llm.models import Message, MessageRole
    msgs = [Message(role=MessageRole.SYSTEM, content="You are a helpful assistant." * 10)]
    tokens = await router.default_provider.count_tokens(msgs)
    assert tokens > 0
    print(f"  OK Token estimation: {tokens} tokens")
    print()

async def test_agent_state():
    print("=" * 60)
    print("4. Testing Agent State Machine")
    print("=" * 60)
    from src.core.state import AgentState, AgentStateMachine, StateTransitionError
    sm = AgentStateMachine()
    assert sm.state == AgentState.IDLE
    print(f"  OK Initial state: {sm.state.value}")
    sm.transition(AgentState.EXECUTING)
    assert sm.state == AgentState.EXECUTING
    print("  OK IDLE -> EXECUTING")
    sm.transition(AgentState.DONE)
    print("  OK EXECUTING -> DONE")
    sm.transition(AgentState.IDLE)
    print("  OK DONE -> IDLE")
    try:
        sm2 = AgentStateMachine()
        sm2.transition(AgentState.EXECUTING)
        sm2.transition(AgentState.DONE)
        sm2.transition(AgentState.PLANNING)
        assert False, "Should have raised"
    except StateTransitionError:
        print("  OK Invalid transition blocked")
    changes = []
    sm3 = AgentStateMachine()
    sm3.on_change(lambda old, new: changes.append((old.value, new.value)))
    sm3.transition(AgentState.EXECUTING)
    sm3.transition(AgentState.DONE)
    assert changes == [("idle", "executing"), ("executing", "done")]
    print(f"  OK State change listener: {changes}")
    print()

async def test_agent_loop():
    print("=" * 60)
    print("5. Testing Agent Loop Structure")
    print("=" * 60)
    from src.config.settings import load_yaml_config, LLMConfig, AgentConfig
    from src.core.loop import AgentLoop
    from src.llm.router import LLMRouter
    from src.llm.models import Message, MessageRole
    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    llm_config = LLMConfig.model_validate(config_yaml["llm"])
    agent_config = AgentConfig.model_validate(config_yaml.get("agent", {}))
    router = LLMRouter(llm_config)
    loop = AgentLoop(llm=router, agent_config=agent_config, system_prompt="Test system prompt")
    assert loop.state.value == "idle"
    assert loop.round == 0
    assert len(loop.messages) == 1
    print(f"  OK Loop initialized: {loop}")
    assert loop.messages[0].role == MessageRole.SYSTEM
    print("  OK System prompt present")
    loop.clear_history()
    assert len(loop.messages) == 1
    print("  OK Clear history preserves system prompt")
    loop.set_system_prompt("Custom system prompt")
    assert loop.messages[0].content == "Custom system prompt"
    print("  OK Custom system prompt set")
    print()

async def test_agent():
    print("=" * 60)
    print("6. Testing Agent Main Class")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent
    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)
    agent = Agent(settings)
    print(f"  OK Agent created: {agent}")
    assert agent.state.value == "idle"
    print(f"  OK Agent state: {agent.state.value}")
    assert len(agent.loop.messages) == 1
    print("  OK System prompt injected")
    agent._settings.llm.default_provider = "ollama"
    assert agent.llm.default_provider.name == "ollama"
    print("  OK Provider switching at agent level")
    print()

async def test_error_hierarchy():
    print("=" * 60)
    print("7. Testing Error Hierarchy")
    print("=" * 60)
    from src.llm.models import LLMError, LLMConnectionError, LLMAuthError, LLMRateLimitError
    e1 = LLMConnectionError("connection failed", provider="bailian")
    assert e1.recoverable is True
    print(f"  OK LLMConnectionError (recoverable={e1.recoverable})")
    e2 = LLMAuthError("auth failed", provider="ollama")
    assert e2.recoverable is False
    print(f"  OK LLMAuthError (recoverable={e2.recoverable})")
    e3 = LLMRateLimitError("rate limited", provider="bailian")
    assert e3.recoverable is True
    print(f"  OK LLMRateLimitError (recoverable={e3.recoverable})")
    print()
