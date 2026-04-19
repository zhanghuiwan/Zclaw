"""
Agent Loop - 核心执行循环

P2: 集成权限系统，支持 confirm/dangerous 工具调用的用户确认。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from src.config.settings import AgentConfig
from src.core.state import AgentState, AgentStateMachine
from src.llm.models import (
    LLMError,
    Message,
    MessageRole,
    Response,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolCallResult,
    ToolDefinition,
    Usage,
)
from src.llm.router import LLMRouter
from src.security.permission import PermissionManager, PermissionRequest
from src.security.audit import AuditLogger
from src.tools.base import ToolResult
from src.tools.cache import ToolResultCache
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentLoop:
    """
    Agent 核心循环。

    P2 新增：
    - 权限检查集成（confirm/dangerous 工具需用户确认）
    - 审计日志记录

    P3 新增：
    - 工具结果缓存（safe 工具自动缓存）
    - safe 工具并行执行
    """

    def __init__(
        self,
        llm: LLMRouter,
        agent_config: AgentConfig,
        system_prompt: str = "",
        tool_registry: ToolRegistry | None = None,
        permission_manager: PermissionManager | None = None,
        audit_logger: AuditLogger | None = None,
        context_manager=None,
        memory_manager=None,
        prompt_builder=None,
    ):
        self._llm = llm
        self._config = agent_config
        self._system_prompt = system_prompt
        self._tools = tool_registry
        self._permissions = permission_manager
        self._audit = audit_logger
        self._context = context_manager
        self._memory_manager = memory_manager
        self._prompt_builder = prompt_builder
        self._cache = ToolResultCache()
        self._state = AgentStateMachine()
        self._messages: list[Message] = []
        self._total_usage = Usage()
        self._round = 0
        self._tool_call_count = 0
        self._current_user_input: str = ""

        if system_prompt:
            self._messages.append(
                Message(role=MessageRole.SYSTEM, content=system_prompt)
            )

    @property
    def state(self) -> AgentState:
        return self._state.state

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    @property
    def usage(self) -> Usage:
        return self._total_usage

    @property
    def round(self) -> int:
        return self._round

    @property
    def tool_call_count(self) -> int:
        return self._tool_call_count

    @property
    def tool_registry(self) -> ToolRegistry | None:
        return self._tools

    @property
    def permission_manager(self) -> PermissionManager | None:
        return self._permissions

    def set_system_prompt(self, prompt: str) -> None:
        if self._messages and self._messages[0].role == MessageRole.SYSTEM:
            self._messages[0].content = prompt
        else:
            self._messages.insert(0, Message(role=MessageRole.SYSTEM, content=prompt))

    def add_message(self, message: Message) -> None:
        self._messages.append(message)

    def clear_history(self) -> None:
        system = None
        if self._messages and self._messages[0].role == MessageRole.SYSTEM:
            system = self._messages[0]
        self._messages = [system] if system else []
        self._round = 0
        self._total_usage = Usage()
        self._tool_call_count = 0

    def _get_tool_definitions(self) -> list[ToolDefinition]:
        if not self._tools:
            return []
        openai_tools = self._tools.to_openai_tools()
        definitions = []
        for t in openai_tools:
            func = t["function"]
            definitions.append(ToolDefinition(
                name=func["name"],
                description=func["description"],
                parameters=func["parameters"],
            ))
        return definitions

    async def _check_permission(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> tuple[bool, str]:
        if not self._permissions:
            return True, "未配置权限管理器"
        danger_level = "safe"
        if self._tools and self._tools.has(tool_name):
            danger_level = self._tools.get(tool_name).danger_level.value
        request = PermissionRequest(
            tool_name=tool_name,
            arguments=arguments,
            danger_level=danger_level,
        )
        response = await self._permissions.check(request)
        return response.allowed, response.reason

    async def _execute_single_tool(self, tc: ToolCall) -> ToolCallResult:
        """执行单个工具调用（含权限检查、缓存、审计）。"""
        try:
            args = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
        except json.JSONDecodeError as e:
            return ToolCallResult(
                tool_call_id=tc.id, name=tc.name,
                success=False, content=f"无效的 JSON 参数: {e}",
                error=f"JSON 解析错误: {e}",
            )

        import time
        start_ms = time.monotonic()
        allowed, reason = await self._check_permission(tc.name, args)
        duration_ms = int((time.monotonic() - start_ms) * 1000)

        if not allowed:
            logger.info(f"Tool call '{tc.name}' denied: {reason}")
            return ToolCallResult(
                tool_call_id=tc.id, name=tc.name,
                success=False, content=f"权限被拒绝: {reason}",
                error=f"权限被拒绝: {reason}",
            )

        # P3: 缓存检查（只对 safe 工具）
        is_safe = False
        if self._tools and self._tools.has(tc.name):
            is_safe = self._tools.get(tc.name).danger_level.value == "safe"

        if is_safe:
            cached = self._cache.get(tc.name, args)
            if cached is not None:
                logger.debug(f"Cache hit for {tc.name}")
                return ToolCallResult(
                    tool_call_id=tc.id, name=tc.name,
                    success=cached.success,
                    content=cached.to_llm_content(),
                    error=cached.error,
                )

        tool_result = await self._tools.execute(tc.name, args)
        self._tool_call_count += 1

        # P3: 写入缓存
        if is_safe and tool_result.success:
            self._cache.put(tc.name, args, tool_result)

        danger_level = "safe" if is_safe else "confirm"
        self._log_audit(
            tc.name, args, danger_level, "allow", True,
            tool_result.success,
            duration_ms=tool_result.metadata.get("duration_ms", 0),
            error=tool_result.error,
        )

        return ToolCallResult(
            tool_call_id=tc.id, name=tc.name,
            success=tool_result.success,
            content=tool_result.to_llm_content(),
            error=tool_result.error,
        )

    async def _execute_tool_calls(
        self, tool_calls: list[ToolCall]
    ) -> list[ToolCallResult]:
        """执行一组工具调用（P3: safe 工具并行执行）。"""
        if not self._tools:
            raise RuntimeError("未配置工具注册表")

        if len(tool_calls) <= 1:
            results = [await self._execute_single_tool(tool_calls[0])] if tool_calls else []
            return results

        # P3: 分离 safe 和非 safe 工具
        safe_calls = []
        sequential_calls = []
        for tc in tool_calls:
            is_safe = False
            if self._tools and self._tools.has(tc.name):
                is_safe = self._tools.get(tc.name).danger_level.value == "safe"
            if is_safe:
                safe_calls.append(tc)
            else:
                sequential_calls.append(tc)

        results_map: dict[str, ToolCallResult] = {}

        # 并行执行 safe 工具
        if safe_calls:
            import asyncio
            tasks = [self._execute_single_tool(tc) for tc in safe_calls]
            safe_results = await asyncio.gather(*tasks, return_exceptions=True)
            for tc, result in zip(safe_calls, safe_results):
                if isinstance(result, Exception):
                    results_map[tc.id] = ToolCallResult(
                        tool_call_id=tc.id, name=tc.name,
                        success=False, content=str(result), error=str(result),
                    )
                else:
                    results_map[tc.id] = result

        # 串行执行非 safe 工具
        for tc in sequential_calls:
            results_map[tc.id] = await self._execute_single_tool(tc)

        # 按原始顺序排列结果
        return [results_map[tc.id] for tc in tool_calls if tc.id in results_map]

    def _log_audit(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        danger_level: str,
        decision: str,
        auto: bool,
        success: bool | None,
        duration_ms: int = 0,
        error: str | None = None,
    ) -> None:
        if self._audit:
            self._audit.log(
                tool_name=tool_name,
                arguments=arguments,
                danger_level=danger_level,
                permission_decision=decision,
                permission_auto=auto,
                execution_success=success,
                execution_error=error,
                duration_ms=duration_ms,
                user_message_context=self._current_user_input,
            )

    def _inject_tool_results(self, results: list[ToolCallResult]) -> None:
        for result in results:
            msg = Message(
                role=MessageRole.TOOL,
                content=result.content if result.success else f"Error: {result.error}\n{result.content}",
                tool_call_id=result.tool_call_id,
                name=result.name,
            )
            self._messages.append(msg)

    async def run(self, user_input: str) -> Response:
        self._state.transition(AgentState.EXECUTING)
        self._round += 1
        self._current_user_input = user_input
        user_msg = Message(role=MessageRole.USER, content=user_input)
        self._messages.append(user_msg)
        max_inner_rounds = self._config.max_loop_rounds
        inner_round = 0
        try:
            while inner_round < max_inner_rounds:
                inner_round += 1
                # P5: 按需自动压缩上下文
                if self._context:
                    self._messages = self._context.prepare_messages(self._messages)
                response = await self._llm.chat(
                    messages=self._messages,
                    tools=self._get_tool_definitions() if self._tools else None,
                )
                self._total_usage += response.usage
                assistant_msg = Message(
                    role=MessageRole.ASSISTANT,
                    content=response.content,
                    tool_calls=response.tool_calls if response.tool_calls else None,
                )
                self._messages.append(assistant_msg)
                if not response.tool_calls:
                    self._state.transition(AgentState.DONE)
                    return response
                results = await self._execute_tool_calls(response.tool_calls)
                self._inject_tool_results(results)
            self._state.transition(AgentState.DONE)
            return Response(
                content=f"[已达到最大循环轮次 ({max_inner_rounds})。"
                        f"请简化你的请求。]",
                finish_reason="max_rounds",
            )
        except LLMError as e:
            self._state.transition(AgentState.ERROR)
            logger.error(f"Round {self._round} failed: {e}")
            raise

    async def run_stream(self, user_input: str) -> AsyncIterator[StreamEvent]:
        self._state.transition(AgentState.EXECUTING)
        self._round += 1
        self._current_user_input = user_input
        user_msg = Message(role=MessageRole.USER, content=user_input)
        self._messages.append(user_msg)
        max_inner_rounds = self._config.max_loop_rounds
        try:
            for inner_round in range(1, max_inner_rounds + 1):
                if inner_round > 1:
                    yield StreamEvent(
                        type=StreamEventType.LOOP_START,
                        data={"round": inner_round},
                    )
                content_buffer = ""
                tool_calls_buffer: dict[int, dict] = {}
                current_usage = Usage()
                # P5: 自动压缩上下文
                if self._context:
                    self._messages = self._context.prepare_messages(self._messages)
                async for event in self._llm.chat_stream(
                    messages=self._messages,
                    tools=self._get_tool_definitions() if self._tools else None,
                ):
                    yield event
                    if event.type == StreamEventType.CONTENT_DELTA:
                        content_buffer += event.data
                    elif event.type == StreamEventType.TOOL_CALL_START:
                        idx = event.data.get("index", 0)
                        tool_calls_buffer[idx] = {
                            "id": event.data["id"],
                            "name": event.data["name"],
                            "arguments": "",
                        }
                    elif event.type == StreamEventType.TOOL_CALL_DELTA:
                        idx = event.data.get("index", 0)
                        if idx in tool_calls_buffer:
                            tool_calls_buffer[idx]["arguments"] += event.data["delta"]
                    elif event.type == StreamEventType.TOOL_CALL_END:
                        idx = event.data.get("index", 0)
                        if idx in tool_calls_buffer:
                            tool_calls_buffer[idx]["arguments"] = event.data["arguments"]
                    elif event.type == StreamEventType.USAGE:
                        current_usage = event.data
                self._total_usage += current_usage
                tool_calls_list: list[ToolCall] = []
                for idx in sorted(tool_calls_buffer.keys()):
                    buf = tool_calls_buffer[idx]
                    tool_calls_list.append(ToolCall(
                        id=buf["id"],
                        name=buf["name"],
                        arguments=buf["arguments"],
                    ))
                assistant_msg = Message(
                    role=MessageRole.ASSISTANT,
                    content=content_buffer if content_buffer else None,
                    tool_calls=tool_calls_list if tool_calls_list else None,
                )
                self._messages.append(assistant_msg)
                if not tool_calls_list:
                    yield StreamEvent(type=StreamEventType.DONE, data=None)
                    self._state.transition(AgentState.DONE)
                    return
                logger.info(
                    f"Executing {len(tool_calls_list)} tool call(s) "
                    f"(inner round {inner_round})"
                )
                for tc in tool_calls_list:
                    yield StreamEvent(
                        type=StreamEventType.TOOL_EXECUTE_START,
                        data={"id": tc.id, "name": tc.name},
                    )
                results = await self._execute_tool_calls(tool_calls_list)
                self._inject_tool_results(results)
                for r in results:
                    yield StreamEvent(
                        type=StreamEventType.TOOL_EXECUTE_END,
                        data={
                            "id": r.tool_call_id,
                            "name": r.name,
                            "success": r.success,
                            "error": r.error,
                        },
                    )
            yield StreamEvent(
                type=StreamEventType.CONTENT_DELTA,
                data=f"\n\n[已达到最大循环轮次 ({max_inner_rounds})。"
                     f"请简化你的请求。]",
            )
            yield StreamEvent(type=StreamEventType.DONE, data=None)
            self._state.transition(AgentState.DONE)
        except LLMError as e:
            self._state.transition(AgentState.ERROR)
            logger.error(f"Round {self._round} (stream) failed: {e}")
            raise

    def handle_tool_result(self, result: ToolCallResult) -> None:
        msg = Message(
            role=MessageRole.TOOL,
            content=result.content if result.success else f"Error: {result.error}",
            tool_call_id=result.tool_call_id,
            name=result.name,
        )
        self._messages.append(msg)

    def __repr__(self) -> str:
        return (
            f"AgentLoop(state={self.state.value}, "
            f"round={self._round}, "
            f"messages={len(self._messages)}, "
            f"tool_calls={self._tool_call_count}, "
            f"total_tokens={self._total_usage.total_tokens})"
        )
