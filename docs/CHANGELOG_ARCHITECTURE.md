# Zclaw 架构优化更改记录

## 更改日期

2026-04-21

## 更改概述

本次更改实现了 Zclaw 架构优化的核心部分：

1. **新增 AgentPool** - 替代 AgentFactory，实现 Agent 实例池化管理
2. **新增 StdioChannel** - 为 CLI 模式提供标准输入/输出通道
3. **Gateway 支持 AgentPool** - Gateway 使用 AgentPool 管理 Agent 生命周期
4. **统一启动入口** - main.py 支持多种启动模式

---

## 详细更改

### 1. 新增 AgentPool（src/brain/agent_pool.py）

**目的**：解决每次消息都创建新 Agent 实例的问题，实现 Agent 实例复用。

**核心功能**：
- `get_agent(agent_id)` - 获取或创建 Agent 实例（单例模式）
- `release_agent(agent_id)` - 释放 Agent（标记为空闲）
- `hibernate_agent(agent_id)` - 休眠 Agent（释放内存）
- `dispose_agent(agent_id)` - 销毁 Agent 实例
- `cleanup_idle()` - 定期清理空闲 Agent

**状态机**：
```
CREATING → ACTIVE → IDLE → DORMANT → DISPOSED
                    ↓
                  (可重新激活)
```

**关键设计**：
- 每个 agent_id 对应一个 Agent 实例（不复用 session）
- 实例按需创建，空闲超时后休眠
- 有最大实例数限制（默认 10）
- 支持并发获取（asyncio.Lock）

### 2. 新增 StdioChannel（src/channel/channels/stdio.py）

**目的**：将标准输入/输出封装为 Channel 接口，使 CLI 模式可以接入 Gateway。

**核心功能**：
- `start()` / `stop()` - 启动/停止通道
- `send(message)` - 发送消息到 stdout
- `on_message(callback)` - 注册消息回调
- `process_input(user_input)` - 处理用户输入

### 3. Gateway 使用 AgentPool（src/channel/gateway.py）

**更改点**：
- `__init__` 新增参数：`agents_dir`, `max_idle_seconds`, `max_agent_instances`
- 替换 `_agent_factory` 为 `_agent_pool`
- `set_agent_factory()` → `set_agent_pool()`
- `handle_message()` 使用 `agent_pool.get_agent()` 和 `release_agent()`
- `handle_cron_task()` 同样使用 AgentPool
- `get_status()` 新增 AgentPool 状态

### 4. gateway_server.py 更新（src/web/gateway_server.py）

**更改点**：
- `initialize_gateway()` 创建 AgentPool 替代 AgentFactory
- 新增 `enable_stdio` 参数
- `_handle_gateway_chat()` 使用 `agent_pool.get_agent()` 和 `release_agent()`
- `reload` 命令使用新的 AgentPool
- 新增 `start_gateway_stdio()` 函数

### 5. main.py 统一启动入口（main.py）

**新增启动模式**：
```bash
# 原有的 .env 模式（保持不变）
python main.py

# Gateway WebSocket/HTTP 模式
python main.py --gateway --port 8080

# Gateway STDIO 模式（交互式 CLI）
python main.py --stdio

# 单次提问模式（保持不变）
python main.py --prompt "hello"
```

---

## 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `src/brain/agent_pool.py` | Agent 实例池管理器 |
| `src/channel/channels/stdio.py` | STDIO 通道适配器 |
| `tests/test_agent_pool.py` | AgentPool 测试（19 个测试）|
| `tests/test_stdio_channel.py` | StdioChannel 测试（21 个测试）|

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/channel/gateway.py` | 使用 AgentPool 替代 AgentFactory |
| `src/web/gateway_server.py` | 集成 AgentPool，新增 STDIO 模式支持 |
| `main.py` | 统一启动入口，支持多种启动模式 |

---

## 测试验证

所有测试通过（40 个测试）：
- AgentPool: 19 个测试
- StdioChannel: 21 个测试

```bash
python -m pytest tests/test_agent_pool.py tests/test_stdio_channel.py -v
```

---

## 架构对比

### 更改前

```
Gateway.handle_message():
  1. agent = await self._agent_factory(agent_id)  # 每次创建新实例！
  2. response = await agent.chat(...)
  3. return response
```

### 更改后

```
Gateway.handle_message():
  1. agent = await self._agent_pool.get_agent(agent_id)  # 复用实例
  2. response = await agent.chat(...)
  3. await self._agent_pool.release_agent(agent_id)  # 标记空闲
  4. return response
```

---

## 向后兼容

- 原有的 `python main.py` 启动方式保持不变
- 原有 `python scripts/start_gateway.py` 启动方式保持不变
- AgentFactory 暂未删除（保留兼容）

---

## 待完成任务

1. [ ] AgentFactory 完全废弃（目前仅未使用）
2. [ ] CLI App 重构使用 StdioChannel（当前保持原有模式）
3. [ ] Telegram/WebSocket Channel 接入 Gateway（部分已实现）

---

## 相关文档

- [PROJECT_TRACKING.md](PROJECT_TRACKING.md) - 项目追踪文档