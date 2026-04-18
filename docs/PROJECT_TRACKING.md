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
| 2026-04-18 | Phase 1 | 完成 Channel/Brain/Body 三层架构基础实现 |
| 2026-04-18 | Phase 2 | 完成 24 小时持续运行核心功能验证 |
| 2026-04-18 | Phase 3 | 完成浏览器自动化 (Playwright) |
| 2026-04-18 | Phase 4 | 完成进程管理和文件监听 |
| 2026-04-18 | Phase 5 | 完成多 Agent 架构所有阶段 |
