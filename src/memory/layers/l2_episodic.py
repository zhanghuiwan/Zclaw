"""
L2: Episodic Memory

SQLite timeline index + vector store (immutable).
Never modified, only appends.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EpisodicEntry:
    """Single episodic memory entry"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    role: str = "assistant"  # "user" | "assistant" | "system"
    content: str = ""
    summary: str = ""  # Optional LLM-generated summary
    embedding_id: str | None = None  # Reference to vector store
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "role": self.role,
            "content": self.content,
            "summary": self.summary,
            "embedding_id": self.embedding_id,
            "tool_calls": self.tool_calls,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> cls:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class EpisodicMemory:
    """
    L2 Episodic Memory - immutable archive.

    Uses SQLite for timeline indexing and sqlite-vss for vector search.

    SQLite schema:
        CREATE TABLE episodes (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp TEXT,
            role TEXT,
            content TEXT,
            summary TEXT,
            embedding_id TEXT,
            tool_calls TEXT
        );
        CREATE INDEX idx_timestamp ON episodes(timestamp);
        CREATE INDEX idx_session ON episodes(session_id);

    Design principles:
    - NEVER modify existing entries
    - Only APPEND new entries
    - Delete only via explicit archival cleanup (age-based)
    """

    def __init__(self, storage_root: Path, vector_store_enabled: bool = True):
        """
        Args:
            storage_root: Root path for .memory/ directory
            vector_store_enabled: Whether to enable vector search (requires sqlite-vss)
        """
        self._root = storage_root / "L2_episodic"
        self._db_path = self._root / "timeline.db"
        self._vector_store_enabled = vector_store_enabled
        self._vss_available = False
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        self._root.mkdir(parents=True, exist_ok=True)

        # Check for sqlite-vss availability
        if self._vector_store_enabled:
            try:
                import sqlite_vss  # noqa: F401
                self._vss_available = True
                logger.info("sqlite-vss available, vector search enabled")
            except ImportError:
                logger.warning("sqlite-vss not available, vector search disabled")
                self._vss_available = False

        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                timestamp TEXT,
                role TEXT,
                content TEXT,
                summary TEXT,
                embedding_id TEXT,
                tool_calls TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON episodes(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON episodes(session_id)")
        conn.commit()
        conn.close()

        # Initialize vss if available
        if self._vss_available:
            self._init_vss()

    def _init_vss(self) -> None:
        """Initialize sqlite-vss extension."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("SELECT vss_init()")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vss_episodes (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    embedding BLOB
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_vss_id ON vss_episodes(id)")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to initialize vss: {e}")
            self._vss_available = False

    def append(self, entry: EpisodicEntry) -> EpisodicEntry:
        """
        Append a new episodic entry.

        This is the ONLY write operation allowed.
        """
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""
            INSERT INTO episodes (id, session_id, timestamp, role, content, summary, embedding_id, tool_calls)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.id,
            entry.session_id,
            entry.timestamp,
            entry.role,
            entry.content,
            entry.summary,
            entry.embedding_id,
            json.dumps(entry.tool_calls),
        ))
        conn.commit()
        conn.close()
        logger.debug(f"Appended episodic entry {entry.id}")
        return entry

    def search(
        self,
        query: str | None = None,
        session_id: str | None = None,
        time_range: tuple[str, str] | None = None,  # (start_iso, end_iso)
        role: str | None = None,
        limit: int = 20,
    ) -> list[EpisodicEntry]:
        """
        Search episodic memory.

        Args:
            query: Text query (uses content LIKE %query%)
            session_id: Filter by session
            time_range: (start_timestamp, end_timestamp)
            role: Filter by role ("user", "assistant")
            limit: Max results

        Returns:
            List of matching EpisodicEntry, ordered by relevance/time
        """
        conn = sqlite3.connect(str(self._db_path))
        conditions = []
        params = []

        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if time_range:
            conditions.append("timestamp >= ? AND timestamp <= ?")
            params.extend(time_range)
        if role:
            conditions.append("role = ?")
            params.append(role)

        sql = "SELECT * FROM episodes"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY timestamp DESC"

        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        results = [self._row_to_entry(row) for row in rows[:limit]]
        return results

    def get_session_history(self, session_id: str, limit: int = 100) -> list[EpisodicEntry]:
        """Get all entries for a specific session, oldest first."""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.execute("""
            SELECT * FROM episodes
            WHERE session_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (session_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: tuple) -> EpisodicEntry:
        """Convert a DB row to EpisodicEntry."""
        return EpisodicEntry(
            id=row[0],
            session_id=row[1],
            timestamp=row[2],
            role=row[3],
            content=row[4],
            summary=row[5] or "",
            embedding_id=row[6],
            tool_calls=json.loads(row[7]) if row[7] else [],
        )

    def count(self) -> int:
        """Get total entry count."""
        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM episodes")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def archive_old_entries(self, older_than_days: int = 90) -> int:
        """
        Delete entries older than N days.

        This is the only "deletion" operation, for maintenance only.
        """
        cutoff = datetime.now().timestamp() - (older_than_days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()

        conn = sqlite3.connect(str(self._db_path))
        cursor = conn.execute("DELETE FROM episodes WHERE timestamp < ?", (cutoff_iso,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Archived {deleted} episodic entries older than {older_than_days} days")
        return deleted

    @property
    def vss_available(self) -> bool:
        return self._vss_available
