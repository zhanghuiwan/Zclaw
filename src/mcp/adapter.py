"""
MCP 工具适配器

将 MCP 服务器提供的工具自动转换为 Zclaw 的 BaseTool 子类，
以便注册到 ToolRegistry 中被 Agent 使用。
"""

from __future__ import annotations

import logging
from typing import Any

from src.mcp.types import MCPToolDefinition
from src.mcp.client import MCPClient
from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


def schema_to_parameters(input_schema: dict[str, Any]) -> list[ToolParameter]:
    """
    将 JSON Schema 转换为 ToolParameter 列表。

    处理常见的 JSON Schema 格式，包括：
    - string, integer, number, boolean, array, object 类型
    - required 字段
    - description 描述
    - enum 枚举
    - default 默认值
    """
    parameters: list[ToolParameter] = []
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    for prop_name, prop_schema in properties.items():
        # 推断类型
        json_type = prop_schema.get("type", "string")
        type_mapping = {
            "string": "string",
            "integer": "integer",
            "number": "number",
            "boolean": "boolean",
            "array": "array",
            "object": "object",
        }
        param_type = type_mapping.get(json_type, "string")

        # 处理 anyOf/oneOf（取第一个非 null 类型）
        if json_type not in type_mapping:
            for sub in prop_schema.get("anyOf", prop_schema.get("oneOf", [])):
                if sub.get("type") != "null" and sub.get("type") in type_mapping:
                    param_type = type_mapping[sub["type"]]
                    break

        param = ToolParameter(
            name=prop_name,
            type=param_type,
            description=prop_schema.get("description", ""),
            required=prop_name in required,
            default=prop_schema.get("default"),
            enum=prop_schema.get("enum"),
        )
        parameters.append(param)

    return parameters


class MCPToolWrapper(BaseTool):
    """
    MCP 工具包装器。

    将 MCP 服务器上的一个工具包装为 Zclaw 的 BaseTool，
    注册到 ToolRegistry 后即可被 Agent 调用。
    """

    def __init__(
        self,
        mcp_client: MCPClient,
        tool_def: MCPToolDefinition,
        original_name: str | None = None,
    ):
        self._mcp_client = mcp_client
        self._tool_def = tool_def
        # 原始工具名（不带服务器前缀，用于调用 MCP 服务器）
        self._original_name = original_name or tool_def.name

        # 设置 BaseTool 属性
        self.name = tool_def.name
        self.description = tool_def.description
        self.parameters = schema_to_parameters(tool_def.input_schema)
        self.metadata = ToolMetadata(
            category="mcp",
            danger_level=DangerLevel.CONFIRM,  # MCP 工具默认需要确认
            timeout_seconds=mcp_client.config.timeout,
        )

    async def execute(self, **kwargs) -> ToolResult:
        """调用 MCP 工具。"""
        try:
            result_text = await self._mcp_client.call_tool(self._original_name, kwargs)
            return ToolResult.ok(
                content=result_text,
                server=self._tool_def.server_name,
                tool_type="mcp",
            )
        except Exception as e:
            return ToolResult.fail(
                error=f"MCP 工具调用失败: {e}",
                content=f"服务器 '{self._tool_def.server_name}' 上的工具 '{self.name}' 调用失败: {e}",
            )

    @property
    def server_name(self) -> str:
        """来源 MCP 服务器名称。"""
        return self._tool_def.server_name

    def __repr__(self) -> str:
        return f"MCPToolWrapper(name='{self.name}', server='{self.server_name}')"


def create_wrappers(mcp_client: MCPClient) -> list[MCPToolWrapper]:
    """
    将 MCP 客户端提供的所有工具转换为 Zclaw 工具包装器。

    Args:
        mcp_client: 已连接的 MCP 客户端

    Returns:
        MCPToolWrapper 列表，可直接注册到 ToolRegistry
    """
    wrappers = []
    for tool_def in mcp_client.tools:
        # 为工具名添加服务器前缀以避免冲突
        prefixed_name = f"{mcp_client.config.name}__{tool_def.name}"

        # 创建工具定义的副本（带前缀名称）
        prefixed_def = MCPToolDefinition(
            name=prefixed_name,
            description=f"[MCP:{mcp_client.config.name}] {tool_def.description}",
            input_schema=tool_def.input_schema,
            server_name=mcp_client.config.name,
        )

        wrapper = MCPToolWrapper(mcp_client, prefixed_def, original_name=tool_def.name)
        wrappers.append(wrapper)
        logger.debug(f"已创建 MCP 工具包装器: {prefixed_name}")

    return wrappers
