"""
Agent 状态机

定义 Agent 的状态流转规则。
"""

from __future__ import annotations

from enum import Enum


class AgentState(str, Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    DONE = "done"
    ERROR = "error"


# 合法状态转换表
_VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.IDLE: {AgentState.PLANNING, AgentState.EXECUTING},
    AgentState.PLANNING: {AgentState.EXECUTING, AgentState.IDLE},
    AgentState.EXECUTING: {AgentState.DONE, AgentState.ERROR, AgentState.WAITING_CONFIRMATION},
    AgentState.WAITING_CONFIRMATION: {AgentState.EXECUTING, AgentState.DONE},
    AgentState.DONE: {AgentState.IDLE, AgentState.EXECUTING},
    AgentState.ERROR: {AgentState.IDLE, AgentState.EXECUTING},
}


class StateTransitionError(Exception):
    """非法状态转换"""
    def __init__(self, from_state: AgentState, to_state: AgentState):
        super().__init__(
            f"非法状态转换: {from_state.value} -> {to_state.value}"
        )
        self.from_state = from_state
        self.to_state = to_state


class AgentStateMachine:
    """Agent 状态机"""

    def __init__(self):
        self._state = AgentState.IDLE
        self._listeners: list = []

    @property
    def state(self) -> AgentState:
        return self._state

    def transition(self, new_state: AgentState) -> None:
        if new_state not in _VALID_TRANSITIONS.get(self._state, set()):
            import logging
            logging.getLogger(__name__).error(f"非法状态转换: {self._state.value} -> {new_state.value}")
            raise StateTransitionError(self._state, new_state)
        old = self._state
        self._state = new_state
        import logging
        logging.getLogger(__name__).debug(f"状态转换: {old.value} -> {new_state.value}")
        for listener in self._listeners:
            listener(old, new_state)

    def on_change(self, callback) -> None:
        """注册状态变更监听器。"""
        self._listeners.append(callback)

    def __repr__(self) -> str:
        return f"AgentStateMachine(state={self._state.value})"
