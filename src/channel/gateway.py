"""
Gateway - 消息网关

系统的心脏，负责接收所有渠道的消息，进行归一化和路由，
并协调 Brain Layer 和 Body Layer 的交互。
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Any

from src.channel.router import MessageRouter
from src.channel.normalizer import MessageNormalizer, UnifiedMessage
from src.channel.channels.base import ChannelAdapter, ChannelMessage
from src.channel.channels.web import WebSocketChannel
from src.brain.session import SessionManager, SessionStatus
from src.brain.soul_loader import SoulLoader
from src.brain.user_profile import UserProfileLoader
from src.brain.agents_config import AgentsConfigLoader
from src.brain.context import ContextAssembler
from src.body.cron import CronScheduler, CronTask
from src.body.heartbeat import HeartbeatManager

logger = logging.getLogger(__name__)


class Gateway:
    """
    消息网关

    统一处理所有渠道的消息，实现：
    - 消息归一化和路由
    - Session 管理
    - Cron 调度
    - Heartbeat 心跳
    - Agent 生命周期管理（通过 AgentPool）
    """

    def __init__(
        self,
        storage_path: str = ".Zclaw",
        default_agent_id: str = "default",
        agents_dir: str | Path = "agents",
        max_idle_seconds: int = 1800,
        max_agent_instances: int = 10,
    ):
        self._storage_path = Path(storage_path).expanduser().resolve()
        self._default_agent_id = default_agent_id
        self._agents_dir = Path(agents_dir)

        # 初始化组件
        self._router = MessageRouter(default_agent_id=default_agent_id)
        self._normalizer = MessageNormalizer()
        self._session_manager = SessionManager(storage_path=str(self._storage_path / "sessions"))

        # 加载器
        self._soul_loader = SoulLoader()
        self._user_loader = UserProfileLoader()
        self._agents_loader = AgentsConfigLoader()
        self._context_assembler = ContextAssembler(
            soul_loader=self._soul_loader,
            user_loader=self._user_loader,
            agents_loader=self._agents_loader,
        )

        # 调度器
        self._cron_scheduler = CronScheduler()
        self._heartbeat_manager = HeartbeatManager(interval_seconds=300)

        # 通道适配器
        self._channels: dict[str, ChannelAdapter] = {}
        self._ws_channel = WebSocketChannel()
        self._channels["websocket"] = self._ws_channel

        # 状态
        self._running = False
        self._shutdown_event = asyncio.Event()

        # 处理器
        self._message_handlers: list[callable] = []

        # AgentPool（替代原来的 AgentFactory）
        self._agent_pool: Any = None

        # 注册信号处理
        self._setup_signal_handlers()

        logger.info(f"Gateway 初始化完成，存储路径: {self._storage_path}, agents目录: {self._agents_dir}")

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        if sys.platform != "win32":
            try:
                loop = asyncio.get_running_loop()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_signal(s)))
            except RuntimeError:
                # 没有运行中的事件循环，忽略
                pass

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """处理系统信号"""
        logger.info(f"收到信号: {sig.name}")
        await self.shutdown()

    # ==================== 属性 ====================

    @property
    def router(self) -> MessageRouter:
        return self._router

    @property
    def normalizer(self) -> MessageNormalizer:
        return self._normalizer

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    @property
    def cron_scheduler(self) -> CronScheduler:
        return self._cron_scheduler

    @property
    def heartbeat_manager(self) -> HeartbeatManager:
        return self._heartbeat_manager

    @property
    def context_assembler(self) -> ContextAssembler:
        return self._context_assembler

    @property
    def is_running(self) -> bool:
        return self._running

    # ==================== 通道管理 ====================

    def register_channel(self, channel: ChannelAdapter) -> None:
        """注册通道适配器"""
        self._channels[channel.channel_name] = channel
        logger.info(f"注册通道: {channel.channel_name}")

    def get_channel(self, channel_name: str) -> ChannelAdapter | None:
        """获取通道适配器"""
        return self._channels.get(channel_name)

    async def start_channel(self, channel_name: str) -> bool:
        """启动通道"""
        channel = self._channels.get(channel_name)
        if channel:
            await channel.start()
            return True
        return False

    async def stop_channel(self, channel_name: str) -> bool:
        """停止通道"""
        channel = self._channels.get(channel_name)
        if channel:
            await channel.stop()
            return True
        return False

    # ==================== 路由配置 ====================

    def add_route(
        self,
        channel: str,
        agent_id: str,
        sender_id: str = "",
        channel_id: str = "",
        priority: int = 0,
    ) -> None:
        """添加路由规则"""
        self._router.add_rule(
            channel=channel,
            agent_id=agent_id,
            sender_id=sender_id,
            channel_id=channel_id,
            priority=priority,
        )

    def load_routes_from_config(self, config: list[dict[str, Any]]) -> None:
        """从配置加载路由规则"""
        self._router.load_rules_from_config(config)

    # ==================== Cron 任务 ====================

    async def schedule_cron(
        self,
        agent_id: str,
        cron_expr: str,
        description: str,
        command: str = "",
        task_id: str | None = None,
    ) -> str:
        """注册 Cron 任务"""
        task = CronTask(
            task_id=task_id or f"{agent_id}_{cron_expr}",
            agent_id=agent_id,
            cron_expr=cron_expr,
            description=description,
            command=command,
        )
        return await self._cron_scheduler.schedule(task)

    async def load_cron_from_agents_config(self, agents_dir: str | Path) -> None:
        """从 agents 配置目录加载 Cron 任务"""
        agents_dir = Path(agents_dir)

        if not agents_dir.exists():
            logger.warning(f"agents 目录不存在: {agents_dir}")
            return

        # 遍历所有 agents
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            agents_md = agent_dir / "AGENTS.md"
            if not agents_md.exists():
                continue

            try:
                config = self._agents_loader.load(agents_md)

                for cron_task in config.cron_tasks:
                    await self.schedule_cron(
                        agent_id=agent_dir.name,
                        cron_expr=cron_task.cron_expr,
                        description=cron_task.description,
                        command=cron_task.command,
                        task_id=f"{agent_dir.name}_{cron_task.task_id}" if hasattr(cron_task, 'task_id') else None,
                    )
                    logger.info(f"加载 Cron 任务: {agent_dir.name} - {cron_task.description}")

            except Exception as e:
                logger.error(f"加载 {agents_md} 失败: {e}")

    # ==================== 消息处理 ====================

    def register_message_handler(self, handler: callable) -> None:
        """注册消息处理器"""
        self._message_handlers.append(handler)

    def set_agent_pool(self, pool: Any) -> None:
        """
        设置 AgentPool 实例。

        Args:
            pool: AgentPool 实例
        """
        self._agent_pool = pool

    @property
    def agent_pool(self) -> Any:
        """获取 AgentPool 实例"""
        return self._agent_pool

    async def handle_message(
        self,
        channel_name: str,
        raw_message: dict[str, Any],
    ) -> str | None:
        """
        处理收到的消息。

        Args:
            channel_name: 渠道名称
            raw_message: 原始消息

        Returns:
            str: 响应内容
        """
        # 1. 归一化消息
        unified = self._normalizer.normalize(raw_message, channel_name)

        if not unified.text:
            logger.debug(f"忽略空消息: {channel_name}")
            return None

        # 2. 路由到 Agent
        agent_id = self.router.route(
            channel=unified.channel,
            sender_id=unified.sender_id,
        )

        # 3. 获取或创建 Session
        session = self.session_manager.get_or_create_session(
            agent_id=agent_id,
            channel=channel_name,
            sender_id=unified.sender_id,
        )

        # 如果 Session 是休眠状态，先唤醒
        if session.status == SessionStatus.DORMANT:
            self.session_manager.wakeup_session(session.session_id)

        # 添加用户消息到会话
        session.add_message("user", unified.text)

        # 4. 调用消息处理器
        response_text = None
        for handler in self._message_handlers:
            try:
                result = handler(unified, session, agent_id)
                if asyncio.iscoroutine(result):
                    result = await result
                if result:
                    response_text = result
                    break
            except Exception as e:
                logger.error(f"消息处理器执行失败: {e}")

        # 5. 如果没有处理器，使用 Agent
        if response_text is None and self._agent_pool:
            agent = None
            try:
                agent = await self._agent_pool.get_agent(agent_id)
                response = await agent.chat(unified.text)
                response_text = response.content

                # 添加助手消息到会话
                session.add_message("assistant", response_text or "")

            except Exception as e:
                logger.error(f"Agent 处理消息失败: {e}", exc_info=True)
                response_text = f"处理消息时出错: {e}"
            finally:
                # 释放 Agent（标记为空闲）
                if agent is not None:
                    await self._agent_pool.release_agent(agent_id)

        return response_text

    async def handle_cron_task(self, task: CronTask) -> None:
        """处理 Cron 任务触发"""
        logger.info(f"Cron 任务触发: {task.task_id} - {task.description}")

        # 获取或创建该 Agent 的 Session
        session = self.session_manager.get_or_create_session(
            agent_id=task.agent_id,
            channel="cron",
            sender_id="system",
        )

        # 添加系统消息
        session.add_message("system", f"[Cron] {task.description}")

        # 调用 Agent 执行
        if self._agent_pool:
            try:
                agent = await self._agent_pool.get_agent(task.agent_id)
                response = await agent.chat(task.command or task.description)
                logger.info(f"Cron 任务执行完成: {task.task_id}")
                # 释放 Agent
                await self._agent_pool.release_agent(task.agent_id)
            except Exception as e:
                logger.error(f"Cron 任务执行失败: {task.task_id}: {e}")

    # ==================== 生命周期 ====================

    async def start(self) -> None:
        """启动 Gateway"""
        if self._running:
            logger.warning("Gateway 已在运行")
            return

        logger.info("Gateway 启动中...")
        self._running = True

        # 启动通道
        for channel in self._channels.values():
            if channel.enabled:
                await channel.start()

        # 注册 Cron 处理器
        self._cron_scheduler.add_handler(self.handle_cron_task)

        # 启动调度器
        await self._cron_scheduler.start()

        # 启动 Heartbeat
        await self._heartbeat_manager.start()

        # 清理空闲 Session
        asyncio.create_task(self._cleanup_loop())

        self._shutdown_event.clear()
        logger.info("Gateway 启动完成")

    async def shutdown(self) -> None:
        """关闭 Gateway"""
        if not self._running:
            return

        logger.info("Gateway 关闭中...")
        self._running = False

        # 停止调度器
        await self._cron_scheduler.stop()
        await self._heartbeat_manager.stop()

        # 停止通道
        for channel in self._channels.values():
            await channel.stop()

        # 归档所有活跃会话
        for session in list(self._session_manager._active_sessions.values()):
            if session.status == SessionStatus.ACTIVE:
                self._session_manager.archive_session(session.session_id)

        self._shutdown_event.set()
        logger.info("Gateway 已关闭")

    async def wait_for_shutdown(self) -> None:
        """等待关闭完成"""
        await self._shutdown_event.wait()

    async def _cleanup_loop(self) -> None:
        """定期清理空闲会话"""
        while self._running:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                self._session_manager.cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理循环异常: {e}")

    # ==================== 状态查询 ====================

    def get_status(self) -> dict[str, Any]:
        """获取 Gateway 状态"""
        status = {
            "running": self._running,
            "default_agent_id": self._default_agent_id,
            "channels": {
                name: channel.enabled
                for name, channel in self._channels.items()
            },
            "routes": [
                {
                    "channel": r.channel,
                    "sender_id": r.sender_id,
                    "channel_id": r.channel_id,
                    "agent_id": r.agent_id,
                    "priority": r.priority,
                }
                for r in self._router.get_rules()
            ],
            "sessions": {
                "active": self._session_manager.get_active_count(),
                "total": len(self._session_manager._active_sessions),
            },
            "cron": self._cron_scheduler.get_status(),
            "heartbeat": self._heartbeat_manager.get_status(),
        }

        # 添加 AgentPool 状态
        if self._agent_pool:
            status["agent_pool"] = self._agent_pool.get_status()

        return status
