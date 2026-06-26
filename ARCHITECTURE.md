# Zclaw 项目完整技术文档

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [模块详解](#3-模块详解)
4. [当前已实现功能一览](#4-当前已实现功能一览)
5. [后续开发方向](#5-后续开发方向)

---

## 1. 项目概述

### 1.1 什么是 Zclaw？

Zclaw 是一个结合 **Claude Code** 与 **OpenClaw** 思想的 AI 编程助手。Claude Code 部分已基本完成，核心功能包括：工具调用循环、多层安全防护、分层记忆系统、智能上下文管理等。

当前正积极开发类似 OpenClaw 的自主 Agent 能力，包括 24 小时持续运行、本地软件操控、多 Agent 架构等。

### 1.2 核心特点

| 特性 | 描述 |
|------|------|
| **多模型支持** | 统一的 OpenAI 兼容接口，支持阿里百炼、本地 Ollama 等任意兼容服务 |
| **工具调用循环** | Agent Loop 机制，LLM 可自主决定调用哪些工具、调用多少轮 |
| **分层安全** | 三级危险等级（safe/confirm/dangerous）+ 路径限制 + 命令拦截 + 用户确认 |
| **持久记忆** | 五层分层架构（L0-L4），Agent 驱动的自主探索，状态与历史分离 |
| **智能上下文** | 自动检测并压缩长对话，适配不同模型的 token 限制 |
| **插件扩展** | 用户可通过编写 Python 文件自定义工具 |
| **默认简易 CLI** | `Zclaw` 与 `python main.py` 共用同一启动实现，支持 REPL 模式和单次命令模式 |

### 1.3 技术栈

```
Python 3.11+
├── pydantic / pydantic-settings  — 数据校验与配置管理
├── openai SDK                    — LLM 调用（OpenAI 兼容协议）
├── rich                          — 终端美化渲染
├── prompt-toolkit                — 交互式输入（历史、补全、快捷键）
├── pyyaml                        — 配置文件解析
└── asyncio                       — 异步并发执行
```

### 1.4 项目结构

```
Zclaw/
├── config.example.yaml           # 配置示例文件
├── pyproject.toml                # 项目元数据与依赖
├── src/
│   ├── __init__.py
│   ├── config/                   # 配置管理
│   │   └── settings.py
│   ├── llm/                      # LLM 抽象层
│   │   ├── models.py             # 数据模型（Message, Response, ToolCall...）
│   │   ├── base.py               # BaseProvider 抽象基类
│   │   ├── openai_compat.py      # OpenAI 兼容实现
│   │   └── router.py             # LLM 路由器（多提供者管理）
│   ├── core/                     # 核心引擎
│   │   ├── state.py              # 状态机
│   │   ├── loop.py               # Agent 循环（工具调用循环）
│   │   ├── agent.py              # Agent 主类（顶层协调器）
│   │   ├── plan.py               # 计划数据结构
│   │   └── planner.py            # 任务规划器
│   ├── tools/                    # 工具系统
│   │   ├── base.py               # BaseTool 抽象基类 + ToolResult
│   │   ├── registry.py           # 工具注册表
│   │   ├── cache.py              # 工具结果缓存（LRU）
│   │   └── builtin/              # 内置工具
│   │       ├── file_tools.py     # 文件操作（read/write/edit）
│   │       ├── search_tools.py   # 搜索（directory/file_search）
│   │       ├── shell_tool.py     # Shell 命令执行
│   │       ├── grep_tool.py      # 正则内容搜索
│   │       ├── glob_tool.py      # Glob 模式匹配
│   │       ├── multi_edit_tool.py # 批量编辑（原子操作）
│   │       ├── line_edit_tool.py  # 行号级编辑
│   │       ├── diff_tool.py      # Diff 预览 + 文件快照
│   │       ├── git_tool.py       # Git 集成
│   │       └── ast_tool.py       # 语法感知编辑
│   ├── sandbox/
│   │   └── runner.py             # 命令运行器（超时、输出控制）
│   ├── security/                 # 安全系统
│   │   ├── permission.py         # 权限管理器
│   │   ├── validator.py          # 输入校验 + 输出清洗
│   │   └── audit.py              # 审计日志
│   ├── memory/                   # 记忆模块
│   │   ├── config.py             # 配置类
│   │   ├── coordinator.py        # 记忆协调器
│   │   ├── extractor.py          # LLM 提取器
│   │   ├── layers/              # 分层实现
│   │   │   ├── l0_perceptual.py  # RingBuffer
│   │   │   ├── l1_working.py    # 会话快照
│   │   │   ├── l2_episodic.py   # SQLite-VSS
│   │   │   ├── l3_semantic.py   # JSON 当前状态
│   │   │   └── l4_procedural.py # YAML 规则
│   │   └── tools/              # 记忆工具
│   │       ├── episodic_search.py # 搜索历史
│   │       └── memory_tools.py   # 更新记忆
│   ├── context/                  # 上下文管理
│   │   ├── budget.py             # Token 预算计算
│   │   ├── compressor.py         # 对话历史压缩
│   │   └── manager.py            # 上下文管理器
│   ├── prompt/                   # 提示词工程
│   │   ├── templates.py          # 模板库
│   │   └── builder.py            # 动态组装器
│   ├── mcp/                      # MCP 协议
│   │   ├── types.py              # 数据类型
│   │   ├── transport.py          # 传输层
│   │   ├── client.py             # MCP 客户端
│   │   ├── adapter.py            # 工具适配器
│   │   └── manager.py            # MCP 管理器
│   ├── plugins/                  # 插件系统
│   │   └── loader.py             # 插件加载器
│   ├── skills/                   # Skills 模块
│   │   ├── config.py             # 配置管理
│   │   ├── executor.py           # Skill 执行器
│   │   ├── loader.py             # Skill 发现与加载
│   │   ├── manager.py            # Skill 管理器
│   │   ├── models.py             # 数据模型
│   │   ├── registry.py           # Skill 注册表
│   │   └── tool.py               # Skill 工具包装
│   ├── web/                      # Web UI
│   │   ├── server.py             # FastAPI 应用
│   │   ├── routes.py             # API 路由
│   │   ├── schemas.py            # 数据模型
│   │   ├── ws_manager.py         # WebSocket 管理
│   │   └── static/               # 前端静态文件
│   └── cli/                      # CLI 界面
│       ├── app.py                # REPL 入口
│       ├── renderer.py           # Rich 渲染器
│       ├── session.py            # 会话管理器
│       └── cost_tracker.py       # Token 用量追踪
└── tests/                        # 验证测试
```

---

## 2. 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI Layer (REPL)                       │
│  prompt-toolkit 输入  │  Rich 渲染输出  │  命令处理 (/help)  │
└──────────────┬──────────────────────────────────────────────┘
               │ user_input
               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent (协调器)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Planner  │ │  Memory   │ │ Context  │ │ PluginLoader │  │
│  │ 规划器   │ │  记忆     │ │ 上下文   │ │ 插件系统     │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Loop (核心循环)                      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  1. 将消息列表发送给 LLM                              │    │
│  │  2. LLM 返回响应（文本 / 工具调用请求）               │    │
│  │  3. 如有工具调用 → 权限检查 → 执行工具               │    │
│  │  4. 将工具结果注入消息列表                            │    │
│  │  5. 回到步骤 1（最多 50 轮）                         │    │
│  │  6. 如无工具调用 → 返回最终响应                       │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  安全检查: PermissionManager + AuditLogger                    │
│  工具缓存: ToolResultCache (LRU, safe 工具)                  │
│  并行执行: safe 工具 asyncio.gather                          │
└──────────┬──────────────┬──────────────────┬────────────────┘
           │              │                  │
           ▼              ▼                  ▼
    ┌────────────┐ ┌────────────┐   ┌────────────────┐
    │  LLM 层     │ │  工具系统   │   │  上下文管理     │
    │  Router     │ │  Registry  │   │  ContextManager │
    │  Provider   │ │  28 tools  │   │  TokenBudget    │
    │  Fallback   │ │  Cache     │   │  Compressor     │
    └────────────┘ └────────────┘   └────────────────┘
```

### 2.2 数据流

```
用户输入 "帮我修复 bug X"
    │
    ▼
REPL 接收 → Agent.chat_stream()
    │
    ▼
AgentLoop.run_stream()
    │
    ├─ ContextManager.prepare_messages() — 检查是否需要压缩
    │
    ├─ LLMRouter.chat_stream(messages, tools)
    │      │
    │      ├─ Provider: OpenAICompatProvider → dashscope/Ollama API
    │      └─ 失败 → 自动回退到下一个 Provider
    │
    ├─ 收到 StreamEvent (content_delta / tool_call)
    │
    ├─ 如有 tool_calls:
    │      │
    │      ├─ 分离 safe / non-safe 工具
    │      │
    │      ├─ safe 工具 → asyncio.gather() 并行执行
    │      │      └─ 检查 ToolResultCache → 命中则直接返回
    │      │
    │      ├─ non-safe 工具 → 串行执行
    │      │      └─ PermissionManager.check() → 可能触发用户确认
    │      │
    │      └─ AuditLogger.log() 记录审计信息
    │
    ├─ 将工具结果注入消息列表 (MessageRole.TOOL)
    │
    └─ 循环回到 LLM 调用（下一轮）
```

### 2.3 状态机

```
    ┌───────┐
    │ IDLE  │ ◄────────────────────────────┐
    └───┬───┘                               │
        │                                   │
        ├──→ PLANNING ──→ EXECUTING         │
        │                    │               │
        │                    ├──→ DONE ──────┘
        │                    │
        │                    ├──→ WAITING_CONFIRMATION ──→ EXECUTING
        │                    │
        │                    └──→ ERROR ─────┘
        │
        └──→ EXECUTING (直接执行，不经过规划)
```

合法转换规则由 `_VALID_TRANSITIONS` 字典定义，非法转换会抛出 `StateTransitionError`。

---

## 3. 模块详解

### 3.1 配置管理 (config)

**文件**: `src/config/settings.py`

#### 核心类

| 类 | 职责 |
|---|------|
| `ProviderConfig` | 单个 LLM 提供者的配置（base_url, api_key, model, max_context_tokens, supports_*） |
| `LLMConfig` | LLM 全局配置（default_provider, fallback_providers, temperature, max_tokens, providers 字典） |
| `AgentConfig` | Agent 行为配置（max_loop_rounds=50, planning_mode） |
| `MemoryConfig` | 记忆引擎配置（storage_path, working_memory_max_tokens, episodic_max_age_days） |
| `ContextConfig` | 上下文管理配置（safety_margin_ratio=0.1） |
| `SecurityConfig` | 安全配置（path_restrictions, auto_approve, audit_log, blocked_patterns） |
| `Settings` | 顶层配置容器，组合以上所有子配置 |

#### 配置加载优先级

```
CLI 参数 > 环境变量 > 项目级 .Zclaw.yaml > 全局 ~/.Zclaw/config.yaml > 默认值
```

#### 关键设计

- **环境变量替换**: YAML 中支持 `${DASHSCOPE_API_KEY}` 语法，由 `_resolve_env_vars()` 递归替换
- **深度合并**: `_deep_merge()` 支持用 overrides 部分覆盖配置而不影响其他字段
- **路径发现**: `_find_config_file()` 优先查找当前目录的 `.Zclaw.yaml`，再查 `~/.Zclaw/config.yaml`

---

### 3.2 LLM 层 (llm)

#### 3.2.1 数据模型 (`models.py`)

| 类 | 描述 |
|---|---|
| `Message` | 聊天消息，包含 role, content, tool_calls, tool_call_id；可序列化为 OpenAI 格式 |
| `Response` | LLM 响应，包含 content, tool_calls, finish_reason, usage |
| `ToolCall` | 工具调用请求（id, name, arguments） |
| `ToolDefinition` | 工具定义（name, description, parameters） |
| `Usage` | Token 使用量（prompt/completion/total），支持 `+` 运算符累加 |
| `StreamEvent` | 流式事件（type + data），11 种事件类型 |
| `LLMError` 及子类 | 异常层次：ConnectionError(recoverable), AuthError, RateLimitError, ResponseError |

**StreamEventType 枚举**:
```
基础: CONTENT_DELTA, TOOL_CALL_START/DELTA/END, USAGE, DONE, ERROR
P1+: TOOL_EXECUTE_START/END, LOOP_START
```

#### 3.2.2 Provider 抽象 (`base.py`)

`BaseProvider` 是所有 LLM 提供者的抽象基类：

```python
class BaseProvider(ABC):
    async def chat(messages, tools, temperature, max_tokens) -> Response
    async def chat_stream(messages, tools, ...) -> AsyncIterator[StreamEvent]
    def count_tokens(messages) -> int  # 默认实现: 1 token ≈ 4 chars
```

每个 Provider 持有 name, base_url, api_key, model 等属性。

#### 3.2.3 OpenAI 兼容实现 (`openai_compat.py`)

`OpenAICompatProvider` 使用 `openai.AsyncOpenAI` SDK，通过配置不同的 `base_url` 连接任意兼容服务：

- **百炼**: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **Ollama**: `http://localhost:11434/v1`
- **其他**: Azure OpenAI、vLLM、LiteLLM 等任何兼容服务

流式实现逐 chunk 解析 `content_delta`、`tool_call_delta` 等，完整复现 OpenAI streaming 协议。

#### 3.2.4 路由器 (`router.py`)

`LLMRouter` 管理多个 Provider 实例，提供统一调用接口：

```python
router = LLMRouter(config.llm)
response = await router.chat(messages, tools)  # 自动回退
```

**回退机制**:
1. 优先使用 `default_provider`
2. 如果失败且异常标记为 `recoverable`，自动尝试 `fallback_providers` 列表中的下一个
3. `AuthError` 等不可恢复异常直接抛出

工厂函数 `create_provider()` 目前只创建 `OpenAICompatProvider`，可扩展为根据配置选择不同实现。

---

### 3.3 核心引擎 (core)

#### 3.3.1 状态机 (`state.py`)

6 种状态：`IDLE → PLANNING → EXECUTING → WAITING_CONFIRMATION → DONE/ERROR`

`AgentStateMachine` 维护当前状态，支持：
- `transition(new_state)`: 执行状态转换（非法则抛异常）
- `on_change(callback)`: 注册监听器，状态变化时触发

#### 3.3.2 Agent 循环 (`loop.py`)

`AgentLoop` 是 Zclaw 的心脏，实现工具调用循环：

**同步模式 `run()`**:
```
user_input → 注入消息 → while(max_rounds):
    ├─ context.prepare_messages() 自动压缩
    ├─ llm.chat(messages, tools)
    ├─ 如有 tool_calls:
    │      ├─ _execute_tool_calls() — 并行 safe / 串行 non-safe
    │      └─ _inject_tool_results() — 注入 tool 消息
    └─ 如无 tool_calls → return response
```

**流式模式 `run_stream()`**:
```
同上，但 llm.chat_stream() 逐 chunk yield StreamEvent
工具执行前后分别 yield TOOL_EXECUTE_START/END
每轮循环开始 yield LOOP_START
```

**安全集成**:
- 每个工具执行前调用 `_check_permission()`
- 权限检查结果记录到 `_log_audit()`
- safe 工具执行后结果写入 `ToolResultCache`

**并行执行**:
```python
safe_calls = [tc for tc in tool_calls if danger == "safe"]
results = await asyncio.gather(*[execute(tc) for tc in safe_calls])
sequential = [tc for tc in tool_calls if danger != "safe"]
for tc in sequential: await execute(tc)
# 最终按原始顺序排列结果
```

#### 3.3.3 Agent 主类 (`agent.py`)

`Agent` 是顶层协调器，在 `__init__` 中初始化所有子模块：

```python
self._llm = LLMRouter(settings.llm)
self._tools = ToolRegistry()           # + 注册 28 个内置工具
self._plugin_loader = PluginLoader()   # + 加载插件工具
self._permissions = PermissionManager()
self._audit = AuditLogger()
self._memory = MemoryCoordinator()     # V4 分层记忆 + 记忆工具
self._context = ContextManager()
self._planner = Planner()
self._prompt_builder = PromptBuilder()
self._loop = AgentLoop(...)            # 将以上模块注入循环
```

对外提供统一接口：
- `agent.chat(user_input) -> Response`
- `agent.chat_stream(user_input) -> AsyncIterator[StreamEvent]`
- 各种 property 访问子模块

#### 3.3.4 规划器 (`planner.py` + `plan.py`)

**Plan 数据结构**:
```python
@dataclass Plan:
    goal: str                           # 计划目标
    steps: list[PlanStep]               # 步骤列表
    status: str                         # active / completed / abandoned

    def advance() -> PlanStep           # 推进到下一步
    def fail_current(error)             # 标记当前步骤失败
    def format_status() -> str          # 格式化为可读文本
    def to_dict() / from_dict()         # 序列化
```

**Planner**:
- `create_plan_from_steps(goal, steps)`: 从步骤列表创建计划
- `parse_plan_from_text(goal, text)`: 从 LLM 文本输出中解析 JSON 计划
- `advance()` / `fail_current()`: 推进/标记计划
- `get_context()`: 获取当前计划状态文本，用于注入 LLM 上下文
- `get_plan_request_prompt()`: 生成请求 LLM 规划的 prompt

---

### 3.4 工具系统 (tools)

#### 3.4.1 基类 (`base.py`)

```python
class BaseTool:
    name: str                           # 工具名称（唯一标识）
    description: str                    # 给 LLM 看的描述
    parameters: list[ToolParameter]     # 参数定义
    metadata: ToolMetadata              # 元数据（category, danger_level, timeout）

    async def execute(**kwargs) -> ToolResult  # 子类实现
    def to_openai_tool() -> dict                # 转换为 OpenAI function schema
```

**DangerLevel 枚举**:
- `SAFE`: 只读操作（file_read, directory, grep, glob），自动批准
- `CONFIRM`: 有副作用的操作（file_write, file_edit, shell），需用户确认
- `DANGEROUS`: 高危操作（动态检测，如 `rm -rf /`），始终需确认

**ToolResult**: 统一的结果包装器，包含 success, content, error, metadata。

#### 3.4.2 注册表 (`registry.py`)

`ToolRegistry` 管理所有工具的生命周期：

- `register(tool)` / `register_many(tools)`: 注册工具
- `execute(name, arguments)`: 执行工具（含参数校验、异常捕获、统计）
- `to_openai_tools()`: 获取所有工具的 OpenAI 格式定义
- `get_stats()`: 获取执行统计

#### 3.4.3 工具结果缓存 (`cache.py`)

`ToolResultCache` 是 LRU 缓存层：

```python
cache = ToolResultCache(max_size=256, ttl_seconds=300)
cache.get(tool_name, args)   # 查询
cache.put(tool_name, args, result)  # 写入
```

- **缓存键**: `SHA256(tool_name + JSON(args))`，确定性生成
- **TTL**: 默认 300 秒过期
- **淘汰**: OrderedDict 实现 LRU，超出 max_size 时淘汰最老
- **只缓存**: 成功的 safe 工具结果
- **统计**: hits/misses/evictions/hit_rate

#### 3.4.4 内置工具 (28 个)

| 工具 | 类别 | 危险等级 | 功能 |
|------|------|---------|------|
| `file_read` | file | safe | 读取文件内容，支持 offset/limit 分段读取 |
| `file_write` | file | confirm | 创建新文件或完全覆盖 |
| `file_edit` | file | confirm | 精确替换文件中的旧文本为新文本 |
| `multi_edit` | file | confirm | 对同一文件原子执行多处替换 |
| `line_edit` | file | confirm | 按行号范围替换/插入/删除 |
| `line_read` | file | safe | 按行号范围读取，显示行号 |
| `diff` | file | safe | 文本/文件差异比较（unified/并排格式） |
| `snapshot` | file | confirm | 文件快照管理（save/list/restore/delete） |
| `directory` | search | safe | 列出目录内容（隐藏文件跳过） |
| `file_search` | search | safe | 按文件名或内容搜索文件 |
| `grep` | search | safe | 正则表达式搜索，支持 include/exclude glob、上下文行 |
| `glob` | search | safe | Glob 模式匹配查找文件（如 `**/*.py`） |
| `shell` | system | confirm/dangerous | 执行 Shell 命令，动态检测危险模式 |
| `git_diff` | git | safe | diff unstaged/staged/commit/file |
| `git_commit` | git | confirm | add + commit + amend |
| `git_log` | git | safe | 提交历史，支持作者/日期/分支过滤 |
| `git_status` | git | safe | 仓库状态 |
| `git_branch` | git | confirm | 分支管理 |
| `git_show` | git | safe | 提交详情 |
| `git_blame` | git | safe | 行级修改信息 |
| `code_structure` | ast | safe | AST 代码结构分析（brief/normal/full） |
| `symbol_find` | ast | safe | 按名称查找符号定义 |
| `symbol_edit` | ast | confirm | 按符号名称精确替换 |
| `import_analyze` | ast | safe | 导入依赖分析 + 未使用检测 |
| `search_conversation_history` | memory | safe | 搜索历史对话 |
| `get_session_history` | memory | safe | 获取特定会话历史 |
| `update_memory` | memory | safe | 更新持久化记忆 |
| `set_preference` | memory | safe | 设置用户偏好 |

**Multi-edit 原子性**: 先 dry-run 验证所有 `old_text` 都存在，全部验证通过才写入，否则不修改文件（零副作用）。

**Shell 危险检测**: 内置正则匹配 `rm -rf /`、`sudo`、`mkfs`、`dd if=`、`:(){ :|` 等危险模式，匹配后动态将危险等级提升为 `DANGEROUS`。

---

### 3.5 沙箱执行 (sandbox)

**文件**: `src/sandbox/runner.py`

`CommandRunner` 在受控环境中执行 Shell 命令：

| 特性 | 实现 |
|------|------|
| **超时控制** | `subprocess.run(timeout=N)`，超时返回 `timed_out=True` |
| **输出截断** | stdout/stderr 各限制 100,000 字符 |
| **ANSI 清理** | 正则移除终端转义码 `\x1b[...` |
| **工作目录** | 支持指定 workdir |
| **返回值** | 成功返回 content，失败返回 error + exit code |

---

### 3.6 安全系统 (security)

Zclaw 采用多层次安全机制，包括危险等级判定、路径限制、命令拦截、输入校验、输出清洗和审计日志。

#### 3.6.1 三级危险等级 (DangerLevel)

定义于 `src/tools/base.py:15-19` 和 `src/security/permission.py:33-37`：

```python
class DangerLevel(str, Enum):
    SAFE = "safe"       # 自动批准
    CONFIRM = "confirm" # 需用户确认
    DANGEROUS = "dangerous"  # 始终确认
```

#### 3.6.2 权限管理器 (PermissionManager)

`src/security/permission.py` 实现五级判定流程：

```
请求进入
    │
    ├─► 1. 检查 auto_approve 列表 ──► ALLOW
    │
    ├─► 2. 检查 blocked_patterns ──► DENY
    │
    ├─► 3. 检查路径限制 ──► DENY (如违反)
    │
    └─► 4. 按危险等级处理:
            ├── safe     ──► ALLOW (自动)
            ├── confirm  ──► CONFIRM (回调或 auto_confirm)
            └── dangerous ──► CONFIRM (无回调时需确认)
```

**回调机制**: `ConfirmCallback = Callable[[PermissionRequest], Awaitable[bool]]`，CLI 层注册回调 (`set_confirm_callback`)，在终端弹出 `[y/N]` 确认提示。

#### 3.6.3 路径限制 (Path Restrictions)

配置于 `src/config/settings.py:82-95`：

```python
path_restrictions: dict[str, list[str]] = {
    "allow": ["."],   # 白名单：当前目录
    "deny": ["/etc", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys"],  # 黑名单
}
```

实现逻辑 (`src/security/permission.py:210-240`)：
- 解析相对路径为绝对路径
- 检查是否在 deny 列表目录下
- 检查是否在 allow 列表目录外
- **仅作用于文件工具**: `file_read`, `file_write`, `file_edit`

#### 3.6.4 危险命令拦截

配置于 `src/config/settings.py:93-95`：

```python
blocked_patterns: list[str] = [
    r"rm\s+-rf\s+/",   # 递归删除根目录
    r"sudo\s+",        # 提权命令
    r"mkfs",           # 文件系统格式化
    r"dd\s+if=",       # 磁盘直接读写
    r":\(\)\{",        # Fork 炸弹
]
```

Shell 工具额外模式 (`src/tools/builtin/shell_tool.py:26-31`)：

```python
_DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/", r"\brm\s+-rf\s+\*", r"\bsudo\s+",
    r"\bmkfs\b", r"\bdd\s+if=", r":\(\)\{\s*:\|",
    r"\bchmod\s+777\s+/", r"\bshutdown\b", r"\breboot\b", r"\binit\s+0\b",
]
```

#### 3.6.5 输入校验 (InputValidator)

`src/security/validator.py` 提供以下校验：

| 方法 | 检测内容 |
|------|---------|
| `validate_path()` | 路径穿越 (`../`, `..\`)、空路径、非法绝对路径 |
| `validate_command()` | 空命令、过多链式命令 (`;`) |
| `validate_length()` | 最大长度限制 |
| `validate_file_size()` | 最大文件大小 (默认 1MB) |

#### 3.6.6 输出清洗 (OutputSanitizer)

`src/security/validator.py:18-100`：

```python
# 敏感信息脱敏
_SENSITIVE_PATTERNS = [
    (re.compile(r'(?:api[_-]?key|apikey|secret|token|password)\s*[=:]\s*["\']?[\w\-]{20,}'), "***REDACTED***"),
    (re.compile(r'Bearer\s+[\w\-\.]{20,}'), "Bearer ***REDACTED***"),
    (re.compile(r'(?:AKIA|ASIA)[A-Z0-9]{16}'), "***AWS_KEY***"),
]

# 控制字符清理：保留 \n\r\t，过滤 ASCII < 32
# 输出截断：最大 50,000 字符

# 完整清洗管道
def sanitize(text):
    text = clean_control_chars(text)
    text = redact_sensitive(text)
    text = truncate(text)
    return text
```

#### 3.6.7 审计日志 (AuditLogger)

`src/security/audit.py` 将所有工具调用追加到 JSONL 文件：

```
~/.Zclaw/audit/2026-04-12_a38db586.jsonl
```

**日志格式**：

```json
{
  "timestamp": "2026-04-12T10:30:00",
  "session_id": "abc123",
  "tool_name": "file_write",
  "arguments": {"path": "/tmp/test.py", "content": "..."},
  "danger_level": "confirm",
  "permission_decision": "ALLOW",
  "permission_auto": false,
  "execution_success": true,
  "duration_ms": 15,
  "user_message_context": "帮我创建测试文件"
}
```

**自动脱敏**: `password`, `token`, `api_key`, `secret`, `private_key` 等字段。

#### 3.6.8 安全配置参考

```yaml
security:
  # 危险等级细化
  danger_levels:
    shell:
      level: dangerous  # 可改为 dangerous
      auto_approve_patterns:  # 允许自动执行的命令白名单
        - "^git "
        - "^ls "
        - "^pwd "

  # 路径限制增强
  path_restrictions:
    allow: ["."]
    deny: ["/etc", "/usr", "/bin", "/sbin", "/boot", "/proc", "/sys"]

  # 审计日志
  audit_log: true
  audit_log_path: ~/.Zclaw/audit
```

---

### 3.7 记忆模块 (memory)

#### 3.7.1 核心设计理念

架构从**"系统驱动的 RAG"**转变为**"Agent 驱动的自主探索"**：

- **状态与记忆分离**: 身份、偏好等全局状态是"活"的当前值，只保留最新态，强制注入；而历史对话是不可变的"档案"，按需探索
- **极简上下文**: System Prompt 只注入绝对必要的当前状态和硬性规则，将上下文窗口留给 Agent 推理
- **工具化访问**: L2 历史记忆通过工具暴露，Agent 自主规划何时查询

#### 3.7.2 五层架构

```
┌────────────────────────────────────────────────────────────────┐
│                      L0: 感知缓冲 Perceptual Buffer            │
│  生命周期: 单轮    | 存储: 内存 RingBuffer     | 用途: 原始输入暂存  │
├────────────────────────────────────────────────────────────────┤
│                      L1: 工作记忆 Working Memory                │
│  生命周期: 会话级  | 存储: 内存 + 会话快照文件  | 用途: 当前任务上下文  │
├────────────────────────────────────────────────────────────────┤
│                      L2: 情景记忆 Episodic Memory (工具化)       │
│  生命周期: 永久    | 存储: SQLite + 向量索引     | 用途: 历史对话档案  │
├────────────────────────────────────────────────────────────────┤
│                      L3: 语义与状态记忆 Semantic & State         │
│  生命周期: 永久    | 存储: 结构化JSON           | 用途: 项目知识与当前态│
├────────────────────────────────────────────────────────────────┤
│                      L4: 过程记忆 Procedural Memory              │
│  生命周期: 永久    | 存储: YAML规则文件          | 用途: 行为宪法与规程│
└────────────────────────────────────────────────────────────────┘
```

#### 3.7.3 各层详解

**L0: PerceptualBuffer** (`layers/l0_perceptual.py`)
- RingBuffer 实现，`deque(maxlen=N)`
- 每轮对话捕获原始输入/输出
- Agent 不自动检索，通过工具按需访问

**L1: WorkingMemory** (`layers/l1_working.py`)
- 会话快照：`task_description`, `active_files`, `pending_goals`, `completed_goals`
- JSON 文件存储在 `.memory/L1_working/sessions/{session_id}.json`
- 不跨会话持久化

**L2: EpisodicMemory** (`layers/l2_episodic.py`)
- 不可变档案，仅 `append()` 无 `update()`
- SQLite 时间线索引 + sqlite-vss 向量索引
- Schema: `episodes(id, session_id, timestamp, role, content, summary, tool_calls)`
- `search()`: 文本过滤 + 向量相似度混合搜索
- `get_session_history()`: 获取特定会话历史

**L3: SemanticMemory** (`layers/l3_semantic.py`)
- 仅存储当前状态，覆盖写入，无历史
- `UserProfile`: name, preferences, preferred_language, preferred_code_style
- `ProjectProfile`: tech_stack, architecture, conventions
- `format_for_system_prompt()`: 格式化注入文本

**L4: ProceduralMemory** (`layers/l4_procedural.py`)
- YAML 规则文件，`global_rules.yaml` + `project_rules.yaml`
- 永不自动修改，仅手动编辑
- `format_for_system_prompt()`: 格式化为规则文本

#### 3.7.4 记忆协调器 (`coordinator.py`)

`MemoryCoordinator` 统一协调各层：

```python
# 各层访问
memoryCoordinator.semantic     # L3 当前状态
memoryCoordinator.procedural  # L4 规则
memoryCoordinator.perceptual  # L0 RingBuffer
memoryCoordinator.working     # L1 会话快照
memoryCoordinator.episodic    # L2 历史档案

# 系统提示词构建 (L4 + L3 + L1)
context = memoryCoordinator.build_system_prompt_context()
```

#### 3.7.5 记忆工具

**search_conversation_history** (`tools/episodic_search.py`)
- 搜索历史对话，Agent 主动调用而非系统自动注入
- 参数: `query`, `session_id` (optional), `limit`

**get_session_history** (`tools/episodic_search.py`)
- 获取特定会话的完整历史

**update_memory** (`tools/memory_tools.py`)
- 更新 L3 持久化记忆（用户/项目）
- 参数: `category` ("user"|"project"), `data` (object)

**set_preference** (`tools/memory_tools.py`)
- 设置单个用户偏好键值对

#### 3.7.6 LLMExtractor 适配

提取器接口保持不变，内部逻辑分发到各层：

```
if type == "preference":
    semantic.set_preference(key, value)
elif type == "fact":
    working.add_extracted_fact(content)
elif type == "episode":
    episodic.archive_turn(role="extracted", content=content)
```

#### 3.7.7 存储结构

```
.memory/
├── L1_working/
│   └── sessions/*.json        # 会话快照
├── L2_episodic/
│   └── timeline.db            # SQLite: 时间线 + 向量索引
├── L3_semantic/
│   ├── user_profile.json      # 用户当前状态
│   └── project_profile.json   # 项目当前状态
└── L4_procedural/
    ├── global_rules.yaml      # 全局规则
    └── project_rules.yaml     # 项目规则
```

---

### 3.8 上下文管理 (context)

#### 3.8.1 Token 预算 (`budget.py`)

`TokenBudget` 计算 token 使用情况：

- `total`: 最大上下文长度（从 Provider config 获取，如 131072）
- `available`: `total × (1 - safety_margin_ratio)`，实际可用量
- `estimate_tokens(messages)`: 粗略估算（1 token ≈ 4 chars）
- `usage_ratio(messages)`: 已使用占比
- `remaining(messages)`: 剩余可用 token

#### 3.8.2 压缩器 (`compressor.py`)

`ContextCompressor` 的压缩策略：

```
原始: [system] [msg1] [msg2] ... [msg20] [msg21] [msg22] [msg23] [msg24]
                         ↑──── 旧消息 ────↑ ↑───── 保留最近 4 轮 ─────↑

压缩后: [system] [摘要消息] [ack] [msg21] [msg22] [msg23] [msg24]
```

- 保留所有 system 消息
- 保留最近 `keep_recent_rounds` 轮（默认 4 轮 = 8 条消息）
- 旧消息提取摘要（每条截取前 200 字符，最多 10 条，总长 ≤ 2000 字符）
- 摘要以 `[Previous conversation summary]` 标记注入

#### 3.8.3 管理器 (`manager.py`)

`ContextManager` 组合预算和压缩器：

```python
ctx.prepare_messages(messages)      # 超过 80% 自动压缩
ctx.prepare_messages(messages, force_compress=True)  # 强制压缩
ctx.should_compress(messages)       # 检查是否需要压缩
ctx.get_usage_info(messages)        # 获取使用统计
```

自动压缩阈值：`usage_ratio >= 0.8`

---

### 3.9 提示词工程 (prompt)

#### 3.9.1 模板库 (`templates.py`)

提供 3 个预定义模板：

- **DEFAULT_PERSONA**: 完整的 system prompt（核心能力 + 行为规则 + 输出格式）
- **COMPACT_PERSONA**: 精简版（用于压缩后的上下文）
- **TOOL_GUIDE_SECTION**: 工具使用指南段落

#### 3.9.2 构建器 (`builder.py`)

`PromptBuilder` 动态组装 system prompt：

```python
builder = PromptBuilder(persona=DEFAULT_PERSONA)
builder.add_section("Project Rules", "Always use type hints.")
prompt = builder.build(tool_names=["file_read", "shell"], memory_context="...")
```

最终 prompt 结构：
```
[Persona 模板]
[工具指南]
[记忆上下文]
[自定义 Section 1]
[自定义 Section 2]
...
```

---

### 3.10 MCP 协议 (mcp)

#### 3.10.1 数据类型 (`types.py`)

| 类 | 描述 |
|---|---|
| `MCPServerConfig` | MCP 服务器配置（command, args, env, transport） |
| `MCPTransportType` | 传输类型枚举（stdio, sse） |
| `MCPToolDefinition` | MCP 工具定义（name, description, inputSchema） |

#### 3.10.2 传输层 (`transport.py`)

支持两种传输模式：

- **StdioTransport**: 通过子进程 stdio 通信，适合本地 MCP 服务器
- **SSETransport**: 通过 HTTP SSE 通信，适合远程 MCP 服务器

#### 3.10.3 MCP 客户端 (`client.py`)

`MCPClient` 实现：
- 连接握手（initialize）
- 工具发现（tools/list）
- 工具调用（tools/call）
- Ping 健康检查

#### 3.10.4 工具适配器 (`adapter.py`)

`MCPToolWrapper` 将 MCP 工具适配为 Zclaw 的 `BaseTool`：
- schema 参数转换为 `ToolParameter` 列表
- 工具执行结果转换为 `ToolResult`
- 工具名称添加 `mcp_` 前缀避免冲突

#### 3.10.5 MCP 管理器 (`manager.py`)

`MCPManager` 管理所有 MCP 服务器连接：
- 配置加载
- 服务器连接/断开
- 工具注册到 Agent

---

### 3.11 插件系统 (plugins)

**文件**: `src/plugins/loader.py`

`PluginLoader` 从 `~/.Zclaw/plugins/` 目录扫描 `.py` 文件，使用 `importlib` 动态加载：

```python
loader = PluginLoader()
plugins = loader.scan()           # 扫描（不加载）
tools = loader.load_all()         # 加载所有
loader.reload()                   # 重新加载（热重载）
```

**插件编写规范**:
```python
# ~/.Zclaw/plugins/my_tool.py
from src.tools.base import BaseTool, ToolResult, ToolParameter, DangerLevel, ToolMetadata

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "A custom tool"
    parameters = [ToolParameter(name="input", type="string", description="Input", required=True)]
    metadata = ToolMetadata(category="custom", danger_level=DangerLevel.SAFE)

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(f"Result: {kwargs['input']}")
```

加载器自动发现文件中所有 `BaseTool` 子类并实例化。

---

### 3.12 Skills 模块 (skills)

#### 3.12.1 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| `SkillsConfig` | config.py | Skill 目录配置 |
| `SkillRegistry` | registry.py | Skill 注册表 |
| `SkillLoader` | loader.py | 发现与加载 SKILL.md |
| `SkillExecutor` | executor.py | Skill 执行器 |
| `SkillManager` | manager.py | 统一管理器 |
| `SkillTool` | tool.py | Skill 作为 Tool 包装 |

#### 3.12.2 SKILL.md 格式

```markdown
---
name: amap-lbs-skill
description: 高德地图综合服务
version: "1.0.0"
metadata:
  triggers: ["地图", "POI", "路径", "导航"]
  requires:
    env:
      - AMAP_API_KEY
    bins:
      - curl
  primaryEnv: AMAP_API_KEY
  homepage: https://lbs.amap.com/
---
# 技能说明

你的技能描述内容...
```

#### 3.12.3 核心功能

| 功能 | 描述 |
|------|------|
| 自动匹配 | 根据触发词自动匹配相关 Skills |
| 上下文注入 | 将匹配的 Skill 内容注入到 LLM 上下文 |
| 依赖检查 | 自动检查环境变量和二进制程序 |
| 热重载 | 支持重新加载 Skills |
| 工具包装 | Skill 可作为 Tool 被 Agent 调用 |

---

### 3.13 Web UI (web)

#### 3.13.1 Web 服务器 (`server.py`)

FastAPI 应用，支持：
- WebSocket 实时通信
- REST API 端点
- 静态文件服务

#### 3.13.2 WebSocket 管理器 (`ws_manager.py`)

| 功能 | 描述 |
|------|------|
| 连接管理 | 连接/断开、连接列表 |
| 消息发送 | JSON 消息发送、广播 |
| 权限请求/响应 | confirm/dangerous 工具的用户确认 |

#### 3.13.3 API 路由 (`routes.py`)

| 端点 | 方法 | 描述 |
|------|------|------|
| `/ws` | GET | WebSocket 连接 |
| `/api/chat` | POST | 发送消息 |
| `/api/files` | GET/POST | 文件操作 |
| `/api/tools` | GET | 工具列表 |
| `/api/sessions` | GET/POST/DELETE | 会话管理 |
| `/api/config` | GET | 配置信息 |

#### 3.13.4 前端 (`static/`)

- `index.html`: 主 SPA 页面
- `css/style.css`: 暗色主题样式
- `js/app.js`: WebSocket 通信、Markdown 渲染

---

### 3.14 CLI 界面 (cli)

#### 3.14.1 默认简易 REPL (`simple.py` / `main.py`)

`Zclaw` console script 指向 `src.cli.simple:main`，根目录 `main.py` 只做薄包装并转发到同一个实现。因此两种启动方式在配置加载、权限策略、交互命令上保持一致。

**支持的命令**:

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助 |
| `/clear` | 清空对话历史 |
| `/undo` | 撤销上一轮对话 |
| `/info` | 显示当前配置 |
| `/quit` `/exit` | 退出 |

**非交互模式**:
```bash
Zclaw -p "列出当前目录的文件"
python main.py -p "列出当前目录的文件"
```

完整 Rich REPL 仍保留在 `src.cli.app`，可通过 `python -m src.cli.app` 启动。

#### 3.14.2 渲染器 (`renderer.py`)

`Renderer` 使用 Rich 库实现美观的终端输出：

- 自定义主题 `AGENT_THEME`（cyan=用户, green=助手, magenta=工具, red=错误）
- Banner、状态栏、分隔线
- Markdown 渲染（助手回复）
- 工具执行动画（开始/结束状态）
- 权限确认面板
- 工具列表表格
- 审计日志统计

#### 3.14.3 会话管理 (`session.py`)

`SessionManager` 支持保存/恢复对话历史：

```
~/.Zclaw/sessions/
├── my_session_20260407_153000.json
└── another_20260407_160000.json
```

- `save(messages, name, session_id)`: 保存为 JSON
- `load(session_id)`: 加载（支持前缀匹配）
- `list_sessions()`: 列出所有会话
- `delete(session_id)`: 删除会话

#### 3.14.4 费用追踪 (`cost_tracker.py`)

`CostTracker` 记录每轮 token 使用：

```python
tracker.record_round(prompt_tokens=100, completion_tokens=200)
tracker.get_total()             # 总 token 数
tracker.get_average_per_round() # 平均每轮
tracker.estimate_cost(0.5, 1.5) # 估算费用（输入/输出每百万 token 价格）
tracker.get_summary()           # 格式化摘要
```

---

## 4. 当前已实现功能一览

### 4.1 核心能力

| 能力 | 状态 | 说明 |
|------|------|------|
| 多 LLM 后端 | ✅ | 百炼 + Ollama，可扩展任意 OpenAI 兼容服务 |
| 自动回退 | ✅ | 主 Provider 失败自动切换备用 |
| 流式输出 | ✅ | 逐 token 输出，实时显示 |
| 工具调用循环 | ✅ | 最多 50 轮，自动注入工具结果 |
| 状态机 | ✅ | 6 种状态，合法转换检查 |

### 4.2 工具集

| 工具 | 状态 | 核心功能 |
|------|------|---------|
| file_read | ✅ | 分段读取、行号显示 |
| file_write | ✅ | 创建/覆盖文件 |
| file_edit | ✅ | 精确局部替换 |
| multi_edit | ✅ | 原子批量替换 |
| line_edit | ✅ | 行号级编辑 |
| line_read | ✅ | 带行号读取 |
| diff | ✅ | unified/并排对比 |
| snapshot | ✅ | 快照管理 |
| directory | ✅ | 目录列表 |
| file_search | ✅ | 文件名/内容搜索 |
| grep | ✅ | 正则搜索 + include/exclude + 上下文 |
| glob | ✅ | 模式匹配查找 |
| shell | ✅ | 命令执行 + 危险检测 |
| git_diff | ✅ | 查看差异 |
| git_commit | ✅ | 暂存并提交 |
| git_log | ✅ | 提交历史 |
| git_status | ✅ | 仓库状态 |
| git_branch | ✅ | 分支管理 |
| git_show | ✅ | 提交详情 |
| git_blame | ✅ | 行级修改 |
| code_structure | ✅ | AST 分析 |
| symbol_find | ✅ | 符号查找 |
| symbol_edit | ✅ | 符号替换 |
| import_analyze | ✅ | 导入分析 |
| search_conversation_history | ✅ | 搜索历史 |
| get_session_history | ✅ | 会话历史 |
| update_memory | ✅ | 更新记忆 |
| set_preference | ✅ | 设置偏好 |

### 4.3 安全特性

| 特性 | 状态 | 说明 |
|------|------|------|
| 三级危险等级 | ✅ | safe/confirm/dangerous |
| 路径限制 | ✅ | allow/deny 目录白名单/黑名单 |
| 危险命令拦截 | ✅ | 正则匹配 `rm -rf /`、`sudo` 等 |
| 用户确认回调 | ✅ | 终端弹出 [y/N] 确认 |
| 输入校验 | ✅ | 路径穿越、命令注入、长度限制 |
| 输出清洗 | ✅ | 敏感信息脱敏、控制字符清理 |
| 审计日志 | ✅ | JSONL 追加写入，自动脱敏 |

### 4.4 智能特性

| 特性 | 状态 | 说明 |
|------|------|------|
| 工具结果缓存 | ✅ | LRU + TTL，只缓存 safe 工具 |
| 并行执行 | ✅ | safe 工具 asyncio.gather 并行 |
| 持久记忆 | ✅ | L0-L4 五层分层架构 |
| 上下文压缩 | ✅ | 自动（>80%）+ 手动（/compact） |
| 动态 System Prompt | ✅ | Persona + 工具指南 + 记忆 + 自定义段 |
| 任务规划 | ✅ | 步骤列表 + 进度跟踪 |

### 4.5 扩展能力

| 特性 | 状态 | 说明 |
|------|------|------|
| MCP 协议 | ✅ | 连接外部 MCP 工具服务器 |
| Skills 模块 | ✅ | 自动匹配、上下文注入 |
| 插件系统 | ✅ | 自动发现 + 热重载 |
| Web UI | ✅ | FastAPI + WebSocket |
| 会话管理 | ✅ | save/load/delete/list |
| 费用追踪 | ✅ | 累计 token + 估算费用 |

---

## 5. 后续开发方向

基于 OpenClaw 架构思想，未来重点发展方向：

### 5.1 24 小时持续运行

**目标**: 实现无人值守的全天候 Agent 运行能力。

**关键技术**:
- **Cron 调度器**: 定时触发 Agent 执行任务
- **Heartbeat 心跳**: 周期性唤醒 Agent 进行状态检查
- **事件驱动**: Webhook、文件监听、API 调用触发
- **休眠/唤醒**: 任务完成后释放资源，需要时快速恢复

### 5.2 本地软件操控

**目标**: 让 Agent 能够操控本地应用程序（浏览器、Office、终端等）。

**关键技术**:
- **Browser 自动化**: Playwright/Puppeteer 网页操作
- **进程管理**: 启动/停止/监控本地进程
- **屏幕截取 + VLM**: 图形界面应用的感知能力
- **MCP 协议扩展**: 连接更多外部服务

### 5.3 多 Agent 架构

**目标**: 支持多个独立 Agent 并行工作，协调完成复杂任务。

**关键技术**:
- **多会话管理**: 独立会话的生命周期管理
- **Agent 间通信**: 消息队列、共享记忆
- **子代理模式**: 主 Agent 动态生成子代理处理子任务
- **路由分发**: 根据规则将任务分配给不同 Agent

### 5.4 多通道接入

**目标**: 支持 WhatsApp、Telegram、Slack、Discord 等多种消息通道。

**关键技术**:
- **Gateway 统一入口**: 消息归一化处理
- **通道适配器**: 各平台消息格式转换
- **通道特定功能**: 支持各平台的特有交互形式
