"""
MCP 管理器

管理多个 MCP 服务器的生命周期：加载配置、连接服务器、注册工具、断开连接。
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from src.mcp.types import MCPServerConfig, MCPToolDefinition
from src.mcp.client import MCPClient
from src.mcp.adapter import MCPToolWrapper, create_wrappers
from src.tools.base import BaseTool

logger = logging.getLogger(__name__)


# 默认 MCP 配置文件路径
DEFAULT_MCP_CONFIG_PATH = "~/.Zclaw/mcp_servers.json"


class MCPManager:
    """
    MCP 服务器管理器。

    职责：
    1. 加载 MCP 服务器配置
    2. 连接/断开服务器
    3. 将 MCP 工具转换为 Zclaw 工具
    4. 提供工具注册和生命周期管理
    """

    def __init__(self, config_path: str = DEFAULT_MCP_CONFIG_PATH):
        # 相对路径解析为项目根目录
        path = Path(config_path)
        if not path.is_absolute() and not str(path).startswith("~"):
            src_dir = Path(__file__).resolve().parent
            project_root = src_dir.parent.parent
            self._config_path = project_root / path
        else:
            self._config_path = path.expanduser().resolve()
        self._servers: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}
        self._wrappers: dict[str, list[MCPToolWrapper]] = {}

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def connected_servers(self) -> list[str]:
        """已连接的服务器名称列表。"""
        return [name for name, client in self._clients.items() if client.is_connected]

    @property
    def all_tools(self) -> list[MCPToolWrapper]:
        """所有已注册的 MCP 工具。"""
        tools = []
        for server_wrappers in self._wrappers.values():
            tools.extend(server_wrappers)
        return tools

    def _resolve_env_vars(self, env_dict: dict[str, str]) -> dict[str, str]:
        """解析 env 字典中的 ${VAR_NAME} 引用，返回实际值。"""
        result = {}
        env_pattern = re.compile(r'\$\{([^}]+)\}')
        for key, value in env_dict.items():
            if isinstance(value, str):
                # 替换 ${VAR_NAME} 为环境变量值
                resolved = value
                for match in env_pattern.finditer(value):
                    var_name = match.group(1)
                    env_value = os.environ.get(var_name, "")
                    resolved = resolved.replace(f"${{{var_name}}}", env_value)
                result[key] = resolved
            else:
                result[key] = value
        return result

    def load_config(self, config_path: str | None = None) -> list[MCPServerConfig]:
        """
        从 JSON 文件加载 MCP 服务器配置。

        配置文件格式示例：
        ```json
        {
            "mcpServers": {
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@anthropic/mcp-filesystem", "/path"],
                    "env": {}
                },
                "web-search": {
                    "command": "python",
                    "args": ["-m", "web_search_server"],
                    "timeout": 60
                }
            }
        }
        ```
        """
        path = Path(config_path).expanduser().resolve() if config_path else self._config_path

        if not path.exists():
            logger.debug(f"MCP 配置文件不存在: {path}")
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"加载 MCP 配置失败: {e}")
            return []

        servers_config = data.get("mcpServers", {})
        configs = []

        for name, server_data in servers_config.items():
            server_data = dict(server_data)
            server_data["name"] = name

            # 解析 env 中的环境变量引用 ${VAR_NAME}
            if "env" in server_data:
                server_data["env"] = self._resolve_env_vars(server_data["env"])

            # 根据是否有 url 判断传输类型
            if server_data.get("url"):
                server_data["transport"] = "sse"
            elif server_data.get("command"):
                server_data["transport"] = server_data.get("transport", "stdio")

            config = MCPServerConfig.from_dict(server_data)

            # 验证
            errors = config.validate()
            if errors:
                logger.warning(f"MCP 服务器 '{name}' 配置错误: {errors}")
                continue

            self._servers[name] = config
            configs.append(config)

        logger.info(f"已加载 {len(configs)} 个 MCP 服务器配置")
        return configs

    def add_server(self, config: MCPServerConfig) -> None:
        """手动添加一个服务器配置。"""
        errors = config.validate()
        if errors:
            raise ValueError(f"配置验证失败: {errors}")
        self._servers[config.name] = config

    def remove_server(self, name: str) -> bool:
        """移除一个服务器配置（同时断开连接）。"""
        if name in self._clients:
            # 断开连接通过异步方法完成，这里只清理同步状态
            self._clients.pop(name, None)
            self._wrappers.pop(name, None)
        if name in self._servers:
            del self._servers[name]
            return True
        return False

    def list_servers(self) -> list[dict[str, Any]]:
        """列出所有服务器配置及其状态。"""
        result = []
        for name, config in self._servers.items():
            client = self._clients.get(name)
            status = "已连接" if client and client.is_connected else "未连接"
            tool_count = len(self._wrappers.get(name, []))
            result.append({
                "name": name,
                "transport": config.transport.value,
                "enabled": config.enabled,
                "status": status,
                "tools": tool_count,
                "command": config.command if config.transport.value == "stdio" else config.url,
            })
        return result

    async def connect_server(self, name: str) -> list[MCPToolWrapper]:
        """
        连接到指定 MCP 服务器并获取工具。

        Args:
            name: 服务器名称

        Returns:
            该服务器提供的工具包装器列表
        """
        config = self._servers.get(name)
        if not config:
            raise ValueError(f"未找到 MCP 服务器: {name}")

        if not config.enabled:
            logger.warning(f"MCP 服务器 '{name}' 已禁用")
            return []

        # 如果已连接，先断开
        if name in self._clients:
            old_client = self._clients[name]
            if old_client.is_connected:
                await old_client.close()

        # 创建客户端并连接
        client = MCPClient(config)
        await client.connect()

        self._clients[name] = client

        # 创建工具包装器
        wrappers = create_wrappers(client)
        self._wrappers[name] = wrappers

        return wrappers

    async def connect_all(self, config_path: str | None = None) -> list[BaseTool]:
        """
        连接所有已配置且启用的 MCP 服务器。

        Args:
            config_path: 可选的自定义配置文件路径

        Returns:
            所有服务器提供的工具列表
        """
        # 加载配置
        if config_path or not self._servers:
            self.load_config(config_path)

        all_tools: list[BaseTool] = []

        for name, config in self._servers.items():
            if not config.enabled:
                continue
            try:
                wrappers = await self.connect_server(name)
                all_tools.extend(wrappers)
                logger.info(f"MCP 服务器 '{name}': {len(wrappers)} 个工具已就绪")
            except Exception as e:
                logger.error(f"MCP 服务器 '{name}' 连接失败: {e}")

        if all_tools:
            logger.info(f"MCP 总计: {len(all_tools)} 个工具可用")
        return all_tools

    async def disconnect_server(self, name: str) -> bool:
        """断开指定服务器的连接。"""
        client = self._clients.get(name)
        if not client:
            return False
        await client.close()
        self._wrappers.pop(name, None)
        return True

    async def disconnect_all(self) -> int:
        """断开所有服务器连接。"""
        count = 0
        for name in list(self._clients.keys()):
            await self.disconnect_server(name)
            count += 1
        return count

    def get_server_tools(self, name: str) -> list[MCPToolWrapper]:
        """获取指定服务器的工具列表。"""
        return list(self._wrappers.get(name, []))

    def get_client(self, name: str) -> MCPClient | None:
        """获取指定服务器的客户端。"""
        return self._clients.get(name)

    async def reconnect(self, name: str) -> list[MCPToolWrapper]:
        """重新连接指定服务器。"""
        return await self.connect_server(name)

    def __repr__(self) -> str:
        connected = len(self.connected_servers)
        total = len(self._servers)
        return f"MCPManager(servers={total}, connected={connected}, tools={len(self.all_tools)})"
