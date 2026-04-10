"""
Memory Update Tools

Tools for updating L3 semantic memory (user/project profiles).
"""

from __future__ import annotations

import logging
from typing import Any

from src.memory.layers.l3_semantic import SemanticMemory
from src.tools.base import BaseTool, ToolParameter, ToolMetadata, ToolResult, DangerLevel

logger = logging.getLogger(__name__)


class UpdateSemanticMemoryTool(BaseTool):
    """
    Tool for updating L3 semantic memory (user/project profiles).

    Agent calls this to store preferences and project information
    that should persist across sessions.
    """

    name = "update_memory"
    description = """
Update persistent memory about the user or project.

Use this to store:
- User preferences (language, code style, timezone, name)
- Project information (tech stack, architecture, conventions)
- Important facts that should persist

This writes to L3 semantic memory (current-state only, direct overwrite).
"""
    parameters = [
        ToolParameter(
            name="category",
            type="string",
            description="Category to update: 'user' or 'project'",
            required=True,
            enum=["user", "project"],
        ),
        ToolParameter(
            name="data",
            type="object",
            description="Key-value pairs to update",
            required=True,
        ),
    ]
    metadata = ToolMetadata(
        category="memory",
        danger_level=DangerLevel.SAFE,
        timeout_seconds=10,
    )

    def __init__(self, semantic_memory: SemanticMemory):
        self._semantic = semantic_memory

    async def execute(self, category: str, data: dict[str, Any], **kwargs) -> ToolResult:
        try:
            if category == "user":
                self._semantic.update_user_profile(**data)
            elif category == "project":
                self._semantic.update_project_profile(**data)
            else:
                return ToolResult.fail(content=f"Unknown category: {category}")

            return ToolResult.ok(f"Updated {category} profile successfully.")
        except Exception as e:
            logger.error(f"update_memory failed: {e}")
            return ToolResult.fail(error=str(e), content="Update failed")


class SetPreferenceTool(BaseTool):
    """
    Tool for setting a specific user preference.

    Simpler than update_memory for single key-value pairs.
    """

    name = "set_preference"
    description = """
Set a specific user preference.

Use this for simple preference updates like:
- "name": "John"
- "language": "Chinese"
- "code_style": "functional"
"""
    parameters = [
        ToolParameter(
            name="key",
            type="string",
            description="Preference key",
            required=True,
        ),
        ToolParameter(
            name="value",
            type="string",
            description="Preference value",
            required=True,
        ),
    ]
    metadata = ToolMetadata(
        category="memory",
        danger_level=DangerLevel.SAFE,
        timeout_seconds=10,
    )

    def __init__(self, semantic_memory: SemanticMemory):
        self._semantic = semantic_memory

    async def execute(self, key: str, value: str, **kwargs) -> ToolResult:
        try:
            self._semantic.set_preference(key, value)
            return ToolResult.ok(f"Set preference: {key} = {value}")
        except Exception as e:
            logger.error(f"set_preference failed: {e}")
            return ToolResult.fail(error=str(e), content="Set preference failed")
