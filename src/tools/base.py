"""
工具基类

定义工具的抽象接口、数据模型和危险等级。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DangerLevel(str, Enum):
    """工具危险等级"""
    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # string, integer, boolean, array, object
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None

    def to_json_schema(self) -> dict[str, Any]:
        """转换为 JSON Schema 格式。"""
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.default is not None:
            schema["default"] = self.default
        if not self.required:
            # 非必填字段在对象层级处理
            pass
        return schema


@dataclass
class ToolMetadata:
    """工具元数据"""
    category: str = "general"
    danger_level: DangerLevel = DangerLevel.SAFE
    timeout_seconds: int = 30


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    content: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def ok(content: str, **meta) -> ToolResult:
        return ToolResult(success=True, content=content, metadata=meta)

    @staticmethod
    def fail(error: str, content: str = "", **meta) -> ToolResult:
        return ToolResult(success=False, content=content, error=error, metadata=meta)

    def to_llm_content(self) -> str:
        """转换为发送给 LLM 的内容。"""
        if self.success:
            return self.content
        return f"错误: {self.error}\n{self.content}"


class BaseTool:
    """
    工具抽象基类。

    所有工具必须继承此类并实现 execute 方法。
    """

    name: str = ""
    description: str = ""
    parameters: list[ToolParameter] = []
    metadata: ToolMetadata = field(default_factory=ToolMetadata)

    # 简写属性
    @property
    def danger_level(self) -> DangerLevel:
        return self.metadata.danger_level

    @property
    def category(self) -> str:
        return self.metadata.category

    def get_danger_level(self, arguments: dict[str, Any] | None = None) -> DangerLevel:
        """返回本次调用的危险等级，子类可根据参数动态判断。"""
        return self.danger_level

    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具逻辑。

        子类必须实现此方法。
        """
        raise NotImplementedError(f"工具 '{self.name}' 必须实现 execute() 方法")

    def get_json_schema(self) -> dict[str, Any]:
        """获取工具参数的 JSON Schema。"""
        properties = {}
        required = []
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_json_schema(),
            },
        }

    def __repr__(self) -> str:
        return f"Tool(name='{self.name}', danger={self.danger_level.value}, category='{self.category}')"
