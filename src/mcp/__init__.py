"""
MCP (Model Context Protocol) 集成模块

让 Zclaw 能够连接外部 MCP 工具服务器，将其提供的工具
自动注册到 Agent 的工具注册表中。
"""

from src.mcp.types import MCPServerConfig, MCPTransportType
from src.mcp.manager import MCPManager

__all__ = ["MCPServerConfig", "MCPTransportType", "MCPManager"]
