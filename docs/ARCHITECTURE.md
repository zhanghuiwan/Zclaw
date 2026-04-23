# Zclaw 项目架构文档

## 一、三层架构

项目采用 **Body Layer / Brain Layer / Channel Layer** 三层架构（见 [src/channel/gateway.py:26-28](src/channel/gateway.py#L26-L28)）：

```
Channel Layer (入口)
    ↓
Gateway (消息网关)
    ↓
Brain Layer (AgentPool + Agent)
    ↓
Body Layer (工具/记忆/MCP/Skills)
```

---

## 二、两种启动模式

### 模式1：`python main.py`（直接对话）

```
main.py
  → chat_loop() 创建 Agent(settings)
  → agent.chat_stream(user_input)
    → agent._memory.perceive()
    → agent._loop.run_stream()
      → llm.chat_stream()  ←→ LLM
      → tools.execute()   ←→ Tools/MCP/Skills
    → agent._memory.archive_turn()
```

### 模式2：`python main.py --gateway`（WebSocket 服务）

```
main.py
  → _run_gateway_mode()
    → gateway_server.create_gateway_app()
      → initialize_gateway()
        → Gateway(storage_path, agents_dir)
        → AgentPool(agents_dir)  ← 替代 AgentFactory
        → gateway.set_agent_pool(pool)
    → uvicorn.Server.serve()

WebSocket 请求到达时：
  → websocket_gateway() 接收请求
  → _handle_gateway_chat()
    → gateway._agent_pool.acquire_agent(agent_id)  ← 获取/创建 Agent
    → agent.chat_stream(message)
      → 流式事件通过 WebSocket 发送
    → gateway._agent_pool.release_agent(agent_id)  ← 释放
```

---

## 三、Agent 创建流程（核心对比）

| 步骤 | `python main.py` | `python main.py --gateway` |
|------|-------------------|---------------------------|
| 入口 | [main.py:343](main.py#L343) `Agent(settings)` | [gateway_server.py:70](src/web/gateway_server.py#L70) `AgentPool(agents_dir)` |
| 配置 | `load_settings_from_env()` | `load_settings(use_env=True)` |
| 工具 | `_init_builtin_tools()` 注册内置工具 | 同左 |
| Skills | `_init_skills()` → `get_skill_tools()` → `_tools.register_many()` | 同左 |
| MCP | `init_mcp()` **未调用** | [agent_pool.py:246-250](src/brain/agent_pool.py#L246-L250) `await agent.init_mcp()` ✅ |
| Loop | `AgentLoop(llm, tools, ...)` | 同左 |

**关键差异**：MCP 初始化在 AgentPool 中修复（刚提交）。

---

## 四、消息处理流程

### Chat 模式

```
用户输入
  → PromptSession.prompt_async()
  → agent.chat_stream()
      → _memory.perceive(user_input)
      → _loop.run_stream()
          → llm.chat_stream(messages, tools)
          → 处理 tool_calls
          → _execute_tool_calls()
      → _memory.extract_and_store()
```

### Gateway 模式

```
WebSocket 消息
  → websocket_gateway() 解析 JSON
  → _handle_gateway_chat()
      → agent_pool.acquire_agent()
      → agent.chat_stream()
          → yield StreamEvent (CONTENT_DELTA / TOOL_EXECUTE_START / ...)
          → WebSocket 推送 events
      → agent_pool.release_agent()
```

---

## 五、AgentPool 如何管理 Agent 实例

[agent_pool.py:276-364](src/brain/agent_pool.py#L276-L364)：

```python
acquire_agent(agent_id):
    1. _ensure_config_loaded(agent_id)  ← 加载 SOUL.md / USER.md / AGENTS.md
    2. 获取锁（asyncio.Lock）
    3. 如果实例存在且 ACTIVE → 等待空闲
    4. 如果实例 DORMANT → 重建 Agent
    5. 如果 AgentLoop 状态非 IDLE → 重置为 IDLE（修复状态同步）
    6. 标记 ACTIVE，返回 agent

release_agent(agent_id):
    1. 标记 IDLE
    2. 释放锁
```

---

## 六、Tools 系统

[agent.py:202-218](src/core/agent.py#L202-L218) 注册顺序：

```python
1. Builtin tools (file_tools, search_tools, shell_tools, ...)
2. Plugin tools (from src/plugins/loader.py)
3. MCP tools (via init_mcp())
4. Skill tools (via _init_skills())
```

Tools 通过 [loop.py:160-220](src/core/loop.py#L160-L220) 执行：

```python
_execute_single_tool():
    1. 检查权限 (permission_manager.check())
    2. 检查缓存 (safe 工具)
    3. tools.execute()
    4. 写入缓存
    5. 记录审计日志
```

---

## 七、记忆系统

[agent.py:108-128](src/core/agent.py#L108-L128)：

```python
MemoryCoordinator (V4 分层架构)
  ├── L0: 感知层 (perceive)
  ├── L1: 语义记忆 (semantic)
  ├── L2: 情景记忆 (episodic)
  ├── L3: 程序记忆 (procedural)
  └── L4: 元认知 (meta-cognitive)
```

---

## 八、使用流程图

```
┌─────────────────────────────────────────────────────────┐
│                    Channel Layer                         │
│  ┌─────────┐  ┌───────────┐  ┌──────────┐  ┌─────────┐ │
│  │  CLI    │  │ WebSocket │  │ Telegram │  │ STDIO   │ │
│  │(main.py)│  │(gateway)  │  │          │  │         │ │
│  └────┬────┘  └─────┬─────┘  └────┬─────┘  └────┬────┘ │
└───────┼────────────┼────────────┼────────────┼───────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────┐
│                    Gateway                               │
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

## 九、关键代码文件索引

| 组件 | 文件 |
|------|------|
| 入口 | [main.py](main.py) |
| Gateway | [src/channel/gateway.py](src/channel/gateway.py) |
| AgentPool | [src/brain/agent_pool.py](src/brain/agent_pool.py) |
| Agent | [src/core/agent.py](src/core/agent.py) |
| AgentLoop | [src/core/loop.py](src/core/loop.py) |
| Tools | [src/tools/registry.py](src/tools/registry.py) |
| Skills | [src/skills/manager.py](src/skills/manager.py) |
| MCP | [src/mcp/manager.py](src/mcp/manager.py) |
| Memory | [src/memory/coordinator.py](src/memory/coordinator.py) |
| Web Server | [src/web/gateway_server.py](src/web/gateway_server.py) |