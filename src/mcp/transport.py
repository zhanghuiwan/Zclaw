"""
MCP 传输层

实现与 MCP 服务器的通信（stdio 和 SSE 两种传输方式）。
基于 JSON-RPC 2.0 协议。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


# JSON-RPC 2.0 相关常量
JSONRPC_VERSION = "2.0"


def _make_request(method: str, params: dict[str, Any] | None = None, request_id: int = 1) -> str:
    """构造 JSON-RPC 请求。"""
    req = {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "method": method,
    }
    if params is not None:
        req["params"] = params
    return json.dumps(req, ensure_ascii=False)


def _make_notification(method: str, params: dict[str, Any] | None = None) -> str:
    """构造 JSON-RPC 通知（无 id，不期望响应）。"""
    req = {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
    }
    if params is not None:
        req["params"] = params
    return json.dumps(req, ensure_ascii=False)


class BaseTransport(ABC):
    """MCP 传输层抽象基类。"""

    @abstractmethod
    async def connect(self) -> None:
        """建立连接。"""
        ...

    @abstractmethod
    async def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """发送请求并等待响应。"""
        ...

    @abstractmethod
    async def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """发送通知（不期望响应）。"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭连接。"""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...


class StdioTransport(BaseTransport):
    """
    Stdio 传输层。

    通过启动子进程并与其 stdin/stdout 通信来实现 MCP 协议。
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        self._command = command
        self._args = args or []
        self._env = env or {}
        self._timeout = timeout
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._read_task: asyncio.Task | None = None

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def connect(self) -> None:
        """启动子进程并开始监听输出。"""
        if self.is_connected:
            return

        # 合并环境变量
        proc_env = os.environ.copy()
        proc_env.update(self._env)

        logger.info(f"启动 MCP 服务器进程: {self._command} {' '.join(self._args)}")
        self._process = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=proc_env,
        )

        # 启动读取任务
        self._read_task = asyncio.create_task(self._read_loop())

        logger.debug(f"MCP stdio 进程已启动, PID={self._process.pid}")

    async def _read_loop(self) -> None:
        """持续读取子进程的 stdout，分派 JSON-RPC 响应。"""
        if not self._process or not self._process.stdout:
            return

        buffer = b""
        try:
            while True:
                chunk = await self._process.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk

                # 按换行符分割消息（MCP stdio 使用 newline 分隔的 JSON）
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self._handle_message(msg)
                    except json.JSONDecodeError as e:
                        logger.warning(f"无效的 MCP 消息: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"MCP stdio 读取错误: {e}")
        finally:
            # 连接断开，取消所有等待中的请求
            for rid, future in self._pending.items():
                if not future.done():
                    future.set_exception(ConnectionError("MCP 进程已退出"))
            self._pending.clear()

    def _handle_message(self, msg: dict[str, Any]) -> None:
        """处理收到的 JSON-RPC 消息。"""
        # 如果是响应（有 id）
        if "id" in msg:
            rid = msg.get("id")
            future = self._pending.pop(rid, None)
            if future and not future.done():
                if "error" in msg:
                    future.set_exception(RuntimeError(
                        f"MCP 错误: {msg['error']}"
                    ))
                else:
                    future.set_result(msg.get("result", {}))
        else:
            # 通知或事件，暂不处理
            logger.debug(f"MCP 通知: {msg.get('method', 'unknown')}")

    async def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """发送请求并等待响应。"""
        if not self.is_connected or not self._process or not self._process.stdin:
            raise ConnectionError("MCP stdio 未连接")

        self._request_id += 1
        rid = self._request_id
        request_str = _make_request(method, params, rid) + "\n"

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rid] = future

        try:
            self._process.stdin.write(request_str.encode("utf-8"))
            await self._process.stdin.drain()
        except Exception as e:
            self._pending.pop(rid, None)
            raise ConnectionError(f"写入 MCP 进程失败: {e}") from e

        # 等待响应
        try:
            return await asyncio.wait_for(future, timeout=self._timeout)
        except asyncio.TimeoutError:
            self._pending.pop(rid, None)
            raise TimeoutError(f"MCP 请求超时 ({self._timeout}s): {method}")

    async def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """发送通知。"""
        if not self.is_connected or not self._process or not self._process.stdin:
            raise ConnectionError("MCP stdio 未连接")

        notification_str = _make_notification(method, params) + "\n"
        self._process.stdin.write(notification_str.encode("utf-8"))
        await self._process.stdin.drain()

    async def close(self) -> None:
        """关闭连接，终止子进程。"""
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        if self._process:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except ProcessLookupError:
                pass
            self._process = None

        self._pending.clear()
        logger.debug("MCP stdio 连接已关闭")


class SSETransport(BaseTransport):
    """
    SSE (Server-Sent Events) 传输层。

    通过 HTTP 连接与远程 MCP 服务器通信。
    这是一个简化实现，使用 POST 请求发送消息，通过 SSE 接收响应。
    """

    def __init__(self, url: str, timeout: int = 30):
        self._url = url.rstrip("/")
        self._timeout = timeout
        self._connected = False
        self._session_id: str | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """通过 HTTP 发送 initialize 请求建立连接。"""
        try:
            import httpx
        except ImportError:
            raise ImportError("SSE 传输层需要 httpx 库: pip install httpx")

        # 发送 initialize
        result = await self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
                "clientInfo": {"name": "Zclaw", "version": "0.6.1"},
        })

        # 发送 initialized 通知
        await self.send_notification("notifications/initialized")
        self._connected = True
        logger.info(f"MCP SSE 连接已建立: {self._url}")

    async def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """通过 HTTP POST 发送请求。"""
        try:
            import httpx
        except ImportError:
            raise ImportError("SSE 传输层需要 httpx 库: pip install httpx")

        self._request_id_counter = getattr(self, "_request_id_counter", 0) + 1
        rid = self._request_id_counter

        headers = {"Content-Type": "application/json"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        payload = _make_request(method, params, rid)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._url,
                    content=payload,
                    headers=headers,
                )
                resp.raise_for_status()

                # 保存 session id
                session_id = resp.headers.get("mcp-session-id")
                if session_id:
                    self._session_id = session_id

                data = resp.json()
                if "error" in data:
                    raise RuntimeError(f"MCP 错误: {data['error']}")
                return data.get("result", {})
        except httpx.TimeoutException:
            raise TimeoutError(f"MCP SSE 请求超时 ({self._timeout}s): {method}")
        except httpx.HTTPError as e:
            raise ConnectionError(f"MCP HTTP 错误: {e}") from e

    async def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        """通过 HTTP POST 发送通知。"""
        try:
            import httpx
        except ImportError:
            raise ImportError("SSE 传输层需要 httpx 库: pip install httpx")

        headers = {"Content-Type": "application/json"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        payload = _make_notification(method, params)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                await client.post(self._url, content=payload, headers=headers)
        except Exception as e:
            logger.warning(f"MCP 通知发送失败: {e}")

    async def close(self) -> None:
        """关闭连接。"""
        self._connected = False
        self._session_id = None
        logger.debug("MCP SSE 连接已关闭")


class MockTransport(BaseTransport):
    """
    Mock 传输层，用于测试。

    模拟 MCP 服务器的行为，返回预设的工具列表和调用结果。
    """

    def __init__(
        self,
        tools: list[dict[str, Any]] | None = None,
        call_results: dict[str, str] | None = None,
    ):
        self._tools = tools or []
        self._call_results = call_results or {}
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._connected:
            raise ConnectionError("Mock 传输层未连接")

        if method == "initialize":
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "mock-mcp-server", "version": "0.6.1"},
            }
        elif method == "tools/list":
            return {"tools": self._tools}
        elif method == "tools/call":
            tool_name = (params or {}).get("name", "")
            result_str = self._call_results.get(tool_name, f"Mock 执行结果: {tool_name}")
            return {
                "content": [{"type": "text", "text": result_str}],
            }
        elif method == "ping":
            return {}
        else:
            return {}

    async def send_notification(self, method: str, params: dict[str, Any] | None = None) -> None:
        pass

    async def close(self) -> None:
        self._connected = False


def create_transport(config: "MCPServerConfig") -> BaseTransport:
    """
    工厂函数：根据配置创建传输层实例。
    """
    from src.mcp.types import MCPTransportType

    if config.transport == MCPTransportType.STDIO:
        return StdioTransport(
            command=config.command,
            args=config.args,
            env=config.env,
            timeout=config.timeout,
        )
    elif config.transport == MCPTransportType.SSE:
        return SSETransport(url=config.url, timeout=config.timeout)
    else:
        raise ValueError(f"不支持的传输类型: {config.transport}")
