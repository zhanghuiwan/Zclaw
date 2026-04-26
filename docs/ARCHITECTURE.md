# Zclaw 项目架构文档

## 一、架构概览

Zclaw 采用 **Channel Layer / Brain Layer / Body Layer** 三层架构，Gateway 作为独立守护进程运行，客户端通过 WebSocket 连接。

```
┌─────────────────────────────────────────────────────────┐
│                    Channel Layer                         │
│  ┌─────────┐  ┌───────────┐  ┌──────────┐  ┌─────────┐ │
│  │  CLI    │  │ WebSocket │  │ Telegram │  │ STDIO   │ │
│  │(zclaw)  │  │(clients)  │  │          │  │         │ │
│  └────┬────┘  └─────┬─────┘  └────┬─────┘  └────┬────┘ │
└───────┼────────────┼────────────┼────────────┼───────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────┐
│                    Gateway (独立进程)                     │
│  ┌────────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │ MessageRouter │ │SessionMgr│  │  AgentPool         │   │
│  └────────────┘  └──────────┘  └──────┬────────────┘   │
└─────────────────────────────────────────┼───────────────┘
                                          │
        ┌─────────────────────────────────┼────────────────┐
        │           Brain Layer           │                │
        │  ┌─────────────────────────────────────────┐   │
        │  │           Agent                           │   │
        │  │  ┌─────┐  ┌──────┐  ┌─────┐  ┌─────────┐  │   │
        │  │  │ LLM │  │ Loop │  │Tools│  │ Memory  │  │   │
        │  │  └─────┘  └──────┘  └─────┘  └────┬────┘  │   │
        │  └───────────────────────────────────┼───────┘   │
        └──────────────────────────────────────┼───────────┘
                                               │
        ┌──────────────────────────────────────┼────────────────┐
        │            Body Layer                 │                │
        │  ┌──────────┐  ┌────────┐  ┌──────┐  ┌───────────┐    │
        │  │ Builtin  │  │ Skills │  │ MCP  │  │ Plugins   │    │
        │  │ Tools    │  │        │  │      │  │           │    │
        │  └──────────┘  └────────┘  └──────┘  └───────────┘    │
        └──────────────────────────────────────────────────────┘
```

---

## 二、Gateway 架构

### 2.1 Gateway 是独立进程

```
python main.py start    → 启动 Gateway (后台守护进程)
zclaw start             → 启动 Gateway (后台守护进程)

Gateway 运行在: ws://127.0.0.1:8080/api/ws/gateway
PID 文件: ~/.Zclaw/gateway.pid
```

### 2.2 客户端连接 Gateway

```
python main.py          → 连接 Gateway REPL 对话
zclaw                   → 连接 Gateway REPL 对话

zclaw status            → 查看 Gateway 状态
zclaw stop              → 停止 Gateway
```

---

## 三、启动模式

### Gateway 管理命令

| 命令 | 说明 |
|------|------|
| `python main.py start` | 启动 Gateway（后台守护进程） |
| `python main.py stop` | 停止 Gateway |
| `python main.py restart` | 重启 Gateway |
| `python main.py status` | 查看 Gateway 状态 |
| `python main.py` | 连接 Gateway REPL 对话 |

### 入口点

| 入口 | 说明 |
|------|------|
| `python main.py` | 统一入口（管理+客户端） |
| `zclaw` | CLI 入口（需安装） |
| `python -m src.web.gateway_server` | 直接启动 Gateway |

---

## 四、核心组件

### 4.1 GatewayManager (`src/channel/gateway_manager.py`)

Gateway 进程管理器，负责生命周期管理。

```python
class GatewayManager:
    def start(daemon=True) -> bool    # 启动 Gateway
    def stop() -> bool                # 停止 Gateway
    def restart() -> bool             # 重启 Gateway
    def status() -> dict              # 获取状态
    def is_running() -> bool          # 检查是否运行
```

### 4.2 GatewayClient (`src/channel/gateway_client.py`)

WebSocket 客户端，连接 Gateway 实现 REPL 对话。

```python
class GatewayClient:
    def connect() -> None             # 连接 Gateway
    def chat(message: str)           # 发送消息，yield 事件
    def run_repl()                    # 运行 REPL 对话界面
```

### 4.3 Gateway (`src/channel/gateway.py`)

消息网关核心，负责消息接收、归一化、路由。

```python
class Gateway:
    def handle_message(channel_name, raw_message)
    def set_agent_pool(pool)
    def register_channel(channel)
    def start() / shutdown()
```

### 4.4 AgentPool (`src/brain/agent_pool.py`)

管理 Agent 实例生命周期。

```python
class AgentPool:
    def acquire_agent(agent_id) -> Agent   # 获取/创建 Agent
    def release_agent(agent_id)            # 释放 Agent
    def cleanup_idle()                     # 清理空闲 Agent
```

---

## 五、环境配置

`.env` 配置项：

```env
# Gateway 配置
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8080
GATEWAY_PID_DIR=~/.Zclaw
GATEWAY_STARTUP_TIMEOUT=10

# LLM 配置
ZCLAW_PROVIDER=minmax
ZCLAW_MODEL=MiniMax-M2.7
ZCLAW_API_KEY=your_api_key
ZCLAW_BASE_URL=https://api.minimaxi.com/v1
```

---

## 六、消息协议

### WebSocket 消息格式

**客户端发送：**
```json
{"type": "chat", "data": {"message": "...", "agent_id": "default"}}
{"type": "cancel", "data": {}}
{"type": "command", "data": {"command": "...", "args": {...}}}
```

**服务端推送：**
```json
{"type": "stream_delta", "data": {"content": "..."}}
{"type": "tool_start", "data": {"id": "...", "name": "..."}}
{"type": "tool_end", "data": {"id": "...", "name": "...", "success": true}}
{"type": "usage", "data": {"prompt_tokens": 100, "completion_tokens": 50}}
{"type": "done", "data": null}
{"type": "error", "data": {"message": "..."}}
```

---

## 七、关键代码文件索引

| 组件 | 文件 |
|------|------|
| 入口 | [main.py](main.py) |
| CLI 命令 | [src/cli/commands.py](src/cli/commands.py) |
| Gateway 管理器 | [src/channel/gateway_manager.py](src/channel/gateway_manager.py) |
| Gateway 客户端 | [src/channel/gateway_client.py](src/channel/gateway_client.py) |
| Gateway 核心 | [src/channel/gateway.py](src/channel/gateway.py) |
| WebSocket 服务 | [src/web/gateway_server.py](src/web/gateway_server.py) |
| Agent 池 | [src/brain/agent_pool.py](src/brain/agent_pool.py) |
| Agent | [src/core/agent.py](src/core/agent.py) |
| AgentLoop | [src/core/loop.py](src/core/loop.py) |
| Tools | [src/tools/registry.py](src/tools/registry.py) |
| Skills | [src/skills/manager.py](src/skills/manager.py) |
| MCP | [src/mcp/manager.py](src/mcp/manager.py) |
| Memory | [src/memory/coordinator.py](src/memory/coordinator.py) |
| 渲染器 | [src/cli/renderer.py](src/cli/renderer.py) |

---

## 八、架构设计决策

### 8.1 为什么 Gateway 是独立进程？

1. **稳定性**：Gateway 崩溃不会影响客户端
2. **资源管理**：Agent 实例复用，避免重复初始化
3. **多客户端**：支持多个客户端同时连接
4. **IM 对接**：便于集成到 IM 通讯工具（如 Telegram）

### 8.2 为什么客户端通过 WebSocket 连接？

1. **解耦**：客户端与 Gateway 独立演进
2. **流式**：天然支持流式响应
3. **协议统一**：同一协议支持 CLI、Web、IM 等多种客户端