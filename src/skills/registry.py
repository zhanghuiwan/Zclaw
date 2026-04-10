"""
Skill 注册表

管理所有已加载的 skills，提供注册、查询和匹配功能。
"""

from __future__ import annotations

import logging
from typing import Callable

from .models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    技能注册表

    职责:
    1. 注册和管理所有已加载的 skills
    2. 根据名称查询 skill
    3. 根据用户输入匹配相关的 skills
    """

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}
        self._custom_matchers: list[Callable[[str], list[SkillDefinition]]] = []

    def register(self, skill: SkillDefinition) -> None:
        """
        注册一个 skill

        Args:
            skill: 要注册的 skill 定义

        Raises:
            ValueError: 如果同名的 skill 已存在
        """
        if skill.name in self._skills:
            logger.warning(f"Skill '{skill.name}' 已存在，将被覆盖")

        self._skills[skill.name] = skill
        logger.info(f"注册 skill: {skill.name} - {skill.description}")

    def get(self, name: str) -> SkillDefinition | None:
        """
        根据名称获取 skill

        Args:
            name: skill 名称

        Returns:
            SkillDefinition 或 None
        """
        return self._skills.get(name)

    def has(self, name: str) -> bool:
        """检查 skill 是否已注册"""
        return name in self._skills

    def remove(self, name: str) -> bool:
        """
        移除一个 skill

        Args:
            name: skill 名称

        Returns:
            是否成功移除
        """
        if name in self._skills:
            del self._skills[name]
            logger.info(f"移除 skill: {name}")
            return True
        return False

    def match(self, query: str) -> list[SkillDefinition]:
        """
        根据用户输入匹配相关的 skills

        匹配策略:
        1. 检查是否包含 skill 的触发词 (triggers)
        2. 检查是否包含 skill 名称或描述
        3. 使用自定义匹配器

        Args:
            query: 用户输入

        Returns:
            匹配的 skill 列表（按相关性排序）
        """
        if not query:
            return []

        matches: list[tuple[int, SkillDefinition]] = []

        for skill in self._skills.values():
            score = self._calculate_match_score(skill, query)
            if score > 0:
                matches.append((score, skill))

        # 使用自定义匹配器
        for matcher in self._custom_matchers:
            try:
                extra_matches = matcher(query)
                for skill in extra_matches:
                    if not any(s.name == skill.name for _, s in matches):
                        matches.append((1, skill))
            except Exception as e:
                logger.error(f"自定义匹配器出错：{e}")

        # 按分数降序排序
        matches.sort(key=lambda x: x[0], reverse=True)

        return [skill for _, skill in matches]

    def _calculate_match_score(self, skill: SkillDefinition, query: str) -> int:
        """
        计算 skill 与查询的匹配分数

        评分规则:
        - 触发词匹配：+10 分（每个触发词）
        - 名称完全匹配：+5 分
        - 名称部分匹配：+2 分
        - 描述匹配：+1 分
        """
        score = 0
        query_lower = query.lower()

        # 触发词匹配（权重最高）
        for trigger in skill.triggers:
            if trigger.lower() in query_lower:
                score += 10

        # 名称完全匹配
        if skill.name.lower() == query_lower:
            score += 5

        # 名称部分匹配
        if skill.name.lower() in query_lower:
            score += 2

        # 描述匹配
        if skill.description.lower() in query_lower:
            score += 1

        return score

    def add_custom_matcher(
        self,
        matcher: Callable[[str], list[SkillDefinition]]
    ) -> None:
        """
        添加自定义匹配器

        Args:
            matcher: 接受查询字符串，返回匹配的 skill 列表
        """
        self._custom_matchers.append(matcher)
        logger.debug(f"添加自定义 skill 匹配器")

    def list_all(self) -> list[SkillDefinition]:
        """列出所有已注册的 skills"""
        return list(self._skills.values())

    def count(self) -> int:
        """返回已注册的 skill 数量"""
        return len(self._skills)

    def get_all_triggers(self) -> list[str]:
        """获取所有 skill 的触发词列表"""
        triggers = []
        for skill in self._skills.values():
            triggers.extend(skill.triggers)
        return triggers

    def get_context_summary(self) -> str:
        """
        获取所有 skills 的摘要信息

        用于注入到 system prompt 中，让 LLM 知道可用的 skills。
        """
        if not self._skills:
            return "当前没有可用的 skills。"

        lines = ["可用的 Skills:"]
        for skill in self._skills.values():
            trigger_str = ", ".join(skill.triggers[:5]) if skill.triggers else "无触发词"
            lines.append(f"  - {skill.name}: {skill.description} (触发：{trigger_str})")

        return "\n".join(lines)
