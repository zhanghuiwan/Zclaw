"""
P9 - MCP (Model Context Protocol) 集成验证
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.types import MCPServerConfig, MCPTransportType, MCPToolDefinition
from src.mcp.transport import (
    MockTransport, StdioTransport, SSETransport,
    _make_request, _make_notification, create_transport,
)
from src.mcp.client import MCPClient
from src.mcp.adapter import MCPToolWrapper, schema_to_parameters, create_wrappers
from src.mcp.manager import MCPManager
from src.config.settings import MCPConfig


# ──────────────────────────────────────────────
# 1. MCP 数据类型测试
# ──────────────────────────────────────────────

async def test_types():
    """测试 MCP 数据类型和配置"""
    print("=" * 60)
    print("1. 测试 MCP 数据类型")
    print("=" * 60)

    # MCPServerConfig - stdio
    config_stdio = MCPServerConfig(
        name="test-stdio",
        transport=MCPTransportType.STDIO,
        command="npx",
        args=["-y", "mcp-server"],
    )
    assert config_stdio.name == "test-stdio"
    assert config_stdio.transport == MCPTransportType.STDIO
    assert config_stdio.validate() == []
    print("  OK MCPServerConfig stdio 配置有效")

    # 序列化
    d = config_stdio.to_dict()
    assert d["transport"] == "stdio"
    assert d["command"] == "npx"
    print("  OK MCPServerConfig 序列化")

    # 从字典创建
    config2 = MCPServerConfig.from_dict({
        "name": "from-dict",
        "command": "python",
        "args": ["-m", "server"],
    })
    assert config2.name == "from-dict"
    assert config2.transport == MCPTransportType.STDIO
    print("  OK MCPServerConfig from_dict")

    # SSE 配置
    config_sse = MCPServerConfig(
        name="test-sse",
        transport=MCPTransportType.SSE,
        url="http://localhost:8080/mcp",
    )
    assert config_sse.validate() == []
    print("  OK MCPServerConfig SSE 配置有效")

    # 验证失败
    config_bad = MCPServerConfig(name="", command="")
    errors = config_bad.validate()
    assert len(errors) >= 2
    print(f"  OK 无效配置检测: {len(errors)} 个错误")

    # MCPToolDefinition
    tool_def = MCPToolDefinition(
        name="read_file",
        description="读取文件内容",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "encoding": {"type": "string", "description": "编码方式", "default": "utf-8"},
            },
            "required": ["path"],
        },
        server_name="filesystem",
    )
    assert tool_def.name == "read_file"
    assert tool_def.server_name == "filesystem"
    print("  OK MCPToolDefinition")

    # MCPConfig (settings)
    mcp_cfg = MCPConfig()
    assert mcp_cfg.enabled is True
    assert mcp_cfg.auto_connect is True
    print("  OK MCPConfig 默认值")

    print()


# ──────────────────────────────────────────────
# 2. 传输层测试
# ──────────────────────────────────────────────

async def test_transport():
    """测试 MCP 传输层"""
    print("=" * 60)
    print("2. 测试 MCP 传输层")
    print("=" * 60)

    # JSON-RPC 消息构造
    req = _make_request("initialize", {"key": "value"}, 1)
    data = json.loads(req)
    assert data["jsonrpc"] == "2.0"
    assert data["method"] == "initialize"
    assert data["id"] == 1
    print("  OK _make_request")

    noti = _make_notification("notifications/initialized")
    data2 = json.loads(noti)
    assert "id" not in data2
    assert data2["method"] == "notifications/initialized"
    print("  OK _make_notification")

    # MockTransport
    mock = MockTransport(
        tools=[
            {
                "name": "echo",
                "description": "回显输入",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            {
                "name": "add",
                "description": "两数相加",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["a", "b"],
                },
            },
        ],
        call_results={
            "echo": "Hello World",
            "add": "42",
        },
    )

    assert not mock.is_connected
    await mock.connect()
    assert mock.is_connected
    print("  OK MockTransport connect")

    # initialize
    result = await mock.send_request("initialize", {})
    assert result["protocolVersion"] == "2024-11-05"
    print("  OK MockTransport initialize")

    # tools/list
    tools_result = await mock.send_request("tools/list", {})
    assert len(tools_result["tools"]) == 2
    assert tools_result["tools"][0]["name"] == "echo"
    print("  OK MockTransport tools/list")

    # tools/call
    call_result = await mock.send_request("tools/call", {"name": "echo"})
    assert "Hello World" in str(call_result)
    print("  OK MockTransport tools/call")

    # ping
    ping_result = await mock.send_request("ping", {})
    assert ping_result == {}
    print("  OK MockTransport ping")

    # notification
    await mock.send_notification("test/event", {"data": 1})
    print("  OK MockTransport notification")

    # close
    await mock.close()
    assert not mock.is_connected
    print("  OK MockTransport close")

    # 未连接时发送请求
    try:
        await mock.send_request("test", {})
        assert False, "应该抛出异常"
    except ConnectionError:
        print("  OK MockTransport 未连接时抛出异常")

    # create_transport 工厂
    config_stdio = MCPServerConfig(name="test", command="echo", args=["hello"])
    transport = create_transport(config_stdio)
    assert isinstance(transport, StdioTransport)
    print("  OK create_transport (stdio)")

    config_sse = MCPServerConfig(name="test", transport=MCPTransportType.SSE, url="http://localhost:8080")
    transport2 = create_transport(config_sse)
    assert isinstance(transport2, SSETransport)
    print("  OK create_transport (sse)")

    print()


# ──────────────────────────────────────────────
# 3. MCP 客户端测试
# ──────────────────────────────────────────────

async def test_client():
    """测试 MCP 客户端"""
    print("=" * 60)
    print("3. 测试 MCP 客户端")
    print("=" * 60)

    # 使用 MockTransport 创建客户端
    mock_transport = MockTransport(
        tools=[
            {
                "name": "get_weather",
                "description": "获取天气信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        ],
        call_results={"get_weather": "晴天, 25°C"},
    )

    config = MCPServerConfig(
        name="weather-server",
        transport=MCPTransportType.STDIO,
        command="python",
        args=["weather_server.py"],
    )

    client = MCPClient(config, transport=mock_transport)
    assert not client.is_connected
    assert len(client.tools) == 0
    print("  OK MCPClient 初始化状态")

    # 连接
    server_info = await client.connect()
    assert client.is_connected
    assert len(client.tools) == 1
    assert client.tools[0].name == "get_weather"
    assert "name" in server_info or server_info == {}
    print(f"  OK MCPClient 连接成功, {len(client.tools)} 个工具")

    # 调用工具
    result = await client.call_tool("get_weather", {"city": "北京"})
    assert "晴天" in result
    print(f"  OK MCPClient call_tool: {result}")

    # ping
    alive = await client.ping()
    assert alive
    print("  OK MCPClient ping")

    # 关闭
    await client.close()
    assert not client.is_connected
    print("  OK MCPClient close")

    # 重复连接
    mock_transport2 = MockTransport(tools=[])
    client2 = MCPClient(config, transport=mock_transport2)
    await client2.connect()
    await client2.connect()  # 第二次应该直接返回
    assert client2.is_connected
    await client2.close()
    print("  OK MCPClient 重复连接")

    # 未初始化时调用工具
    mock_transport3 = MockTransport(tools=[])
    client3 = MCPClient(config, transport=mock_transport3)
    try:
        await client3.call_tool("test", {})
        assert False
    except ConnectionError:
        print("  OK MCPClient 未初始化时调用抛出异常")

    print()


# ──────────────────────────────────────────────
# 4. 工具适配器测试
# ──────────────────────────────────────────────

async def test_adapter():
    """测试 MCP 工具适配器"""
    print("=" * 60)
    print("4. 测试 MCP 工具适配器")
    print("=" * 60)

    # schema_to_parameters
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "line": {"type": "integer", "description": "行号", "default": 1},
            "encoding": {"type": "string", "description": "编码"},
        },
        "required": ["path"],
    }
    params = schema_to_parameters(schema)
    assert len(params) == 3
    assert params[0].name == "path"
    assert params[0].required is True
    assert params[0].type == "string"
    assert params[1].name == "line"
    assert params[1].default == 1
    print(f"  OK schema_to_parameters: {len(params)} 个参数")

    # 空 schema
    params_empty = schema_to_parameters({})
    assert len(params_empty) == 0
    print("  OK schema_to_parameters 空输入")

    # anyOf 类型处理
    schema_union = {
        "type": "object",
        "properties": {
            "value": {
                "anyOf": [{"type": "null"}, {"type": "string"}],
                "description": "可选值",
            },
        },
    }
    params_union = schema_to_parameters(schema_union)
    assert params_union[0].type == "string"
    print("  OK schema_to_parameters anyOf 处理")

    # MCPToolWrapper
    mock_transport = MockTransport(
        tools=[
            {
                "name": "search",
                "description": "搜索文件",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                    },
                    "required": ["query"],
                },
            },
        ],
        call_results={"search": "找到 3 个结果"},
    )

    config = MCPServerConfig(name="search-srv", command="python", args=["search.py"])
    client = MCPClient(config, transport=mock_transport)
    await client.connect()

    wrappers = create_wrappers(client)
    assert len(wrappers) == 1
    wrapper = wrappers[0]
    assert isinstance(wrapper, MCPToolWrapper)
    assert "search-srv__search" == wrapper.name
    assert "[MCP:search-srv]" in wrapper.description
    assert wrapper.server_name == "search-srv"
    assert wrapper.danger_level.value == "confirm"
    print(f"  OK MCPToolWrapper: {wrapper}")

    # 执行工具
    result = await wrapper.execute(query="hello world")
    assert result.success is True
    assert "3 个结果" in result.content
    print(f"  OK MCPToolWrapper execute: {result.content[:30]}")

    # JSON Schema 生成
    schema = wrapper.get_json_schema()
    assert "query" in schema["properties"]
    assert "query" in schema["required"]
    print("  OK MCPToolWrapper get_json_schema")

    # OpenAI 格式
    openai_tool = wrapper.to_openai_tool()
    assert openai_tool["function"]["name"] == "search-srv__search"
    print("  OK MCPToolWrapper to_openai_tool")

    await client.close()
    print()


# ──────────────────────────────────────────────
# 5. MCP 管理器测试
# ──────────────────────────────────────────────

async def test_manager():
    """测试 MCP 管理器"""
    print("=" * 60)
    print("5. 测试 MCP 管理器")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "mcp_servers.json"

        # 写入配置
        config_data = {
            "mcpServers": {
                "echo-server": {
                    "command": "echo",
                    "args": ["hello"],
                    "description": "测试服务器",
                },
                "disabled-server": {
                    "command": "echo",
                    "args": ["disabled"],
                    "enabled": False,
                },
            }
        }
        config_path.write_text(json.dumps(config_data, ensure_ascii=False), encoding="utf-8")

        manager = MCPManager(config_path=str(config_path))

        # 加载配置
        configs = manager.load_config(str(config_path))
        assert len(configs) == 2
        print(f"  OK load_config: {len(configs)} 个服务器")

        # list_servers
        servers = manager.list_servers()
        assert len(servers) == 2
        assert servers[0]["name"] == "echo-server"
        print(f"  OK list_servers: {len(servers)} 个")

        # 手动添加服务器
        manual_config = MCPServerConfig(
            name="manual-server",
            command="python",
            args=["-c", "print()"],
        )
        manager.add_server(manual_config)
        assert len(manager.list_servers()) == 3
        print("  OK add_server")

        # 移除服务器
        removed = manager.remove_server("manual-server")
        assert removed
        assert len(manager.list_servers()) == 2
        print("  OK remove_server")

        # 使用 MockTransport 手动连接
        mock = MockTransport(
            tools=[
                {
                    "name": "test_tool",
                    "description": "测试工具",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"x": {"type": "string"}},
                        "required": ["x"],
                    },
                },
            ],
            call_results={"test_tool": "ok"},
        )

        mock_client = MCPClient(
            MCPServerConfig(name="mock-srv", command="test"),
            transport=mock,
        )
        await mock_client.connect()

        # 直接注册客户端
        manager._clients["mock-srv"] = mock_client
        manager._wrappers["mock-srv"] = create_wrappers(mock_client)

        assert "mock-srv" in manager.connected_servers
        assert len(manager.all_tools) == 1
        print(f"  OK 手动注册客户端: {len(manager.all_tools)} 个工具")

        # get_server_tools
        tools = manager.get_server_tools("mock-srv")
        assert len(tools) == 1
        print("  OK get_server_tools")

        # get_client
        client = manager.get_client("mock-srv")
        assert client is mock_client
        print("  OK get_client")

        # disconnect
        count = await manager.disconnect_all()
        assert count >= 1
        assert len(manager.connected_servers) == 0
        print(f"  OK disconnect_all: 断开 {count} 个")

        # 不存在的配置文件
        manager2 = MCPManager(config_path="/nonexistent/path.json")
        configs2 = manager2.load_config()
        assert len(configs2) == 0
        print("  OK 不存在的配置文件返回空列表")

    print()


# ──────────────────────────────────────────────
# 6. Agent 集成测试
# ──────────────────────────────────────────────

async def test_agent_integration():
    """测试 MCP 与 Agent 的集成"""
    print("=" * 60)
    print("6. 测试 Agent MCP 集成")
    print("=" * 60)

    from src.core.agent import Agent
    from src.config.settings import Settings

    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings()

        # 禁用 MCP 自动连接（测试环境无服务器）
        settings.mcp.enabled = True
        settings.mcp.auto_connect = False
        settings.mcp.config_path = str(Path(tmpdir) / "mcp.json")

        agent = Agent(settings=settings)

        # MCP 管理器已初始化
        assert agent.mcp_manager is not None
        print("  OK Agent.mcp_manager 已初始化")

        # init_mcp 在 auto_connect=False 时返回 0
        count = await agent.init_mcp()
        assert count == 0
        print("  OK Agent.init_mcp (auto_connect=False)")

        # 手动添加 Mock 服务器并注入 MockTransport
        mock = MockTransport(
            tools=[
                {
                    "name": "mcp_tool",
                    "description": "MCP 测试工具",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"data": {"type": "string"}},
                        "required": ["data"],
                    },
                },
            ],
            call_results={"mcp_tool": "mcp result"},
        )

        server_config = MCPServerConfig(
            name="test-mcp",
            command="test",
            args=[],
        )
        agent.mcp_manager.add_server(server_config)

        # 创建 MCPClient 并注入 MockTransport，手动完成连接
        mock_client = MCPClient(server_config, transport=mock)
        await mock_client.connect()

        # 手动注册到 manager
        from src.mcp.adapter import create_wrappers
        wrappers = create_wrappers(mock_client)
        agent.mcp_manager._clients["test-mcp"] = mock_client
        agent.mcp_manager._wrappers["test-mcp"] = wrappers
        assert len(wrappers) == 1

        # 注册到工具注册表
        agent.tools.register_many(wrappers)
        assert "test-mcp__mcp_tool" in agent.tools.tool_names
        print(f"  OK MCP 工具已注册: {agent.tools.tool_names}")

        # 验证可执行
        result = await agent.tools.execute("test-mcp__mcp_tool", {"data": "hello"})
        assert result.success
        assert "mcp result" in result.content
        print(f"  OK MCP 工具执行成功: {result.content}")

        # shutdown_mcp
        await agent.shutdown_mcp()
        print("  OK Agent.shutdown_mcp")

    print()


# ──────────────────────────────────────────────

async def main():
    print()
    print("=" * 60)
    print("        Zclaw P9 - MCP 集成验证")
    print("=" * 60)
    print()

    await test_types()
    await test_transport()
    await test_client()
    await test_adapter()
    await test_manager()
    await test_agent_integration()

    print("=" * 60)
    print("Results: 6 passed, 0 failed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
