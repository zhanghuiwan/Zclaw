"""
Episodic Memory Search Tools

Exposes L2 episodic memory as tools for the Agent.
Agent calls these tools to query conversation history - not auto-retrieved.
"""

from __future__ import annotations

import logging
from typing import Any

from src.memory.layers.l2_episodic import EpisodicEntry, EpisodicMemory
from src.tools.base import BaseTool, ToolParameter, ToolMetadata, ToolResult, DangerLevel

logger = logging.getLogger(__name__)


class SearchConversationHistoryTool(BaseTool):
    """
    Tool for searching conversation history from L2 episodic memory.

    This is the ONLY way Agent accesses L2 episodic memory.
    The Agent must explicitly call this tool - no auto-retrieval.
    """

    name = "search_conversation_history"
    description = """
Search through past conversation history stored in episodic memory.

Use this to find:
- Previous discussions about similar topics
- Past decisions and their contexts
- Information shared in previous sessions

Returns relevant conversation entries with timestamps and summaries.
"""
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Search query to find relevant conversations",
            required=True,
        ),
        ToolParameter(
            name="session_id",
            type="string",
            description="Optional: Filter by specific session ID",
            required=False,
            default="",
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of results to return",
            required=False,
            default=10,
        ),
    ]
    metadata = ToolMetadata(
        category="memory",
        danger_level=DangerLevel.SAFE,
        timeout_seconds=30,
    )

    def __init__(self, episodic_memory: EpisodicMemory):
        """
        Args:
            episodic_memory: EpisodicMemory instance from MemoryCoordinator
        """
        self._episodic = episodic_memory

    async def execute(
        self,
        query: str,
        session_id: str = "",
        limit: int = 10,
        **kwargs,
    ) -> ToolResult:
        """Execute the search."""
        try:
            results = self._episodic.search(
                query=query,
                session_id=session_id if session_id else None,
                limit=limit,
            )

            if not results:
                return ToolResult.ok("No matching conversation history found.")

            lines = [f"Found {len(results)} matching entries:\n"]
            for entry in results:
                lines.append(self._format_entry(entry))
                lines.append("---")

            return ToolResult.ok("\n".join(lines))
        except Exception as e:
            logger.error(f"search_conversation_history failed: {e}")
            return ToolResult.fail(error=str(e), content="Search failed")

    def _format_entry(self, entry: EpisodicEntry) -> str:
        """Format an episodic entry for display."""
        role_icon = {"user": "User", "assistant": "Assistant", "system": "System"}.get(entry.role, entry.role)
        lines = [
            f"[{entry.timestamp}] {role_icon} (session: {entry.session_id})",
            f"Content: {entry.content[:300]}{'...' if len(entry.content) > 300 else ''}",
        ]
        if entry.summary:
            lines.append(f"Summary: {entry.summary}")
        if entry.tool_calls:
            tc_names = [tc.get("tool", "unknown") for tc in entry.tool_calls]
            lines.append(f"Tools used: {', '.join(tc_names)}")
        return "\n".join(lines)


class GetSessionHistoryTool(BaseTool):
    """
    Tool for getting full conversation history of a specific session.
    """

    name = "get_session_history"
    description = """
Get the complete conversation history for a specific session.

Use this to recall what was discussed and done in a previous session.
Returns all turns in chronological order.
"""
    parameters = [
        ToolParameter(
            name="session_id",
            type="string",
            description="Session ID to retrieve history for",
            required=True,
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of turns to return",
            required=False,
            default=100,
        ),
    ]
    metadata = ToolMetadata(
        category="memory",
        danger_level=DangerLevel.SAFE,
        timeout_seconds=30,
    )

    def __init__(self, episodic_memory: EpisodicMemory):
        self._episodic = episodic_memory

    async def execute(self, session_id: str, limit: int = 100, **kwargs) -> ToolResult:
        """Execute the retrieval."""
        try:
            results = self._episodic.get_session_history(session_id, limit=limit)

            if not results:
                return ToolResult.ok(f"No history found for session {session_id}.")

            lines = [f"Session {session_id} - {len(results)} entries:\n"]
            for entry in results:
                lines.append(self._format_entry(entry))
                lines.append("---")

            return ToolResult.ok("\n".join(lines))
        except Exception as e:
            logger.error(f"get_session_history failed: {e}")
            return ToolResult.fail(error=str(e), content="Retrieval failed")

    def _format_entry(self, entry: EpisodicEntry) -> str:
        role_icon = {"user": "User", "assistant": "Assistant", "system": "System"}.get(entry.role, entry.role)
        return f"[{entry.timestamp}] {role_icon}: {entry.content[:200]}{'...' if len(entry.content) > 200 else ''}"
