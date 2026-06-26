<div align="center">

# 🦀 Zclaw

**结合 Claude Code 与 OpenClaw 的 AI 编程助手**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Version](https://img.shields.io/badge/Version-0.6.1-green.svg)]()
[![License](https://img.shields.io/badge/License-MIT-orange.svg)]()

一个用 Python 编写的 AI 编程助手，将大语言模型（LLM）与本地文件系统、Shell 环境深度结合，
让 AI 能够像人类程序员一样读取代码、修改文件、执行命令、搜索项目，从而完成复杂的编程任务。

**当前状态**: Claude Code 核心功能已基本完成，正积极开发类似 OpenClaw 的自主 Agent 能力。

</div>

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **多模型支持** | 统一的 OpenAI 兼容接口，支持阿里百炼、Ollama、Azure 等任意兼容服务 |
| 🔧 **工具调用循环** | Agent Loop 机制，LLM 可自主决定调用哪些工具、调用多少轮 |
| 🔒 **分层安全** | 三级危险等级（safe/confirm/dangerous）+ 路径限制 + 命令拦截 + 审计日志 |
| 🧠 **持久记忆** | 分层记忆架构（L0-L4），Agent 驱动的自主探索模式，状态与历史分离 |
| 📏 **智能上下文** | 自动检测并压缩长对话，适配不同模型的 token 限制 |
| 🔌 **插件扩展** | 用户可通过编写 Python 文件自定义工具，支持热重载 |
| 🌐 **Web UI** | FastAPI + WebSocket 构建的现代化 Web 界面，实时流式输出 |
| 🐙 **Git 集成** | diff、commit、log、status、branch、show、blame 全功能支持 |
| 🧩 **语法感知** | 基于 AST 的代码结构分析、符号查找、精确替换、导入分析 |
| 🔗 **MCP 协议** | 连接外部 MCP 工具服务器，自动注册工具到 Agent |
| 📋 **任务规划** | 复杂任务前自动生成执行计划，跟踪步骤进度 |
| 🧩 **Skills 扩展** | 类似 Claude Code / OpenClaw，支持项目和全局 Skills 扩展 |
| 💰 **费用追踪** | Token 用量实时统计和费用估算 |

## 🏗️ 项目结构

```
Zclaw/
├── main.py                          # 简易对话入口
├── config.example.yaml              # 配置示例
├── config.mcp.example.json          # MCP 配置示例
├── pyproject.toml                   # 项目元数据
├── README.md                        # 项目文档
├── ARCHITECTURE.md                  # 技术架构文档
├── src/
│   ├── config/                      # 配置管理
│   │   └── settings.py
│   ├── llm/                         # LLM 抽象层
│   │   ├── models.py                # 数据模型
│   │   ├── base.py                  # Provider 基类
│   │   ├── openai_compat.py         # OpenAI 兼容实现
│   │   └── router.py                # LLM 路由器
│   ├── core/                        # 核心引擎
│   │   ├── state.py                 # 状态机
│   │   ├── loop.py                  # Agent 循环
│   │   ├── agent.py                 # Agent 主类
│   │   ├── plan.py                  # 计划数据结构
│   │   └── planner.py              # 任务规划器
│   ├── tools/                       # 工具系统
│   │   ├── base.py                  # BaseTool + ToolResult
│   │   ├── registry.py              # 工具注册表
│   │   ├── cache.py                 # LRU 结果缓存
│   │   └── builtin/                 # 内置工具
│   │       ├── file_tools.py        # 文件操作
│   │       ├── search_tools.py      # 文件搜索
│   │       ├── shell_tool.py        # Shell 命令
│   │       ├── grep_tool.py         # 正则搜索
│   │       ├── glob_tool.py         # Glob 匹配
│   │       ├── multi_edit_tool.py   # 批量编辑
│   │       ├── line_edit_tool.py    # 行号编辑
│   │       ├── diff_tool.py         # Diff 预览 + 快照
│   │       ├── git_tool.py          # Git 集成
│   │       └── ast_tool.py          # 语法分析
│   ├── sandbox/
│   │   └── runner.py                # 命令运行器
│   ├── security/                    # 安全系统
│   │   ├── permission.py            # 权限管理
│   │   ├── validator.py             # 输入/输出校验
│   │   └── audit.py                 # 审计日志
│   ├── memory/                      # 记忆模块
│   │   ├── config.py                # 配置
│   │   ├── coordinator.py           # 记忆协调器
│   │   ├── extractor.py            # LLM 提取器
│   │   ├── layers/                 # 分层实现
│   │   │   ├── l0_perceptual.py   # RingBuffer
│   │   │   ├── l1_working.py      # 会话快照
│   │   │   ├── l2_episodic.py     # SQLite-VSS 向量存储
│   │   │   ├── l3_semantic.py     # JSON 当前状态
│   │   │   └── l4_procedural.py   # YAML 规则
│   │   └── tools/                  # 记忆工具
│   │       ├── episodic_search.py   # 搜索历史工具
│   │       └── memory_tools.py     # 更新记忆工具
│   ├── context/                     # 上下文管理
│   │   ├── budget.py               # Token 预算
│   │   ├── compressor.py           # 对话压缩
│   │   └── manager.py              # 上下文管理器
│   ├── prompt/                      # 提示词工程
│   │   ├── templates.py            # 模板库
│   │   └── builder.py              # 动态组装器
│   ├── mcp/                         # MCP 协议
│   │   ├── types.py                 # 数据类型
│   │   ├── transport.py             # 传输层
│   │   ├── client.py               # MCP 客户端
│   │   ├── adapter.py              # 工具适配器
│   │   └── manager.py              # MCP 管理器
│   ├── plugins/                     # 插件系统
│   │   └── loader.py               # 插件加载器
│   ├── skills/                      # Skills 模块
│   │   ├── config.py               # 配置管理
│   │   ├── executor.py             # Skill 执行器
│   │   ├── loader.py              # Skill 发现与加载
│   │   ├── manager.py             # Skill 管理器
│   │   ├── models.py              # 数据模型
│   │   ├── registry.py            # Skill 注册表
│   │   └── tool.py                # Skill 工具包装
│   ├── web/                         # Web UI
│   │   ├── server.py                # FastAPI 应用
│   │   ├── routes.py               # API 路由
│   │   ├── schemas.py              # 数据模型
│   │   ├── ws_manager.py           # WebSocket 管理
│   │   └── static/                  # 前端静态文件
│   └── cli/                         # CLI 界面
│       ├── app.py                   # REPL 入口
│       ├── renderer.py              # Rich 渲染
│       ├── session.py              # 会话管理
│       └── cost_tracker.py         # 费用追踪
└── tests/                           # 验证测试
```

## 🚀 快速开始

### 1. 安装

```bash
cd Zclaw
pip install -e .
```

### 2. 配置 API Key

复制环境变量模板并填入你的 API 配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
ZCLAW_PROVIDER=bailian          # 或 ollama, openai 等
ZCLAW_MODEL=qwen-plus           # 或其他模型
ZCLAW_API_KEY=sk-xxxxxxx        # 你的 API Key
ZCLAW_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

也可以不创建 `.env` 文件，直接通过环境变量启动：

```bash
export ZCLAW_API_KEY=sk-xxxxxxx
Zclaw
```

### 3. 运行

```bash
# 交互模式（两者等价）
python main.py
Zclaw

# 非交互模式（单次提问）
python main.py -p "列出当前目录的文件"
Zclaw -p "列出当前目录的文件"

# 启动 Web UI
python -m src.web.server
```

## 🛠️ 工具清单

Zclaw 内置 **28 个工具**，分为 6 大类：

### 📁 文件工具（8 个）

| 工具 | 危险等级 | 功能 |
|------|---------|------|
| `file_read` | safe | 读取文件内容，支持 offset/limit 分段 |
| `file_write` | confirm | 创建新文件或完全覆盖 |
| `file_edit` | confirm | 精确替换文件中的旧文本 |
| `multi_edit` | confirm | 对同一文件原子执行多处替换 |
| `line_edit` | confirm | 按行号替换/插入/删除 |
| `line_read` | safe | 按行号范围读取，显示行号 |
| `diff` | safe | 比较文本/文件差异（unified/并排） |
| `snapshot` | confirm | 文件快照管理（保存/恢复/删除） |

### 🔍 搜索工具（4 个）

| 工具 | 危险等级 | 功能 |
|------|---------|------|
| `directory` | safe | 列出目录内容 |
| `file_search` | safe | 按文件名或内容搜索 |
| `grep` | safe | 正则表达式搜索（include/exclude/上下文） |
| `glob` | safe | Glob 模式匹配查找文件 |

### 💻 系统工具（1 个）

| 工具 | 危险等级 | 功能 |
|------|---------|------|
| `shell` | confirm/dangerous | 执行 Shell 命令，动态危险检测 |

### 🐙 Git 工具（7 个）

| 工具 | 危险等级 | 功能 |
|------|---------|------|
| `git_diff` | safe | 查看差异（未暂存/已暂存/提交间/文件） |
| `git_commit` | confirm | 暂存并提交（支持 amend） |
| `git_log` | safe | 查看提交历史（支持过滤） |
| `git_status` | safe | 查看仓库状态 |
| `git_branch` | confirm | 查看/创建/切换分支 |
| `git_show` | safe | 查看提交详情 |
| `git_blame` | safe | 查看行级修改信息 |

### 🧩 分析工具（4 个）

| 工具 | 危险等级 | 功能 |
|------|---------|------|
| `code_structure` | safe | AST 代码结构分析（类/函数/导入） |
| `symbol_find` | safe | 按名称查找符号定义 |
| `symbol_edit` | confirm | 按符号名称精确替换函数/类 |
| `import_analyze` | safe | 导入依赖分析 + 未使用检测 |

### 🧠 记忆工具（4 个）

| 工具 | 危险等级 | 功能 |
|------|---------|------|
| `search_conversation_history` | safe | 搜索历史对话记录（跨会话） |
| `get_session_history` | safe | 获取特定会话的完整历史 |
| `update_memory` | safe | 更新用户/项目的持久化记忆 |
| `set_preference` | safe | 设置单个用户偏好 |

## ⌨️ CLI 命令

默认入口 `Zclaw` 与 `python main.py` 共用同一套简易对话实现，支持：

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清空对话历史 |
| `/undo` | 撤销上一轮对话 |
| `/info` | 显示当前配置 |
| `/quit` `/exit` | 退出 |

完整 REPL 入口仍保留，可通过 `python -m src.cli.app` 启动。

## ⚙️ 配置说明

### 环境变量 (.env)

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ZCLAW_PROVIDER` | LLM 提供者名称 | `bailian` |
| `ZCLAW_MODEL` | 模型名称 | `qwen-plus` |
| `ZCLAW_API_KEY` | API Key | — |
| `ZCLAW_BASE_URL` | API 基础 URL | 百炼地址 |
| `ZCLAW_MAX_CONTEXT_TOKENS` | 最大上下文 token | `131072` |
| `ZCLAW_TEMPERATURE` | 温度参数 | `0.3` |
| `ZCLAW_MAX_TOKENS` | 最大生成 token | `8192` |
| `ZCLAW_MAX_LOOP_ROUNDS` | 最大循环轮数 | `50` |

### YAML 配置 (.Zclaw.yaml)

```yaml
llm:
  default_provider: bailian
  temperature: 0.3
  max_tokens: 8192
  providers:
    bailian:
      base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
      api_key: ${DASHSCOPE_API_KEY}
      model: qwen-plus
      max_context_tokens: 131072
      supports_tools: true

agent:
  max_loop_rounds: 50

memory:
  storage_path: ~/.Zclaw/memory
  episodic_max_age_days: 90

security:
  audit_log: true
  path_restrictions:
    allow: ["."]
    deny: ["/etc", "/usr", "/bin"]

web:
  enabled: true
  host: 0.0.0.0
  port: 8080

mcp:
  enabled: true
  auto_connect: true
  config_path: ~/.Zclaw/mcp_servers.json
```

## 🔌 插件开发

在 `~/.Zclaw/plugins/` 目录下创建 Python 文件即可扩展工具：

```python
# ~/.Zclaw/plugins/my_tool.py
from src.tools.base import BaseTool, ToolResult, ToolParameter, DangerLevel, ToolMetadata

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "A custom tool"
    parameters = [
        ToolParameter(name="input", type="string", description="Input", required=True)
    ]
    metadata = ToolMetadata(category="custom", danger_level=DangerLevel.SAFE)

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult.ok(f"Result: {kwargs['input']}")
```

## 🔗 MCP 集成

Zclaw 支持连接外部 MCP (Model Context Protocol) 工具服务器：

```json
// config.mcp.json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-filesystem", "/path/to/dir"],
      "transport": "stdio"
    },
    "web-search": {
      "url": "http://localhost:3001/sse",
      "transport": "sse"
    }
  }
}
```

## 🧩 Skills 模块

Zclaw 支持 Skills 功能，遵循 Claude Code / OpenClaw 通用标准，允许扩展 AI 的专业能力。

### 目录结构

Skills 从以下目录加载，与 Claude Code / OpenClaw 兼容：

| 类型 | 目录 | 说明 |
|------|------|------|
| 全局 | `~/.agents/skills/` | 所有项目共享的 Skills |
| 项目 | `project_root/.agents/skills/` | 仅当前项目可用的 Skills |

每个 Skill 放在独立目录中，包含 `SKILL.md` 定义文件。

### 核心功能

- **自动匹配**: 根据触发词自动匹配相关 Skills
- **上下文注入**: 将匹配的 Skill 内容注入到 LLM 上下文
- **依赖检查**: 自动检查环境变量和二进制程序是否配置
- **热重载**: 支持重新加载 Skills
- **工具包装**: Skill 可作为 Tool 被 Agent 调用

## 🌐 Web UI

Zclaw 提供完整的 Web 界面：

- 实时流式对话（WebSocket）
- 工具执行可视化
- 权限确认对话框
- 文件浏览器
- 工具列表面板
- 会话管理
- 费用统计
- 暗色主题

```bash
python -m src.web.server
# 访问 http://localhost:8080
```

## 🔒 安全特性

Zclaw 采用多层次安全机制，详见 [ARCHITECTURE.md](ARCHITECTURE.md)。

### 三级危险等级

| 等级 | 行为 | 示例工具 |
|------|------|---------|
| `safe` | 自动批准 | `file_read`, `grep`, `glob` |
| `confirm` | 需用户确认 | `shell`, `file_write`, `git_commit` |
| `dangerous` | 始终确认 | 高危系统命令 |

**权限判定流程**: auto_approve列表 → blocked_patterns → 路径限制 → 危险等级

### 路径限制

文件工具 (`file_read/write/edit`) 受路径限制约束：
- **黑名单**: `/etc`, `/usr`, `/bin`, `/sbin`, `/proc`, `/sys` 等系统目录
- **白名单**: 默认为当前目录 (`.`)

### 危险命令拦截

Shell 工具拦截以下正则模式：
```
rm\s+-rf\s+/  |  sudo\s+  |  mkfs  |  dd\s+if=  |  :\(\)\{
```

### 输入校验 (Validator)

| 校验类型 | 检测内容 |
|---------|---------|
| 路径穿越 | `../`, `..\` |
| 命令注入 | 过多链式命令 (`;`) |
| 长度限制 | 最大 1MB 文件 |
| 空输入 | 空路径/空命令 |

### 输出清洗

- **敏感信息脱敏**: API Key、Token、Password、AWS 密钥
- **控制字符清理**: 保留 `\n\r\t`，过滤 ASCII < 32
- **输出截断**: 最大 50,000 字符

### 审计日志

JSONL 格式存储于 `~/.Zclaw/audit/`，自动脱敏敏感参数字段。

## 📊 开发进度

### 模块进度

| 模块 | 功能 | 状态 |
|------|------|------|
| **配置管理** | Settings 配置加载、环境变量、YAML | ✅ 已完成 |
| **LLM 层** | 多模型支持、OpenAI 兼容接口、Router 路由 | ✅ 已完成 |
| **核心引擎** | Agent、Loop、State、Planner、Plan | ✅ 已完成 |
| **工具系统** | 28 个内置工具、注册表、缓存 | ✅ 已完成 |
| **沙箱执行** | CommandRunner 超时控制 | ✅ 已完成 |
| **安全系统** | 权限管理、校验、审计日志 | ✅ 已完成 |
| **记忆模块** | L0-L4 分层记忆、协调器、提取器 | ✅ 已完成 |
| **上下文管理** | Token 预算、压缩器 | ✅ 已完成 |
| **提示词工程** | 模板库、PromptBuilder | ✅ 已完成 |
| **插件系统** | PluginLoader 热重载 | ✅ 已完成 |
| **Skills 模块** | SkillManager、自动匹配、上下文注入 | ✅ 已完成 |
| **MCP 协议** | MCPClient、Transport、Adapter、Manager | ✅ 已完成 |
| **Web UI** | FastAPI + WebSocket、实时流式 | ✅ 已完成 |
| **CLI 界面** | REPL、Rich 渲染、会话管理 | ✅ 已完成 |

### 后续开发方向

基于 OpenClaw 架构思想，未来重点发展方向：

| 方向 | 说明 |
|------|------|
| **24 小时持续运行** | Cron 调度器、Heartbeat 心跳机制、事件驱动触发 |
| **本地软件操控** | Browser 自动化（Playwright）、进程管理、屏幕截取 |
| **多 Agent 架构** | 多会话管理、Agent 间通信、子代理模式 |
| **多通道接入** | WhatsApp/Telegram/Slack/Discord 等消息通道 |

## 📄 许可证

MIT License
