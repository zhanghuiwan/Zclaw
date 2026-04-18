"""
Phase 5 验证测试 - 多 Agent 架构

测试 AgentRegistry、InterAgentMessenger 和 SubAgent 功能。
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==================== Agent Registry Tests ====================

def test_agent_registry_register():
    """测试 Agent 注册"""
    print("\n" + "=" * 60)
    print("测试 1: Agent 注册")
    print("=" * 60)

    from src.brain.agent_registry import AgentRegistry, AgentConfig

    registry = AgentRegistry()

    config = AgentConfig(
        id="agent-personal",
        name="私人助理",
        soul_file="agents/personal/SOUL.md",
        routes=[
            {"channel": "telegram", "sender": "123456"},
        ],
        tools=["browser", "shell", "file"],
    )

    registry.register(config)

    assert registry.has_agent("agent-personal")
    assert registry.get_config("agent-personal").name == "私人助理"
    print(f"  ✓ Agent 已注册: {config.id}")


def test_agent_registry_find_by_route():
    """测试根据路由规则查找 Agent"""
    print("\n" + "=" * 60)
    print("测试 2: 根据路由规则查找 Agent")
    print("=" * 60)

    from src.brain.agent_registry import AgentRegistry, AgentConfig

    registry = AgentRegistry()

    registry.register(AgentConfig(
        id="agent-personal",
        name="私人助理",
        routes=[
            {"channel": "telegram", "sender": "123456"},
            {"channel": "whatsapp", "sender": "789"},
        ],
    ))

    registry.register(AgentConfig(
        id="agent-dev",
        name="开发助手",
        routes=[
            {"channel": "slack", "channel_id": "C01ABCDE"},
        ],
    ))

    # 精确匹配
    agent_id = registry.find_agent_by_route("telegram", sender_id="123456")
    assert agent_id == "agent-personal"
    print(f"  ✓ Telegram 精确匹配: {agent_id}")

    # 通道匹配
    agent_id = registry.find_agent_by_route("slack", channel_id="C01ABCDE")
    assert agent_id == "agent-dev"
    print(f"  ✓ Slack 通道匹配: {agent_id}")

    # 无匹配
    agent_id = registry.find_agent_by_route("unknown", sender_id="xxx")
    assert agent_id is None
    print(f"  ✓ 无匹配时返回 None")


def test_agent_registry_list():
    """测试列出所有 Agent"""
    print("\n" + "=" * 60)
    print("测试 3: 列出所有 Agent")
    print("=" * 60)

    from src.brain.agent_registry import AgentRegistry, AgentConfig

    registry = AgentRegistry()

    registry.register(AgentConfig(id="agent-1", name="Agent 1"))
    registry.register(AgentConfig(id="agent-2", name="Agent 2"))

    agents = registry.list_agents()
    assert len(agents) == 2
    print(f"  ✓ 列出 {len(agents)} 个 Agent")


# ==================== Inter-Agent Messenger Tests ====================

async def test_inter_agent_send():
    """测试 Agent 间消息发送"""
    print("\n" + "=" * 60)
    print("测试 4: Agent 间消息发送")
    print("=" * 60)

    from src.brain.inter_agent import InterAgentMessenger

    messenger = InterAgentMessenger()

    msg_id = await messenger.send(
        from_agent="agent-personal",
        to_agent="agent-dev",
        content={"task": "检查部署状态"},
    )

    assert msg_id is not None
    print(f"  ✓ 消息已发送: {msg_id}")

    # 验证收件箱
    inbox = messenger.get_inbox("agent-dev")
    assert len(inbox) == 1
    assert inbox[0].from_agent == "agent-personal"
    print(f"  ✓ 收件箱验证成功")


async def test_inter_agent_broadcast():
    """测试广播消息"""
    print("\n" + "=" * 60)
    print("测试 5: 广播消息")
    print("=" * 60)

    from src.brain.inter_agent import InterAgentMessenger

    messenger = InterAgentMessenger()

    # 模拟多个 Agent 的收件箱
    messenger._inboxes["agent-1"] = []
    messenger._inboxes["agent-2"] = []
    messenger._inboxes["agent-3"] = []

    targets = await messenger.broadcast(
        from_agent="agent-personal",
        content={"alert": "系统升级"},
        exclude_agents=["agent-3"],
    )

    assert len(targets) == 2
    assert "agent-1" in targets
    assert "agent-2" in targets
    assert "agent-3" not in targets
    print(f"  ✓ 广播到 {len(targets)} 个 Agent（排除 1 个）")


async def test_inter_agent_inbox_management():
    """测试收件箱管理"""
    print("\n" + "=" * 60)
    print("测试 6: 收件箱管理")
    print("=" * 60)

    from src.brain.inter_agent import InterAgentMessenger

    messenger = InterAgentMessenger()

    # 发送多条消息
    await messenger.send("agent-1", "agent-2", {"msg": "1"})
    await messenger.send("agent-1", "agent-2", {"msg": "2"})
    await messenger.send("agent-1", "agent-2", {"msg": "3"})

    # 查看未取走的消息
    messages = messenger.peek_inbox("agent-2", count=2)
    assert len(messages) == 2
    print(f"  ✓ peek_inbox 返回 {len(messages)} 条")

    # 取走一条
    msg = messenger.pop_message("agent-2", messages[0].msg_id)
    assert msg is not None
    print(f"  ✓ pop_message 取走消息: {msg.msg_id}")

    # 剩余消息
    inbox = messenger.get_inbox("agent-2")
    assert len(inbox) == 2
    print(f"  ✓ 剩余消息: {len(inbox)} 条")


# ==================== Sub-Agent Manager Tests ====================

async def test_sub_agent_create():
    """测试子代理创建"""
    print("\n" + "=" * 60)
    print("测试 7: 子代理创建")
    print("=" * 60)

    from src.brain.sub_agent import SubAgentManager

    manager = SubAgentManager()

    sub_agent = await manager.create(
        parent_id="agent-personal",
        task="分析代码结构",
        inherited_context={"repo": "Zclaw"},
    )

    assert sub_agent.sub_agent_id is not None
    assert sub_agent.config.parent_id == "agent-personal"
    assert sub_agent.config.task == "分析代码结构"
    assert sub_agent.status.value == "created"
    print(f"  ✓ 子代理已创建: {sub_agent.sub_agent_id}")


async def test_sub_agent_lifecycle():
    """测试子代理生命周期"""
    print("\n" + "=" * 60)
    print("测试 8: 子代理生命周期")
    print("=" * 60)

    from src.brain.sub_agent import SubAgentManager, SubAgentStatus

    manager = SubAgentManager()

    # 创建
    sub_agent = await manager.create(
        parent_id="agent-personal",
        task="测试任务",
    )
    sub_id = sub_agent.sub_agent_id
    print(f"  ✓ 创建: {sub_id} (status={sub_agent.status.value})")

    # 启动
    await manager.start(sub_id)
    sub_agent = manager.get(sub_id)
    assert sub_agent.status == SubAgentStatus.RUNNING
    print(f"  ✓ 启动: {sub_id} (status={sub_agent.status.value})")

    # 完成
    await manager.complete(sub_id, result={"analysis": "完成"})
    sub_agent = manager.get(sub_id)
    assert sub_agent.status == SubAgentStatus.DONE
    assert sub_agent.result is not None
    print(f"  ✓ 完成: {sub_id} (status={sub_agent.status.value})")

    # 销毁
    await manager.destroy(sub_id)
    assert manager.get(sub_id) is None
    print(f"  ✓ 销毁: {sub_id}")


async def test_sub_agent_get_by_parent():
    """测试获取父代理的子代理"""
    print("\n" + "=" * 60)
    print("测试 9: 获取父代理的子代理")
    print("=" * 60)

    from src.brain.sub_agent import SubAgentManager

    manager = SubAgentManager()

    # 创建多个子代理
    sub1 = await manager.create(parent_id="agent-1", task="任务1")
    sub2 = await manager.create(parent_id="agent-1", task="任务2")
    sub3 = await manager.create(parent_id="agent-2", task="任务3")

    # 获取父代理的子代理
    children = manager.get_by_parent("agent-1")
    assert len(children) == 2
    print(f"  ✓ agent-1 有 {len(children)} 个子代理")

    # 获取活跃子代理
    await manager.start(sub1.sub_agent_id)
    await manager.start(sub2.sub_agent_id)
    await manager.start(sub3.sub_agent_id)

    active = manager.get_active()
    assert len(active) == 3
    print(f"  ✓ 活跃子代理: {len(active)} 个")


async def test_sub_agent_cleanup():
    """测试子代理清理"""
    print("\n" + "=" * 60)
    print("测试 10: 子代理清理")
    print("=" * 60)

    from src.brain.sub_agent import SubAgentManager

    manager = SubAgentManager()

    # 创建并完成多个子代理
    sub1 = await manager.create(parent_id="agent-1", task="任务1")
    await manager.complete(sub1.sub_agent_id, result="完成")

    sub2 = await manager.create(parent_id="agent-1", task="任务2")
    await manager.fail(sub2.sub_agent_id, error="失败")

    sub3 = await manager.create(parent_id="agent-1", task="任务3")
    await manager.start(sub3.sub_agent_id)

    # 清理已完成的
    cleaned = manager.cleanup_completed("agent-1")
    assert cleaned == 2

    # 剩余活跃的
    children = manager.get_by_parent("agent-1")
    assert len(children) == 1
    assert children[0].sub_agent_id == sub3.sub_agent_id
    print(f"  ✓ 清理了 {cleaned} 个，剩余 {len(children)} 个")


# ==================== Main ====================

async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("        Zclaw Phase 5 - 多 Agent 架构验证")
    print("=" * 60)

    tests = [
        # Agent Registry
        test_agent_registry_register,
        test_agent_registry_find_by_route,
        test_agent_registry_list,
        # Inter-Agent Messenger
        test_inter_agent_send,
        test_inter_agent_broadcast,
        test_inter_agent_inbox_management,
        # Sub-Agent Manager
        test_sub_agent_create,
        test_sub_agent_lifecycle,
        test_sub_agent_get_by_parent,
        test_sub_agent_cleanup,
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
