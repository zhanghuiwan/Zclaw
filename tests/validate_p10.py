"""
P10 验证测试 - Web UI 模块

测试 Web 模块的所有核心组件：
1. 数据模型 (schemas.py)
2. WebSocket 管理器 (ws_manager.py)
3. FastAPI 路由 (routes.py, server.py)
4. 静态文件存在性
5. 配置集成

运行方式: python -m pytest tests/validate_p10.py -v
         或: python tests/validate_p10.py
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

passed = 0
failed = 0
errors = []


def run_test(name, func):
    """运行单个测试并记录结果。"""
    global passed, failed, errors
    try:
        func()
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


def run_async_test(name, func):
    """运行异步测试。"""
    global passed, failed, errors
    try:
        asyncio.get_event_loop().run_until_complete(func())
        passed += 1
        print(f"  ✅ {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


# ============================================================
# Test 1: 数据模型 (schemas.py)
# ============================================================

def test_schemas_import():
    """测试 schemas 模块可以正确导入。"""
    from src.web.schemas import (
        WSMessageType, WSMessage, WSChatMessage, WSCommandMessage,
        WSPermissionMessage, WSPermissionResponse,
        ChatRequest, ChatResponse, ToolInfo, FileEntry, FileInfo,
        AgentStatus, ErrorResponse, SuccessResponse,
        HistoryMessage, HistoryResponse, CostInfo,
        SessionInfo, SessionListResponse, SessionLoadResponse,
    )
    assert len(WSMessageType) >= 8, "WSMessageType 应该有至少 8 种类型"
    assert WSMessageType.CHAT.value == "chat"
    assert WSMessageType.STREAM_DELTA.value == "stream_delta"


def test_schemas_chat_request_validation():
    """测试 ChatRequest 模型验证。"""
    from src.web.schemas import ChatRequest
    # 有效请求
    req = ChatRequest(message="你好")
    assert req.message == "你好"
    # 空消息应该失败
    try:
        ChatRequest(message="")
        assert False, "空消息应该验证失败"
    except Exception:
        pass


def test_schemas_ws_message_types():
    """测试 WebSocket 消息类型。"""
    from src.web.schemas import (
        WSMessageType, WSChatMessage, WSPermissionMessage,
        WSPermissionResponse,
    )
    # Chat 消息
    chat = WSChatMessage(data={"message": "hello"})
    assert chat.type == WSMessageType.CHAT
    assert chat.data["message"] == "hello"

    # Permission 消息
    perm = WSPermissionMessage(data={"request_id": "abc", "tool_name": "shell", "arguments": {}, "danger_level": "dangerous"})
    assert perm.type == WSMessageType.PERMISSION
    assert perm.data["request_id"] == "abc"

    # Permission 响应
    resp = WSPermissionResponse(data={"request_id": "abc", "allowed": True})
    assert resp.data["allowed"] is True


def test_schemas_tool_info():
    """测试 ToolInfo 模型。"""
    from src.web.schemas import ToolInfo
    tool = ToolInfo(
        name="file_read",
        description="读取文件",
        category="file",
        danger_level="safe",
        parameters=[{"name": "path", "type": "string", "required": True}],
    )
    assert tool.name == "file_read"
    assert len(tool.parameters) == 1
    json_str = tool.model_dump_json()
    assert "file_read" in json_str


def test_schemas_agent_status():
    """测试 AgentStatus 模型。"""
    from src.web.schemas import AgentStatus
    status = AgentStatus(
        state="idle",
        provider="bailian",
        model="qwen-plus",
        tools_count=9,
        tool_names=["file_read", "shell"],
        session_id="abc123",
        round=1,
        tool_call_count=3,
        usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        message_count=10,
    )
    assert status.tools_count == 9
    assert status.usage["total_tokens"] == 300


# ============================================================
# Test 2: WebSocket 管理器 (ws_manager.py)
# ============================================================

def test_ws_manager_creation():
    """测试 ConnectionManager 创建。"""
    from src.web.ws_manager import ConnectionManager
    manager = ConnectionManager()
    assert manager.active_connections == 0


async def test_ws_manager_connect_disconnect():
    """测试连接和断开。"""
    from src.web.ws_manager import ConnectionManager

    manager = ConnectionManager()

    # Mock WebSocket
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    conn_id = await manager.connect(mock_ws)
    assert conn_id is not None
    assert len(conn_id) == 12
    assert manager.active_connections == 1

    manager.disconnect(conn_id)
    assert manager.active_connections == 0


async def test_ws_manager_send_json():
    """测试发送 JSON 消息。"""
    from src.web.ws_manager import ConnectionManager

    manager = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    conn_id = await manager.connect(mock_ws)

    # 成功发送
    result = await manager.send_json(conn_id, {"type": "test", "data": {}})
    assert result is True
    mock_ws.send_json.assert_called_once()

    # 发送给不存在的连接
    result = await manager.send_json("nonexistent", {"type": "test"})
    assert result is False


async def test_ws_manager_broadcast():
    """测试广播消息。"""
    from src.web.ws_manager import ConnectionManager

    manager = ConnectionManager()
    mock_ws1 = AsyncMock()
    mock_ws1.accept = AsyncMock()
    mock_ws2 = AsyncMock()
    mock_ws2.accept = AsyncMock()

    conn_id1 = await manager.connect(mock_ws1)
    conn_id2 = await manager.connect(mock_ws2)

    # 广播给所有人
    count = await manager.broadcast({"type": "test"})
    assert count == 2

    # 排除一个连接
    count = await manager.broadcast({"type": "test"}, exclude=conn_id1)
    assert count == 1


async def test_ws_manager_permission():
    """测试权限请求/响应机制。"""
    from src.web.ws_manager import ConnectionManager

    manager = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    conn_id = await manager.connect(mock_ws)

    # 请求权限（超时短一些方便测试）
    # 在另一个 task 中响应权限
    async def respond():
        await asyncio.sleep(0.1)
        manager.resolve_permission("req1", True)

    asyncio.create_task(respond())

    result = await manager.request_permission(
        conn_id=conn_id,
        request_id="req1",
        tool_name="shell",
        arguments={"command": "ls"},
        danger_level="confirm",
        timeout=2.0,
    )
    assert result is True


async def test_ws_manager_permission_timeout():
    """测试权限请求超时。"""
    from src.web.ws_manager import ConnectionManager

    manager = ConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    conn_id = await manager.connect(mock_ws)

    # 不响应，等待超时
    result = await manager.request_permission(
        conn_id=conn_id,
        request_id="req_timeout",
        tool_name="shell",
        arguments={"command": "rm -rf /"},
        danger_level="dangerous",
        timeout=0.5,
    )
    assert result is False  # 超时返回 False


# ============================================================
# Test 3: FastAPI 应用 (server.py)
# ============================================================

def test_server_creation():
    """测试 FastAPI 应用创建。"""
    from src.web.server import create_app

    app = create_app()
    assert app is not None
    assert app.title == "Zclaw Web UI"
    assert app.version == "0.1.0"

    # 检查路由已注册
    routes = [r.path for r in app.routes]
    assert "/api/ws" in routes
    assert "/api/status" in routes
    assert "/api/tools" in routes
    assert "/api/history" in routes
    assert "/api/files/list" in routes
    assert "/api/files/read" in routes
    assert "/api/clear" in routes
    assert "/api/sessions" in routes
    assert "/api/cost" in routes
    assert "/api/config" in routes


def test_server_with_agent():
    """测试带 Agent 参数的创建。"""
    from src.web.server import create_app

    # Mock Agent
    mock_agent = MagicMock()
    mock_agent._settings = MagicMock()
    mock_agent._settings.llm.default_provider = "test"
    mock_agent._settings.llm.providers = {
        "test": MagicMock(model="test-model", max_context_tokens=32768)
    }
    mock_agent.state.value = "idle"
    mock_agent.session_id = "test123"
    mock_agent.tools.__len__ = Mock(return_value=9)
    mock_agent.tools.tool_names = ["file_read"]
    mock_agent.loop.state.value = "idle"
    mock_agent.loop.round = 0
    mock_agent.loop.tool_call_count = 0
    mock_agent.loop.usage = MagicMock(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    mock_agent.loop.messages = []
    mock_agent.permission_manager = MagicMock()

    # Mock Settings
    mock_settings = MagicMock()
    mock_settings.web.cors_origins = ["http://localhost:3000"]

    app = create_app(agent=mock_agent, settings=mock_settings)
    assert app is not None


# ============================================================
# Test 4: 静态文件
# ============================================================

def test_static_files_exist():
    """测试静态文件存在。"""
    static_dir = PROJECT_ROOT / "src" / "web" / "static"

    # 检查目录
    assert static_dir.exists(), "static 目录不存在"
    assert (static_dir / "index.html").exists(), "index.html 不存在"
    assert (static_dir / "css" / "style.css").exists(), "style.css 不存在"
    assert (static_dir / "js" / "app.js").exists(), "app.js 不存在"


def test_index_html_content():
    """测试 index.html 包含关键元素。"""
    index_path = PROJECT_ROOT / "src" / "web" / "static" / "index.html"
    content = index_path.read_text()

    # 检查关键 DOM 元素
    assert "chatMessages" in content
    assert "chatInput" in content
    assert "connectionStatus" in content
    assert "sidebar" in content
    assert "fileList" in content
    assert "toolList" in content
    assert "permissionDialog" in content

    # 检查 JS/CSS 引用
    assert "/static/css/style.css" in content
    assert "/static/js/app.js" in content


def test_css_content():
    """测试 CSS 文件包含关键样式。"""
    css_path = PROJECT_ROOT / "src" / "web" / "static" / "css" / "style.css"
    content = css_path.read_text()

    # 检查关键 CSS 变量和类
    assert "--bg-primary:" in content
    assert ".header" in content
    assert ".sidebar" in content
    assert ".chat-area" in content
    assert ".message" in content
    assert ".tool-card" in content
    assert ".permission-dialog" in content
    assert "@media" in content  # 响应式设计


def test_js_content():
    """测试 JavaScript 文件包含关键功能。"""
    js_path = PROJECT_ROOT / "src" / "web" / "static" / "js" / "app.js"
    content = js_path.read_text()

    # 检查关键功能
    assert "WebSocket" in content
    assert "connectWebSocket" in content
    assert "sendMessage" in content
    assert "handleStreamDelta" in content
    assert "handleToolStart" in content
    assert "handleToolEnd" in content
    assert "handlePermission" in content
    assert "loadFiles" in content
    assert "loadTools" in content
    assert "loadSessions" in content


# ============================================================
# Test 5: 配置集成
# ============================================================

def test_web_config():
    """测试 WebConfig 在 Settings 中。"""
    from src.config.settings import Settings, WebConfig

    settings = Settings()
    assert settings.web is not None
    assert isinstance(settings.web, WebConfig)
    assert settings.web.enabled is True
    assert settings.web.host == "0.0.0.0"
    assert settings.web.port == 8080
    assert settings.web.cors_origins == ["*"]

    # 自定义配置
    custom = Settings(web=WebConfig(host="127.0.0.1", port=9090))
    assert custom.web.host == "127.0.0.1"
    assert custom.web.port == 9090


def test_web_config_serialization():
    """测试 WebConfig 序列化。"""
    from src.config.settings import Settings
    settings = Settings()
    data = settings.model_dump()
    assert "web" in data
    assert data["web"]["port"] == 8080


# ============================================================
# Test 6: 路由模块导入和基础功能
# ============================================================

def test_routes_import():
    """测试路由模块可以正确导入。"""
    from src.web.routes import router, ws_manager
    assert router is not None
    assert ws_manager is not None


def test_routes_ws_manager_singleton():
    """测试 WebSocket 管理器是模块级单例。"""
    from src.web.routes import ws_manager
    from src.web.ws_manager import ConnectionManager
    assert isinstance(ws_manager, ConnectionManager)


# ============================================================
# 运行所有测试
# ============================================================

def main():
    print("=" * 60)
    print("P10 验证测试 - Web UI 模块")
    print("=" * 60)

    print("\n📦 1. 数据模型 (schemas.py)")
    run_test("schemas 导入和类型检查", test_schemas_import)
    run_test("ChatRequest 验证", test_schemas_chat_request_validation)
    run_test("WS 消息类型", test_schemas_ws_message_types)
    run_test("ToolInfo 模型", test_schemas_tool_info)
    run_test("AgentStatus 模型", test_schemas_agent_status)

    print("\n🔌 2. WebSocket 管理器 (ws_manager.py)")
    run_test("ConnectionManager 创建", test_ws_manager_creation)
    run_async_test("连接和断开", test_ws_manager_connect_disconnect)
    run_async_test("发送 JSON 消息", test_ws_manager_send_json)
    run_async_test("广播消息", test_ws_manager_broadcast)
    run_async_test("权限请求/响应", test_ws_manager_permission)
    run_async_test("权限请求超时", test_ws_manager_permission_timeout)

    print("\n🌐 3. FastAPI 应用 (server.py)")
    run_test("应用创建和路由注册", test_server_creation)
    run_test("带 Agent 参数创建", test_server_with_agent)

    print("\n📁 4. 静态文件")
    run_test("静态文件存在性", test_static_files_exist)
    run_test("index.html 内容", test_index_html_content)
    run_test("CSS 内容", test_css_content)
    run_test("JavaScript 内容", test_js_content)

    print("\n⚙️  5. 配置集成")
    run_test("WebConfig 在 Settings 中", test_web_config)
    run_test("WebConfig 序列化", test_web_config_serialization)

    print("\n🛣️  6. 路由模块")
    run_test("路由模块导入", test_routes_import)
    run_test("WS 管理器单例", test_routes_ws_manager_singleton)

    # 汇总
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"结果: {passed}/{total} 通过, {failed} 失败")
    print("=" * 60)

    if errors:
        print("\n失败详情:")
        for name, err in errors:
            print(f"  - {name}: {err}")

    return failed == 0


class Mock:
    """Simple mock helper for __len__."""
    def __init__(self, return_value):
        self.return_value = return_value

    def __call__(self):
        return self.return_value


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
