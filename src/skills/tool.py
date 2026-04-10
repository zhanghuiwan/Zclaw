"""
Skill 工具包装器

将 SkillDefinition 包装为可被 Agent 调用的 Tool。
"""

from __future__ import annotations

import os
from typing import Any

from src.tools.base import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    DangerLevel,
)


class SkillTool(BaseTool):
    """
    Skill 工具包装器

    将 SkillDefinition 包装为标准的 BaseTool，使其可以被 Agent 发现和调用。
    当 LLM 调用此工具时，返回 skill 的完整内容供其参考。
    """

    def __init__(self, skill_def):
        """
        初始化 Skill 工具

        Args:
            skill_def: SkillDefinition 实例
        """
        self._skill = skill_def

        # 工具名称使用 skill 名称
        self.name = f"skill__{skill_def.name}"
        self.description = skill_def.description

        # 工具参数
        self.parameters = [
            ToolParameter(
                name="query",
                type="string",
                description=f"向 {skill_def.name} 提出的具体请求或问题",
                required=True,
            ),
        ]

        # 元数据
        self.metadata = ToolMetadata(
            category="skill",
            danger_level=DangerLevel.SAFE,
            timeout_seconds=30,
        )

    @property
    def skill(self):
        """获取原始 skill 定义"""
        return self._skill

    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        """
        执行 skill 工具

        返回 skill 的完整内容，帮助 LLM 生成更好的回答。

        Args:
            query: 用户的具体请求

        Returns:
            ToolResult 包含 skill 的完整 SKILL.md 内容
        """
        skill = self._skill

        # 初始化变量
        missing_envs = []
        missing_bins = []

        # 构建返回内容
        lines = [
            f"# Skill: {skill.name} (v{skill.version})",
            f"",
            f"## 描述",
            f"{skill.description}",
            "",
        ]

        # 添加环境变量状态
        if skill.requires.env_vars:
            env_status = []
            for env_var in skill.requires.env_vars:
                if os.environ.get(env_var):
                    env_status.append(f"✓ {env_var} 已配置")
                else:
                    env_status.append(f"✗ {env_var} 未配置")
                    missing_envs.append(env_var)

            lines.extend([
                f"## 环境变量状态",
                "\n".join(env_status),
                "",
            ])

        # 添加二进制要求状态
        if skill.requires.binaries:
            import shutil
            bin_status = []
            for bin_name in skill.requires.binaries:
                if shutil.which(bin_name):
                    bin_status.append(f"✓ {bin_name} 已安装")
                else:
                    bin_status.append(f"✗ {bin_name} 未安装")
                    missing_bins.append(bin_name)

            lines.extend([
                f"## 二进制程序状态",
                "\n".join(bin_status),
                "",
            ])

        # 如果缺少依赖，给出明确指示
        if missing_envs or missing_bins:
            lines.extend([
                f"## ⚠️ 缺少依赖",
                f"请先配置以下环境变量或安装以下程序后重试。",
                "",
            ])
            if missing_envs:
                lines.append(f"环境变量：{', '.join(missing_envs)}")
            if missing_bins:
                lines.append(f"程序：{', '.join(missing_bins)}")
            lines.append("")

        # 添加触发条件
        if skill.triggers:
            lines.extend([
                f"## 触发关键词",
                f"当用户提到以下关键词时应使用此 skill：{', '.join(skill.triggers)}",
                "",
            ])

        # 添加完整内容（SKILL.md body 部分）
        lines.extend([
            f"## 完整技能说明",
            f"---",
            f"{skill.content}",
        ])

        content = "\n".join(lines)

        return ToolResult.ok(
            content=content,
            skill_name=skill.name,
            skill_version=skill.version,
            env_configured=not missing_envs if skill.requires.env_vars else True,
            bins_configured=not missing_bins if skill.requires.binaries else True,
        )

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_json_schema(),
            },
        }

    def __repr__(self) -> str:
        return f"SkillTool(name='{self.name}', skill='{self._skill.name}')"
