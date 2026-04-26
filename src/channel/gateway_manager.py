"""
Gateway 进程管理器

负责 Gateway 的启动、停止、状态检查等生命周期管理。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logger = __import__("logging").getLogger(__name__)


class GatewayManager:
    """Gateway 进程管理器"""

    PID_FILE = "~/.Zclaw/gateway.pid"
    DEFAULT_PORT = 8080
    DEFAULT_HOST = "127.0.0.1"
    STARTUP_TIMEOUT = 10  # 秒
    PORT_CHECK_INTERVAL = 0.2  # 秒

    def __init__(self, host: str | None = None, port: int | None = None):
        self.host = host or self.DEFAULT_HOST
        self.port = port or self.DEFAULT_PORT
        self.pid_dir = Path("~/.Zclaw").expanduser()
        self.pid_file = self.pid_dir / "gateway.pid"

    def _get_pid(self) -> Optional[int]:
        """读取 PID 文件，返回 PID 或 None"""
        if not self.pid_file.exists():
            return None
        try:
            pid = int(self.pid_file.read_text().strip())
            return pid if pid > 0 else None
        except (ValueError, IOError):
            return None

    def _write_pid(self, pid: int) -> None:
        """写入 PID 文件"""
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(pid))

    def _remove_pid(self) -> None:
        """删除 PID 文件"""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def is_running(self) -> bool:
        """检查 Gateway 是否正在运行"""
        pid = self._get_pid()
        if pid is None:
            return False
        # 检查进程是否存在
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            # 进程不存在，清理 PID 文件
            self._remove_pid()
            return False

    def _is_port_open(self) -> bool:
        """检查端口是否开放"""
        import socket
        try:
            with socket.create_connection((self.host, self.port), timeout=1):
                return True
        except (socket.error, OSError):
            return False

    def status(self) -> dict:
        """获取 Gateway 状态"""
        pid = self._get_pid()
        running = self.is_running() if pid else False
        port_open = self._is_port_open() if running else False

        return {
            "running": running,
            "pid": pid,
            "host": self.host,
            "port": self.port,
            "port_open": port_open,
        }

    def start(self, daemon: bool = True) -> bool:
        """
        启动 Gateway

        Args:
            daemon: 是否以后台守护进程方式启动

        Returns:
            是否成功启动
        """
        # 检查是否已运行
        if self.is_running():
            logger.error(f"Gateway is already running (PID: {self._get_pid()})")
            print(f"Gateway is already running (PID: {self._get_pid()})")
            return False

        # 确保 PID 目录存在
        self.pid_dir.mkdir(parents=True, exist_ok=True)

        if daemon:
            # 使用 nohup 和 & 后台启动
            # 将输出重定向到 /dev/null 或日志文件
            log_file = self.pid_dir / "gateway.log"
            with open(log_file, "a") as f:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "src.web.gateway_server",
                     "--host", self.host, "--port", str(self.port)],
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            self._write_pid(proc.pid)
            print(f"Gateway starting in background (PID: {proc.pid})")
        else:
            # 前台启动（调试用）
            proc = subprocess.Popen(
                [sys.executable, "-m", "src.web.gateway_server",
                 "--host", self.host, "--port", str(self.port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self._write_pid(proc.pid)
            print(f"Gateway starting (PID: {proc.pid})")

        # 等待 Gateway 启动完成
        if not self._wait_for_startup():
            logger.error("Gateway failed to start within timeout")
            print("Gateway failed to start within timeout")
            self._remove_pid()
            return False

        print(f"Gateway started successfully on {self.host}:{self.port}")
        return True

    def _wait_for_startup(self) -> bool:
        """等待 Gateway 启动完成"""
        for _ in range(int(self.STARTUP_TIMEOUT / self.PORT_CHECK_INTERVAL)):
            if self._is_port_open():
                return True
            time.sleep(self.PORT_CHECK_INTERVAL)

        # 最后一次检查
        return self._is_port_open()

    def stop(self) -> bool:
        """
        停止 Gateway

        Returns:
            是否成功停止
        """
        pid = self._get_pid()
        if pid is None:
            logger.error("Gateway is not running (no PID file)")
            print("Gateway is not running")
            return False

        if not self.is_running():
            logger.warning("Gateway PID exists but process is not running")
            self._remove_pid()
            print("Gateway was not running, PID file cleaned up")
            return True

        try:
            # 尝试优雅关闭 (SIGTERM)
            os.kill(pid, signal.SIGTERM)

            # 等待进程退出
            for _ in range(50):  # 最多 5 秒
                try:
                    os.kill(pid, 0)
                except OSError:
                    # 进程已退出
                    break
                time.sleep(0.1)

            # 如果还在运行，强制终止
            try:
                os.kill(pid, 0)
                logger.warning(f"Gateway (PID: {pid}) did not stop gracefully, sending SIGKILL")
                os.kill(pid, signal.SIGKILL)
                time.sleep(0.5)
            except OSError:
                pass

        except OSError as e:
            logger.error(f"Failed to stop Gateway: {e}")
            print(f"Failed to stop Gateway: {e}")
            return False

        # 清理 PID 文件
        self._remove_pid()
        print(f"Gateway stopped (PID: {pid})")
        return True

    def restart(self) -> bool:
        """重启 Gateway"""
        if self.is_running():
            self.stop()
        return self.start()

    def print_status(self) -> None:
        """打印状态信息"""
        status = self.status()
        print()
        print("=" * 40)
        print("Zclaw Gateway Status")
        print("=" * 40)
        print(f"  Running:    {'Yes' if status['running'] else 'No'}")
        print(f"  PID:        {status['pid'] or 'N/A'}")
        print(f"  Host:       {status['host']}")
        print(f"  Port:       {status['port']}")
        print(f"  Port Open:  {'Yes' if status['port_open'] else 'No'}")
        print("=" * 40)
        print()


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Zclaw Gateway Manager")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_argument("start", help="Start Gateway")
    sub.add_argument("stop", help="Stop Gateway")
    sub.add_argument("status", help="Show Gateway status")
    sub.add_argument("restart", help="Restart Gateway")

    args = parser.parse_args()

    manager = GatewayManager()

    if args.command == "start":
        manager.start()
    elif args.command == "stop":
        manager.stop()
    elif args.command == "status":
        manager.print_status()
    elif args.command == "restart":
        manager.restart()


if __name__ == "__main__":
    main()