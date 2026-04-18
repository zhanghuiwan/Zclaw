# Zclaw → OpenClaw 风格扩展项目追踪

## 项目总目标

将 Zclaw 从"Claude Code 风格 AI 编程助手"扩展为类似 OpenClaw 的**全天候自主 Agent 工具**，具备：
- 24 小时持续运行能力（定时触发 + 事件驱动）
- 本地软件操控能力（浏览器、Shell、进程管理）
- 多会话与多 Agent 管理
- SOUL.md/AGENTS.md/USER.md 纯文本配置体系

## 技术栈

- **语言**: Python 3.11+
- **核心框架**: FastAPI + asyncio + pydantic
- **LLM**: OpenAI 兼容协议（阿里百炼、本地 Ollama 等）
- **浏览器自动化**: Playwright ✅
- **持久化**: SQLite + JSON + YAML
- **文件监听**: watchdog ✅

## 项目现状（扩展后）

| 模块 | 状态 | 说明 |
|------|------|------|
| Channel/Brain/Body 架构 | ✅ 完成 | 三层架构重构 |
| SOUL.md/AGENTS.md/USER.md | ✅ 完成 | 纯文本配置体系 |
| Gateway 常驻进程 | ✅ 完成 | 支持 Cron/Heartbeat |
| Session 管理 | ✅ 完成 | 归档/恢复/休眠/唤醒 |
| 浏览器自动化 | ✅ 完成 | Playwright 封装 |
| 进程管理 | ✅ 完成 | ProcessTool |
| 文件监听 | ✅ 完成 | FileWatcher |
| 多 Agent 架构 | ✅ 完成 | AgentRegistry |
| Agent 间通信 | ✅ 完成 | InterAgentMessenger |
| 子代理支持 | ✅ 完成 | SubAgentManager |

---

## 阶段一：架构重构（Channel/Brain/Body + SOUL.md）

**目标**: 建立 Channel/Brain/Body 三层架构 + SOUL.md/AGENTS.md/USER.md 配置体系

**时间**: 2-3 周

### 子任务

- [x] 1.1 创建 `src/channel/` 目录结构
- [x] 1.2 创建 `src/brain/` 目录结构
- [x] 1.3 创建 `src/body/` 目录结构
- [x] 1.4 实现 SOUL.md 加载器
- [x] 1.5 实现 AGENTS.md 加载器
- [x] 1.6 实现 USER.md 加载器
- [x] 1.7 实现消息归一化（MessageNormalizer）
- [x] 1.8 实现消息路由器（MessageRouter）
- [x] 1.9 重构 Session Manager（支持归档/恢复）
- [x] 1.10 实现 Context Assembler（上下文组装）
- [x] 1.11 编写 Phase 1 测试用例
- [x] 1.12 验收测试

**完成日期**: 2026-04-18

**提交**: 095139c

---

## 阶段二：24 小时持续运行

**目标**: 实现 Cron 调度器 + Heartbeat 心跳 + Gateway 常驻进程 + 休眠唤醒

**时间**: 2-3 周

### 子任务

- [x] 2.1 实现 Cron 调度器（`src/body/cron.py`） - **已实现（Phase 1 中）**
- [x] 2.2 实现 Heartbeat 心跳管理器 - **已实现（Phase 1 中）**
- [x] 2.3 重构 Gateway 为常驻进程 - **已实现（Phase 1 中）**
- [x] 2.4 实现 Session 休眠/唤醒机制 - **已实现（Phase 1 中）**
- [x] 2.5 实现优雅关闭（Signal 处理） - **已实现（Phase 1 中）**
- [x] 2.6 编写 Phase 2 测试用例
- [x] 2.7 验收测试

**完成日期**: 2026-04-18

**提交**: ef3cbe6

---

## 阶段三：浏览器自动化

**目标**: 实现 Playwright 浏览器控制 + Screenshot

**时间**: 2 周

### 子任务

- [x] 3.1 安装 Playwright 依赖
- [x] 3.2 实现 BrowserTool（`src/tools/builtin/browser_tool.py`）
- [x] 3.3 实现 browser_navigate
- [x] 3.4 实现 browser_click / browser_type
- [x] 3.5 实现 browser_screenshot
- [x] 3.6 实现 browser_get_content
- [x] 3.7 实现浏览器导航控制（back/forward/reload）
- [x] 3.8 实现 BrowserToolExecutor
- [x] 3.9 编写 Phase 3 测试用例
- [x] 3.10 验收测试

**完成日期**: 2026-04-18

**提交**: b9d7064

---

## 阶段四：进程管理 + 文件监听

**目标**: 实现 ProcessTool + FileWatcher

**时间**: 2 周

### 子任务

- [x] 4.1 实现 ProcessTool（启动/停止/监控）
- [x] 4.2 实现 FileWatcher
- [x] 4.3 编写 Phase 4 测试用例
- [x] 4.4 验收测试

**完成日期**: 2026-04-18

**提交**: e9b5050

---

## 阶段五：多 Agent 架构

**目标**: 实现 AgentRegistry + Agent 间通信 + Sub-Agent

**时间**: 3-4 周

### 子任务

- [x] 5.1 实现 AgentRegistry
- [x] 5.2 实现路由规则动态配置
- [x] 5.3 实现 InterAgentMessenger
- [x] 5.4 实现 SubAgent 生命周期管理
- [x] 5.5 编写 Phase 5 测试用例
- [x] 5.6 验收测试

**完成日期**: 2026-04-18

**提交**: ee447cc

---

## 全部阶段完成总结

### 新增文件

```
src/channel/           # Channel 层
  __init__.py
  gateway.py          # 统一消息网关
  router.py          # 消息路由器
  normalizer.py      # 消息归一化
  channels/
    __init__.py
    base.py         # 通道适配器基类
    web.py          # WebSocket 适配器

src/brain/            # Brain 层
  __init__.py
  soul_loader.py     # SOUL.md 加载器
  user_profile.py    # USER.md 加载器
  agents_config.py    # AGENTS.md 加载器
  session.py         # Session 管理器
  context.py         # 上下文组装器
  agent_registry.py  # Agent 注册表
  inter_agent.py    # Agent 间通信
  sub_agent.py      # 子代理管理

src/body/             # Body 层
  __init__.py
  cron.py            # Cron 调度器
  heartbeat.py      # 心跳管理器
  file_watcher.py   # 文件监听器

src/tools/builtin/
  browser_tool.py   # 浏览器自动化工具
  process_tool.py   # 进程管理工具

agents/default/       # 默认 Agent 配置
  SOUL.md
  AGENTS.md
  USER.md

tests/
  validate_phase1.py
  validate_phase2.py
  validate_phase3.py
  validate_phase4.py
  validate_phase5.py
```

### 新增依赖

- `croniter>=2.0.0` - Cron 表达式解析
- `playwright>=1.40.0` - 浏览器自动化
- `watchdog>=3.0.0` - 文件监听

### 测试覆盖

- Phase 1: 19 个测试通过
- Phase 2: 8 个测试通过
- Phase 3: 9 个测试通过
- Phase 4: 8 个测试通过
- Phase 5: 10 个测试通过

---

## 更新日志

| 日期 | 阶段 | 更新内容 |
|------|------|---------|
| 2026-04-18 | - | 项目启动，编写追踪文档 |
| 2026-04-18 | Phase 1-5 | 完成基础架构模块 |
| 2026-04-18 | Phase 6 | 补充文档，分析架构缺口 |

---

## Phase 6：架构补全与 24 小时运行接入

**目标**: 完成 Gateway 与现有 Agent 的连接，实现真正的 24 小时自主运行

### 当前架构缺口分析

```
现有架构（已完成）:
┌─────────────────────────────────────────────────────┐
│                    Gateway                            │
│  (已实现: 消息路由、Cron调度、心跳、Session管理)       │
└─────────────────────────────────────────────────────┘
           │                                        ▲
           │  缺少连接                               │ 缺少连接
           ▼                                        │
┌─────────────────────────────────────────────────────┐
│              Agent Core (现有 src/core/agent.py)     │
│  (已实现: chat(), tools, memory, skills)          │
└─────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│              Tool Registry (现有)                    │
│  + 新增 BrowserTool, ProcessTool                   │
└─────────────────────────────────────────────────────┘
```

### 缺口列表

| 缺口 | 优先级 | 说明 |
|------|--------|------|
| 6.1 AgentFactory 连接 | P0 | 将 Gateway 与现有 Agent 类连接 |
| 6.2 FastAPI Webhook 入口 | P0 | 接收外部请求（HTTP/WebSocket）|
| 6.3 多通道适配器完善 | P1 | Telegram/WhatsApp/Slack Webhook |
| 6.4 WebhookReceiver | P1 | 接收外部事件触发 |
| 6.5 启动脚本/服务化 | P1 | systemd/Docker 部署配置 |
| 6.6 现有工具注册到新架构 | P0 | 将 BrowserTool/ProcessTool 注册到 Agent |

### 6.1 AgentFactory 连接（最优先）

**问题**: Gateway 的 `set_agent_factory()` 需要一个异步工厂函数，但尚未实现。

**目标**: 实现 `agent_factory(agent_id: str) -> Agent`

```python
# 目标：在 Gateway 中调用
agent = await self._agent_factory("default")

# 需要实现：
# 1. 从 agents/default/ 目录加载配置
# 2. 创建 Agent 实例并注入配置
# 3. 注册 BrowserTool, ProcessTool 等新工具
```

**文件**: 需要在 `src/channel/gateway.py` 或新文件 `src/brain/agent_factory.py` 中实现

### 6.2 FastAPI Webhook 入口

**问题**: Gateway 没有 HTTP/WebSocket 入口，无法接收外部请求。

**目标**: 在 `src/web/` 基础上增加与 Gateway 的集成

**文件**: `src/web/gateway_integration.py`

```python
# 需要的端点:
POST /webhook/telegram     # Telegram Bot API
POST /webhook/github       # GitHub Webhook
POST /webhook/gcal        # Google Calendar
WS   /ws/gateway          # WebSocket 连接到 Gateway
GET  /api/gateway/status   # Gateway 状态查询
```

### 6.3 多通道适配器完善

**问题**: 只有 WebSocket 适配器，其他通道未实现。

**目标**: 实现各通道的 Webhook 接收

| 通道 | 优先级 | Webhook 格式 |
|------|--------|--------------|
| Telegram | P1 | `POST /webhook/telegram` + Bot API |
| WhatsApp | P2 | Cloud API Webhook |
| Slack | P2 | `POST /webhook/slack` Events API |
| GitHub | P1 | `POST /webhook/github` |

**文件**: `src/channel/channels/telegram.py` 等

### 6.4 WebhookReceiver

**目标**: 统一接收外部 Webhook 事件

**文件**: `src/body/webhook.py`

```python
class WebhookReceiver:
    """Webhook 事件接收器"""
    
    async def handle_github(self, payload: dict) -> None:
        """处理 GitHub Webhook"""
        
    async def handle_gcal(self, payload: dict) -> None:
        """处理 Google Calendar 事件"""
        
    async def handle_file_change(self, event: FileWatchEvent) -> None:
        """处理文件变化事件"""
```

### 6.5 启动脚本/服务化

**目标**: 提供生产环境部署方案

**文件**:
- `scripts/start_gateway.py` - 直接启动脚本
- `deploy/systemd/zclaw-gateway.service` - systemd 服务配置
- `Dockerfile.gateway` - Docker 镜像
- `docker-compose.yml` - 完整部署

### 6.6 现有工具注册到新架构

**问题**: BrowserTool, ProcessTool 需要注册到 Agent 的 ToolRegistry

**目标**: 在 Agent 初始化时加载新工具

**文件**: `src/core/agent.py` 或 `src/tools/registry.py`

---

## 待开发子任务

### P0 - 必须完成（才能启动 Gateway）

- [x] 6.1.1 实现 AgentFactory 类 ✅
- [x] 6.1.2 将 BrowserTool 注册到 Agent ✅
- [x] 6.1.3 将 ProcessTool 注册到 Agent ✅
- [x] 6.2.1 实现 Gateway 与 FastAPI 的连接 ✅
- [x] 6.2.2 实现 WebSocket Gateway 端点 ✅

### P1 - 重要（多通道支持）

- [x] 6.3.1 实现 Telegram 适配器 ✅
- [x] 6.3.2 实现 GitHub Webhook 处理 ✅
- [x] 6.4.1 实现 WebhookReceiver 类 ✅
- [x] 6.5.1 创建 systemd 服务文件 ✅
- [x] 6.5.2 创建 Docker 部署配置 ✅

### P2 - 可选（增强功能）

- [ ] 6.3.3 实现 WhatsApp 适配器
- [ ] 6.3.4 实现 Slack 适配器

---

## 启动 24 小时运行的步骤

### 1. 加载 Agent 配置
```python
from src.brain.agent_factory import AgentFactory

factory = AgentFactory()
await factory.load_agents_from_directory("agents")
```

### 2. 连接到 Gateway
```python
gateway.set_agent_factory(factory.create_agent)
```

### 3. 启动 Web 服务
```python
# 接收 Telegram/Slack 等通道的消息
from src.web.gateway_server import start_gateway_server
await start_gateway_server(gateway)
```

### 4. Gateway 主循环
```python
await gateway.start()
await gateway.wait_for_shutdown()
```

---

## 架构现状图

```
                    外部请求
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Web Server (src/web/)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Telegram │  │  GitHub  │  │ WebSocket│  │  REST    │       │
│  │ Webhook  │  │  Webhook │  │  端点    │  │   API    │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
└───────┼─────────────┼─────────────┼─────────────┼──────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │    Gateway      │
                    │  (已实现)       │
                    └────────┬───────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ CronScheduler │ │HeartbeatMgr │ │SessionMgr    │
    └──────────────┘ └──────────────┘ └──────────────┘
                             │
                             ▼
                    ┌────────────────┐
                    │  AgentFactory │ ◄── 缺失
                    └────────┬───────┘
                             │
                             ▼
                    ┌────────────────┐
                    │     Agent      │ ◄── 现有 src/core/agent.py
                    │   (已实现)     │
                    └────────┬───────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ ToolRegistry │ │   Memory     │ │    LLM      │
    │ (需扩展)     │ │  Coordinator │ │   Router    │
    └──────────────┘ └──────────────┘ └──────────────┘
            │
            ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │ BrowserTool  │ │ ProcessTool  │ │  其他工具   │
    │ (已实现)     │ │ (已实现)     │ │              │
    └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 实施顺序建议

```
Step 1: 实现 AgentFactory (2-3 小时)
  └─ 连接到 Gateway

Step 2: 实现 WebSocket Gateway 端点 (2-3 小时)  
  └─ FastAPI + Gateway 集成

Step 3: 注册新工具到 Agent (1-2 小时)
  └─ BrowserTool, ProcessTool

Step 4: 测试完整流程 (2-3 小时)
  └─ 启动 Gateway，发送消息，验证响应

Step 5: 实现 Telegram 适配器 (4-6 小时)
  └─ Webhook 接收 + Bot API 发送

Step 6: systemd 服务化 (2-3 小时)
  └─ 生产环境部署
```

---

## 更新日志

| 日期 | 阶段 | 更新内容 |
|------|------|---------|
| 2026-04-18 | - | 项目启动，编写追踪文档 |
| 2026-04-18 | Phase 1-5 | 完成基础架构模块 |
| 2026-04-18 | Phase 6 | 补充文档，分析架构缺口，制定补全计划 |
| 2026-04-18 | Phase 6 | 完成 P0 任务：AgentFactory、WebSocket Gateway 端点、工具注册 |
| 2026-04-18 | Phase 6 | 完成 P1 任务：Telegram 适配器、GitHub Webhook、WebhookReceiver、systemd/Docker 部署 |
