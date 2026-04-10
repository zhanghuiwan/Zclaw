"""
L0: Perceptual Buffer

Ring buffer in memory - single round perception.
Captures the immediate current turn input/output before any processing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PerceptualEntry:
    """Single perceptual buffer entry"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    user_input: str = ""
    assistant_output: str = ""
    turn_index: int = 0


class PerceptualBuffer:
    """
    L0 Perceptual Buffer - ring buffer for single-round perception.

    Captures the current turn's raw input/output before any processing.
    One entry per turn, auto-evicts after N rounds (configurable).

    Design: Agent does NOT auto-retrieve from this. Tools query it if needed.
    """

    def __init__(self, max_turns: int = 1):
        """
        Args:
            max_turns: How many turns to keep (default 1 = single round)
        """
        self._max_turns = max_turns
        self._buffer: deque[PerceptualEntry] = deque(maxlen=max_turns)
        self._turn_counter = 0

    def capture(self, user_input: str, assistant_output: str = "") -> PerceptualEntry:
        """Capture a turn's perception."""
        self._turn_counter += 1
        entry = PerceptualEntry(
            turn_index=self._turn_counter,
            user_input=user_input,
            assistant_output=assistant_output,
        )
        self._buffer.append(entry)
        return entry

    def get_current(self) -> PerceptualEntry | None:
        """Get the most recent perceptual entry."""
        return self._buffer[-1] if self._buffer else None

    def get_all(self) -> list[PerceptualEntry]:
        """Get all entries in order (oldest first)."""
        return list(self._buffer)

    def clear(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()

    @property
    def turn_count(self) -> int:
        return self._turn_counter
