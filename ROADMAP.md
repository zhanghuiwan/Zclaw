# Zclaw Development Roadmap (P3 - P11)

> 当前状态：**P0-P11 全部完成**，104/105 测试通过（P1 有 1 个历史遗留失败）。
> 项目根目录：`/home/z/my-project/download/Zclaw/`

---

## P3: Enhanced Tool System（增强工具系统） ✅

### 目标
扩展工具集，使 Agent 具备更强的代码操作能力；支持工具执行结果缓存和并行执行。

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/tools/builtin/grep_tool.py` | 正则内容搜索工具（支持行号、上下文、include/exclude glob） |
| `src/tools/builtin/glob_tool.py` | Glob 模式匹配文件查找工具 |
| `src/tools/builtin/multi_edit_tool.py` | 批量编辑工具（一次调用修改多处，原子回滚） |
| `src/tools/cache.py` | 工具结果缓存层（LRU，TTL 过期，失败不缓存） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/core/agent.py` | 注册 3 个新工具 (grep, glob, multi_edit) |
| `src/core/loop.py` | 集成工具结果缓存；safe 工具并行执行 |
| `src/config/settings.py` | ToolConfig 增加 `cache_enabled`, `cache_ttl` |
| `src/cli/renderer.py` | 并行工具执行的可视化 |

### 验证结果
- [x] `grep_tool`: 正则搜索、行号输出、上下文行、include/exclude glob 过滤
- [x] `glob_tool`: `**/*.py` 等模式匹配、隐藏文件跳过
- [x] `multi_edit_tool`: 多处替换、冲突检测、原子回滚
- [x] 缓存：相同参数不重复执行，TTL 过期自动清除，LRU 驱逐
- [x] 并行执行：多个 safe 工具同时执行，结果顺序一致
- [x] validate_p3.py 7/7 通过

---

## P4: Memory Module（记忆模块） ✅

### 目标
实现跨会话的持久化记忆系统，让 Agent 能够"记住"用户偏好、项目上下文和历史交互。

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/memory/store.py` | 记忆存储引擎（JSON 文件存储，支持 CRUD + 持久化） |
| `src/memory/types.py` | 记忆数据类型（FactMemory, EpisodicMemory, PreferenceMemory） |
| `src/memory/retriever.py` | 记忆检索器（关键词匹配 + 时序衰减权重） |
| `src/memory/manager.py` | 记忆管理器（remember, recall, forget, get_context） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/core/agent.py` | 初始化 MemoryManager |
| `src/config/settings.py` | MemoryConfig 字段 |
| `src/cli/app.py` | `/memory` 命令 |

### 验证结果
- [x] 记忆存储：写入/读取/删除/更新记忆条目
- [x] 分类记忆：fact（事实）、episodic（事件）、preference（偏好）
- [x] 记忆检索：关键词匹配返回相关记忆
- [x] 时序衰减：近期记忆权重更高
- [x] Agent 集成：MemoryManager 持久化跨实例
- [x] validate_p4.py 5/5 通过

---

## P5: Context Management（上下文管理） ✅

### 目标
实现智能上下文窗口管理，自动压缩对话历史以适配模型的 token 限制。

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/context/budget.py` | Token 预算计算器（估算 token 数，计算剩余空间） |
| `src/context/compressor.py` | 对话历史压缩器（提取摘要、移除冗余工具调用） |
| `src/context/manager.py` | 上下文管理器（组装最终消息列表，自动/手动压缩） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/core/loop.py` | 发送消息前通过 ContextManager 裁剪历史 |
| `src/core/agent.py` | 初始化 ContextManager（从 provider config 获取 max_context_tokens） |
| `src/config/settings.py` | ContextConfig 字段 |
| `src/cli/app.py` | `/compact` 命令 |

### 验证结果
- [x] Token 预算：准确估算消息 token 数
- [x] 自动裁剪：token 使用超过阈值时自动压缩旧消息
- [x] 压缩策略：保留 system + 最近 N 轮完整对话 + 旧对话摘要
- [x] `/compact` 手动触发压缩
- [x] 上下文使用率显示
- [x] validate_p5.py 5/5 通过

---

## P6: Prompt Engineering + Planner（提示词工程 + 规划器） ✅

### 目标
1. 实现结构化提示词模板系统，动态组装高质量的 system prompt
2. 实现简单规划器，让 Agent 在复杂任务前先生成执行计划

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/prompt/templates.py` | 提示词模板库（persona、工具指南） |
| `src/prompt/builder.py` | System Prompt 构建器（动态组装 persona + tools + memory + sections） |
| `src/core/planner.py` | 任务规划器（create_plan, parse_plan_from_text, get_context） |
| `src/core/plan.py` | 计划数据结构（Plan, PlanStep, PlanStepStatus, 序列化） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/core/agent.py` | 使用 PromptBuilder 生成 system prompt；集成 Planner |
| `src/cli/app.py` | `/plan` 命令 |

### 验证结果
- [x] PromptBuilder：动态生成 system prompt（含工具列表、记忆、自定义 section）
- [x] 模板系统：DEFAULT_PERSONA + COMPACT_PERSONA
- [x] Planner：create_plan_from_steps, parse_plan_from_text
- [x] Plan 数据结构：advance, fail_current, to_dict/from_dict, format_status
- [x] validate_p6p7.py 中 P6 相关测试通过

---

## P7: CLI Enhancement + Plugin System（CLI 增强 + 插件系统） ✅

### 目标
完善 CLI 交互体验；实现插件加载机制，支持用户自定义工具扩展。

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/plugins/loader.py` | 插件加载器（从 `~/.Zclaw/plugins/` 扫描加载 `.py` 插件） |
| `src/cli/session.py` | 会话管理器（保存/恢复/列出对话历史） |
| `src/cli/cost_tracker.py` | Token 用量追踪和费用估算（round 记录、汇总统计） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/core/agent.py` | 集成 PluginLoader + SessionManager |
| `src/config/settings.py` | PluginConfig |

### 验证结果
- [x] 会话管理：SessionManager（save/load/list）
- [x] 插件加载：PluginLoader scan/load_all
- [x] 费用追踪：CostTracker（record_round, get_total, get_summary）
- [x] validate_p6p7.py 中 P7 相关测试通过

---

## 依赖关系

```
P3 (增强工具) ✅ ─────────────────────────┐
                                              ├──→ P6 (提示词+规划器) ✅
P4 (记忆模块) ✅ ──→ P5 (上下文管理) ✅ ────┘          │
                                                     ├──→ P7 (CLI+插件) ✅
                                                     ├──→ P8 (记忆完善) ✅
                                                     └──→ P9 (MCP集成) ✅
```

---

## P8: Memory System Completion（记忆系统完善） ✅

### 目标
1. 自动从对话中提取值得长期记住的信息
2. 每次对话前自动检索并注入相关记忆到 system prompt
3. 记忆分层管理（工作/近期/长期/归档）+ 容量控制

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/memory/extractor.py` | 记忆自动提取器（BaseExtractor + MockExtractor + LLMExtractor + 工厂函数） |
| `src/memory/lifecycle.py` | 记忆分层生命周期管理（4层分级 + 过期淘汰 + 溢出控制 + 相似合并检测） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/memory/manager.py` | 集成提取器和生命周期管理；新增 `extract_from_conversation`, `remember_batch`, `run_lifecycle` |
| `src/core/agent.py` | `chat()`/`chat_stream()` 中每次对话前注入记忆上下文，对话后自动提取记忆 |
| `src/prompt/builder.py` | 已有 `memory_context` 参数，现在被正确传递 |

### 验证结果
- [x] MockExtractor: 偏好检测、事实检测、固定结果注入
- [x] LLMExtractor: JSON 解析（含代码围栏）、无效 JSON 处理
- [x] 生命周期: 分层分配、分类、可删除检测、溢出淘汰、相似合并
- [x] MemoryManager: 提取器可替换、batch 保存、extract_from_conversation、run_lifecycle
- [x] Agent 集成: 记忆上下文注入、set_extractor
- [x] P4 兼容性: remember/recall/forget/get_context 正常
- [x] validate_p8.py 5/5 通过

---

## P9: MCP Integration（MCP 协议集成） ✅

### 目标
让 Zclaw 能够连接外部 MCP (Model Context Protocol) 工具服务器，将其提供的工具自动注册到 Agent 的工具注册表中，实现无缝调用。

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/mcp/__init__.py` | MCP 模块入口 |
| `src/mcp/types.py` | MCP 数据类型（MCPServerConfig, MCPTransportType, MCPToolDefinition） |
| `src/mcp/transport.py` | 传输层（StdioTransport, SSETransport, MockTransport, JSON-RPC 2.0） |
| `src/mcp/client.py` | MCP 客户端（连接握手、工具发现、工具调用、ping） |
| `src/mcp/adapter.py` | 工具适配器（MCPToolWrapper: MCP tool → Zclaw BaseTool 自动转换） |
| `src/mcp/manager.py` | MCP 管理器（配置加载、多服务器生命周期、工具注册） |
| `config.mcp.example.json` | MCP 配置示例文件 |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/config/settings.py` | 新增 `MCPConfig`（enabled, config_path, auto_connect） |
| `src/core/agent.py` | 集成 MCPManager；新增 `init_mcp()` 和 `shutdown_mcp()` |
| `src/cli/app.py` | 新增 `/mcp` 命令（list, connect, disconnect, reconnect） |

### 架构设计
```
MCP Server (外部进程/远程服务)
    ↕ JSON-RPC 2.0 (stdio/SSE)
MCP Transport (transport.py)
    ↕
MCP Client (client.py) → 工具发现 (tools/list) → 工具调用 (tools/call)
    ↕
MCP Adapter (adapter.py) → MCPToolWrapper(BaseTool)
    ↕
ToolRegistry → AgentLoop → LLM
```

### 验证结果
- [x] MCPServerConfig: stdio/SSE 配置、序列化/反序列化、验证
- [x] 传输层: MockTransport 全功能、JSON-RPC 消息构造、工厂函数
- [x] MCPClient: 连接握手、工具发现、工具调用、ping、重复连接保护
- [x] 适配器: schema_to_parameters（含 anyOf）、MCPToolWrapper 执行、前缀命名
- [x] MCPManager: 配置加载、服务器管理、手动注册、disconnect_all
- [x] Agent 集成: init_mcp、shutdown_mcp、工具注册和执行
- [x] validate_p9.py 6/6 通过

---

## 依赖关系

```
P3 (增强工具) ✅ ─────────────────────────┐
                                              ├──→ P6 (提示词+规划器) ✅
P4 (记忆模块) ✅ ──→ P5 (上下文管理) ✅ ────┘          │
                                                     ├──→ P7 (CLI+插件) ✅
                                                     ├──→ P8 (记忆完善) ✅
                                                     └──→ P9 (MCP集成) ✅
```

## 测试汇总

| 阶段 | 测试文件 | 通过 | 失败 |
|------|---------|------|------|
| P0 | validate_p0.py | 7 | 0 |
| P1 | validate_p1.py | 8 | 1 |
| P2 | validate_p2.py | 6 | 0 |
| P3 | validate_p3.py | 7 | 0 |
| P4 | validate_p4.py | 5 | 0 |
| P5 | validate_p5.py | 5 | 0 |
| P6+P7 | validate_p6p7.py | 5 | 0 |
| P8 | validate_p8.py | 5 | 0 |
| P9 | validate_p9.py | 6 | 0 |
| P10 | validate_p10.py | 21 | 0 |
| P11 | validate_p11.py | 29 | 0 |
| **合计** | | **105** | **1** |

---

## P10: Web UI（Web 界面） ✅

### 目标
基于 FastAPI + WebSocket 构建现代化 Web 界面，提供实时流式对话、文件浏览、工具可视化和会话管理功能。

### 已完成文件
| 文件 | 说明 |
|------|------|
| `src/web/__init__.py` | Web 模块入口 |
| `src/web/schemas.py` | Web API 数据模型（WebSocket 消息、REST 请求/响应） |
| `src/web/ws_manager.py` | WebSocket 连接管理器（多连接、广播、权限请求/响应） |
| `src/web/routes.py` | API 路由（REST + WebSocket 端点） |
| `src/web/server.py` | FastAPI 应用创建、静态文件服务、Uvicorn 启动 |
| `src/web/static/index.html` | 主 SPA 页面（聊天、文件浏览器、工具面板、设置） |
| `src/web/static/css/style.css` | 暗色主题样式（响应式设计、动画、自定义滚动条） |
| `src/web/static/js/app.js` | 前端 JavaScript（WebSocket 通信、Markdown 渲染、文件浏览） |
| `tests/validate_p10.py` | P10 验证测试（21 个测试） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/config/settings.py` | 新增 `WebConfig`（enabled, host, port, cors_origins, static_dir） |
| `pyproject.toml` | 新增 `fastapi`, `uvicorn`, `websockets` 依赖 |

### 架构设计
```
浏览器 (index.html + app.js + style.css)
    ↕ WebSocket (实时流式通信)
    ↕ REST API (文件/工具/会话/配置)
FastAPI Server (server.py + routes.py)
    ↕
WebSocket Manager (ws_manager.py) → 连接管理、广播、权限请求
    ↕
Agent (agent.py) → chat_stream() → StreamEvent
    ↕
Agent Loop → LLM → 工具执行 → 流式结果推送
```

### 功能清单
| 功能 | 说明 |
|------|------|
| 实时流式对话 | WebSocket 推送 content_delta，逐字显示 |
| 工具执行可视化 | 工具开始/结束卡片，状态指示，错误展示 |
| 权限确认对话框 | confirm/dangerous 工具通过 WebSocket 请求用户确认 |
| 文件浏览器 | 目录列表、文件查看、路径导航 |
| 工具列表面板 | 已注册工具名称、描述、危险等级标签 |
| 会话管理 | 保存/加载历史会话 |
| 设置面板 | LLM 配置、Agent 配置查看（API Key 脱敏） |
| 对话历史 | 加载、清空对话记录 |
| 费用统计 | Token 用量实时显示 |
| 暗色主题 | 专业级暗色 UI，GitHub 风格 |
| 响应式设计 | 适配桌面和移动端 |
| Markdown 渲染 | 代码高亮、列表、引用、链接 |
| 多轮循环指示 | 显示工具调用轮次 |
| 连接状态 | 实时显示 WebSocket 连接状态 |
| 自动重连 | 断线后指数退避重连 |

### 验证结果
- [x] 数据模型: WSMessageType、WSChatMessage、WSPermissionMessage、ChatRequest、AgentStatus 等
- [x] WebSocket 管理器: 连接/断开、JSON 发送、广播、权限请求/响应/超时
- [x] FastAPI 应用: 路由注册（11 个端点）、CORS 配置、静态文件挂载
- [x] 静态文件: index.html、style.css、app.js 存在性和内容验证
- [x] 配置集成: WebConfig 默认值、序列化
- [x] 路由模块: 导入、WS 管理器单例
- [x] validate_p10.py 21/21 通过
- [x] 全量测试 P0-P10: 76/76 通过

---

## P11: Advanced Editing（高级编辑能力） ✅

### 目标
增强 Agent 的代码编辑能力，提供行号级编辑、Diff 预览、文件快照、Git 集成和语法感知编辑功能。

### 新增文件
| 文件 | 说明 |
|------|------|
| `src/tools/builtin/line_edit_tool.py` | 行号级编辑工具（line_edit: replace/insert/delete, line_read: 带行号读取） |
| `src/tools/builtin/diff_tool.py` | Diff 预览 + 文件快照（diff: text/file/snapshot 比较, snapshot: save/list/restore/delete） |
| `src/tools/builtin/git_tool.py` | Git 集成工具（git_diff, git_commit, git_log, git_status, git_branch, git_show, git_blame） |
| `src/tools/builtin/ast_tool.py` | 语法感知编辑（code_structure, symbol_find, symbol_edit, import_analyze） |
| `tests/validate_p11.py` | P11 验证测试（29 个测试） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `src/core/agent.py` | 导入并注册 15 个 P11 新工具 |
| `src/config/settings.py` | 新增 `_get_zclaw_dir()` 辅助函数 |

### 架构设计
```
P11 新增工具 (15 个)
├── 文件编辑增强
│   ├── line_edit    → 行号级替换/插入/删除（confirm）
│   ├── line_read    → 按行号范围读取（safe）
│   ├── diff         → 文本/文件差异比较（safe, unified/并排格式）
│   └── snapshot     → 文件快照管理（save/list/restore/delete, confirm）
├── Git 集成
│   ├── git_diff     → diff unstaged/staged/commit/file（safe）
│   ├── git_commit   → add + commit + amend（confirm）
│   ├── git_log      → 提交历史（safe, 支持过滤）
│   ├── git_status   → 仓库状态（safe）
│   ├── git_branch   → 分支管理（confirm）
│   ├── git_show     → 提交详情（safe）
│   └── git_blame    → 行级修改信息（safe）
└── 语法分析
    ├── code_structure → AST 代码结构分析（safe, brief/normal/full）
    ├── symbol_find    → 按名称查找符号定义（safe）
    ├── symbol_edit    → 按符号名称精确替换（confirm）
    └── import_analyze → 导入依赖分析 + 未使用检测（safe）
```

### 功能清单
| 功能 | 说明 |
|------|------|
| 行号级编辑 | 支持按行号范围进行 replace/insert/delete 操作 |
| 带行号读取 | 按行号范围读取文件，显示行号对齐 |
| Diff 比较 | 支持文本比较、文件比较、与快照比较 |
| 并排对比 | Side-by-side 格式的 diff 输出 |
| 文件快照 | 编辑前保存快照，支持恢复和删除 |
| Git Diff | 查看 unstaged/staged/commit/文件级差异 |
| Git Commit | 暂存并提交文件，支持 amend |
| Git Log | 查看提交历史，支持作者/日期/分支过滤 |
| Git Status | 查看仓库状态 |
| Git Branch | 查看/创建/切换分支 |
| Git Show | 查看提交详情 |
| Git Blame | 查看行级修改信息 |
| 代码结构分析 | 基于 AST 提取类、函数、导入等结构 |
| 符号查找 | 按名称查找函数/类定义，返回完整代码 |
| 符号替换 | 基于 AST 定位的精确函数/类替换 |
| 导入分析 | 分类导入（标准库/第三方/项目内）+ 未使用检测 |

### 验证结果
- [x] line_edit: replace（行号范围替换）、insert（行前插入）、delete（行号删除）
- [x] line_edit: 边界检查（行号越界、结束行小于起始行）
- [x] line_read: 按行号范围读取、行号显示/隐藏
- [x] diff: 文本比较（unified 格式）
- [x] diff: 文件比较
- [x] diff: 并排对比格式（side_by_side）
- [x] snapshot: 保存快照、恢复快照、删除快照
- [x] snapshot: 列出快照（按文件过滤）
- [x] git_diff: 工具导入、属性验证
- [x] git_commit: 工具属性验证
- [x] git_log: 工具属性验证
- [x] git_status: 工具属性验证
- [x] git_branch: 工具属性验证
- [x] Git 操作: status/commit/log/diff 完整流程
- [x] git_show: 查看提交详情
- [x] git_blame: 查看行级修改
- [x] git_branch: 列出/创建切换分支
- [x] code_structure: AST 结构分析（brief/normal/full）
- [x] symbol_find: 查找存在的符号、报告不存在的符号
- [x] symbol_edit: 精确替换符号定义
- [x] import_analyze: 导入分类 + 未使用检测
- [x] AST 工具属性验证
- [x] 非 Python 文件处理
- [x] Agent 工具注册: 15 个 P11 工具全部注册
- [x] Diff 统计功能
- [x] `_get_zclaw_dir` 辅助函数
- [x] validate_p11.py 29/29 通过
- [x] 全量测试 P0-P11: 104/105 通过
