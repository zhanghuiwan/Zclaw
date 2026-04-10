"""
WebSocket 连接管理器

管理多个 WebSocket 连接，支持广播和单播消息。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket 连接管理器。

    管理活跃的 WebSocket 连接，支持：
    - 连接/断开管理
    - 单播消息（发送给指定连接）
    - 广播消息（发送给所有连接）
    - 权限请求/响应管理
    """

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}  # conn_id → WebSocket
        self._pending_permissions: dict[str, asyncio.Future] = {}  # request_id → Future

    @property
    def active_connections(self) -> int:
        """当前活跃连接数。"""
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> str:
        """
        接受一个新的 WebSocket 连接。

        Args:
            websocket: WebSocket 实例

        Returns:
            连接 ID
        """
        await websocket.accept()
        conn_id = uuid.uuid4().hex[:12]
        self._connections[conn_id] = websocket
        logger.info(f"WebSocket 连接已建立: {conn_id} (当前共 {self.active_connections} 个)")
        return conn_id

    def disconnect(self, conn_id: str) -> None:
        """断开指定连接。"""
        if conn_id in self._connections:
            del self._connections[conn_id]
            # 清理该连接相关的权限请求
            pending_to_remove = [
                rid for rid, fut in self._pending_permissions.items()
                if not fut.done()
            ]
            for rid in pending_to_remove:
                self._pending_permissions[rid].set_result(False)
                del self._pending_permissions[rid]
            logger.info(f"WebSocket 连接已断开: {conn_id} (当前共 {self.active_connections} 个)")

    async def send_json(self, conn_id: str, data: dict[str, Any]) -> bool:
        """
        向指定连接发送 JSON 消息。

        Args:
            conn_id: 连接 ID
            data: 要发送的数据

        Returns:
            是否发送成功
        """
        websocket = self._connections.get(conn_id)
        if not websocket:
            return False
        try:
            await websocket.send_json(data)
            return True
        except Exception as e:
            logger.warning(f"发送消息失败 ({conn_id}): {e}")
            self.disconnect(conn_id)
            return False

    async def broadcast(self, data: dict[str, Any], exclude: str | None = None) -> int:
        """
        向所有连接广播消息。

        Args:
            data: 要广播的数据
            exclude: 要排除的连接 ID

        Returns:
            成功发送的连接数
        """
        success_count = 0
        disconnected: list[str] = []

        for conn_id, websocket in self._connections.items():
            if conn_id == exclude:
                continue
            try:
                await websocket.send_json(data)
                success_count += 1
            except Exception:
                disconnected.append(conn_id)

        for conn_id in disconnected:
            self.disconnect(conn_id)

        return success_count

    async def request_permission(
        self, conn_id: str, request_id: str, tool_name: str,
        arguments: dict[str, Any], danger_level: str,
        timeout: float = 60.0,
    ) -> bool:
        """
        向客户端请求权限确认。

        Args:
            conn_id: 连接 ID
            request_id: 请求 ID
            tool_name: 工具名称
            arguments: 工具参数
            danger_level: 危险等级
            timeout: 超时时间（秒）

        Returns:
            用户是否批准
        """
        # 发送权限请求
        sent = await self.send_json(conn_id, {
            "type": "permission",
            "data": {
                "request_id": request_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "danger_level": danger_level,
            },
        })
        if not sent:
            return False

        # 创建 Future 等待响应
        loop = asyncio.get_event_loop()
        future: asyncio.Future[bool] = loop.create_future()
        self._pending_permissions[request_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"权限请求超时: {request_id}")
            return False
        finally:
            self._pending_permissions.pop(request_id, None)

    def resolve_permission(self, request_id: str, allowed: bool) -> bool:
        """
        处理客户端的权限响应。

        Args:
            request_id: 请求 ID
            allowed: 用户是否批准

        Returns:
            是否成功处理（请求是否存在）
        """
        future = self._pending_permissions.get(request_id)
        if future is None or future.done():
            return False
        future.set_result(allowed)
        return True

    def get_connection_ids(self) -> list[str]:
        """获取所有活跃连接 ID。"""
        return list(self._connections.keys())
