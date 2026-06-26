"""
MCP 客户端

封装与单个 MCP 服务器的交互：连接、工具发现、工具调用。
"""

from __future__ import annotations

import logging
from typing import Any

from src.mcp.types import MCPServerConfig, MCPToolDefinition
from src.mcp.transport import BaseTransport, create_transport, MockTransport

logger = logging.getLogger(__name__)


class MCPClient:
    """
    MCP 客户端。

    封装与单个 MCP 服务器的完整交互生命周期：
    1. connect() - 建立连接并完成握手
    2. list_tools() - 获取服务器提供的工具列表
    3. call_tool() - 调用指定工具
    4. close() - 断开连接
    """

    def __init__(self, config: MCPServerConfig, transport: BaseTransport | None = None):
        self._config = config
        self._transport = transport or create_transport(config)
        self._tools: list[MCPToolDefinition] = []
        self._server_info: dict[str, Any] = {}
        self._initialized = False

    @property
    def config(self) -> MCPServerConfig:
        return self._config

    @property
    def transport(self) -> BaseTransport:
        return self._transport

    @property
    def is_connected(self) -> bool:
        return self._transport.is_connected

    @property
    def tools(self) -> list[MCPToolDefinition]:
        return list(self._tools)

    @property
    def server_info(self) -> dict[str, Any]:
        return dict(self._server_info)

    async def connect(self) -> dict[str, Any]:
        """
        连接到 MCP 服务器并完成初始化握手。

        Returns:
            服务器信息（serverInfo）

        Raises:
            ConnectionError: 连接失败
            TimeoutError: 连接超时
        """
        if self._initialized:
            return self._server_info

        logger.info(f"正在连接 MCP 服务器: {self._config.name} ({self._config.transport.value})")

        try:
            # 建立传输层连接
            await self._transport.connect()

            # 发送 initialize 请求
            result = await self._transport.send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "Zclaw",
                    "version": "0.6.1",
                },
            })

            self._server_info = result.get("serverInfo", {})
            logger.info(
                f"MCP 服务器已连接: {self._server_info.get('name', 'unknown')} "
                f"(v{self._server_info.get('version', '?')})"
            )

            # 发送 initialized 通知
            await self._transport.send_notification("notifications/initialized")

            # 获取工具列表
            self._tools = await self.list_tools()

            self._initialized = True
            logger.info(
                f"MCP 服务器 '{self._config.name}' 已就绪, "
                f"提供 {len(self._tools)} 个工具"
            )

            return self._server_info

        except Exception as e:
            logger.error(f"MCP 服务器连接失败 ({self._config.name}): {e}")
            await self.close()
            raise

    async def list_tools(self) -> list[MCPToolDefinition]:
        """
        获取服务器提供的所有工具。

        Returns:
            MCPToolDefinition 列表
        """
        try:
            result = await self._transport.send_request("tools/list", {})
            tools_data = result.get("tools", [])

            self._tools = [
                MCPToolDefinition.from_dict(td, server_name=self._config.name)
                for td in tools_data
            ]

            logger.debug(
                f"MCP '{self._config.name}' 提供工具: "
                f"{[t.name for t in self._tools]}"
            )
            return self._tools

        except Exception as e:
            logger.error(f"获取 MCP 工具列表失败 ({self._config.name}): {e}")
            raise

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """
        调用 MCP 服务器上的工具。

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行的文本结果
        """
        if not self._initialized:
            raise ConnectionError("MCP 客户端未初始化，请先调用 connect()")

        params: dict[str, Any] = {"name": name}
        if arguments:
            params["arguments"] = arguments

        logger.debug(f"MCP 调用工具: {self._config.name}/{name}({arguments})")

        try:
            result = await self._transport.send_request("tools/call", params)

            # 提取文本内容
            content = result.get("content", [])
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))

            return "\n".join(text_parts) if text_parts else str(result)

        except Exception as e:
            logger.error(f"MCP 工具调用失败 ({self._config.name}/{name}): {e}")
            raise

    async def ping(self) -> bool:
        """检查服务器是否存活。"""
        try:
            await self._transport.send_request("ping", {})
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """断开连接。"""
        if self._initialized:
            logger.info(f"断开 MCP 服务器连接: {self._config.name}")
        self._initialized = False
        self._tools.clear()
        await self._transport.close()

    def __repr__(self) -> str:
        status = "已连接" if self._initialized else "未连接"
        return (
            f"MCPClient(name='{self._config.name}', "
            f"transport={self._config.transport.value}, "
            f"tools={len(self._tools)}, status={status})"
        )
