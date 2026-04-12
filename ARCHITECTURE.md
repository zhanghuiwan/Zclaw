# Zclaw 项目完整技术文档

> 版本: 0.4.0 | 最后更新: 2026-04-10  
> 测试状态: V4 Memory Module **4/4 测试通过**

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [模块详解](#3-模块详解)
   - 3.1 [配置管理 (config)](#31-配置管理-config)
   - 3.2 [LLM 层 (llm)](#32-llm-层-llm)
   - 3.3 [核心引擎 (core)](#33-核心引擎-core)
   - 3.4 [工具系统 (tools)](#34-工具系统-tools)
   - 3.5 [沙箱执行 (sandbox)](#35-沙箱执行-sandbox)
   - 3.6 [安全系统 (security)](#36-安全系统-security)
   - 3.7 [记忆模块 (memory)](#37-记忆模块-memory)
   - 3.8 [上下文管理 (context)](#38-上下文管理-context)
   - 3.9 [提示词工程 (prompt)](#39-提示词工程-prompt)
   - 3.10 [插件系统 (plugins)](#310-插件系统-plugins)
   - 3.11 [CLI 界面 (cli)](#311-cli-界面-cli)
4. [当前已实现功能一览](#4-当前已实现功能一览)
5. [扩展方向](#5-扩展方向)

---

## 1. 项目概述

### 1.1 什么是 Zclaw？

Zclaw 是一个用 Python 编写的 **Claude Code 风格 AI 编程助手**。它的核心思想是：将大语言模型（LLM）与本地文件系统、Shell 环境深度结合，让 AI 能够像人类程序员一样 **读取代码、修改文件、执行命令、搜索项目**，从而完成复杂的编程任务。

### 1.2 核心特点

| 特性 | 描述 |
|------|------|
| **多模型支持** | 统一的 OpenAI 兼容接口，支持阿里百炼、本地 Ollama 等任意兼容服务 |
| **工具调用循环** | Agent Loop 机制，LLM 可自主决定调用哪些工具、调用多少轮 |
| **分层安全** | 三级危险等级（safe/confirm/dangerous）+ 路径限制 + 命令拦截 + 用户确认 |
| **V4 持久记忆** | 五层分层架构，Agent 驱动的自主探索，状态与历史分离 |
| **智能上下文** | 自动检测并压缩长对话，适配不同模型的 token 限制 |
| **插件扩展** | 用户可通过编写 Python 文件自定义工具 |
| **完整 CLI** | Rich 渲染的终端交互界面，支持 REPL 模式和单次命令模式 |

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
├── ROADMAP.md                    # 开发路线图
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
│   │       └── multi_edit_tool.py# 批量编辑（原子操作）
│   ├── sandbox/
│   │   └── runner.py             # 命令运行器（超时、输出控制）
│   ├── security/                 # 安全系统
│   │   ├── permission.py         # 权限管理器
│   │   ├── validator.py          # 输入校验 + 输出清洗
│   │   └── audit.py              # 审计日志
│   ├── memory/                   # V4 记忆模块
│   │   ├── config.py             # V4 配置类
│   │   ├── coordinator.py         # 记忆协调器
│   │   ├── extractor.py          # LLM 提取器
│   │   ├── layers/              # 分层实现
│   │   │   ├── l0_perceptual.py # RingBuffer
│   │   │   ├── l1_working.py    # 会话快照
│   │   │   ├── l2_episodic.py  # SQLite-VSS
│   │   │   ├── l3_semantic.py   # JSON 当前状态
│   │   │   └── l4_procedural.py # YAML 规则
│   │   └── tools/               # 记忆工具
│   │       ├── episodic_search.py # 搜索历史
│   │       └── memory_tools.py   # 更新记忆
│   ├── context/                  # 上下文管理
│   │   ├── budget.py             # Token 预算计算
│   │   ├── compressor.py         # 对话历史压缩
│   │   └── manager.py            # 上下文管理器
│   ├── prompt/                   # 提示词工程
│   │   ├── templates.py          # 模板库
│   │   └── builder.py            # 动态组装器
│   ├── plugins/                  # 插件系统
│   │   └── loader.py             # 插件加载器
│   └── cli/                      # CLI 界面
│       ├── app.py                # REPL 入口
│       ├── renderer.py           # Rich 渲染器
│       ├── session.py            # 会话管理器
│       └── cost_tracker.py       # Token 用量追踪
└── tests/                        # 验证测试
    ├── validate_p0.py            # P0: 骨架 (7 tests)
    ├── validate_p1.py            # P1: 工具 (9 tests)
    ├── validate_p2.py            # P2: 安全 (6 tests)
    ├── validate_p3.py            # P3: 增强工具 (7 tests)
    ├── validate_p4.py            # P4: 记忆 (5 tests)
    ├── validate_p5.py            # P5: 上下文 (5 tests)
    └── validate_p6p7.py          # P6+P7: 提示词/规划器/插件 (5 tests)
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
    │  Provider   │ │  9 tools   │   │  TokenBudget    │
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
|---|------|
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
self._tools = ToolRegistry()           # + 注册 9 个内置工具
self._plugin_loader = PluginLoader()   # + 加载插件工具
self._permissions = PermissionManager()
self._audit = AuditLogger()
self._memory = MemoryManager()
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

#### 3.4.4 内置工具 (9 个)

| 工具 | 类别 | 危险等级 | 功能 |
|------|------|---------|------|
| `file_read` | file | safe | 读取文件内容，支持 offset/limit 分段读取 |
| `file_write` | file | confirm | 创建新文件或完全覆盖 |
| `file_edit` | file | confirm | 精确替换文件中的旧文本为新文本 |
| `multi_edit` | file | confirm | 对同一文件原子执行多处替换 |
| `directory` | search | safe | 列出目录内容（隐藏文件跳过） |
| `file_search` | search | safe | 按文件名或内容搜索文件 |
| `grep` | search | safe | 正则表达式搜索，支持 include/exclude glob、上下文行 |
| `glob` | search | safe | Glob 模式匹配查找文件（如 `**/*.py`） |
| `shell` | system | confirm/dangerous | 执行 Shell 命令，动态检测危险模式 |

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

内置工具危险等级：

| 工具 | 等级 | 说明 |
|------|------|------|
| `file_read`, `grep`, `glob`, `directory` | safe | 只读操作 |
| `shell`, `file_write`, `file_edit`, `git_commit` | confirm | 需确认 |
| 高危系统命令 | dangerous | 始终确认 |

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

#### 3.6.8 安全集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI / REPL                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  app.py     │  │  renderer.py│  │  permission callback     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Agent                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  chat_stream│  │ Permission  │  │ AuditLogger             │ │
│  │             │  │ Manager      │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  Validator      │ │ Permission      │ │ AuditLogger     │
│  (输入/输出校验) │ │ Manager         │ │ (日志记录)       │
│                 │ │ (危险等级/路径)  │ │                 │
│  · 路径穿越     │ │                 │ │ · JSONL 格式    │
│  · 命令注入     │ │ · Danger Level  │ │ · 自动脱敏      │
│  · 长度限制     │ │ · Path Restrict │ │                 │
│  · 敏感信息脱敏 │ │ · Blocked Cmds  │ │                 │
│  · 控制字符清理 │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

#### 3.6.9 安全配置参考

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

#### 3.6.10 安全子系统文件索引

| 功能 | 文件路径 | 关键行号 |
|------|----------|----------|
| 危险等级定义 | `src/tools/base.py` | 15-19 |
| 权限检查实现 | `src/security/permission.py` | 148-196 |
| 路径限制实现 | `src/security/permission.py` | 210-240 |
| 危险命令拦截 | `src/security/permission.py` | 88-93, 198-205 |
| 输入校验 | `src/security/validator.py` | 全文 |
| 输出清洗 | `src/security/validator.py` | 18-100 |
| 审计日志 | `src/security/audit.py` | 全文 |
| 安全配置 | `src/config/settings.py` | 82-95 |

---

### 3.7 记忆模块 V4 (memory)

#### 3.7.1 核心设计理念

V4 架构从**"系统驱动的 RAG"**转变为**"Agent 驱动的自主探索"**：

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

### 3.10 插件系统 (plugins)

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

### 3.11 CLI 界面 (cli)

#### 3.11.1 REPL (`app.py`)

`REPL` 类实现交互式命令循环：

**支持的命令**:

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助 |
| `/clear` | 清空对话历史 |
| `/compact` | 手动压缩上下文 |
| `/undo` | 撤销上一轮对话 |
| `/usage` | 显示 token 使用统计 |
| `/tools` | 列出已注册工具 |
| `/provider [name]` | 查看/切换 LLM Provider |
| `/model [name]` | 查看/切换模型 |
| `/info` | 显示完整配置信息 |
| `/memory` | 查看/搜索/删除记忆 |
| `/session save\|load\|delete\|list` | 会话管理 |
| `/plugin [reload\|list]` | 插件管理 |
| `/cost` | Token 用量和费用统计 |
| `/plan [clear]` | 查看/清除当前计划 |
| `/quit` `/exit` | 退出 |

**非交互模式**:
```bash
Zclaw --prompt "列出当前目录的文件"
```

**输入增强**: prompt-toolkit 提供命令历史（`~/.Zclaw/history`）、自动补全、`Ctrl+C` 取消。

**权限确认**: 当 confirm/dangerous 工具需要执行时，弹出确认面板：
```
┌─ ! Permission Required (DANGEROUS) ────────────┐
│ shell                                           │
│                                                  │
│   command: rm -rf /tmp/test                     │
│                                                  │
│   Allow? [y/N] _                                │
└──────────────────────────────────────────────────┘
```

#### 3.11.2 渲染器 (`renderer.py`)

`Renderer` 使用 Rich 库实现美观的终端输出：

- 自定义主题 `AGENT_THEME`（cyan=用户, green=助手, magenta=工具, red=错误）
- Banner、状态栏、分隔线
- Markdown 渲染（助手回复）
- 工具执行动画（开始/结束状态）
- 权限确认面板
- 工具列表表格
- 审计日志统计

#### 3.11.3 会话管理 (`session.py`)

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

#### 3.11.4 费用追踪 (`cost_tracker.py`)

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
| directory | ✅ | 目录列表 |
| file_search | ✅ | 文件名/内容搜索 |
| grep | ✅ | 正则搜索 + include/exclude + 上下文 |
| glob | ✅ | 模式匹配查找 |
| shell | ✅ | 命令执行 + 危险检测 |

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
| 持久记忆 | ✅ | JSON 存储，4 种类型，加权检索 |
| 上下文压缩 | ✅ | 自动（>80%）+ 手动（/compact） |
| 动态 System Prompt | ✅ | Persona + 工具指南 + 记忆 + 自定义段 |
| 任务规划 | ✅ | 步骤列表 + 进度跟踪 |

### 4.5 CLI 功能

| 功能 | 状态 | 说明 |
|------|------|------|
| REPL 交互 | ✅ | prompt-toolkit，历史，补全 |
| 非交互模式 | ✅ | `--prompt` 单次执行 |
| 会话管理 | ✅ | save/load/delete/list |
| 费用追踪 | ✅ | 累计 token + 估算费用 |
| 插件系统 | ✅ | 自动发现 + 热重载 |
| Rich 渲染 | ✅ | 主题、Markdown、表格、面板 |

---

## 5. 扩展方向

### 5.1 P8: 多模态能力（高优先级）

**当前差距**: 不支持图片理解、文件上传

**扩展方案**:
- 在 `BaseProvider` 中增加 `supports_vision` 的实际处理逻辑
- 在 `Message` 中增加 `image_url` 字段
- 新增 `image_analyze` 工具，调用多模态模型（如 qwen-vl）分析截图/图片
- 支持 `file_read` 的二进制/图片模式

### 5.2 P9: 语义记忆（中高优先级）

**当前差距**: 记忆检索只基于关键词匹配

**扩展方案**:
- 集成向量数据库（SQLite-VSS、ChromaDB）
- 实现嵌入生成（使用本地模型或 API）
- `MemoryRetriever` 增加语义检索模式
- 支持自动记忆提取（每轮对话后 LLM 自动总结关键信息）

### 5.3 P10: Web UI（中优先级）

**当前差距**: 只有 CLI 界面

**扩展方案**:
- 使用 FastAPI + WebSocket 提供 Web API
- 前端使用 React/Next.js 或 Gradio
- 实时流式输出（SSE 或 WebSocket）
- 文件浏览器面板
- 工具执行可视化面板

### 5.4 P11: 高级编辑能力（中优先级）

**当前差距**: file_edit 只支持简单字符串替换

**扩展方案**:
- 行号级编辑（指定行范围替换）
- Diff 预览（编辑前显示 diff）
- Git 集成工具（git_diff, git_commit, git_log）
- 语法感知编辑（利用 tree-sitter）

### 5.5 P12: 项目理解（中优先级）

**当前差距**: 无项目级别的知识管理

**扩展方案**:
- 项目索引构建（AST 分析、依赖图、类型关系）
- 符号级搜索（函数定义、类继承、引用关系）
- 项目规则自动提取（从配置文件中学习 lint 规则、测试命令等）
- `.zclawrules` 项目配置文件（类似 Claude Code 的 CLAUDE.md）

### 5.6 P13: 多 Agent 协作（低优先级）

**扩展方案**:
- Agent 拆分为专门角色（编码 Agent、测试 Agent、审查 Agent）
- 任务分发器（复杂任务拆分后并行分配给不同 Agent）
- Agent 间通信协议
- 结果合并与冲突解决

### 5.7 P14: 增强安全（持续改进）

**扩展方案**:
- Docker 容器沙箱（命令在隔离容器中执行）
- 网络访问控制（限制工具的网络请求）
- 磁盘写入预览（file_write 前显示 diff）
- 成本控制（设置每轮/每日最大 token 限额）
- 多用户支持（用户认证和隔离）

### 5.8 P15: 性能优化（持续改进）

**扩展方案**:
- Token 计数优化（使用 tiktoken 精确计算替代字符估算）
- 增量上下文（只发送变化的消息，而非全量）
- 工具执行超时分级（不同工具不同默认超时）
- 异步文件 I/O（aiofiles 替代同步读写）
- 会话持久化（自动保存对话，崩溃恢复）

### 5.9 P16: 测试与质量

**扩展方案**:
- 单元测试覆盖（pytest + pytest-asyncio）
- 集成测试（mock LLM 响应的端到端测试）
- 性能基准测试（工具执行延迟、内存占用）
- CI/CD 集成（自动测试、版本发布）

### 5.10 其他可能方向

| 方向 | 说明 |
|------|------|
| MCP 协议支持 | 实现 Model Context Protocol，接入外部工具服务器 |
| 自然语言工具定义 | 用 LLM 将自然语言描述转换为工具 schema |
| 多语言 CLI | 支持中英文切换 |
| TTS 语音输出 | 集成语音合成，语音播报结果 |
| Agent 市场 | 插件分享平台，用户可下载社区工具 |
| IDE 集成 | VS Code / JetBrains 插件 |
| 代码审查模式 | 专门的 code review 流程 |
| 文档生成 | 自动生成 README、API 文档 |

---

> 本文档基于 Zclaw v0.3.0 源码分析生成。项目位于 `/home/z/my-project/download/Zclaw/`。
