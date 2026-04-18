"""
AGENTS.md 加载器

加载并解析 AGENTS.md 配置文件，定义 Agent 的操作规则和行为约束。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CronTask:
    """定时任务定义"""
    cron_expr: str           # Cron 表达式
    description: str          # 任务描述
    command: str = ""         # 执行的命令
    enabled: bool = True      # 是否启用


@dataclass
class HeartbeatConfig:
    """心跳配置"""
    interval_seconds: int = 300       # 间隔秒数
    tasks: list[str] = field(default_factory=list)  # 心跳时执行的检查任务


@dataclass
class ToolPermission:
    """工具权限配置"""
    auto_approve: list[str] = field(default_factory=list)   # 自动批准的工具
    confirm: list[str] = field(default_factory=list)       # 需要确认的工具
    deny: list[str] = field(default_factory=list)          # 禁止的工具


@dataclass
class AgentBehaviorConfig:
    """Agent 行为配置"""
    startup_behavior: list[str] = field(default_factory=list)   # 启动行为
    tool_permissions: ToolPermission = field(default_factory=ToolPermission)
    cron_tasks: list[CronTask] = field(default_factory=list)   # 定时任务
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    raw_content: str = ""                                       # 原始内容


class AgentsConfigLoader:
    """
    AGENTS.md 加载器

    解析 AGENTS.md 文件，提取 Agent 的行为规则、工具权限和调度配置。
    """

    SECTION_PATTERN = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    SUBSECTION_PATTERN = re.compile(r"^###\s+(.+)$", re.MULTILINE)
    LIST_ITEM_PATTERN = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)
    NUMBERED_LIST_PATTERN = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)
    CRON_TASK_PATTERN = re.compile(r'^[\-\*]?\s*["\'"]?([^"\']+?)["\'"]?\s*:\s*(.+)$', re.MULTILINE)
    KEY_VALUE_PATTERN = re.compile(r"^[\-\*]?\s*(?:interval|间隔)[\s:：]+(\d+)", re.IGNORECASE)

    def load(self, path: str | Path) -> AgentBehaviorConfig:
        """
        加载 AGENTS.md 文件。

        Args:
            path: AGENTS.md 文件路径

        Returns:
            AgentBehaviorConfig: 解析后的行为配置
        """
        path = Path(path)
        if not path.exists():
            logger.warning(f"AGENTS.md 不存在: {path}，使用默认配置")
            return AgentBehaviorConfig()

        content = path.read_text(encoding="utf-8")
        return self.parse(content, str(path))

    def parse(self, content: str, source: str = "unknown") -> AgentBehaviorConfig:
        """
        解析 AGENTS.md 内容。

        Args:
            content: AGENTS.md 文本内容
            source: 来源路径

        Returns:
            AgentBehaviorConfig: 解析后的行为配置对象
        """
        config = AgentBehaviorConfig(raw_content=content)

        sections = self._split_sections(content)

        for section_title, section_content in sections.items():
            title_lower = section_title.lower().strip()

            if "启动" in title_lower or "startup" in title_lower:
                config.startup_behavior = self._extract_list_items(section_content)

            elif "工具" in title_lower or "tool" in title_lower:
                self._parse_tool_permissions(config, section_content)

            elif "cron" in title_lower or "定时" in title_lower:
                config.cron_tasks = self._parse_cron_tasks(section_content)

            elif "heartbeat" in title_lower or "心跳" in title_lower:
                config.heartbeat = self._parse_heartbeat_config(section_content)

        logger.info(f"AGENTS 配置加载完成: {len(config.cron_tasks)} 个定时任务")
        return config

    def _split_sections(self, content: str) -> dict[str, str]:
        """按二级标题分割内容"""
        sections = {}
        current_title = "header"
        current_content = []

        lines = content.split("\n")
        for line in lines:
            section_match = self.SECTION_PATTERN.match(line)
            if section_match:
                if current_content:
                    sections[current_title] = "\n".join(current_content)
                current_title = section_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections[current_title] = "\n".join(current_content)

        return sections

    def _extract_list_items(self, content: str) -> list[str]:
        """提取列表项"""
        items = []
        # 匹配无序列表（- 或 *）
        for match in self.LIST_ITEM_PATTERN.finditer(content):
            items.append(match.group(1).strip())
        # 匹配有序列表（1. 2. 3.）
        for match in self.NUMBERED_LIST_PATTERN.finditer(content):
            items.append(match.group(1).strip())
        return items

    def _split_subsections(self, content: str) -> dict[str, str]:
        """按三级标题分割内容"""
        subsections = {}
        current_title = "header"
        current_content = []

        lines = content.split("\n")
        for line in lines:
            subsection_match = self.SUBSECTION_PATTERN.match(line)
            if subsection_match:
                if current_content:
                    subsections[current_title] = "\n".join(current_content)
                current_title = subsection_match.group(1)
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            subsections[current_title] = "\n".join(current_content)

        return subsections

    def _parse_tool_permissions(self, config: AgentBehaviorConfig, content: str) -> None:
        """解析工具权限部分"""
        # 先按三级标题分割
        subsections = self._split_subsections(content)

        permissions = ToolPermission()

        for subsection_title, subsection_content in subsections.items():
            title_lower = subsection_title.lower().strip()
            items = self._extract_list_items(subsection_content)

            if "auto" in title_lower or "自动" in title_lower:
                permissions.auto_approve = items
            elif "confirm" in title_lower or "确认" in title_lower:
                permissions.confirm = items
            elif "deny" in title_lower or "禁止" in title_lower:
                permissions.deny = items

        config.tool_permissions = permissions

    def _parse_cron_tasks(self, content: str) -> list[CronTask]:
        """解析 Cron 任务"""
        tasks = []

        # 匹配格式: - "0 9 * * 1-5": 每天9点检查邮件
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 尝试匹配带引号的 cron 表达式
            match = re.match(r'^[\-\*]?\s*["\']([^"\']+)["\']\s*[:\s]+\[?(.+?)\]?$', line)
            if match:
                cron_expr = match.group(1)
                description = match.group(2).strip()
                tasks.append(CronTask(cron_expr=cron_expr, description=description))
                continue

            # 尝试匹配无引号的 cron 表达式
            match = re.match(r'^[\-\*]?\s*([\d\*\/\-\,]+(?:\s+[\d\*\/\-\,]+){4,5})\s*[:\s]+(.+)$', line)
            if match:
                cron_expr = match.group(1)
                description = match.group(2).strip()
                tasks.append(CronTask(cron_expr=cron_expr, description=description))

        return tasks

    def _parse_heartbeat_config(self, content: str) -> HeartbeatConfig:
        """解析心跳配置"""
        config = HeartbeatConfig()

        # 提取间隔
        interval_match = self.KEY_VALUE_PATTERN.search(content)
        if interval_match:
            config.interval_seconds = int(interval_match.group(1))

        # 提取任务
        config.tasks = self._extract_list_items(content)

        return config

    def to_agents_md(self, config: AgentBehaviorConfig) -> str:
        """
        将 AgentBehaviorConfig 转换为 AGENTS.md 格式字符串。

        Args:
            config: AgentBehaviorConfig 对象

        Returns:
            str: AGENTS.md 格式的字符串
        """
        lines = ["# AGENTS.md\n"]

        if config.startup_behavior:
            lines.append("## 启动行为")
            for behavior in config.startup_behavior:
                lines.append(f"- {behavior}")
            lines.append("")

        if config.tool_permissions.auto_approve or config.tool_permissions.confirm:
            lines.append("## 工具权限")
            if config.tool_permissions.auto_approve:
                lines.append("### 自动批准")
                for tool in config.tool_permissions.auto_approve:
                    lines.append(f"- {tool}")
            if config.tool_permissions.confirm:
                lines.append("### 需要确认")
                for tool in config.tool_permissions.confirm:
                    lines.append(f"- {tool}")
            lines.append("")

        if config.cron_tasks:
            lines.append("## Cron 任务")
            for task in config.cron_tasks:
                lines.append(f'- "{task.cron_expr}": {task.description}')
            lines.append("")

        if config.heartbeat.interval_seconds:
            lines.append(f"## Heartbeat 配置\n- 间隔：{config.heartbeat.interval_seconds} 秒")
            if config.heartbeat.tasks:
                for task in config.heartbeat.tasks:
                    lines.append(f"- {task}")

        return "\n".join(lines)
