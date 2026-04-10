"""
MemoryCoordinator

Coordinates all memory layers (L0-L4) and exposes a unified API.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.memory.layers.l0_perceptual import PerceptualBuffer, PerceptualEntry
from src.memory.layers.l1_working import WorkingMemory, SessionSnapshot
from src.memory.layers.l2_episodic import EpisodicMemory, EpisodicEntry
from src.memory.layers.l3_semantic import SemanticMemory, UserProfile, ProjectProfile
from src.memory.layers.l4_procedural import ProceduralMemory
from src.memory.config import V4MemoryConfig

logger = logging.getLogger(__name__)


class MemoryCoordinator:
    """
    MemoryCoordinator - coordinates all memory layers.

    Primary API:
    - perceive(): L0 capture
    - working: L1 access
    - episodic: L2 access (append only)
    - semantic: L3 access (current state)
    - procedural: L4 access (rules)
    - build_system_prompt_context(): Build minimal context for system prompt
    """

    def __init__(self, storage_root: Path, session_id: str, config: V4MemoryConfig | None = None):
        """
        Args:
            storage_root: Root path for .memory/ directory
            session_id: Current session ID
            config: V4 memory configuration
        """
        self._session_id = session_id
        self._config = config or V4MemoryConfig()
        self._storage_root = Path(storage_root).expanduser().resolve()
        self._storage_root.mkdir(parents=True, exist_ok=True)

        # Initialize all layers
        self._l0_perceptual = PerceptualBuffer(max_turns=self._config.perceptual_max_turns)
        self._l1_working = WorkingMemory(self._storage_root)
        self._l2_episodic = EpisodicMemory(
            self._storage_root,
            vector_store_enabled=self._config.vector_store_enabled,
        )
        self._l3_semantic = SemanticMemory(self._storage_root)
        self._l4_procedural = ProceduralMemory(self._storage_root)

        # Create or load session snapshot
        existing = self._l1_working.load_snapshot(session_id)
        if existing:
            self._l1_working._current_snapshot = existing
        else:
            self._l1_working.create_snapshot(session_id)

        # For backward compatibility with tests that access _memory.extractor
        self._extractor: Any | None = None

        logger.info(f"MemoryCoordinator initialized for session {session_id}")

    # L0 Perceptual
    def perceive(self, user_input: str, assistant_output: str = "") -> PerceptualEntry:
        """L0: Capture current turn perception."""
        return self._l0_perceptual.capture(user_input, assistant_output)

    @property
    def perceptual(self) -> PerceptualBuffer:
        return self._l0_perceptual

    # L1 Working Memory
    def update_working_context(
        self,
        task_description: str | None = None,
        active_files: list[str] | None = None,
        pending_goals: list[str] | None = None,
        completed_goals: list[str] | None = None,
    ) -> SessionSnapshot | None:
        """L1: Update current session snapshot."""
        updates = {}
        if task_description is not None:
            updates["task_description"] = task_description
        if active_files is not None:
            updates["active_files"] = active_files
        if pending_goals is not None:
            updates["pending_goals"] = pending_goals
        if completed_goals is not None:
            updates["completed_goals"] = completed_goals
        return self._l1_working.update_snapshot(**updates) if updates else self._l1_working.current

    def add_pending_goal(self, goal: str) -> None:
        """L1: Add a pending goal."""
        self._l1_working.add_pending_goal(goal)

    def complete_goal(self, goal: str) -> None:
        """L1: Mark a goal as completed."""
        self._l1_working.complete_goal(goal)

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any], result: str) -> None:
        """L1: Record a tool call."""
        self._l1_working.add_tool_call(tool_name, arguments, result)

    @property
    def working(self) -> WorkingMemory:
        return self._l1_working

    # L2 Episodic (append-only)
    def archive_turn(
        self,
        role: str,
        content: str,
        summary: str = "",
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> EpisodicEntry:
        """L2: Archive a turn to episodic memory (append-only)."""
        entry = EpisodicEntry(
            session_id=self._session_id,
            role=role,
            content=content,
            summary=summary,
            tool_calls=tool_calls or [],
        )
        return self._l2_episodic.append(entry)

    def search_episodic(
        self,
        query: str | None = None,
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[EpisodicEntry]:
        """L2: Search episodic memory."""
        return self._l2_episodic.search(query=query, session_id=session_id, limit=limit)

    def get_session_history(self, session_id: str, limit: int = 100) -> list[EpisodicEntry]:
        """L2: Get session history."""
        return self._l2_episodic.get_session_history(session_id, limit=limit)

    @property
    def episodic(self) -> EpisodicMemory:
        return self._l2_episodic

    # L3 Semantic
    @property
    def semantic(self) -> SemanticMemory:
        return self._l3_semantic

    # L4 Procedural
    @property
    def procedural(self) -> ProceduralMemory:
        return self._l4_procedural

    # System prompt context builder
    def build_system_prompt_context(self) -> str:
        """
        Build minimal context for system prompt injection.

        INJECTED:
        - L4 rules (always)
        - L3 current state (always)
        - L1 current task (always)

        NOT injected (Agent uses tools to query):
        - L2 episodic (immutable archive, tool-based access)
        - L0 perceptual (too transient)
        """
        parts = []

        # L4: Procedural rules (always injected)
        rules_context = self._l4_procedural.format_for_system_prompt()
        if rules_context:
            parts.append(rules_context)

        # L3: Semantic state (always injected)
        semantic_context = self._l3_semantic.format_for_system_prompt()
        if semantic_context:
            parts.append(semantic_context)

        # L1: Current task context
        current = self._l1_working.current
        if current:
            task_lines = []
            if current.task_description:
                task_lines.append(f"- Task: {current.task_description}")
            if current.pending_goals:
                task_lines.append(f"- Pending goals: {', '.join(current.pending_goals)}")
            if current.completed_goals:
                task_lines.append(f"- Completed: {', '.join(current.completed_goals)}")
            if current.active_files:
                task_lines.append(f"- Active files: {', '.join(current.active_files)}")

            if task_lines:
                parts.append("## Current Task\n" + "\n".join(task_lines))

        return "\n\n".join(parts)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def extractor(self) -> Any | None:
        """Backward compat: returns stored extractor."""
        return self._extractor

    @extractor.setter
    def extractor(self, value: Any) -> None:
        """Backward compat: store extractor."""
        self._extractor = value

    async def extract_and_store(
        self,
        messages: list,
        extractor: Any | None = None,
    ) -> list[str]:
        """
        Extract memories from conversation and store to appropriate layers.

        Args:
            messages: Conversation messages
            extractor: Memory extractor (BaseExtractor interface)

        Returns:
            List of stored memory IDs/descriptions
        """
        if extractor is None:
            return []

        try:
            extracted = await extractor.extract(messages)
        except Exception as e:
            logger.error(f"记忆提取失败: {e}")
            return []

        stored = []
        for em in extracted:
            if not em.content.strip():
                continue

            try:
                if em.type == "preference":
                    # Preferences → L3 semantic (store as a preference)
                    self._l3_semantic.set_preference(
                        key=em.content[:50],  # Use first 50 chars as key
                        value=True,
                    )
                    stored.append(f"preference: {em.content[:50]}")

                elif em.type == "fact":
                    # Facts → L1 working (extracted_facts)
                    self._l1_working.add_extracted_fact(em.content)
                    stored.append(f"fact: {em.content[:50]}")

                elif em.type == "episode":
                    # Episodes → L2 episodic
                    entry = self._l2_episodic.append(EpisodicEntry(
                        session_id=self._session_id,
                        role="extracted",
                        content=em.content,
                        summary=f"[auto-extracted] {em.tags}",
                    ))
                    stored.append(f"episode: {entry.id}")

                elif em.type == "skill":
                    # Skills → L1 working (extracted_facts with skill tag)
                    self._l1_working.add_extracted_fact(f"[skill] {em.content}")
                    stored.append(f"skill: {em.content[:50]}")

            except Exception as e:
                logger.error(f"Failed to store extracted memory: {e}")

        if stored:
            logger.info(f"Extracted and stored {len(stored)} memories")

        return stored

