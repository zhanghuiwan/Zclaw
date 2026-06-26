"""Tests for deterministic skill discovery, matching, and tool wrapping."""

from __future__ import annotations

from pathlib import Path

from src.skills import SkillManager
from src.skills.config import SkillsConfig
from src.skills.models import SkillDefinition
from src.skills.tool import SkillTool


def _write_skill(root: Path, name: str, description: str, triggers: list[str]) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    triggers_yaml = "\n".join(f"      - {trigger}" for trigger in triggers)
    (skill_dir / "SKILL.md").write_text(
        f"""---
name: {name}
description: {description}
version: 0.6.1
metadata:
  openclaw:
    triggers:
{triggers_yaml}
---

# {name}

Use this skill when the request mentions {', '.join(triggers)}.
""",
        encoding="utf-8",
    )
    return skill_dir


def test_skill_definition_parses_frontmatter(tmp_path: Path):
    skill_dir = _write_skill(tmp_path, "python-helper", "Python project helper", ["python", "pytest"])

    skill = SkillDefinition.from_file(skill_dir)

    assert skill.name == "python-helper"
    assert skill.description == "Python project helper"
    assert skill.version == "0.6.1"
    assert skill.triggers == ["python", "pytest"]
    assert "Use this skill" in skill.content


def test_skill_manager_discovers_and_matches(isolated_skills_config: SkillsConfig):
    _write_skill(
        isolated_skills_config.project_path,
        "python-helper",
        "Python project helper",
        ["python", "pytest"],
    )

    manager = SkillManager(isolated_skills_config)
    assert manager.initialize() == 1

    skills = manager.list_skills()
    assert [skill.name for skill in skills] == ["python-helper"]

    matches = manager.match_skills("请帮我运行 pytest")
    assert [skill.name for skill in matches] == ["python-helper"]

    context = manager.get_context("python 测试")
    assert "python-helper" in context
    assert "Python project helper" in context


def test_skill_manager_disabled_returns_no_context(isolated_skills_config: SkillsConfig):
    isolated_skills_config.enabled = False

    manager = SkillManager(isolated_skills_config)
    assert manager.initialize() == 0
    assert manager.match_skills("python") == []
    assert manager.get_context("python") == ""


def test_skill_tool_exposes_definition(tmp_path: Path):
    skill = SkillDefinition.from_file(
        _write_skill(tmp_path, "docs-helper", "Documentation helper", ["docs"])
    )
    tool = SkillTool(skill)

    assert tool.name == "skill__docs-helper"
    assert "Documentation helper" in tool.description
    assert tool.danger_level.value == "safe"
