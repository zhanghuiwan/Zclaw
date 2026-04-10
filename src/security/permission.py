"""
权限控制中心

管理工具调用的权限判定，支持：
- 按工具危险等级自动判定
- 自动批准规则（白名单）
- 用户交互式确认（通过回调函数）
- 路径限制检查
- 危险命令拦截
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Awaitable

from src.config.settings import SecurityConfig

logger = logging.getLogger(__name__)


class PermissionDecision(str, Enum):
    """权限判定结果"""
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


class DangerLevel(str, Enum):
    """危险等级"""
    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"


@dataclass
class PermissionRequest:
    """权限请求"""
    tool_name: str
    arguments: dict[str, Any]
    danger_level: str
    session_id: str = ""


@dataclass
class PermissionResponse:
    """权限响应"""
    decision: PermissionDecision
    reason: str = ""
    auto: bool = False

    @property
    def allowed(self) -> bool:
        return self.decision == PermissionDecision.ALLOW


ConfirmCallback = Callable[[PermissionRequest], Awaitable[bool]]


class PermissionManager:
    """
    权限管理器。

    判定流程：
    1. 检查是否在 auto_approve 列表中 → ALLOW
    2. 检查是否匹配 blocked_patterns → DENY
    3. 检查路径限制（对文件类工具） → DENY
    4. 按危险等级判定：
       - safe → ALLOW
       - confirm → CONFIRM（调用用户回调或自动批准）
       - dangerous → CONFIRM（调用用户回调，始终需确认）
    """

    def __init__(
        self,
        config: SecurityConfig,
        confirm_callback: ConfirmCallback | None = None,
        auto_confirm: bool = False,
    ):
        self._config = config
        self._confirm_callback = confirm_callback
        self._auto_confirm = auto_confirm

        self._blocked_regexes: list[re.Pattern] = []
        for pattern in config.blocked_patterns:
            try:
                self._blocked_regexes.append(re.compile(pattern))
            except re.error:
                logger.warning(f"无效的拦截模式 regex: {pattern}")

        self._allowed_paths: list[Path] = []
        self._denied_paths: list[Path] = []
        for p in config.path_restrictions.get("allow", []):
            self._allowed_paths.append(Path(p).expanduser().resolve())
        for p in config.path_restrictions.get("deny", []):
            self._denied_paths.append(Path(p).expanduser().resolve())

        self._stats = {
            "total_checks": 0,
            "auto_allowed": 0,
            "auto_denied": 0,
            "user_confirmed": 0,
            "user_denied": 0,
        }

    def set_confirm_callback(self, callback: ConfirmCallback) -> None:
        self._confirm_callback = callback

    def set_auto_confirm(self, auto: bool) -> None:
        self._auto_confirm = auto

    async def check(self, request: PermissionRequest) -> PermissionResponse:
        self._stats["total_checks"] += 1

        # 1. 自动批准列表
        if request.tool_name in self._config.auto_approve:
            self._stats["auto_allowed"] += 1
            return PermissionResponse(
                decision=PermissionDecision.ALLOW,
                reason=f"工具 '{request.tool_name}' 在自动批准列表中",
                auto=True,
            )

        # 2. 危险模式拦截
        if self._is_blocked(request):
            self._stats["auto_denied"] += 1
            return PermissionResponse(
                decision=PermissionDecision.DENY,
                reason=f"工具调用匹配到拦截模式",
                auto=True,
            )

        # 3. 路径限制检查
        if self._is_file_tool(request.tool_name):
            path_check = self._check_path(request)
            if path_check:
                self._stats["auto_denied"] += 1
                return PermissionResponse(
                    decision=PermissionDecision.DENY,
                    reason=path_check,
                    auto=True,
                )

        # 4. 按危险等级判定
        if request.danger_level == "safe":
            self._stats["auto_allowed"] += 1
            return PermissionResponse(
                decision=PermissionDecision.ALLOW,
                reason="工具安全",
                auto=True,
            )

        if self._auto_confirm:
            self._stats["auto_allowed"] += 1
            return PermissionResponse(
                decision=PermissionDecision.ALLOW,
                reason=f"自动批准（{request.danger_level} 级别，auto_confirm=True）",
                auto=True,
            )

        if self._confirm_callback is not None:
            try:
                approved = await self._confirm_callback(request)
                if approved:
                    self._stats["user_confirmed"] += 1
                    return PermissionResponse(
                        decision=PermissionDecision.ALLOW,
                        reason=f"用户已批准（{request.danger_level} 级别）",
                        auto=False,
                    )
                else:
                    self._stats["user_denied"] += 1
                    return PermissionResponse(
                        decision=PermissionDecision.DENY,
                        reason="用户已拒绝",
                        auto=False,
                    )
            except Exception as e:
                logger.error(f"确认回调错误: {e}")
                self._stats["auto_denied"] += 1
                return PermissionResponse(
                    decision=PermissionDecision.DENY,
                    reason=f"确认回调失败: {e}",
                    auto=True,
                )

        self._stats["auto_denied"] += 1
        return PermissionResponse(
            decision=PermissionDecision.DENY,
            reason=f"未设置确认回调，拒绝 {request.danger_level} 级别的工具调用",
            auto=True,
        )

    def _is_blocked(self, request: PermissionRequest) -> bool:
        if request.tool_name == "shell":
            command = request.arguments.get("command", "")
            for regex in self._blocked_regexes:
                if regex.search(command):
                    logger.warning(f"检测到被拦截的命令: {command[:50]}")
                    return True
        return False

    def _is_file_tool(self, tool_name: str) -> bool:
        return tool_name in ("file_read", "file_write", "file_edit")

    def _check_path(self, request: PermissionRequest) -> str | None:
        path_str = request.arguments.get("path", "")
        if not path_str:
            return None
        try:
            resolved = Path(path_str).expanduser().resolve()
        except (OSError, ValueError):
            return f"无效的路径: {path_str}"
        for denied in self._denied_paths:
            try:
                resolved.relative_to(denied)
                return f"路径 '{resolved}' 位于受限区域 '{denied}'"
            except ValueError:
                pass
            if str(resolved).startswith(str(denied)):
                return f"路径 '{resolved}' 位于受限区域 '{denied}'"
        if self._allowed_paths:
            in_allowed = False
            for allowed in self._allowed_paths:
                try:
                    resolved.relative_to(allowed)
                    in_allowed = True
                    break
                except ValueError:
                    pass
                if str(resolved).startswith(str(allowed)):
                    in_allowed = True
                    break
            if not in_allowed:
                return f"路径 '{resolved}' 不在允许的区域内"
        return None

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def __repr__(self) -> str:
        return (
            f"PermissionManager("
            f"auto_confirm={self._auto_confirm}, "
            f"has_callback={self._confirm_callback is not None})"
        )
