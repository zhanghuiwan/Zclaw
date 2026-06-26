"""Shared pytest fixtures for the public test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.settings import ProviderConfig, Settings
from src.skills.config import SkillsConfig


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    settings = Settings()
    settings.llm.providers = {
        "test": ProviderConfig(
            base_url="http://localhost:11434/v1",
            api_key="test",
            model="test-model",
            supports_tools=True,
        )
    }
    settings.llm.default_provider = "test"
    settings.memory.storage_path = str(tmp_path / "memory")
    settings.mcp.enabled = False
    settings.skills.enabled = False
    settings.security.audit_log = False
    return settings


@pytest.fixture
def isolated_skills_config(tmp_path: Path) -> SkillsConfig:
    global_path = tmp_path / "global-skills"
    project_path = tmp_path / "project-skills"
    global_path.mkdir()
    project_path.mkdir()
    return SkillsConfig(
        global_path=global_path,
        project_path=project_path,
        auto_load=True,
        match_threshold=1,
        inject_to_prompt=True,
    )
