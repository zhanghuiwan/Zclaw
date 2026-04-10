"""
L1: Working Memory

Session snapshot files - memory + disk.
Holds current session context that does not persist beyond session.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionSnapshot:
    """Single session snapshot"""
    session_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    task_description: str = ""
    working_directory: str = ""
    active_files: list[str] = field(default_factory=list)  # files currently open/editing
    pending_goals: list[str] = field(default_factory=list)  # goals not yet completed
    completed_goals: list[str] = field(default_factory=list)  # goals completed this session
    extracted_facts: list[str] = field(default_factory=list)  # facts extracted this session
    tool_history: list[dict[str, Any]] = field(default_factory=list)  # tool calls this session

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "task_description": self.task_description,
            "working_directory": self.working_directory,
            "active_files": self.active_files,
            "pending_goals": self.pending_goals,
            "completed_goals": self.completed_goals,
            "extracted_facts": self.extracted_facts,
            "tool_history": self.tool_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionSnapshot:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class WorkingMemory:
    """
    L1 Working Memory - session snapshot storage.

    Stores current session context to disk as JSON files.
    Snapshots are written on:
    - Session start
    - After each major task completion
    - Session end

    File location: .memory/L1_working/sessions/{session_id}.json
    """

    def __init__(self, storage_root: Path):
        """
        Args:
            storage_root: Root path for .memory/ directory
        """
        self._storage_root = storage_root / "L1_working" / "sessions"
        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._current_snapshot: SessionSnapshot | None = None

    def create_snapshot(self, session_id: str) -> SessionSnapshot:
        """Create a new session snapshot."""
        snap = SessionSnapshot(session_id=session_id)
        self._current_snapshot = snap
        self._write_snapshot(snap)
        logger.debug(f"Created session snapshot for {session_id}")
        return snap

    def update_snapshot(self, **updates) -> SessionSnapshot | None:
        """Update fields on current snapshot."""
        if self._current_snapshot is None:
            return None
        for key, value in updates.items():
            if hasattr(self._current_snapshot, key):
                setattr(self._current_snapshot, key, value)
        self._current_snapshot.timestamp = datetime.now().isoformat()
        self._write_snapshot(self._current_snapshot)
        return self._current_snapshot

    def add_tool_call(self, tool_name: str, arguments: dict[str, Any], result: str) -> None:
        """Record a tool call in the current snapshot."""
        if self._current_snapshot is None:
            return
        self._current_snapshot.tool_history.append({
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "result_summary": result[:200] if len(result) > 200 else result,
        })
        self._write_snapshot(self._current_snapshot)

    def add_pending_goal(self, goal: str) -> None:
        """Add a pending goal."""
        if self._current_snapshot is None:
            return
        if goal not in self._current_snapshot.pending_goals:
            self._current_snapshot.pending_goals.append(goal)
            self._write_snapshot(self._current_snapshot)

    def complete_goal(self, goal: str) -> None:
        """Move a goal from pending to completed."""
        if self._current_snapshot is None:
            return
        if goal in self._current_snapshot.pending_goals:
            self._current_snapshot.pending_goals.remove(goal)
        if goal not in self._current_snapshot.completed_goals:
            self._current_snapshot.completed_goals.append(goal)
            self._write_snapshot(self._current_snapshot)

    def add_extracted_fact(self, fact: str) -> None:
        """Add an extracted fact."""
        if self._current_snapshot is None:
            return
        if fact not in self._current_snapshot.extracted_facts:
            self._current_snapshot.extracted_facts.append(fact)
            self._write_snapshot(self._current_snapshot)

    def load_snapshot(self, session_id: str) -> SessionSnapshot | None:
        """Load a specific session snapshot from disk."""
        path = self._storage_root / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SessionSnapshot.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load session snapshot {session_id}: {e}")
            return None

    def list_sessions(self) -> list[str]:
        """List all session IDs on disk."""
        return [p.stem for p in self._storage_root.glob("*.json")]

    def _write_snapshot(self, snap: SessionSnapshot) -> None:
        """Write snapshot to disk."""
        path = self._storage_root / f"{snap.session_id}.json"
        path.write_text(json.dumps(snap.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def current(self) -> SessionSnapshot | None:
        return self._current_snapshot
