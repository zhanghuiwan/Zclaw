"""
Phase 1 验证测试 - Channel/Brain/Body 架构 + SOUL.md 系统

测试新引入的架构组件：
- Channel Layer: Gateway, Router, Normalizer
- Brain Layer: SoulLoader, UserProfileLoader, AgentsConfigLoader, Session, ContextAssembler
- Body Layer: CronScheduler, HeartbeatManager
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==================== Soul Loader Tests ====================

def test_soul_loader_basic():
    """测试 SOUL.md 加载和解析"""
    print("\n" + "=" * 60)
    print("测试 1.1: SOUL.md 加载")
    print("=" * 60)

    from src.brain.soul_loader import SoulLoader

    loader = SoulLoader()
    soul = loader.load(str(PROJECT_ROOT / "agents/default/SOUL.md"))

    assert soul.name == "Zclaw", f"Expected name 'Zclaw', got '{soul.name}'"
    assert soul.version == "1.0.0"
    assert len(soul.personality) > 0
    assert len(soul.behavior_rules) > 0
    assert len(soul.capabilities) >= 0
    assert len(soul.constraints) >= 0

    print(f"  ✓ 名称: {soul.name}")
    print(f"  ✓ 版本: {soul.version}")
    print(f"  ✓ 人格特点: {len(soul.personality)} 条")
    print(f"  ✓ 行为准则: {len(soul.behavior_rules)} 条")
    print(f"  ✓ 能力: {len(soul.capabilities)} 条")
    print(f"  ✓ 约束: {len(soul.constraints)} 条")


def test_soul_to_system_prompt():
    """测试 SOUL 转换为系统提示词"""
    print("\n" + "=" * 60)
    print("测试 1.2: SOUL 转系统提示词")
    print("=" * 60)

    from src.brain.soul_loader import SoulLoader

    loader = SoulLoader()
    soul = loader.load(str(PROJECT_ROOT / "agents/default/SOUL.md"))
    prompt = loader.to_system_prompt(soul)

    assert "Zclaw" in prompt
    assert "你是" in prompt or "你是 Zclaw" in prompt
    print(f"  ✓ 系统提示词生成成功 ({len(prompt)} 字符)")
    print(f"  预览: {prompt[:200]}...")


# ==================== User Profile Tests ====================

def test_user_profile_loader():
    """测试 USER.md 加载"""
    print("\n" + "=" * 60)
    print("测试 2.1: USER.md 加载")
    print("=" * 60)

    from src.brain.user_profile import UserProfileLoader

    loader = UserProfileLoader()
    profile = loader.load(str(PROJECT_ROOT / "agents/default/USER.md"))

    assert profile.name == "用户"
    assert profile.timezone == "Asia/Shanghai"
    assert len(profile.preferences) > 0
    assert len(profile.sensitive_operations) > 0

    print(f"  ✓ 姓名: {profile.name}")
    print(f"  ✓ 时区: {profile.timezone}")
    print(f"  ✓ 偏好: {len(profile.preferences)} 条")
    print(f"  ✓ 敏感操作: {len(profile.sensitive_operations)} 条")


def test_user_to_context():
    """测试 UserProfile 转上下文字符串"""
    print("\n" + "=" * 60)
    print("测试 2.2: UserProfile 转上下文")
    print("=" * 60)

    from src.brain.user_profile import UserProfileLoader

    loader = UserProfileLoader()
    profile = loader.load(str(PROJECT_ROOT / "agents/default/USER.md"))
    context = loader.to_context_string(profile)

    assert "用户" in context or "USER" in context.upper()
    assert "Asia/Shanghai" in context
    print(f"  ✓ 上下文生成成功 ({len(context)} 字符)")


# ==================== Agents Config Tests ====================

def test_agents_config_loader():
    """测试 AGENTS.md 加载"""
    print("\n" + "=" * 60)
    print("测试 3.1: AGENTS.md 加载")
    print("=" * 60)

    from src.brain.agents_config import AgentsConfigLoader

    loader = AgentsConfigLoader()
    config = loader.load(str(PROJECT_ROOT / "agents/default/AGENTS.md"))

    assert len(config.startup_behavior) > 0
    assert len(config.tool_permissions.auto_approve) > 0
    assert len(config.tool_permissions.confirm) > 0
    assert len(config.cron_tasks) >= 0
    assert config.heartbeat.interval_seconds == 300

    print(f"  ✓ 启动行为: {len(config.startup_behavior)} 条")
    print(f"  ✓ 自动批准工具: {len(config.tool_permissions.auto_approve)} 个")
    print(f"  ✓ 需确认工具: {len(config.tool_permissions.confirm)} 个")
    print(f"  ✓ Cron 任务: {len(config.cron_tasks)} 个")
    print(f"  ✓ 心跳间隔: {config.heartbeat.interval_seconds}s")


# ==================== Message Normalizer Tests ====================

def test_message_normalizer_websocket():
    """测试 WebSocket 消息归一化"""
    print("\n" + "=" * 60)
    print("测试 4.1: WebSocket 消息归一化")
    print("=" * 60)

    from src.channel.normalizer import MessageNormalizer

    normalizer = MessageNormalizer()

    ws_msg = {"type": "chat", "data": {"message": "Hello World"}}
    normalized = normalizer.normalize(ws_msg, "websocket")

    assert normalized.text == "Hello World"
    assert normalized.channel == "websocket"
    print(f"  ✓ 文本: {normalized.text}")
    print(f"  ✓ 渠道: {normalized.channel}")


def test_message_normalizer_telegram():
    """测试 Telegram 消息归一化"""
    print("\n" + "=" * 60)
    print("测试 4.2: Telegram 消息归一化")
    print("=" * 60)

    from src.channel.normalizer import MessageNormalizer

    normalizer = MessageNormalizer()

    tg_msg = {
        "message": {
            "text": "Test message",
            "from": {"id": 123456789, "first_name": "Test"},
            "chat": {"id": 987654321},
            "message_id": 1,
        }
    }
    normalized = normalizer.normalize(tg_msg, "telegram")

    assert normalized.text == "Test message"
    assert normalized.channel == "telegram"
    assert normalized.sender_id == "123456789"
    print(f"  ✓ 文本: {normalized.text}")
    print(f"  ✓ 发送者: {normalized.sender_id}")


# ==================== Message Router Tests ====================

def test_message_router_basic():
    """测试消息路由器"""
    print("\n" + "=" * 60)
    print("测试 5.1: 消息路由器基础")
    print("=" * 60)

    from src.channel.router import MessageRouter

    router = MessageRouter(default_agent_id="default")

    # 添加路由规则
    router.add_rule("telegram", sender_id="123456", agent_id="agent-personal")
    router.add_rule("slack", channel_id="C01ABCDE", agent_id="agent-dev")

    # 精确匹配
    agent = router.route(channel="telegram", sender_id="123456")
    assert agent == "agent-personal", f"Expected 'agent-personal', got '{agent}'"

    # 通道匹配
    agent = router.route(channel="slack", sender_id="anyone", channel_id="C01ABCDE")
    assert agent == "agent-dev", f"Expected 'agent-dev', got '{agent}'"

    # 默认路由
    agent = router.route(channel="web", sender_id="anyone")
    assert agent == "default", f"Expected 'default', got '{agent}'"

    print(f"  ✓ Telegram 精确匹配: agent-personal")
    print(f"  ✓ Slack 通道匹配: agent-dev")
    print(f"  ✓ 默认路由: default")


def test_message_router_priority():
    """测试路由优先级"""
    print("\n" + "=" * 60)
    print("测试 5.2: 路由优先级")
    print("=" * 60)

    from src.channel.router import MessageRouter

    router = MessageRouter(default_agent_id="default")

    # 添加不同优先级的规则
    router.add_rule("telegram", agent_id="agent-general", priority=0)
    router.add_rule("telegram", sender_id="123456", agent_id="agent-personal", priority=10)

    # 高优先级优先
    agent = router.route(channel="telegram", sender_id="123456")
    assert agent == "agent-personal"

    # 无精确匹配时用低优先级
    agent = router.route(channel="telegram", sender_id="other")
    assert agent == "agent-general"

    print(f"  ✓ 高优先级规则优先")


# ==================== Session Manager Tests ====================

def test_session_create():
    """测试会话创建"""
    print("\n" + "=" * 60)
    print("测试 6.1: 会话创建")
    print("=" * 60)

    from src.brain.session import SessionManager, SessionStatus

    manager = SessionManager(storage_path=str(PROJECT_ROOT / ".Zclaw/test_sessions"))
    session = manager.create_session("agent-personal", "telegram", "123456")

    assert session.agent_id == "agent-personal"
    assert session.channel == "telegram"
    assert session.sender_id == "123456"
    assert session.status == SessionStatus.ACTIVE
    assert len(session.message_history) == 0

    print(f"  ✓ 会话 ID: {session.session_id}")
    print(f"  ✓ 状态: {session.status.value}")


def test_session_message_history():
    """测试会话消息历史"""
    print("\n" + "=" * 60)
    print("测试 6.2: 会话消息历史")
    print("=" * 60)

    from src.brain.session import SessionManager

    manager = SessionManager(storage_path=str(PROJECT_ROOT / ".Zclaw/test_sessions"))
    session = manager.create_session("agent-personal", "telegram", "123456")

    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there")

    assert len(session.message_history) == 2
    assert session.message_history[0].role == "user"
    assert session.message_history[0].content == "Hello"

    print(f"  ✓ 消息数量: {len(session.message_history)}")


def test_session_get_or_create():
    """测试获取或创建会话"""
    print("\n" + "=" * 60)
    print("测试 6.3: 获取或创建会话")
    print("=" * 60)

    from src.brain.session import SessionManager

    manager = SessionManager(storage_path=str(PROJECT_ROOT / ".Zclaw/test_sessions"))

    # 第一次获取（创建）
    session1 = manager.get_or_create_session("agent-personal", "telegram", "123456")
    session1.add_message("user", "First message")

    # 第二次获取（返回同一会话）
    session2 = manager.get_or_create_session("agent-personal", "telegram", "123456")

    assert session1.session_id == session2.session_id
    assert len(session2.message_history) == 1

    print(f"  ✓ 同一会话ID: {session1.session_id == session2.session_id}")
    print(f"  ✓ 消息累积: {len(session2.message_history)} 条")


# ==================== Context Assembler Tests ====================

def test_context_assembler():
    """测试上下文组装器"""
    print("\n" + "=" * 60)
    print("测试 7.1: 上下文组装")
    print("=" * 60)

    from src.brain.context import ContextAssembler
    from src.brain.soul_loader import Soul
    from src.brain.user_profile import UserProfile

    assembler = ContextAssembler()

    soul = Soul(
        name="Zclaw",
        version="1.0.0",
        role="AI Assistant",
        personality=["简洁", "直接"],
        behavior_rules=["主动确认"],
    )

    profile = UserProfile(
        name="测试用户",
        timezone="Asia/Shanghai",
        preferences=["Python"],
    )

    context = assembler.assemble(
        soul=soul,
        user_profile=profile,
        recent_memories=["用户上周问了关于 Python 的问题"],
        available_tools=["browser", "shell", "file"],
    )

    assert "Zclaw" in context
    assert "测试用户" in context
    assert "简洁" in context
    assert "browser" in context

    print(f"  ✓ 上下文生成成功 ({len(context)} 字符)")
    print(f"  ✓ 包含 Soul 信息")
    print(f"  ✓ 包含 User 信息")
    print(f"  ✓ 包含工具信息")


# ==================== Cron Scheduler Tests ====================

def test_cron_expression_parsing():
    """测试 Cron 表达式解析"""
    print("\n" + "=" * 60)
    print("测试 8.1: Cron 表达式解析")
    print("=" * 60)

    from src.body.cron import CronScheduler

    scheduler = CronScheduler()

    # 测试标准 cron 表达式
    next_run = scheduler.get_next_run("0 9 * * 1-5")
    assert next_run is not None
    assert next_run.hour == 9
    assert next_run.minute == 0

    # 测试间隔 cron
    next_run = scheduler.get_next_run("*/15 * * * *")
    assert next_run is not None
    assert next_run.minute % 15 == 0

    print(f"  ✓ 标准表达式解析正确")
    print(f"  ✓ 间隔表达式解析正确")
    print(f"  ✓ 下次执行时间: {next_run}")


async def test_cron_scheduler_register():
    """测试 Cron 调度器注册任务"""
    print("\n" + "=" * 60)
    print("测试 8.2: Cron 任务注册")
    print("=" * 60)

    from src.body.cron import CronScheduler, CronTask

    scheduler = CronScheduler()

    task = CronTask(
        task_id="test_task",
        agent_id="agent-personal",
        cron_expr="*/1 * * * *",  # 每分钟
        description="测试任务",
    )

    task_id = await scheduler.schedule(task)
    assert task_id == "test_task"

    scheduled_tasks = scheduler.get_scheduled_tasks()
    assert len(scheduled_tasks) == 1
    assert scheduled_tasks[0].task_id == "test_task"

    print(f"  ✓ 任务注册成功: {task_id}")
    print(f"  ✓ 调度器中任务数: {len(scheduled_tasks)}")


# ==================== Heartbeat Manager Tests ====================

async def test_heartbeat_manager():
    """测试心跳管理器"""
    print("\n" + "=" * 60)
    print("测试 9.1: Heartbeat 管理器")
    print("=" * 60)

    from src.body.heartbeat import HeartbeatManager

    manager = HeartbeatManager(interval_seconds=1)

    tick_count = 0

    async def test_handler():
        nonlocal tick_count
        tick_count += 1
        return [f"task_{tick_count}"]

    manager.register_handler(test_handler)

    await manager.start()
    await asyncio.sleep(2.5)  # 等待至少2次心跳
    await manager.stop()

    assert tick_count >= 2
    assert manager.tick_count >= 2

    print(f"  ✓ 心跳次数: {tick_count}")
    print(f"  ✓ 处理器正常执行")


# ==================== Gateway Tests ====================

async def test_gateway_basic():
    """测试 Gateway 基本功能"""
    print("\n" + "=" * 60)
    print("测试 10.1: Gateway 基本功能")
    print("=" * 60)

    from src.channel.gateway import Gateway

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    # 添加路由规则
    gateway.add_route("telegram", agent_id="agent-personal", sender_id="123456")

    # 验证状态
    status = gateway.get_status()
    assert status["running"] is False
    assert status["default_agent_id"] == "default"

    print(f"  ✓ Gateway 创建成功")
    print(f"  ✓ 默认 Agent: {status['default_agent_id']}")


async def test_gateway_message_routing():
    """测试 Gateway 消息路由"""
    print("\n" + "=" * 60)
    print("测试 10.2: Gateway 消息路由")
    print("=" * 60)

    from src.channel.gateway import Gateway

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    gateway.add_route("telegram", agent_id="agent-personal", sender_id="123456")
    gateway.add_route("slack", agent_id="agent-dev", channel_id="C01ABCDE")

    # 测试路由
    msg = gateway.normalizer.normalize(
        {"type": "chat", "data": {"message": "Hello"}},
        "telegram",
    )

    agent_id = gateway.router.route(
        channel=msg.channel,
        sender_id=msg.sender_id,
    )

    assert agent_id == "default"  # sender_id 不匹配，使用默认

    # 测试匹配
    msg2 = gateway.normalizer.normalize(
        {
            "message": {
                "text": "Hello",
                "from": {"id": 123456, "first_name": "Test"},
            }
        },
        "telegram",
    )
    gateway.router.route(channel=msg2.channel, sender_id=msg2.sender_id)

    print(f"  ✓ 消息归一化正常")
    print(f"  ✓ 路由规则正常")


# ==================== Integration Test ====================

async def test_integration():
    """集成测试"""
    print("\n" + "=" * 60)
    print("测试 11: 集成测试")
    print("=" * 60)

    from src.channel.gateway import Gateway
    from src.brain.context import ContextAssembler

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    # 加载 agents 配置
    await gateway.load_cron_from_agents_config(PROJECT_ROOT / "agents")

    # 获取状态
    status = gateway.get_status()

    print(f"  ✓ Gateway 状态: running={status['running']}")
    print(f"  ✓ Cron 任务数: {status['cron']['task_count']}")
    print(f"  ✓ Heartbeat: interval={status['heartbeat']['interval']}s")

    # 测试上下文组装
    context = gateway.context_assembler.assemble_from_paths(
        soul_path=str(PROJECT_ROOT / "agents/default/SOUL.md"),
        user_path=str(PROJECT_ROOT / "agents/default/USER.md"),
        agents_path=str(PROJECT_ROOT / "agents/default/AGENTS.md"),
        recent_memories=["测试记忆"],
        available_tools=["file_read", "shell"],
    )

    assert len(context) > 0
    assert "Zclaw" in context

    print(f"  ✓ 上下文组装成功 ({len(context)} 字符)")


# ==================== Main ====================

async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("        Zclaw Phase 1 - 架构验证测试")
    print("=" * 60)

    tests = [
        # Soul Loader
        test_soul_loader_basic,
        test_soul_to_system_prompt,
        # User Profile
        test_user_profile_loader,
        test_user_to_context,
        # Agents Config
        test_agents_config_loader,
        # Message Normalizer
        test_message_normalizer_websocket,
        test_message_normalizer_telegram,
        # Message Router
        test_message_router_basic,
        test_message_router_priority,
        # Session Manager
        test_session_create,
        test_session_message_history,
        test_session_get_or_create,
        # Context Assembler
        test_context_assembler,
        # Cron Scheduler
        test_cron_expression_parsing,
        test_cron_scheduler_register,
        # Heartbeat Manager
        test_heartbeat_manager,
        # Gateway
        test_gateway_basic,
        test_gateway_message_routing,
        # Integration
        test_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        test_name = test.__name__
        try:
            if asyncio.iscoroutinefunction(test):
                await test()
            else:
                test()
            passed += 1
        except Exception as e:
            print(f"\n  ❌ {test_name} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"        测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
