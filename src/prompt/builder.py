"""
System Prompt 构建器

根据上下文动态组装 system prompt。
"""
from __future__ import annotations
import logging
from src.prompt.templates import DEFAULT_PERSONA, COMPACT_PERSONA, TOOL_GUIDE_SECTION

logger = logging.getLogger(__name__)


class PromptBuilder:
    """System Prompt 构建器"""

    def __init__(self, persona: str = DEFAULT_PERSONA):
        self._persona = persona
        self._extra_sections: list[tuple[str, str]] = []

    def add_section(self, title: str, content: str) -> None:
        self._extra_sections.append((title, content))

    def clear_sections(self) -> None:
        self._extra_sections.clear()

    def set_persona(self, persona: str) -> None:
        self._persona = persona

    def build(
        self,
        tool_names: list[str] | None = None,
        memory_context: str = "",
        skill_context: str = "",
    ) -> str:
        """构建最终 system prompt。"""
        parts = [self._persona]

        # 始终包含工具引导部分（工具是 Zclaw 的核心组成部分）
        parts.append(TOOL_GUIDE_SECTION)

        if memory_context:
            parts.append(memory_context)

        if skill_context:
            parts.append(skill_context)

        for title, content in self._extra_sections:
            parts.append(f"## {title}\n{content}")

        return "\n\n".join(parts)

    def build_compact(self, tool_names: list[str] | None = None) -> str:
        """构建精简版 system prompt。"""
        parts = [COMPACT_PERSONA]
        if tool_names:
            parts.append(TOOL_GUIDE_SECTION)
        for title, content in self._extra_sections:
            parts.append(f"## {title}\n{content[:500]}")
        return "\n\n".join(parts)
