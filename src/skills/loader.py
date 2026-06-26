"""
Skill 加载器

从文件系统发现和加载 SKILL.md 文件。
"""

from __future__ import annotations

import logging
from pathlib import Path

from .models import SkillDefinition

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    Skill 加载器

    职责:
    1. 管理 skill 搜索路径
    2. 发现所有可用的 skill 目录
    3. 从 SKILL.md 加载 skill 定义
    """

    def __init__(self):
        self._search_paths: list[Path] = []

    def add_search_path(self, path: Path, exist_ok: bool = True) -> None:
        """
        添加搜索路径

        Args:
            path: 要添加的路径
            exist_ok: 如果路径不存在，是否不报错（仅记录日志）
        """
        resolved = path.resolve()
        if not resolved.exists():
            if exist_ok:
                logger.debug(f"搜索路径不存在（已跳过）: {resolved}")
            else:
                raise FileNotFoundError(f"搜索路径不存在：{resolved}")
            return

        if resolved not in self._search_paths:
            self._search_paths.append(resolved)
            logger.debug(f"添加搜索路径：{resolved}")

    def remove_search_path(self, path: Path) -> bool:
        """移除搜索路径"""
        resolved = path.resolve()
        if resolved in self._search_paths:
            self._search_paths.remove(resolved)
            logger.debug(f"移除搜索路径：{resolved}")
            return True
        return False

    def clear_search_paths(self) -> None:
        """清空所有搜索路径"""
        self._search_paths.clear()

    def get_search_paths(self) -> list[Path]:
        """获取所有搜索路径"""
        return self._search_paths.copy()

    def discover_skills(self) -> list[Path]:
        """
        发现所有 skill 目录

        在每个搜索路径下查找包含 SKILL.md 的目录。

        Returns:
            skill 目录路径列表
        """
        skill_dirs = []
        seen_resolved: set[Path] = set()

        for search_path in self._search_paths:
            if not search_path.exists():
                continue

            # 直接检查路径本身是否是 skill 目录
            if (search_path / "SKILL.md").exists():
                resolved = search_path.resolve()
                # 去重：跳过相同真实路径的 skill
                if resolved not in seen_resolved:
                    skill_dirs.append(search_path)
                    seen_resolved.add(resolved)
                continue

            # 扫描子目录
            try:
                for item in search_path.iterdir():
                    if item.is_dir() and (item / "SKILL.md").exists():
                        resolved = item.resolve()
                        if resolved not in seen_resolved:
                            skill_dirs.append(item)
                            seen_resolved.add(resolved)
                            logger.debug(f"发现 skill 目录：{item}")
            except PermissionError as e:
                logger.warning(f"无权限访问目录 {search_path}: {e}")

        logger.info(f"发现 {len(skill_dirs)} 个 skill 目录")
        return skill_dirs

    def load_skill(self, skill_dir: Path) -> SkillDefinition:
        """
        从目录加载单个 skill

        Args:
            skill_dir: skill 目录路径

        Returns:
            SkillDefinition 实例

        Raises:
            FileNotFoundError: 如果 SKILL.md 不存在
            ValueError: 如果 SKILL.md 格式无效
        """
        resolved = skill_dir.resolve()

        if not resolved.exists():
            raise FileNotFoundError(f"Skill 目录不存在：{resolved}")

        logger.debug(f"加载 skill: {resolved}")
        return SkillDefinition.from_file(resolved)

    def load_all_skills(self) -> list[SkillDefinition]:
        """
        加载所有发现的 skills

        Returns:
            SkillDefinition 列表
        """
        skills = []
        skill_dirs = self.discover_skills()

        for skill_dir in skill_dirs:
            try:
                skill = self.load_skill(skill_dir)
                skills.append(skill)
                logger.info(f"成功加载 skill: {skill.name}")
            except Exception as e:
                logger.error(f"加载 skill 失败 {skill_dir}: {e}")

        logger.info(f"成功加载 {len(skills)} 个 skills")
        return skills

    def reload_skill(self, skill_dir: Path) -> SkillDefinition | None:
        """
        重新加载指定 skill

        用于支持热更新。

        Args:
            skill_dir: skill 目录路径

        Returns:
            重新加载后的 SkillDefinition，失败返回 None
        """
        try:
            skill = self.load_skill(skill_dir)
            logger.info(f"重新加载 skill: {skill.name}")
            return skill
        except Exception as e:
            logger.error(f"重新加载 skill 失败 {skill_dir}: {e}")
            return None

    @staticmethod
    def get_default_global_path() -> Path:
        """获取全局 skill 目录的默认路径 (~/.agents/skills)"""
        return Path.home() / ".agents" / "skills"

    @staticmethod
    def get_default_project_path(project_root: Path) -> Path:
        """获取项目级 skill 目录的默认路径 (project_root/.agents/skills)"""
        return project_root / ".agents" / "skills"
