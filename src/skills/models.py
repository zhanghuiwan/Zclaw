"""
Skill 数据模型

定义 Skill 的核心数据结构和解析逻辑。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SkillRequirements:
    """Skill 运行所需的环境要求"""

    env_vars: list[str] = field(default_factory=list)
    binaries: list[str] = field(default_factory=list)

    def check_availability(self) -> tuple[bool, list[str]]:
        """
        检查所有依赖是否可用

        Returns:
            (是否可用，缺失项列表)
        """
        import os
        import shutil

        missing = []

        # 检查环境变量
        for env_var in self.env_vars:
            if not os.environ.get(env_var):
                missing.append(f"环境变量：{env_var}")

        # 检查二进制文件
        for binary in self.binaries:
            if not shutil.which(binary):
                missing.append(f"二进制文件：{binary}")

        return len(missing) == 0, missing


@dataclass
class SkillDefinition:
    """
    Skill 定义

    从 SKILL.md 解析得到的完整技能描述。
    """

    name: str
    description: str
    version: str = "0.6.1"
    source_path: Path | None = None
    triggers: list[str] = field(default_factory=list)
    requires: SkillRequirements = field(default_factory=SkillRequirements)
    primary_env: str | None = None
    homepage: str | None = None
    content: str = ""
    frontmatter_raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, skill_dir: Path) -> SkillDefinition:
        """
        从 skill 目录加载定义

        Args:
            skill_dir: skill 目录路径（应包含 SKILL.md）

        Returns:
            SkillDefinition 实例
        """
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        content = skill_md.read_text(encoding="utf-8")
        return cls.from_markdown(content, source_path=skill_md)

    @classmethod
    def from_markdown(
        cls,
        content: str,
        source_path: Path | None = None
    ) -> SkillDefinition:
        """
        从 SKILL.md 内容解析定义

        Args:
            content: SKILL.md 完整内容
            source_path: 源文件路径（可选）
        """
        frontmatter, body = cls._parse_frontmatter(content)

        # 提取基本信息
        name = frontmatter.get("name", "unknown")
        description = frontmatter.get("description", "")
        version = frontmatter.get("version", "0.6.1")

        # 提取触发条件
        triggers = []
        metadata = frontmatter.get("metadata", {})

        # 支持多种格式的 triggers
        if isinstance(metadata, dict):
            # OpenClaw 格式: metadata.openclaw.triggers
            openclaw_meta = metadata.get("openclaw", {})
            if isinstance(openclaw_meta, dict) and "triggers" in openclaw_meta:
                triggers = openclaw_meta.get("triggers", [])
            # 直接格式: metadata.triggers
            elif "triggers" in metadata:
                triggers = metadata.get("triggers", [])

        # 提取依赖要求
        requires_data = {}
        if isinstance(metadata, dict):
            requires_data = metadata.get("requires", {})

        env_vars = requires_data.get("env", []) if isinstance(requires_data, dict) else []
        binaries = requires_data.get("bins", []) if isinstance(requires_data, dict) else []

        requirements = SkillRequirements(
            env_vars=env_vars,
            binaries=binaries,
        )

        # 主要环境变量
        primary_env = None
        if isinstance(metadata, dict):
            primary_env = metadata.get("primaryEnv")

        # 主页
        homepage = None
        if isinstance(metadata, dict):
            homepage = metadata.get("homepage")

        return cls(
            name=name,
            description=description,
            version=version,
            source_path=source_path,
            triggers=triggers,
            requires=requirements,
            primary_env=primary_env,
            homepage=homepage,
            content=content,
            frontmatter_raw=frontmatter,
        )

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        """
        解析 YAML frontmatter

        格式:
        ---
        key: value
        ---
        body content...

        Returns:
            (frontmatter 字典，body 内容)
        """
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return {}, content

        frontmatter_yaml = match.group(1)
        body = match.group(2)

        try:
            frontmatter = yaml.safe_load(frontmatter_yaml) or {}
        except yaml.YAMLError:
            frontmatter = {}

        return frontmatter, body

    def matches_query(self, query: str) -> bool:
        """
        检查 skill 是否匹配用户查询

        基于 triggers 关键词和 description 进行匹配。
        """
        query_lower = query.lower()

        # 检查触发词
        for trigger in self.triggers:
            if trigger.lower() in query_lower:
                return True

        # 检查名称和描述
        if self.name.lower() in query_lower:
            return True
        if self.description.lower() in query_lower:
            return True

        return False

    def to_prompt(self) -> str:
        """
        渲染为提示词

        返回完整的 SKILL.md 内容，供 LLM 使用。
        """
        return self.content

    def __repr__(self) -> str:
        return (
            f"SkillDefinition(name={self.name!r}, "
            f"description={self.description!r}, "
            f"triggers={len(self.triggers)} items)"
        )
