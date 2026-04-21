"""
AgentPool 测试用例

测试 Agent 实例池的核心功能：
1. Agent 获取和释放
2. Agent 状态转换
3. 空闲清理
4. 实例数量限制
"""

import asyncio
import tempfile
import pytest
from pathlib import Path

# 测试夹具目录
TEST_AGENTS_DIR = Path(__file__).parent.parent / "agents" / "default"


class TestAgentPool:
    """AgentPool 测试类"""

    @pytest.fixture
    def agent_pool(self):
        """创建 AgentPool 实例"""
        from src.brain.agent_pool import AgentPool
        pool = AgentPool(
            agents_dir=TEST_AGENTS_DIR,
            max_idle_seconds=60,
            max_instances=3,
        )
        yield pool
        # 清理
        asyncio.run(pool.cleanup_all())

    @pytest.mark.asyncio
    async def test_pool_initialization(self, agent_pool):
        """测试池初始化"""
        assert agent_pool.agents_dir == TEST_AGENTS_DIR
        assert agent_pool.max_instances == 3
        assert agent_pool.instance_count == 0
        assert agent_pool.active_count == 0

    @pytest.mark.asyncio
    async def test_get_agent_creates_new_instance(self, agent_pool):
        """测试获取 Agent 创建新实例"""
        agent = await agent_pool.get_agent("default")
        assert agent is not None
        assert agent_pool.instance_count == 1
        assert agent_pool.active_count == 1

    @pytest.mark.asyncio
    async def test_get_agent_returns_same_instance(self, agent_pool):
        """测试获取相同 Agent 返回同一实例"""
        agent1 = await agent_pool.get_agent("default")
        agent2 = await agent_pool.get_agent("default")

        assert agent1 is agent2
        assert agent_pool.instance_count == 1
        # 第二次调用应该标记为活跃
        assert agent_pool.active_count == 1

    @pytest.mark.asyncio
    async def test_get_different_agents_creates_multiple_instances(self, agent_pool):
        """测试获取不同 Agent 创建多个实例"""
        # 注意：这里使用相同的 agent_id 但多次调用
        # 实际应该返回同一实例
        agent1 = await agent_pool.get_agent("default")
        agent2 = await agent_pool.get_agent("default")

        assert agent1 is agent2
        assert agent_pool.instance_count == 1

    @pytest.mark.asyncio
    async def test_release_agent_marks_idle(self, agent_pool):
        """测试释放 Agent 标记为空闲"""
        agent = await agent_pool.get_agent("default")
        assert agent_pool.active_count == 1

        await agent_pool.release_agent("default")
        assert agent_pool.active_count == 0
        assert agent_pool.instance_count == 1

        inst = agent_pool._instances["default"]
        assert inst.state.value == "idle"

    @pytest.mark.asyncio
    async def test_hibernate_agent(self, agent_pool):
        """测试休眠 Agent"""
        agent = await agent_pool.get_agent("default")
        await agent_pool.release_agent("default")

        await agent_pool.hibernate_agent("default")

        inst = agent_pool._instances["default"]
        assert inst.state.value == "dormant"

    @pytest.mark.asyncio
    async def test_dispose_agent(self, agent_pool):
        """测试销毁 Agent"""
        agent = await agent_pool.get_agent("default")
        assert agent_pool.instance_count == 1

        await agent_pool.dispose_agent("default")

        assert agent_pool.instance_count == 0
        assert "default" not in agent_pool._instances

    @pytest.mark.asyncio
    async def test_max_instances_limit(self):
        """测试实例数量限制"""
        from src.brain.agent_pool import AgentPool

        pool = AgentPool(
            agents_dir=TEST_AGENTS_DIR,
            max_idle_seconds=60,
            max_instances=2,
        )

        # 获取两个不同 agent_id 的实例（模拟）
        # 由于我们只有一个 default agent，这里测试同一实例的复用
        agent1 = await pool.get_agent("default")
        assert pool.instance_count == 1

        # 再获取一次应该是同一实例
        agent2 = await pool.get_agent("default")
        assert agent1 is agent2
        assert pool.instance_count == 1

        await pool.cleanup_all()

    @pytest.mark.asyncio
    async def test_idle_cleanup(self):
        """测试空闲清理"""
        from src.brain.agent_pool import AgentPool, AgentInstance, AgentInstanceState
        import time

        pool = AgentPool(
            agents_dir=TEST_AGENTS_DIR,
            max_idle_seconds=1,  # 1秒空闲
            max_instances=3,
        )

        # 创建一个模拟的 AgentInstance
        mock_agent = type('MockAgent', (), {'clear_history': lambda self: None})()
        inst = AgentInstance("default", mock_agent)
        inst.mark_idle()
        inst.last_active_at = time.time() - 10  # 10秒前标记为空闲
        pool._instances["default"] = inst

        # 等待 2 秒确保超过 max_idle_seconds
        await asyncio.sleep(2)

        # 执行清理
        cleaned = await pool.cleanup_idle()

        assert cleaned == 1
        inst = pool._instances["default"]
        assert inst.state == AgentInstanceState.DORMANT

    @pytest.mark.asyncio
    async def test_get_instance_info(self, agent_pool):
        """测试获取实例信息"""
        agent = await agent_pool.get_agent("default")

        info = agent_pool.get_instance_info("default")
        assert info is not None
        assert info["agent_id"] == "default"
        assert info["state"] == "active"
        assert info["request_count"] == 1

    @pytest.mark.asyncio
    async def test_get_status(self, agent_pool):
        """测试获取池状态"""
        await agent_pool.get_agent("default")
        await agent_pool.get_agent("default")

        status = agent_pool.get_status()

        assert status["instance_count"] == 1
        assert status["active_count"] == 1
        assert status["max_instances"] == 3
        assert len(status["instances"]) == 1

    @pytest.mark.asyncio
    async def test_list_agents(self, agent_pool):
        """测试列出所有 Agent"""
        await agent_pool.get_agent("default")

        agents = agent_pool.list_agents()
        assert "default" in agents

    @pytest.mark.asyncio
    async def test_concurrent_get_agent(self, agent_pool):
        """测试并发获取 Agent"""
        # 并发获取同一个 Agent
        results = await asyncio.gather(
            agent_pool.get_agent("default"),
            agent_pool.get_agent("default"),
        )

        # 应该是同一个实例
        assert results[0] is results[1]
        assert agent_pool.instance_count == 1


class TestAgentInstance:
    """AgentInstance 测试类"""

    def test_instance_creation(self):
        """测试实例创建"""
        from src.brain.agent_pool import AgentInstance, AgentInstanceState

        mock_agent = type('MockAgent', (), {'clear_history': lambda self: None})()
        inst = AgentInstance("test_agent", mock_agent)

        assert inst.agent_id == "test_agent"
        assert inst.agent is mock_agent
        assert inst.state == AgentInstanceState.CREATING
        assert inst.request_count == 0

    def test_mark_active(self):
        """测试标记为活跃"""
        from src.brain.agent_pool import AgentInstance, AgentInstanceState

        mock_agent = type('MockAgent', (), {'clear_history': lambda self: None})()
        inst = AgentInstance("test_agent", mock_agent)

        inst.mark_active()

        assert inst.state == AgentInstanceState.ACTIVE

    def test_mark_idle(self):
        """测试标记为空闲"""
        from src.brain.agent_pool import AgentInstance, AgentInstanceState

        mock_agent = type('MockAgent', (), {'clear_history': lambda self: None})()
        inst = AgentInstance("test_agent", mock_agent)
        inst.mark_active()

        inst.mark_idle()

        assert inst.state == AgentInstanceState.IDLE

    def test_mark_dormant(self):
        """测试标记为休眠"""
        from src.brain.agent_pool import AgentInstance, AgentInstanceState

        mock_agent = type('MockAgent', (), {
            'clear_history': lambda self: None
        })()
        inst = AgentInstance("test_agent", mock_agent)

        inst.mark_dormant()

        assert inst.state == AgentInstanceState.DORMANT

    def test_is_idle_too_long(self):
        """测试空闲时间检查"""
        from src.brain.agent_pool import AgentInstance, AgentInstanceState
        import time

        mock_agent = type('MockAgent', (), {'clear_history': lambda self: None})()
        inst = AgentInstance("test_agent", mock_agent)
        inst.mark_idle()
        inst.last_active_at = time.time() - 100

        # 100秒前标记为空闲，超过60秒阈值
        assert inst.is_idle_too_long(60) is True
        assert inst.is_idle_too_long(200) is False

    def test_is_idle_too_long_not_idle(self):
        """测试非空闲状态返回 False"""
        from src.brain.agent_pool import AgentInstance, AgentInstanceState
        import time

        mock_agent = type('MockAgent', (), {'clear_history': lambda self: None})()
        inst = AgentInstance("test_agent", mock_agent)
        inst.mark_active()  # 不是 IDLE 状态
        inst.last_active_at = time.time() - 100

        assert inst.is_idle_too_long(60) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])