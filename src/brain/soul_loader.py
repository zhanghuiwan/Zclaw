"""
SOUL.md 加载器

加载并解析 SOUL.md 配置文件，定义 Agent 的人格和身份。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Soul:
    """Agent 灵魂配置"""
    name: str = "Zclaw"                              # Agent 名称
    version: str = "1.0.0"                           # 版本号
    role: str = "AI Assistant"                        # 角色
    personality: list[str] = field(default_factory=list)  # 人格特点列表
    behavior_rules: list[str] = field(default_factory=list)  # 行为规则列表
    capabilities: list[str] = field(default_factory=list)   # 能力列表
    constraints: list[str] = field(default_factory=list)   # 约束限制
    raw_content: str = ""                            # 原始内容（用于调试）


class SoulLoader:
    """
    SOUL.md 加载器

    解析 SOUL.md 文件，提取 Agent 的身份定义和人格特征。
    """

    # 标题行正则
    TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    # 二级标题正则（用于分类）
    SECTION_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    # 列表项正则
    LIST_ITEM_PATTERN = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)
    # 编号列表正则
    NUMBERED_ITEM_PATTERN = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)

    def load(self, path: str | Path) -> Soul:
        """
        加载 SOUL.md 文件。

        Args:
            path: SOUL.md 文件路径

        Returns:
            Soul: 解析后的 Soul 对象
        """
        path = Path(path)
        if not path.exists():
            logger.warning(f"SOUL.md 不存在: {path}，使用默认配置")
            return Soul()

        content = path.read_text(encoding="utf-8")
        return self.parse(content, str(path))

    def parse(self, content: str, source: str = "unknown") -> Soul:
        """
        解析 SOUL.md 内容。

        Args:
            content: SOUL.md 文本内容
            source: 来源路径（用于日志）

        Returns:
            Soul: 解析后的 Soul 对象
        """
        soul = Soul(raw_content=content)

        # 提取标题（Agent 名称）
        title_match = self.TITLE_PATTERN.search(content)
        if title_match:
            # 第一行是主标题（格式：# Agent 名称）
            name_part = title_match.group(1).strip()
            # 检查是否有版本信息
            if " v" in name_part.lower():
                parts = re.split(r"\s+v", name_part, maxsplit=1)
                soul.name = parts[0].strip()
                soul.version = parts[1].strip() if len(parts) > 1 else "1.0.0"
            else:
                soul.name = name_part

        # 按二级标题分割内容块
        sections = self._split_sections(content)

        # 解析各部分
        for section_title, section_content in sections.items():
            title_lower = section_title.lower().strip()

            if "身份" in title_lower or "identity" in title_lower:
                self._parse_identity_section(soul, section_content)
            elif "人格" in title_lower or "性格" in title_lower or "personality" in title_lower:
                self._parse_personality_section(soul, section_content)
            elif "行为" in title_lower or "准则" in title_lower or "rules" in title_lower:
                self._parse_behavior_section(soul, section_content)
            elif "能力" in title_lower or "技能" in title_lower or "capabilities" in title_lower:
                self._parse_capabilities_section(soul, section_content)
            elif "约束" in title_lower or "限制" in title_lower or "constraints" in title_lower:
                self._parse_constraints_section(soul, section_content)

        logger.info(f"SOUL 加载完成: {soul.name} v{soul.version}")
        return soul

    def _split_sections(self, content: str) -> dict[str, str]:
        """按二级标题分割内容块"""
        sections = {}
        current_title = "header"
        current_content = []

        lines = content.split("\n")
        for line in lines:
            section_match = self.SECTION_PATTERN.match(line)
            if section_match:
                # 保存前一个 section
                if current_content:
                    sections[current_title] = "\n".join(current_content)
                current_title = section_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        # 保存最后一个 section
        if current_content:
            sections[current_title] = "\n".join(current_content)

        return sections

    def _parse_identity_section(self, soul: Soul, content: str) -> None:
        """解析身份定义部分"""
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 识别键值对：- 名称：xxx 或 - name: xxx
            match = re.match(r"^[\-\*]?\s*(?:名称|name|版本|version|角色|role)[\s:：]+(.+)$", line, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if "name" in line.lower() or "名称" in line:
                    soul.name = value
                elif "version" in line.lower() or "版本" in line:
                    soul.version = value
                elif "role" in line.lower() or "角色" in line:
                    soul.role = value

    def _parse_personality_section(self, soul: Soul, content: str) -> None:
        """解析人格特点部分"""
        soul.personality = self._extract_list_items(content)

    def _parse_behavior_section(self, soul: Soul, content: str) -> None:
        """解析行为规则部分"""
        soul.behavior_rules = self._extract_list_items(content)

    def _parse_capabilities_section(self, soul: Soul, content: str) -> None:
        """解析能力列表部分"""
        soul.capabilities = self._extract_list_items(content)

    def _parse_constraints_section(self, soul: Soul, content: str) -> None:
        """解析约束限制部分"""
        soul.constraints = self._extract_list_items(content)

    def _extract_list_items(self, content: str) -> list[str]:
        """提取列表项"""
        items = []

        # 提取无序列表
        for match in self.LIST_ITEM_PATTERN.finditer(content):
            items.append(match.group(1).strip())

        # 提取有序列表
        for match in self.NUMBERED_ITEM_PATTERN.finditer(content):
            items.append(match.group(1).strip())

        return items

    def to_system_prompt(self, soul: Soul) -> str:
        """
        将 Soul 转换为系统提示词。

        Args:
            soul: Soul 对象

        Returns:
            str: 格式化的系统提示词
        """
        lines = [
            f"你是 {soul.name}，版本 {soul.version}。",
            f"角色：{soul.role}。",
        ]

        if soul.personality:
            lines.append("")
            lines.append("## 人格特点")
            for p in soul.personality:
                lines.append(f"- {p}")

        if soul.behavior_rules:
            lines.append("")
            lines.append("## 行为准则")
            for i, rule in enumerate(soul.behavior_rules, 1):
                lines.append(f"{i}. {rule}")

        if soul.capabilities:
            lines.append("")
            lines.append("## 能力")
            for cap in soul.capabilities:
                lines.append(f"- {cap}")

        if soul.constraints:
            lines.append("")
            lines.append("## 约束限制")
            for constraint in soul.constraints:
                lines.append(f"- {constraint}")

        return "\n".join(lines)
