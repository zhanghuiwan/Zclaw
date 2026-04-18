"""
Heartbeat 心跳管理器

提供轻量级的定期检查机制，让 Agent 能够执行"日常巡检"类任务。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


HeartbeatHandler = Callable[[], Awaitable[list[str]]]
"""心跳处理器类型，返回待处理任务列表"""


class HeartbeatManager:
    """
    Heartbeat 心跳管理器

    以固定间隔执行检查任务，如检查待办队列、外部触发器等。
    """

    def __init__(self, interval_seconds: int = 300):
        """
        Args:
            interval_seconds: 心跳间隔（默认 5 分钟）
        """
        self._interval = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self._handlers: list[HeartbeatHandler] = []
        self._last_tick: datetime | None = None
        self._tick_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def interval(self) -> int:
        return self._interval

    @property
    def last_tick(self) -> datetime | None:
        return self._last_tick

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def set_interval(self, interval_seconds: int) -> None:
        """动态调整心跳间隔"""
        if interval_seconds < 10:
            logger.warning(f"心跳间隔不能小于 10 秒，设置最小值")
            interval_seconds = 10
        self._interval = interval_seconds
        logger.info(f"心跳间隔已调整为 {interval_seconds} 秒")

    def register_handler(self, handler: HeartbeatHandler) -> None:
        """
        注册心跳处理器。

        Args:
            handler: 异步函数，返回待处理任务列表
        """
        self._handlers.append(handler)
        logger.info(f"已注册心跳处理器: {handler.__name__}")

    def unregister_handler(self, handler: HeartbeatHandler) -> bool:
        """注销心跳处理器"""
        if handler in self._handlers:
            self._handlers.remove(handler)
            return True
        return False

    async def tick(self) -> list[str]:
        """
        执行一次心跳检查。

        Returns:
            list[str]: 待处理任务列表
        """
        self._last_tick = datetime.now()
        self._tick_count += 1
        all_tasks = []

        logger.debug(f"Heartbeat tick #{self._tick_count}")

        for handler in self._handlers:
            try:
                tasks = await handler()
                if tasks:
                    all_tasks.extend(tasks)
                    logger.debug(f"Handler {handler.__name__} 返回 {len(tasks)} 个任务")
            except Exception as e:
                logger.error(f"心跳处理器执行失败: {handler.__name__} - {e}")

        if all_tasks:
            logger.info(f"Heartbeat #{self._tick_count}: {len(all_tasks)} 个待处理任务")

        return all_tasks

    async def start(self) -> None:
        """启动心跳管理器"""
        if self._running:
            logger.warning("Heartbeat 管理器已在运行")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Heartbeat 管理器已启动（间隔: {self._interval}s）")

    async def stop(self) -> None:
        """停止心跳管理器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Heartbeat 管理器已停止")

    async def _run_loop(self) -> None:
        """心跳主循环"""
        while self._running:
            try:
                await self.tick()
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat 异常: {e}")
                await asyncio.sleep(self._interval)

    async def wait_for_tasks(self, timeout: float = 60) -> list[str]:
        """
        等待并收集一次心跳的所有待处理任务。

        Args:
            timeout: 超时时间（秒）

        Returns:
            list[str]: 待处理任务列表
        """
        tasks = []

        async def background_tick():
            nonlocal tasks
            tasks = await self.tick()

        asyncio.create_task(background_tick())
        await asyncio.sleep(min(self._interval, timeout))

        return tasks

    def get_status(self) -> dict[str, Any]:
        """获取心跳管理器状态"""
        return {
            "running": self._running,
            "interval": self._interval,
            "last_tick": self._last_tick.isoformat() if self._last_tick else None,
            "tick_count": self._tick_count,
            "handler_count": len(self._handlers),
        }
