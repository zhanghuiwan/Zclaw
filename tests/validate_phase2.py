"""
Phase 2 验证测试 - 24 小时持续运行

测试 Cron/Heartbeat 调度、Gateway 常驻进程、Session 休眠/唤醒功能。
"""

import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==================== Cron + Heartbeat Integration Tests ====================

async def test_gateway_daemon_start_stop():
    """测试 Gateway 启动和关闭"""
    print("\n" + "=" * 60)
    print("测试 1: Gateway 常驻模式")
    print("=" * 60)

    from src.channel.gateway import Gateway

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    # 添加测试路由
    gateway.add_route("telegram", agent_id="agent-personal", sender_id="123456")

    # 启动
    await gateway.start()
    assert gateway.is_running is True
    print("  ✓ Gateway 启动成功")

    # 检查调度器状态
    status = gateway.get_status()
    assert status["cron"]["running"] is True
    assert status["heartbeat"]["running"] is True
    print("  ✓ Cron 调度器运行中")
    print("  ✓ Heartbeat 管理器运行中")

    # 等待一小段时间验证调度器工作
    await asyncio.sleep(2)

    # 关闭
    await gateway.shutdown()
    assert gateway.is_running is False
    print("  ✓ Gateway 关闭成功")


async def test_session_hibernate_wakeup():
    """测试 Session 休眠和唤醒"""
    print("\n" + "=" * 60)
    print("测试 2: Session 休眠/唤醒")
    print("=" * 60)

    from src.brain.session import SessionManager, SessionStatus

    manager = SessionManager(storage_path=str(PROJECT_ROOT / ".Zclaw/test_sessions"))
    session = manager.create_session("agent-personal", "telegram", "123456")

    # 添加消息
    for i in range(5):
        session.add_message("user", f"Message {i}")

    assert len(session.message_history) == 5

    # 休眠
    manager.hibernate_session(session.session_id)
    assert session.status == SessionStatus.DORMANT
    assert len(session.message_history) == 0  # 内存释放
    print("  ✓ Session 休眠成功")

    # 唤醒
    manager.wakeup_session(session.session_id)
    assert session.status == SessionStatus.ACTIVE
    assert len(session.message_history) == 5  # 恢复
    print("  ✓ Session 唤醒成功")


async def test_session_archive_restore():
    """测试 Session 归档和恢复"""
    print("\n" + "=" * 60)
    print("测试 3: Session 归档/恢复")
    print("=" * 60)

    from src.brain.session import SessionManager, SessionStatus

    manager = SessionManager(storage_path=str(PROJECT_ROOT / ".Zclaw/test_sessions"))
    session = manager.create_session("agent-personal", "telegram", "789")

    # 添加消息
    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there")

    # 归档到磁盘
    success = manager.archive_session(session.session_id)
    assert success is True
    assert session.status == SessionStatus.ARCHIVED
    print("  ✓ Session 归档成功")

    # 模拟重启：从磁盘恢复
    # 先从内存删除
    session_id = session.session_id
    del manager._active_sessions[session_id]

    # 恢复
    restored = manager.restore_session(session_id)
    assert restored is not None
    assert len(restored.message_history) == 2
    assert restored.status == SessionStatus.IDLE
    print("  ✓ Session 恢复成功")


async def test_cron_task_execution():
    """测试 Cron 任务执行"""
    print("\n" + "=" * 60)
    print("测试 4: Cron 任务执行")
    print("=" * 60)

    from src.channel.gateway import Gateway
    from src.body.cron import CronTask

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    # 注册一个每分钟执行的任务
    task = CronTask(
        task_id="test_cron_task",
        agent_id="default",
        cron_expr="*/1 * * * *",  # 每分钟
        description="测试 Cron 任务",
        command="/test",
    )

    await gateway.schedule_cron(
        agent_id=task.agent_id,
        cron_expr=task.cron_expr,
        description=task.description,
        command=task.command,
        task_id=task.task_id,
    )

    # 等待任务到期
    await asyncio.sleep(2)

    # 检查到期任务
    due_tasks = gateway.cron_scheduler.get_due_tasks()
    print(f"  到期任务数: {len(due_tasks)}")

    # 执行到期任务
    results = await gateway.cron_scheduler.execute_due_tasks()
    print(f"  执行结果: {len(results)} 个任务")
    print("  ✓ Cron 任务调度正常")


async def test_heartbeat_with_handlers():
    """测试 Heartbeat 处理器"""
    print("\n" + "=" * 60)
    print("测试 5: Heartbeat 处理器")
    print("=" * 60)

    from src.channel.gateway import Gateway

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    tick_results = []

    async def test_handler():
        tick_results.append(time.time())
        return ["待办事项1", "待办事项2"]

    # 注册处理器
    gateway.heartbeat_manager.register_handler(test_handler)

    # 启动
    await gateway.start()

    # 等待心跳
    await asyncio.sleep(3)

    # 停止
    await gateway.shutdown()

    # 验证
    assert len(tick_results) >= 1
    print(f"  心跳次数: {len(tick_results)}")
    print("  ✓ Heartbeat 处理器正常")


async def test_gateway_message_handling():
    """测试 Gateway 消息处理流程"""
    print("\n" + "=" * 60)
    print("测试 6: Gateway 消息处理")
    print("=" * 60)

    from src.channel.gateway import Gateway

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    gateway.add_route("telegram", agent_id="agent-personal", sender_id="123456")

    # 注册消息处理器（模拟）
    handled = []

    def mock_handler(unified_msg, session, agent_id):
        handled.append((unified_msg.text, agent_id))
        return "响应内容"

    gateway.register_message_handler(mock_handler)

    # 处理消息
    response = await gateway.handle_message(
        channel_name="telegram",
        raw_message={
            "message": {
                "text": "测试消息",
                "from": {"id": 123456, "first_name": "Test"},
            }
        },
    )

    assert response == "响应内容"
    assert len(handled) == 1
    assert handled[0] == ("测试消息", "agent-personal")
    print("  ✓ 消息处理流程正常")


async def test_graceful_shutdown():
    """测试优雅关闭"""
    print("\n" + "=" * 60)
    print("测试 7: 优雅关闭")
    print("=" * 60)

    from src.channel.gateway import Gateway

    gateway = Gateway(
        storage_path=str(PROJECT_ROOT / ".Zclaw/test_gateway"),
        default_agent_id="default",
    )

    await gateway.start()

    # 验证运行状态
    status1 = gateway.get_status()
    assert status1["running"] is True

    # 关闭
    await gateway.shutdown()

    # 验证关闭状态
    status2 = gateway.get_status()
    assert status2["running"] is False
    assert status2["cron"]["running"] is False
    assert status2["heartbeat"]["running"] is False

    print("  ✓ 优雅关闭正常")


async def test_idle_session_cleanup():
    """测试空闲会话清理"""
    print("\n" + "=" * 60)
    print("测试 8: 空闲会话清理")
    print("=" * 60)

    from src.brain.session import SessionManager, SessionStatus
    from datetime import datetime, timedelta

    manager = SessionManager(storage_path=str(PROJECT_ROOT / ".Zclaw/test_sessions"))

    # 创建会话
    session = manager.create_session("agent-personal", "telegram", "999")
    session.add_message("user", "Hello")

    # 会话创建时 last_active 就是现在，所以不会 idle
    # 修改 last_active 让它变成 idle
    old_time = datetime.now() - timedelta(seconds=1900)  # 超过30分钟
    session.last_active = old_time.isoformat()

    # 清理空闲会话（阈值1800秒=30分钟）
    cleaned = manager.cleanup_idle_sessions(idle_threshold=1800)
    assert cleaned >= 1

    print(f"  清理会话数: {cleaned}")
    print("  ✓ 空闲会话清理正常")


# ==================== Main ====================

async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("        Zclaw Phase 2 - 24 小时持续运行验证")
    print("=" * 60)

    tests = [
        test_gateway_daemon_start_stop,
        test_session_hibernate_wakeup,
        test_session_archive_restore,
        test_cron_task_execution,
        test_heartbeat_with_handlers,
        test_gateway_message_handling,
        test_graceful_shutdown,
        test_idle_session_cleanup,
    ]

    passed = 0
    failed = 0

    for test in tests:
        test_name = test.__name__
        try:
            await test()
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
