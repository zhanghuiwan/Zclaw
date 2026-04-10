"""
Skill 执行器

执行 skill 定义的操作。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from .models import SkillDefinition

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Skill 执行结果"""

    success: bool
    skill_name: str
    output: str = ""
    error: str = ""
    data: Any = None

    def __str__(self) -> str:
        if self.success:
            return f"Skill '{self.skill_name}' 执行成功"
        return f"Skill '{self.skill_name}' 执行失败：{self.error}"


class SkillExecutor:
    """
    Skill 执行器

    职责:
    1. 检查 skill 依赖是否满足
    2. 执行 skill 定义的操作
    3. 返回执行结果
    """

    def __init__(self):
        self._executors: dict[str, callable] = {}

    def register_executor(
        self,
        skill_name: str,
        executor: callable
    ) -> None:
        """
        注册自定义执行器

        Args:
            skill_name: skill 名称
            executor: 执行函数，接收 (skill, arguments) 参数
        """
        self._executors[skill_name] = executor
        logger.debug(f"注册 skill 执行器：{skill_name}")

    def can_execute(self, skill: SkillDefinition) -> tuple[bool, list[str]]:
        """
        检查 skill 是否可执行

        Args:
            skill: 要检查的 skill

        Returns:
            (是否可执行，缺失依赖列表)
        """
        return skill.requires.check_availability()

    async def execute(
        self,
        skill: SkillDefinition,
        arguments: str = ""
    ) -> SkillResult:
        """
        执行 skill

        Args:
            skill: 要执行的 skill 定义
            arguments: 执行参数

        Returns:
            SkillResult 执行结果
        """
        # 检查是否有自定义执行器
        if skill.name in self._executors:
            try:
                executor = self._executors[skill.name]
                result = executor(skill, arguments)
                return result
            except Exception as e:
                logger.error(f"自定义执行器失败 {skill.name}: {e}")
                return SkillResult(
                    success=False,
                    skill_name=skill.name,
                    error=str(e),
                )

        # 检查依赖
        available, missing = self.can_execute(skill)
        if not available:
            missing_str = "; ".join(missing)
            logger.warning(f"Skill '{skill.name}' 依赖不满足：{missing_str}")
            return SkillResult(
                success=False,
                skill_name=skill.name,
                error=f"依赖不满足：{missing_str}",
            )

        # 默认执行策略：返回 skill 内容供 LLM 参考
        # 具体执行逻辑由 LLM 根据 SKILL.md 内容决定
        logger.info(f"执行 skill: {skill.name}, 参数：{arguments}")

        # 生成执行摘要
        summary = self._generate_execution_summary(skill, arguments)

        return SkillResult(
            success=True,
            skill_name=skill.name,
            output=summary,
            data={
                "skill_content": skill.content,
                "arguments": arguments,
            },
        )

    def _generate_execution_summary(
        self,
        skill: SkillDefinition,
        arguments: str
    ) -> str:
        """生成执行摘要"""
        lines = [
            f"Skill: {skill.name} v{skill.version}",
            f"描述：{skill.description}",
        ]

        if arguments:
            lines.append(f"参数：{arguments}")

        if skill.primary_env:
            env_value = os.environ.get(skill.primary_env, "(未设置)")
            lines.append(f"主要环境变量 {skill.primary_env}: {env_value}")

        if skill.triggers:
            lines.append(f"触发词：{', '.join(skill.triggers[:5])}")

        return "\n".join(lines)

    def execute_shell_command(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = 30
    ) -> tuple[bool, str, str]:
        """
        执行 shell 命令（供 skills 使用）

        Args:
            command: 要执行的命令
            cwd: 工作目录
            timeout: 超时时间（秒）

        Returns:
            (成功与否，stdout, stderr)
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时：{command}")
            return False, "", "命令执行超时"
        except Exception as e:
            logger.error(f"命令执行失败：{e}")
            return False, "", str(e)

    def check_binary(self, name: str) -> bool:
        """检查二进制文件是否可用"""
        return shutil.which(name) is not None

    def check_env(self, name: str) -> bool:
        """检查环境变量是否已设置"""
        return name in os.environ and os.environ[name] != ""
