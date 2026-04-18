"""
Cron 调度器

提供定时任务调度功能，支持标准的 6 字段 cron 表达式。
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from croniter import croniter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class CronTask:
    """Cron 任务定义"""
    task_id: str
    agent_id: str
    cron_expr: str           # cron 表达式
    description: str         # 任务描述
    command: str = ""        # 执行的命令
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None


@dataclass
class CronJob:
    """Cron 作业（已解析的定时任务）"""
    task: CronTask
    cron: croniter


class CronScheduler:
    """
    Cron 调度器

    支持 6 字段 cron 表达式（秒 分 时 日 月 周），
    与传统 Unix cron（5字段）兼容。
    """

    def __init__(self):
        self._tasks: dict[str, CronTask] = {}
        self._jobs: dict[str, CronJob] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._handlers: list[Callable[[CronTask], Awaitable[Any]]] = []
        self._check_interval = 60  # 每分钟检查一次

    @property
    def is_running(self) -> bool:
        return self._running

    def add_handler(self, handler: Callable[[CronTask], Awaitable[Any]]) -> None:
        """添加任务执行处理器"""
        self._handlers.append(handler)

    async def schedule(self, task: CronTask) -> str:
        """
        注册定时任务。

        Args:
            task: CronTask 对象

        Returns:
            str: 任务 ID
        """
        # 验证 cron 表达式
        base_time = datetime.now()
        cron = None
        error_msg = None

        # 尝试不同的格式
        for expr in [task.cron_expr, f"0 {task.cron_expr}"]:
            try:
                cron = croniter(expr, base_time)
                break
            except (ValueError, KeyError) as e:
                error_msg = str(e)
                continue

        if cron is None:
            logger.error(f"无效的 cron 表达式: {task.cron_expr} - {error_msg}")
            raise ValueError(f"无效的 cron 表达式: {task.cron_expr}")

        task.next_run = cron.get_next(datetime)
        self._tasks[task.task_id] = task
        self._jobs[task.task_id] = CronJob(task=task, cron=cron)
        logger.info(f"注册 Cron 任务: {task.task_id} ({task.cron_expr}) -> 下次执行: {task.next_run}")
        return task.task_id

    async def unschedule(self, task_id: str) -> bool:
        """取消定时任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            del self._jobs[task_id]
            logger.info(f"取消 Cron 任务: {task_id}")
            return True
        return False

    def get_due_tasks(self) -> list[CronTask]:
        """获取所有到期任务"""
        now = datetime.now()
        due_tasks = []

        for task in self._tasks.values():
            if not task.enabled:
                continue

            if task.next_run and task.next_run <= now:
                due_tasks.append(task)
                # 计算下次执行时间
                job = self._jobs.get(task.task_id)
                if job:
                    task.last_run = now
                    task.next_run = job.cron.get_next(datetime)

        return due_tasks

    async def execute_due_tasks(self) -> list[dict[str, Any]]:
        """
        执行所有到期任务。

        Returns:
            list: 执行结果列表
        """
        due_tasks = self.get_due_tasks()
        results = []

        for task in due_tasks:
            logger.info(f"执行 Cron 任务: {task.task_id} - {task.description}")

            result = {
                "task_id": task.task_id,
                "agent_id": task.agent_id,
                "description": task.description,
                "command": task.command,
                "success": False,
                "error": None,
            }

            try:
                if self._handlers:
                    # 调用所有处理器
                    for handler in self._handlers:
                        await handler(task)
                    result["success"] = True
                else:
                    logger.warning(f"任务 {task.task_id} 没有注册处理器")
            except Exception as e:
                logger.error(f"执行 Cron 任务失败: {task.task_id} - {e}")
                result["error"] = str(e)

            results.append(result)

        return results

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("Cron 调度器已在运行")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Cron 调度器已启动")

    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Cron 调度器已停止")

    async def _run_loop(self) -> None:
        """调度器主循环"""
        while self._running:
            try:
                # 执行到期任务
                await self.execute_due_tasks()

                # 等待下一次检查
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cron 调度器异常: {e}")
                await asyncio.sleep(self._check_interval)

    def get_next_run(self, cron_expr: str) -> datetime | None:
        """
        获取 cron 表达式下一次执行时间。

        Args:
            cron_expr: cron 表达式

        Returns:
            datetime | None: 下次执行时间
        """
        base_time = datetime.now()
        cron = None

        # 尝试不同的格式
        for expr in [cron_expr, f"0 {cron_expr}"]:
            try:
                cron = croniter(expr, base_time)
                break
            except (ValueError, KeyError):
                continue

        if cron is None:
            logger.error(f"无效的 cron 表达式: {cron_expr}")
            return None

        return cron.get_next(datetime)

    def get_scheduled_tasks(self) -> list[CronTask]:
        """获取所有已注册的任务"""
        return list(self._tasks.values())

    def get_status(self) -> dict[str, Any]:
        """获取调度器状态"""
        return {
            "running": self._running,
            "task_count": len(self._tasks),
            "tasks": [
                {
                    "task_id": t.task_id,
                    "agent_id": t.agent_id,
                    "description": t.description,
                    "cron_expr": t.cron_expr,
                    "enabled": t.enabled,
                    "last_run": t.last_run.isoformat() if t.last_run else None,
                    "next_run": t.next_run.isoformat() if t.next_run else None,
                }
                for t in self._tasks.values()
            ],
        }
