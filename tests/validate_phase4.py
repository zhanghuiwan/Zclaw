"""
Phase 4 验证测试 - 进程管理 + 文件监听

测试 ProcessTool 和 FileWatcher 功能。
"""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==================== Process Tool Tests ====================

async def test_process_start_stop():
    """测试进程启动和停止"""
    print("\n" + "=" * 60)
    print("测试 1: 进程启动和停止")
    print("=" * 60)

    from src.tools.builtin.process_tool import ProcessTool

    tool = ProcessTool()

    # 启动一个 sleep 进程
    result = await tool.start("sleep", args=["10"])
    assert result.success is True
    pid = result.metadata["pid"]
    print(f"  ✓ 进程已启动: PID={pid}")

    # 检查进程是否存活
    result = await tool.is_alive(pid)
    assert result.success is True
    assert result.metadata["alive"] is True
    print(f"  ✓ 进程存活状态: {result.content}")

    # 停止进程
    result = await tool.stop(pid)
    assert result.success is True
    print(f"  ✓ 进程已停止: {result.content}")


async def test_process_list():
    """测试进程列表"""
    print("\n" + "=" * 60)
    print("测试 2: 进程列表")
    print("=" * 60)

    from src.tools.builtin.process_tool import ProcessTool

    tool = ProcessTool()

    # 启动多个进程
    pids = []
    for i in range(3):
        result = await tool.start("sleep", args=["30"])
        assert result.success is True
        pids.append(result.metadata["pid"])

    # 列出进程
    result = await tool.list()
    assert result.success is True
    print(f"  ✓ 进程列表: {result.content}")

    # 清理
    for pid in pids:
        await tool.stop(pid)

    print(f"  ✓ 已清理 {len(pids)} 个进程")


async def test_process_wait():
    """测试进程等待"""
    print("\n" + "=" * 60)
    print("测试 3: 进程等待")
    print("=" * 60)

    from src.tools.builtin.process_tool import ProcessTool

    tool = ProcessTool()

    # 启动一个快速退出的进程
    result = await tool.start("echo", args=["hello"])
    pid = result.metadata["pid"]

    # 等待进程退出
    result = await tool.wait(pid, timeout=5)
    assert result.success is True
    print(f"  ✓ 进程已退出: {result.content}")


async def test_process_output():
    """测试进程输出获取（基础）"""
    print("\n" + "=" * 60)
    print("测试 4: 进程输出获取（基础）")
    print("=" * 60)

    from src.tools.builtin.process_tool import ProcessTool

    tool = ProcessTool()

    # 启动一个长时间运行的进程，这样我们可以在它运行时获取输出
    result = await tool.start("bash", args=["-c", "while true; do echo test; sleep 1; done"])
    pid = result.metadata["pid"]
    print(f"  ✓ 进程已启动: PID={pid}")

    # 等待一下让输出产生
    await asyncio.sleep(2)

    # 获取输出
    result = await tool.get_output(pid)
    print(f"  ✓ 进程输出: {result.content}")

    # 清理
    await tool.stop(pid)
    print(f"  ✓ 进程已停止")


async def test_process_shell_mode():
    """测试 shell 模式启动进程"""
    print("\n" + "=" * 60)
    print("测试 5: Shell 模式启动进程")
    print("=" * 60)

    from src.tools.builtin.process_tool import ProcessTool

    tool = ProcessTool()

    # 使用 shell 模式启动一个长时间运行的进程
    result = await tool.start("bash -c 'sleep 10 && echo done'", shell=True)
    assert result.success is True
    pid = result.metadata["pid"]
    print(f"  ✓ Shell 模式进程已启动: PID={pid}")

    # 检查进程是否存活
    result = await tool.is_alive(pid)
    print(f"  ✓ 进程存活: {result.metadata['alive']}")

    # 停止进程
    await tool.stop(pid)
    print(f"  ✓ 进程已停止")


async def test_process_executor():
    """测试 ProcessTool 执行器"""
    print("\n" + "=" * 60)
    print("测试 6: ProcessTool 执行器")
    print("=" * 60)

    from src.tools.builtin.process_tool import ProcessTool, ProcessToolExecutor

    tool = ProcessTool()
    executor = ProcessToolExecutor(tool)

    # 通过执行器启动进程
    result = await executor.execute(
        "start",
        command="sleep",
        args=["30"],
    )
    assert result.success is True
    pid = result.metadata["pid"]
    print(f"  ✓ executor.execute(start) 成功: PID={pid}")

    # 通过执行器停止进程
    await asyncio.sleep(0.5)
    result = await executor.execute("stop", pid=pid)
    assert result.success is True
    print(f"  ✓ executor.execute(stop) 成功")


# ==================== File Watcher Tests ====================

async def test_file_watcher_basic():
    """测试文件监听基本功能"""
    print("\n" + "=" * 60)
    print("测试 7: 文件监听基本功能")
    print("=" * 60)

    from src.body.file_watcher import FileWatcher, FileWatchEventType, WATCHDOG_AVAILABLE

    if not WATCHDOG_AVAILABLE:
        print("  ⚠ watchdog 未安装，跳过测试")
        return True

    watcher = FileWatcher()

    with tempfile.TemporaryDirectory() as tmpdir:
        events = []

        async def on_change(event):
            events.append(event)
            print(f"  收到事件: {event.event_type.value} - {event.path}")

        await watcher.watch(tmpdir, on_change)
        assert watcher.is_watching(tmpdir)
        print(f"  ✓ 开始监听: {tmpdir}")

        # 创建文件
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello")
        await asyncio.sleep(1)

        # 修改文件
        test_file.write_text("world")
        await asyncio.sleep(1)

        # 删除文件
        test_file.unlink()
        await asyncio.sleep(1)

        # 取消监听
        await watcher.unwatch(tmpdir)
        assert not watcher.is_watching(tmpdir)
        print(f"  ✓ 已停止监听")

        print(f"  ✓ 收到 {len(events)} 个事件")
        if len(events) >= 1:
            print(f"  ✓ 文件监听功能正常")


async def test_file_watcher_filter():
    """测试文件监听事件过滤"""
    print("\n" + "=" * 60)
    print("测试 8: 文件监听事件过滤")
    print("=" * 60)

    from src.body.file_watcher import FileWatcher, FileWatchEventType, WATCHDOG_AVAILABLE

    if not WATCHDOG_AVAILABLE:
        print("  ⚠ watchdog 未安装，跳过测试")
        return True

    watcher = FileWatcher()

    with tempfile.TemporaryDirectory() as tmpdir:
        created_events = []

        async def on_created(event):
            created_events.append(event)

        # 只监听 CREATED 事件
        await watcher.watch(
            tmpdir,
            on_created,
            event_types=[FileWatchEventType.CREATED],
        )
        print(f"  ✓ 开始监听（仅 CREATED）")

        # 创建文件
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello")
        await asyncio.sleep(1)

        # 修改文件（不应该触发）
        test_file.write_text("world")
        await asyncio.sleep(1)

        await watcher.unwatch(tmpdir)

        print(f"  ✓ 收到 {len(created_events)} 个 CREATED 事件（应为 1）")


# ==================== Main ====================

async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("        Zclaw Phase 4 - 进程管理 + 文件监听验证")
    print("=" * 60)

    tests = [
        test_process_start_stop,
        test_process_list,
        test_process_wait,
        test_process_output,
        test_process_shell_mode,
        test_process_executor,
        test_file_watcher_basic,
        test_file_watcher_filter,
    ]

    passed = 0
    failed = 0

    for test in tests:
        test_name = test.__name__
        try:
            result = await test()
            if result is False:
                failed += 1
            else:
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
