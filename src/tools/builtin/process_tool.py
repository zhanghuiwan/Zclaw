"""
Process Tool - 进程管理工具

提供进程生命周期管理能力：
- 启动进程
- 停止进程
- 列出进程
- 检查进程状态
- 监控进程输出
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """进程信息"""
    pid: int
    name: str
    command: str
    status: str  # running/stopped/zombie
    cpu_percent: float = 0.0
    memory_percent: float = 0.0


class ProcessTool(BaseTool):
    """
    进程管理工具

    管理和监控本地进程的生命周期。
    """

    name = "process"
    description = "管理系统进程，包括启动、停止、查看状态等"
    danger_level = "confirm"  # 需要确认，因为可以启动/停止进程

    def __init__(self):
        self._processes: dict[int, asyncio.subprocess.Process] = {}
        self._process_outputs: dict[int, list[str]] = {}

    async def start(
        self,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        shell: bool = False,
    ) -> ToolResult:
        """
        启动一个新进程。

        Args:
            command: 要执行的命令
            args: 命令参数
            cwd: 工作目录
            env: 环境变量
            shell: 是否使用 shell 执行

        Returns:
            ToolResult: 包含 PID 和启动状态
        """
        try:
            if shell and isinstance(args, list):
                # shell 模式下，args 被忽略
                cmd_str = command
            else:
                cmd_str = command

            if shell:
                cmd = ["sh", "-c", cmd_str]
            elif args:
                cmd = [command] + args
            else:
                cmd = [command]

            # 设置环境变量
            process_env = None
            if env:
                process_env = os.environ.copy()
                process_env.update(env)

            # 启动进程
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=process_env,
            )

            self._processes[process.pid] = process
            self._process_outputs[process.pid] = []

            logger.info(f"启动进程: PID={process.pid}, command={' '.join(cmd)}")

            return ToolResult(
                success=True,
                content=f"进程已启动: PID={process.pid}\n命令: {' '.join(cmd)}",
                metadata={
                    "pid": process.pid,
                    "command": " ".join(cmd),
                    "cwd": cwd or os.getcwd(),
                },
            )

        except Exception as e:
            logger.error(f"启动进程失败: {e}")
            return ToolResult(
                success=False,
                content=f"启动进程失败: {e}",
                error=str(e),
            )

    async def stop(self, pid: int, force: bool = False) -> ToolResult:
        """
        停止指定进程。

        Args:
            pid: 进程 ID
            force: 是否强制终止

        Returns:
            ToolResult: 操作结果
        """
        try:
            if pid not in self._processes:
                # 尝试直接终止系统进程
                try:
                    os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)
                    return ToolResult(
                        success=True,
                        content=f"已终止进程: PID={pid}",
                        metadata={"pid": pid, "force": force},
                    )
                except ProcessLookupError:
                    return ToolResult(
                        success=False,
                        content=f"进程不存在: PID={pid}",
                        error=f"进程 {pid} 不存在",
                    )
                except PermissionError:
                    return ToolResult(
                        success=False,
                        content=f"权限不足: PID={pid}",
                        error=f"没有权限终止进程 {pid}",
                    )

            process = self._processes[pid]

            if force:
                process.kill()
            else:
                process.terminate()

            # 等待进程退出
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

            del self._processes[pid]
            if pid in self._process_outputs:
                del self._process_outputs[pid]

            logger.info(f"已终止进程: PID={pid}, force={force}")

            return ToolResult(
                success=True,
                content=f"已终止进程: PID={pid}",
                metadata={"pid": pid, "force": force},
            )

        except Exception as e:
            logger.error(f"终止进程失败: {e}")
            return ToolResult(
                success=False,
                content=f"终止进程失败: {e}",
                error=str(e),
            )

    async def is_alive(self, pid: int) -> ToolResult:
        """
        检查进程是否存活。

        Args:
            pid: 进程 ID

        Returns:
            ToolResult: 包含存活状态
        """
        alive = self._is_pid_alive(pid)

        if pid in self._processes:
            process = self._processes[pid]
            proc_alive = process.returncode is None
        else:
            proc_alive = alive

        final_alive = alive and proc_alive

        return ToolResult(
            success=True,
            content=f"进程 {'存活' if final_alive else '已退出'}",
            metadata={
                "pid": pid,
                "alive": final_alive,
                "tracked": pid in self._processes,
            },
        )

    def _is_pid_alive(self, pid: int) -> bool:
        """检查 PID 是否存活"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    async def list(self) -> ToolResult:
        """
        列出所有跟踪的进程。

        Returns:
            ToolResult: 进程列表
        """
        results = []
        dead_pids = []

        for pid, process in self._processes.items():
            returncode = process.returncode
            status = "running" if returncode is None else f"exited({returncode})"

            results.append({
                "pid": pid,
                "status": status,
                "tracked": True,
            })

            if returncode is not None:
                dead_pids.append(pid)

        # 清理已退出的进程
        for pid in dead_pids:
            del self._processes[pid]
            if pid in self._process_outputs:
                del self._process_outputs[pid]

        content = f"跟踪的进程数: {len(results)}\n"
        for r in results:
            content += f"  PID={r['pid']}: {r['status']}\n"

        return ToolResult(
            success=True,
            content=content.strip(),
            metadata={"processes": results, "count": len(results)},
        )

    async def get_output(self, pid: int, clear: bool = False) -> ToolResult:
        """
        获取进程的 stdout/stderr 输出。

        Args:
            pid: 进程 ID
            clear: 是否在读取后清空输出

        Returns:
            ToolResult: 进程输出
        """
        if pid not in self._processes:
            return ToolResult(
                success=False,
                content=f"进程不存在: PID={pid}",
                error=f"进程 {pid} 未被跟踪",
            )

        process = self._processes[pid]
        outputs = self._process_outputs.get(pid, [])

        # 读取新的输出
        try:
            stdout_data = await asyncio.wait_for(
                process.stdout.read(), timeout=0.1
            ) if process.stdout else b""
            stderr_data = await asyncio.wait_for(
                process.stderr.read(), timeout=0.1
            ) if process.stderr else b""

            if stdout_data:
                outputs.append(f"[stdout] {stdout_data.decode('utf-8', errors='replace')}")
            if stderr_data:
                outputs.append(f"[stderr] {stderr_data.decode('utf-8', errors='replace')}")

        except (asyncio.TimeoutError, ValueError):
            pass  # 没有新输出

        output_text = "\n".join(outputs[-100:])  # 最多保留100行

        if clear:
            self._process_outputs[pid] = []

        return ToolResult(
            success=True,
            content=output_text or "(无输出)",
            metadata={"pid": pid, "lines": len(outputs)},
        )

    async def wait(self, pid: int, timeout: float | None = None) -> ToolResult:
        """
        等待进程退出。

        Args:
            pid: 进程 ID
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            ToolResult: 退出状态
        """
        if pid not in self._processes:
            return ToolResult(
                success=False,
                content=f"进程不存在: PID={pid}",
                error=f"进程 {pid} 未被跟踪",
            )

        process = self._processes[pid]

        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=timeout)

            del self._processes[pid]

            logger.info(f"进程已退出: PID={pid}, returncode={returncode}")

            return ToolResult(
                success=True,
                content=f"进程已退出: returncode={returncode}",
                metadata={"pid": pid, "returncode": returncode},
            )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                content=f"等待超时: PID={pid}",
                metadata={"pid": pid, "timeout": timeout},
            )


class ProcessToolExecutor:
    """
    Process Tool 执行器

    将 ProcessTool 的各种操作封装为标准的工具执行接口。
    """

    def __init__(self, process_tool: ProcessTool):
        self._process = process_tool

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """
        执行进程操作。

        Args:
            action: 操作类型
            **kwargs: 操作参数

        Returns:
            ToolResult: 操作结果
        """
        action_map = {
            "start": lambda: self._process.start(
                command=kwargs.get("command", ""),
                args=kwargs.get("args"),
                cwd=kwargs.get("cwd"),
                env=kwargs.get("env"),
                shell=kwargs.get("shell", False),
            ),
            "stop": lambda: self._process.stop(
                pid=kwargs.get("pid"),
                force=kwargs.get("force", False),
            ),
            "is_alive": lambda: self._process.is_alive(pid=kwargs.get("pid")),
            "list": lambda: self._process.list(),
            "get_output": lambda: self._process.get_output(
                pid=kwargs.get("pid"),
                clear=kwargs.get("clear", False),
            ),
            "wait": lambda: self._process.wait(
                pid=kwargs.get("pid"),
                timeout=kwargs.get("timeout"),
            ),
        }

        action_func = action_map.get(action)
        if action_func is None:
            return ToolResult(
                success=False,
                content=f"未知操作: {action}",
                error=f"支持的操作: {list(action_map.keys())}",
            )

        return await action_func()
