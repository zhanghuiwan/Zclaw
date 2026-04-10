"""
工具注册表

管理所有可用工具的注册、查找和执行。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表。

    负责工具的注册、查找、执行和统计。
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._stats = {
            "total_tools": 0,
            "total_executions": 0,
            "by_tool": {},
        }

    def register(self, tool: BaseTool) -> None:
        """注册一个工具。"""
        if not tool.name:
            raise ValueError("工具名称不能为空")
        if tool.name in self._tools:
            logger.warning(f"工具 '{tool.name}' 已注册，将被覆盖")
        self._tools[tool.name] = tool
        self._stats["total_tools"] = len(self._tools)
        self._stats["by_tool"][tool.name] = 0
        logger.debug(f"已注册工具: {tool.name}")

    def register_many(self, tools: list[BaseTool]) -> None:
        """批量注册工具。"""
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> bool:
        """注销一个工具。"""
        if name in self._tools:
            del self._tools[name]
            self._stats["total_tools"] = len(self._tools)
            return True
        return False

    def has(self, name: str) -> bool:
        """检查工具是否已注册。"""
        return name in self._tools

    def get(self, name: str) -> BaseTool:
        """获取工具实例。"""
        if name not in self._tools:
            raise KeyError(f"未找到工具 '{name}'。可用工具: {list(self._tools.keys())}")
        return self._tools[name]

    @property
    def all_tools(self) -> dict[str, BaseTool]:
        return dict(self._tools)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        执行一个工具。

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult 执行结果
        """
        tool = self.get(name)

        # 参数校验
        required_params = {p.name for p in tool.parameters if p.required}
        missing = required_params - set(arguments.keys())
        if missing:
            return ToolResult.fail(
                error=f"缺少必需参数: {', '.join(missing)}",
                content=f"工具 '{name}' 需要: {', '.join(required_params)}",
            )

        # 执行
        import time
        start = time.monotonic()
        try:
            result = await tool.execute(**arguments)
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(f"工具 '{name}' 执行错误: {e}")
            result = ToolResult.fail(
                error=str(e),
                content=f"工具 '{name}' 抛出异常: {e}",
                duration_ms=duration_ms,
            )

        # 统计
        self._stats["total_executions"] += 1
        self._stats["by_tool"][name] = self._stats["by_tool"].get(name, 0) + 1

        return result

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """获取所有工具的 OpenAI function calling 格式定义。"""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def get_stats(self) -> dict[str, Any]:
        """获取执行统计。"""
        return dict(self._stats)

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={len(self._tools)}, names={list(self._tools.keys())})"
