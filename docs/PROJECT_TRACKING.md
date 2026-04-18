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
- **浏览器自动化**: Playwright（待实现）
- **持久化**: SQLite + JSON + YAML

## 项目现状（扩展前）

| 模块 | 状态 | 说明 |
|------|------|------|
| LLM 路由 | ✅ 完成 | 支持多 Provider + Fallback |
| 工具系统 | ✅ 完成 | 28 个内置工具 + Registry |
| 分层记忆 | ✅ 完成 | L0-L4 架构，SQLite 持久化 |
| 安全审计 | ✅ 完成 | 权限分级 + 危险检测 + 审计日志 |
| Skills 系统 | ✅ 完成 | SKILL.md 格式，支持触发词匹配 |
| MCP 协议 | ✅ 完成 | Stdio/SSE 双传输模式 |
| Web 接口 | ✅ 完成 | FastAPI + WebSocket |
| CLI REPL | ✅ 完成 | Rich 渲染 + 命令历史 |

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

**提交**: 待提交

---

## 阶段二：24 小时持续运行

**目标**: 实现 Cron 调度器 + Heartbeat 心跳 + Gateway 常驻进程 + 休眠唤醒

**时间**: 2-3 周

### 子任务

- [x] 2.1 实现 Cron 调度器（`src/body/cron.py`） - **已实现（Phase 1 中）**
- [x] 2.2 实现 Heartbeat 心跳管理器 - **已实现（Phase 1 中）**
- [ ] 2.3 重构 Gateway 为常驻进程
- [ ] 2.4 实现 Session 休眠/唤醒机制
- [ ] 2.5 实现优雅关闭（Signal 处理）
- [ ] 2.6 编写 Phase 2 测试用例
- [ ] 2.7 验收测试

**完成日期**: -

**提交**: -

---

## 阶段三：浏览器自动化

**目标**: 实现 Playwright 浏览器控制 + Screenshot + OCR

**时间**: 2 周

### 子任务

- [ ] 3.1 安装 Playwright 依赖
- [ ] 3.2 实现 BrowserTool（`src/tools/builtin/browser_tool.py`）
- [ ] 3.3 实现 browser_navigate
- [ ] 3.4 实现 browser_click / browser_type
- [ ] 3.5 实现 browser_screenshot
- [ ] 3.6 实现 browser_get_content
- [ ] 3.7 实现 ScreenCapture（平台相关截屏）
- [ ] 3.8 实现 ProcessTool
- [ ] 3.9 编写 Phase 3 测试用例
- [ ] 3.10 验收测试

**完成日期**: -

**提交**: -

---

## 阶段四：进程管理 + 文件监听

**目标**: 实现 ProcessTool + FileWatcher + WebhookReceiver

**时间**: 2 周

### 子任务

- [ ] 4.1 实现 ProcessTool（启动/停止/监控）
- [ ] 4.2 实现 FileWatcher
- [ ] 4.3 实现 WebhookReceiver
- [ ] 4.4 事件驱动唤醒 Agent
- [ ] 4.5 编写 Phase 4 测试用例
- [ ] 4.6 验收测试

**完成日期**: -

**提交**: -

---

## 阶段五：多 Agent 架构

**目标**: 实现 AgentRegistry + Agent 间通信 + Sub-Agent

**时间**: 3-4 周

### 子任务

- [ ] 5.1 实现 AgentRegistry
- [ ] 5.2 实现路由规则动态配置
- [ ] 5.3 实现 InterAgentMessenger
- [ ] 5.4 实现 SubAgent 生命周期管理
- [ ] 5.5 编写 Phase 5 测试用例
- [ ] 5.6 验收测试

**完成日期**: -

**提交**: -

---

## 更新日志

| 日期 | 阶段 | 更新内容 |
|------|------|---------|
| 2026-04-18 | - | 项目启动，编写追踪文档 |
| 2026-04-18 | Phase 1 | 完成 Channel/Brain/Body 三层架构基础实现 |
