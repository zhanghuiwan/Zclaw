"""
L3: Semantic & State Memory

JSON files, current state only (no history).
Stores identity, preferences, project state - current values only.
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
class UserProfile:
    """User profile - current state only"""
    name: str = ""
    preferred_language: str = "en"
    preferred_code_style: str = ""
    timezone: str = "UTC"
    preferences: dict[str, Any] = field(default_factory=dict)  # Arbitrary key-value preferences
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "preferred_language": self.preferred_language,
            "preferred_code_style": self.preferred_code_style,
            "timezone": self.timezone,
            "preferences": self.preferences,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProjectProfile:
    """Project profile - current state only"""
    name: str = ""
    root_path: str = ""
    tech_stack: list[str] = field(default_factory=list)  # e.g., ["python", "fastapi", "react"]
    architecture: str = ""  # e.g., "microservices", "monolith"
    conventions: dict[str, str] = field(default_factory=dict)  # convention rules
    important_files: list[str] = field(default_factory=list)  # Key files agent should know about
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "root_path": self.root_path,
            "tech_stack": self.tech_stack,
            "architecture": self.architecture,
            "conventions": self.conventions,
            "important_files": self.important_files,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SemanticMemory:
    """
    L3 Semantic & State Memory - JSON files, current state only.

    File locations:
    - .memory/L3_semantic/user_profile.json
    - .memory/L3_semantic/project_profile.json

    Design principles:
    - Current-state ONLY - no history tracking
    - Force-injected into system prompt (always available)
    - Written by explicit tools, not auto-extracted
    """

    def __init__(self, storage_root: Path):
        """
        Args:
            storage_root: Root path for .memory/ directory
        """
        self._root = storage_root / "L3_semantic"
        self._root.mkdir(parents=True, exist_ok=True)

        self._user_profile_path = self._root / "user_profile.json"
        self._project_profile_path = self._root / "project_profile.json"

        self._user_profile: UserProfile = self._load_user_profile()
        self._project_profile: ProjectProfile = self._load_project_profile()

    def _load_user_profile(self) -> UserProfile:
        if self._user_profile_path.exists():
            try:
                data = json.loads(self._user_profile_path.read_text(encoding="utf-8"))
                return UserProfile.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load user profile: {e}")
        return UserProfile()

    def _load_project_profile(self) -> ProjectProfile:
        if self._project_profile_path.exists():
            try:
                data = json.loads(self._project_profile_path.read_text(encoding="utf-8"))
                return ProjectProfile.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load project profile: {e}")
        return ProjectProfile()

    def get_user_profile(self) -> UserProfile:
        """Get current user profile."""
        return self._user_profile

    def update_user_profile(self, **updates) -> UserProfile:
        """Update user profile fields (direct overwrite, no history)."""
        for key, value in updates.items():
            if hasattr(self._user_profile, key):
                setattr(self._user_profile, key, value)
        self._user_profile.updated_at = datetime.now().isoformat()
        self._save_user_profile()
        logger.debug(f"Updated user profile: {list(updates.keys())}")
        return self._user_profile

    def set_preference(self, key: str, value: Any) -> None:
        """Set a specific preference (direct overwrite)."""
        self._user_profile.preferences[key] = value
        self._user_profile.updated_at = datetime.now().isoformat()
        self._save_user_profile()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a specific preference."""
        return self._user_profile.preferences.get(key, default)

    def _save_user_profile(self) -> None:
        self._user_profile_path.write_text(
            json.dumps(self._user_profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_project_profile(self) -> ProjectProfile:
        """Get current project profile."""
        return self._project_profile

    def update_project_profile(self, **updates) -> ProjectProfile:
        """Update project profile fields (direct overwrite, no history)."""
        for key, value in updates.items():
            if hasattr(self._project_profile, key):
                setattr(self._project_profile, key, value)
        self._project_profile.updated_at = datetime.now().isoformat()
        self._save_project_profile()
        logger.debug(f"Updated project profile: {list(updates.keys())}")
        return self._project_profile

    def add_convention(self, key: str, value: str) -> None:
        """Add a project convention."""
        self._project_profile.conventions[key] = value
        self._project_profile.updated_at = datetime.now().isoformat()
        self._save_project_profile()

    def _save_project_profile(self) -> None:
        self._project_profile_path.write_text(
            json.dumps(self._project_profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def format_for_system_prompt(self) -> str:
        """
        Format L3 state for injection into system prompt.

        Returns a concise summary of current user/project state.
        """
        lines = []

        if self._user_profile.name:
            lines.append(f"- User: {self._user_profile.name}")
        if self._user_profile.preferred_language:
            lines.append(f"- Language: {self._user_profile.preferred_language}")
        if self._user_profile.preferred_code_style:
            lines.append(f"- Code style: {self._user_profile.preferred_code_style}")

        if self._project_profile.name:
            lines.append(f"- Project: {self._project_profile.name}")
        if self._project_profile.tech_stack:
            lines.append(f"- Tech stack: {', '.join(self._project_profile.tech_stack)}")
        if self._project_profile.architecture:
            lines.append(f"- Architecture: {self._project_profile.architecture}")

        # Include active preferences as bullet points
        if self._user_profile.preferences:
            pref_lines = [f"- {k}: {v}" for k, v in self._user_profile.preferences.items() if v]
            lines.extend(pref_lines)

        if lines:
            return "## Current State\n" + "\n".join(lines)
        return ""

    def clear(self) -> None:
        """Clear all semantic memory (for testing/reset)."""
        self._user_profile = UserProfile()
        self._project_profile = ProjectProfile()
        if self._user_profile_path.exists():
            self._user_profile_path.unlink()
        if self._project_profile_path.exists():
            self._project_profile_path.unlink()
