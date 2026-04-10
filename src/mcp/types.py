"""
MCP 数据类型

定义 MCP 服务器配置、工具描述等数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MCPTransportType(str, Enum):
    """MCP 传输协议类型"""
    STDIO = "stdio"    # 标准输入输出（子进程）
    SSE = "sse"        # Server-Sent Events（HTTP）


@dataclass
class MCPServerConfig:
    """
    MCP 服务器配置。

    Attributes:
        name: 服务器名称（唯一标识）
        transport: 传输协议类型
        command: stdio 模式的启动命令（如 "npx", "python"）
        args: stdio 模式的命令参数
        env: 传递给子进程的环境变量
        url: SSE 模式的服务器 URL
        enabled: 是否启用
        timeout: 连接和调用超时（秒）
    """
    name: str = ""
    transport: MCPTransportType = MCPTransportType.STDIO
    # stdio 配置
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    # SSE 配置
    url: str = ""
    # 通用配置
    enabled: bool = True
    timeout: int = 30

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPServerConfig:
        """从字典创建配置。"""
        transport_str = data.get("transport", "stdio")
        try:
            transport = MCPTransportType(transport_str)
        except ValueError:
            transport = MCPTransportType.STDIO

        return cls(
            name=data.get("name", ""),
            transport=transport,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            url=data.get("url", ""),
            enabled=data.get("enabled", True),
            timeout=data.get("timeout", 30),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "name": self.name,
            "transport": self.transport.value,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "url": self.url,
            "enabled": self.enabled,
            "timeout": self.timeout,
        }

    def validate(self) -> list[str]:
        """验证配置，返回错误列表。"""
        errors = []
        if not self.name:
            errors.append("服务器名称不能为空")

        if self.transport == MCPTransportType.STDIO:
            if not self.command:
                errors.append("stdio 模式需要指定 command")
        elif self.transport == MCPTransportType.SSE:
            if not self.url:
                errors.append("sse 模式需要指定 url")

        return errors


@dataclass
class MCPToolDefinition:
    """
    MCP 工具定义（来自服务器的 tools/list 响应）。

    Attributes:
        name: 工具名称
        description: 工具描述
        input_schema: JSON Schema 格式的参数定义
        server_name: 来源服务器名称
    """
    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], server_name: str = "") -> MCPToolDefinition:
        """从 MCP 协议的 tools/list 响应创建。"""
        tool_data = data.get("tool", data)  # 兼容两种格式
        return cls(
            name=tool_data.get("name", ""),
            description=tool_data.get("description", ""),
            input_schema=tool_data.get("inputSchema", {}),
            server_name=server_name,
        )
