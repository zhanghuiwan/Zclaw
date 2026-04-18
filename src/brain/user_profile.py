"""
USER.md 加载器

加载并解析 USER.md 配置文件，告诉 Agent 关于用户的信息。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """用户信息配置"""
    name: str = ""                                 # 用户姓名
    timezone: str = "UTC"                          # 时区
    role: str = ""                                 # 用户角色
    preferences: list[str] = field(default_factory=list)   # 偏好列表
    sensitive_operations: list[str] = field(default_factory=list)  # 敏感操作
    languages: list[str] = field(default_factory=list)    # 编程语言偏好
    raw_content: str = ""                          # 原始内容


class UserProfileLoader:
    """
    USER.md 加载器

    解析 USER.md 文件，提取用户的基本信息、偏好和敏感操作定义。
    """

    SECTION_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    LIST_ITEM_PATTERN = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)

    def load(self, path: str | Path) -> UserProfile:
        """
        加载 USER.md 文件。

        Args:
            path: USER.md 文件路径

        Returns:
            UserProfile: 解析后的用户配置对象
        """
        path = Path(path)
        if not path.exists():
            logger.warning(f"USER.md 不存在: {path}，使用默认配置")
            return UserProfile()

        content = path.read_text(encoding="utf-8")
        return self.parse(content, str(path))

    def parse(self, content: str, source: str = "unknown") -> UserProfile:
        """
        解析 USER.md 内容。

        Args:
            content: USER.md 文本内容
            source: 来源路径

        Returns:
            UserProfile: 解析后的用户配置对象
        """
        profile = UserProfile(raw_content=content)

        # 按二级标题分割
        sections = self._split_sections(content)

        for section_title, section_content in sections.items():
            title_lower = section_title.lower().strip()

            if "基本" in title_lower or "basic" in title_lower or "信息" in title_lower:
                self._parse_basic_section(profile, section_content)
            elif "偏好" in title_lower or "preference" in title_lower:
                self._parse_preferences_section(profile, section_content)
            elif "敏感" in title_lower or "sensitive" in title_lower:
                self._parse_sensitive_section(profile, section_content)
            elif "语言" in title_lower or "language" in title_lower:
                self._parse_languages_section(profile, section_content)

        logger.info(f"USER 加载完成: {profile.name or 'unknown'}")
        return profile

    def _split_sections(self, content: str) -> dict[str, str]:
        """按二级标题分割内容"""
        sections = {}
        current_title = "header"
        current_content = []

        lines = content.split("\n")
        for line in lines:
            section_match = self.SECTION_PATTERN.match(line)
            if section_match:
                if current_content:
                    sections[current_title] = "\n".join(current_content)
                current_title = section_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_title] = "\n".join(current_content)

        return sections

    def _parse_basic_section(self, profile: UserProfile, content: str) -> None:
        """解析基本信息部分"""
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            match = re.match(r"^[\-\*]?\s*(?:姓名|name|时区|timezone|角色|role)[\s:：]+(.+)$", line, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if "name" in line.lower() or "姓名" in line:
                    profile.name = value
                elif "timezone" in line.lower() or "时区" in line:
                    profile.timezone = value
                elif "role" in line.lower() or "角色" in line:
                    profile.role = value

    def _parse_preferences_section(self, profile: UserProfile, content: str) -> None:
        """解析偏好部分"""
        profile.preferences = self._extract_list_items(content)

    def _parse_sensitive_section(self, profile: UserProfile, content: str) -> None:
        """解析敏感操作部分"""
        profile.sensitive_operations = self._extract_list_items(content)

    def _parse_languages_section(self, profile: UserProfile, content: str) -> None:
        """解析编程语言偏好"""
        profile.languages = self._extract_list_items(content)

    def _extract_list_items(self, content: str) -> list[str]:
        """提取列表项"""
        items = []
        for match in self.LIST_ITEM_PATTERN.finditer(content):
            items.append(match.group(1).strip())
        return items

    def to_context_string(self, profile: UserProfile) -> str:
        """
        将 UserProfile 转换为上下文字符串。

        Args:
            profile: UserProfile 对象

        Returns:
            str: 格式化的用户信息
        """
        lines = ["## 关于用户"]

        if profile.name:
            lines.append(f"- 姓名：{profile.name}")
        if profile.timezone:
            lines.append(f"- 时区：{profile.timezone}")
        if profile.role:
            lines.append(f"- 角色：{profile.role}")

        if profile.languages:
            lines.append(f"- 偏好语言：{', '.join(profile.languages)}")

        if profile.preferences:
            lines.append("")
            lines.append("## 用户偏好")
            for pref in profile.preferences:
                lines.append(f"- {pref}")

        if profile.sensitive_operations:
            lines.append("")
            lines.append("## 敏感操作（需要确认）")
            for op in profile.sensitive_operations:
                lines.append(f"- {op}")

        return "\n".join(lines)
