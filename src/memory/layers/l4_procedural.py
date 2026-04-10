"""
L4: Procedural Memory

YAML rules files.
Stores global and project-specific rules for agent behavior.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ProceduralMemory:
    """
    L4 Procedural Memory - YAML rules files.

    File locations:
    - .memory/L4_procedural/global_rules.yaml
    - .memory/L4_procedural/project_rules.yaml

    Design principles:
    - Rules are loaded at startup and injected into system prompt
    - Rules are NEVER auto-modified, only manually edited
    - Clear separation: global rules apply to all projects
    """

    def __init__(self, storage_root: Path):
        """
        Args:
            storage_root: Root path for .memory/ directory
        """
        self._root = storage_root / "L4_procedural"
        self._global_rules_path = self._root / "global_rules.yaml"
        self._project_rules_path = self._root / "project_rules.yaml"

        self._global_rules: dict[str, Any] = {}
        self._project_rules: dict[str, Any] = {}

        self._init_default_rules()
        self._load_rules()

    def _init_default_rules(self) -> None:
        """Create default rules files if they don't exist."""
        self._root.mkdir(parents=True, exist_ok=True)

        if not self._global_rules_path.exists():
            default_global = {
                "coding_rules": [
                    "Always read a file before editing it",
                    "Use meaningful variable and function names",
                    "Add comments for complex logic",
                ],
                "communication_rules": [
                    "Ask clarifying questions when requirements are unclear",
                    "Provide clear explanations of changes made",
                ],
                "safety_rules": [
                    "Verify destructive operations before executing",
                    "Keep backups before major changes",
                ],
            }
            self._global_rules_path.write_text(
                yaml.dump(default_global, allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )
            logger.info(f"Created default global rules at {self._global_rules_path}")

    def _load_rules(self) -> None:
        """Load rules from YAML files."""
        if self._global_rules_path.exists():
            try:
                self._global_rules = yaml.safe_load(
                    self._global_rules_path.read_text(encoding="utf-8")
                ) or {}
            except Exception as e:
                logger.error(f"Failed to load global rules: {e}")
                self._global_rules = {}

        if self._project_rules_path.exists():
            try:
                self._project_rules = yaml.safe_load(
                    self._project_rules_path.read_text(encoding="utf-8")
                ) or {}
            except Exception as e:
                logger.error(f"Failed to load project rules: {e}")
                self._project_rules = {}

    def get_global_rules(self) -> dict[str, Any]:
        """Get all global rules."""
        return dict(self._global_rules)

    def get_project_rules(self) -> dict[str, Any]:
        """Get all project rules."""
        return dict(self._project_rules)

    def get_rule(self, category: str, key: str, default: Any = None) -> Any:
        """Get a specific rule value."""
        if category in self._global_rules and key in self._global_rules[category]:
            return self._global_rules[category][key]
        if category in self._project_rules and key in self._project_rules[category]:
            return self._project_rules[category][key]
        return default

    def reload(self) -> None:
        """Reload rules from disk."""
        self._load_rules()

    def format_for_system_prompt(self) -> str:
        """
        Format L4 rules for injection into system prompt.

        Returns a rules section for the system prompt.
        """
        lines = ["## Behavior Rules"]

        # Global rules
        if self._global_rules:
            for category, rules in self._global_rules.items():
                if isinstance(rules, list):
                    lines.append(f"\n### {category.replace('_', ' ').title()}")
                    for rule in rules:
                        lines.append(f"- {rule}")
                elif isinstance(rules, dict):
                    lines.append(f"\n### {category.replace('_', ' ').title()}")
                    for key, value in rules.items():
                        lines.append(f"- {key}: {value}")

        # Project rules (merged, project overrides global)
        if self._project_rules:
            lines.append("\n### Project-Specific Rules")
            for category, rules in self._project_rules.items():
                if isinstance(rules, list):
                    lines.append(f"\n#### {category.replace('_', ' ').title()}")
                    for rule in rules:
                        lines.append(f"- {rule}")

        return "\n".join(lines)
