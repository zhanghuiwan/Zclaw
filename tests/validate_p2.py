"""
P2 End-to-End Validation - Security permissions, input validation, audit logging.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_permission_manager():
    print("=" * 60)
    print("1. Testing Permission Manager")
    print("=" * 60)
    from src.config.settings import SecurityConfig
    from src.security.permission import PermissionManager, PermissionRequest
    config = SecurityConfig()
    pm = PermissionManager(config=config)
    req = PermissionRequest(tool_name="file_read", arguments={"path": "/tmp/test"}, danger_level="safe")
    resp = await pm.check(req)
    assert resp.allowed and resp.auto
    print("  OK file_read auto-approved")
    req2 = PermissionRequest(tool_name="file_write", arguments={"path": "/tmp/test.py"}, danger_level="confirm")
    resp2 = await pm.check(req2)
    assert not resp2.allowed
    print("  OK file_write denied (no callback, no auto_confirm)")
    pm2 = PermissionManager(config=config, auto_confirm=True)
    req2b = PermissionRequest(tool_name="file_write", arguments={"path": "./test.py"}, danger_level="confirm")
    resp3 = await pm2.check(req2b)
    assert resp3.allowed and resp3.auto
    print("  OK file_write auto-approved (auto_confirm=True)")
    req3 = PermissionRequest(tool_name="shell", arguments={"command": "rm -rf /"}, danger_level="dangerous")
    resp4 = await pm.check(req3)
    assert not resp4.allowed
    print("  OK Dangerous command blocked")
    req4 = PermissionRequest(tool_name="file_write", arguments={"path": "/etc/passwd"}, danger_level="confirm")
    resp5 = await pm.check(req4)
    assert not resp5.allowed
    print("  OK Path restriction: /etc denied")
    config_wide = SecurityConfig(path_restrictions={
        "allow": ["/tmp", "."],
        "deny": ["/etc", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys"],
    })
    async def always_allow(request):
        return True
    pm3 = PermissionManager(config=config_wide)
    pm3.set_confirm_callback(always_allow)
    req5 = PermissionRequest(tool_name="file_write", arguments={"path": "/tmp/test"}, danger_level="confirm")
    resp6 = await pm3.check(req5)
    assert resp6.allowed and not resp6.auto
    print("  OK Custom callback: allowed")
    async def always_deny(request):
        return False
    pm4 = PermissionManager(config=config_wide)
    pm4.set_confirm_callback(always_deny)
    resp7 = await pm4.check(req5)
    assert not resp7.allowed and not resp7.auto
    print("  OK Custom callback: denied")
    stats = pm.get_stats()
    assert "total_checks" in stats
    print(f"  OK Stats: {stats}")
    print()


async def test_input_validator():
    print("=" * 60)
    print("2. Testing Input Validator")
    print("=" * 60)
    from src.security.validator import InputValidator
    v = InputValidator()
    ok, err = v.validate_path("../../../etc/passwd")
    assert not ok and "穿越" in err
    print("  OK Path traversal detected")
    ok, err = v.validate_path("/tmp/test.py")
    assert ok
    print("  OK Valid path accepted")
    ok, err = v.validate_path("")
    assert not ok
    print("  OK Empty path rejected")
    ok, err = v.validate_command("ls -la")
    assert ok
    print("  OK Safe command accepted")
    ok, err = v.validate_command("")
    assert not ok
    print("  OK Empty command rejected")
    ok, err = v.validate_length("a" * 100, 50, "test")
    assert not ok
    print("  OK Length exceeded")
    ok, err = v.validate_file_size("x" * 2_000_000, max_bytes=1_000_000)
    assert not ok
    print("  OK File size exceeded")
    print()


async def test_output_sanitizer():
    print("=" * 60)
    print("3. Testing Output Sanitizer")
    print("=" * 60)
    from src.security.validator import OutputSanitizer
    s = OutputSanitizer()
    text = "api_key = sk-1234567890abcdefghijklmnop"
    result = s.redact_sensitive(text)
    assert "sk-1234" not in result and "***REDACTED***" in result
    print("  OK API key redacted")
    text2 = "password = supersecret12345678901"
    result2 = s.redact_sensitive(text2)
    assert "***REDACTED***" in result2
    print("  OK Password redacted")
    text3 = "hello\x00\x01\x02world"
    result3 = s.clean_control_chars(text3)
    assert "\x00" not in result3
    print("  OK Control chars cleaned")
    text4 = "a" * 100_000
    result4 = s.truncate(text4, 1000)
    assert len(result4) < 1100 and "截断" in result4
    print("  OK Long text truncated")
    text5 = "normal text with \x00control chars and api_key=sk-abcdefghijklmnopqrstuvwxyz"
    result5 = s.sanitize(text5)
    assert "\x00" not in result5 and "sk-abcdef" not in result5
    print("  OK Full sanitize pipeline")
    print()


async def test_audit_logger():
    print("=" * 60)
    print("4. Testing Audit Logger")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.security.audit import AuditLogger
        audit = AuditLogger(enabled=True, log_dir=tmpdir, session_id="test123")
        audit.log(tool_name="file_read", arguments={"path": "/tmp/test.py"}, danger_level="safe", permission_decision="allow", permission_auto=True, execution_success=True, duration_ms=50)
        audit.log(tool_name="file_write", arguments={"path": "/tmp/out.py", "content": "hello"}, danger_level="confirm", permission_decision="allow", permission_auto=False, execution_success=True, duration_ms=120)
        audit.log(tool_name="shell", arguments={"command": "ls"}, danger_level="safe", permission_decision="deny", permission_auto=True, execution_success=None, execution_error="Blocked")
        stats = audit.get_stats()
        assert stats["total_entries"] == 3 and stats["allowed"] == 2 and stats["denied"] == 1
        print(f"  OK Logged 3 entries: {stats}")
        entries = audit.read_entries(limit=10)
        assert len(entries) == 3 and entries[0]["tool_name"] == "shell"
        print("  OK Read entries in reverse order")
        assert audit.log_file.exists()
        print(f"  OK Log file exists: {audit.log_file.name}")
    print()


async def test_integration_with_loop():
    print("=" * 60)
    print("5. Testing Permission + Loop Integration")
    print("=" * 60)
    from src.config.settings import load_yaml_config, LLMConfig, AgentConfig, SecurityConfig
    from src.core.loop import AgentLoop
    from src.llm.router import LLMRouter
    from src.llm.models import ToolCall
    from src.security.permission import PermissionManager
    from src.security.audit import AuditLogger
    from src.tools.base import BaseTool, ToolResult, DangerLevel, ToolParameter
    from src.tools.registry import ToolRegistry
    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    llm_config = LLMConfig.model_validate(config_yaml["llm"])
    agent_config = AgentConfig.model_validate(config_yaml.get("agent", {}))
    security_config = SecurityConfig()
    with tempfile.TemporaryDirectory() as tmpdir:
        router = LLMRouter(llm_config)
        registry = ToolRegistry()
        class WriteTool(BaseTool):
            name = "test_write"
            description = "Test write"
            danger_level = DangerLevel.CONFIRM
            category = "test"
            parameters = [ToolParameter(name="path", type="string", description="Path", required=True)]
            async def execute(self, **kwargs):
                return ToolResult.ok(f"Written to {kwargs['path']}")
        class ReadTool(BaseTool):
            name = "test_read"
            description = "Test read"
            danger_level = DangerLevel.SAFE
            category = "test"
            parameters = [ToolParameter(name="path", type="string", description="Path", required=True)]
            async def execute(self, **kwargs):
                return ToolResult.ok(f"Read from {kwargs['path']}")
        registry.register_many([WriteTool(), ReadTool()])
        audit = AuditLogger(enabled=True, log_dir=tmpdir, session_id="test_integ")
        pm = PermissionManager(config=security_config, auto_confirm=True)
        loop = AgentLoop(llm=router, agent_config=agent_config, system_prompt="Test", tool_registry=registry, permission_manager=pm, audit_logger=audit)
        assert loop.permission_manager is not None
        print("  OK Loop with permission manager created")
        calls = [ToolCall(id="c1", name="test_read", arguments='{"path": "/tmp/test"}')]
        results = await loop._execute_tool_calls(calls)
        assert results[0].success and "Read from" in results[0].content
        print("  OK Safe tool executed without blocking")
        calls2 = [ToolCall(id="c2", name="test_write", arguments='{"path": "/tmp/out"}')]
        results2 = await loop._execute_tool_calls(calls2)
        assert results2[0].success and "Written to" in results2[0].content
        print("  OK Confirm tool executed (auto_confirm=True)")
        audit_stats = audit.get_stats()
        assert audit_stats["total_entries"] == 2
        print(f"  OK Audit log: {audit_stats}")
    print()


async def test_full_agent_init():
    print("=" * 60)
    print("6. Testing Full Agent with Security")
    print("=" * 60)
    from src.config.settings import load_yaml_config, Settings
    from src.core.agent import Agent
    config_yaml = load_yaml_config(Path(__file__).parent.parent / "config.example.yaml")
    settings = Settings.model_validate(config_yaml)
    agent = Agent(settings)
    print(f"  OK Agent: {agent}")
    assert agent.permission_manager is not None
    assert agent.audit_logger is not None
    assert agent.session_id
    print(f"  OK Session: {agent.session_id}")
    print(f"  OK Permissions: {agent.permission_manager}")
    print(f"  OK Audit: {agent.audit_logger}")
    agent2 = Agent(settings)
    assert agent.session_id != agent2.session_id
    print("  OK Different sessions have different IDs")
    print()


async def main():
    print()
    print("=" * 60)
    print("        Zclaw P2 - Security Validation")
    print("=" * 60)
    print()
    tests = [test_permission_manager, test_input_validator, test_output_sanitizer, test_audit_logger, test_integration_with_loop, test_full_agent_init]
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
