<div align="center">

# 🦀 Zclaw

**类 Claude Code 的 AI 编程助手**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Version](https://img.shields.io/badge/Version-0.4.0-green.svg)]()
[![License](https://img.shields.io/badge/License-MIT-orange.svg)]()

一个用 Python 编写的 AI 编程助手，将大语言模型（LLM）与本地文件系统、Shell 环境深度结合，
让 AI 能够像人类程序员一样读取代码、修改文件、执行命令、搜索项目，从而完成复杂的编程任务。

</div>

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🤖 **多模型支持** | 统一的 OpenAI 兼容接口，支持阿里百炼、Ollama、Azure 等任意兼容服务 |
| 🔧 **工具调用循环** | Agent Loop 机制，LLM 可自主决定调用哪些工具、调用多少轮 |
| 🔒 **分层安全** | 三级危险等级（safe/confirm/dangerous）+ 路径限制 + 命令拦截 + 审计日志 |
| 🧠 **持久记忆** | 跨会话记忆系统，自动提取、分层管理（工作/近期/长期/归档） |
| 📏 **智能上下文** | 自动检测并压缩长对话，适配不同模型的 token 限制 |
| 🔌 **插件扩展** | 用户可通过编写 Python 文件自定义工具，支持热重载 |
| 🌐 **Web UI** | FastAPI + WebSocket 构建的现代化 Web 界面，实时流式输出 |
| 🐙 **Git 集成** | diff、commit、log、status、branch、show、blame 全功能支持 |
| 🧩 **语法感知** | 基于 AST 的代码结构分析、符号查找、精确替换、导入分析 |
| 🔗 **MCP 协议** | 连接外部 MCP 工具服务器，自动注册工具到 Agent |
| 📋 **任务规划** | 复杂任务前自动生成执行计划，跟踪步骤进度 |
| 💰 **费用追踪** | Token 用量实时统计和费用估算 |

## 🏗️ 项目结构

```
Zclaw/
├── main.py                          # 简易对话入口
├── config.example.yaml              # 配置示例
├── config.mcp.example.json          # MCP 配置示例
├── pyproject.toml                   # 项目元数据
├── ROADMAP.md                       # 开发路线图
├── ARCHITECTURE.md                  # 技术文档
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
│   │   └── builtin/                 # 内置工具 (24 个)
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
│   │   ├── types.py                 # 数据类型
│   │   ├── store.py                 # JSON 存储
│   │   ├── retriever.py             # 加权检索
│   │   ├── manager.py              # 记忆管理器
│   │   ├── extractor.py            # 自动提取
│   │   └── lifecycle.py            # 生命周期管理
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
└── tests/                           # 验证测试 (104/105)
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

### 3. 运行

```bash
# 交互模式
python main.py

# 非交互模式（单次提问）
python main.py -p "列出当前目录的文件"

# 启动 Web UI
python -m src.web.server
```

## 🛠️ 工具清单

Zclaw 内置 **24 个工具**，分为 5 大类：

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

## ⌨️ CLI 命令

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助信息 |
| `/clear` | 清空对话历史 |
| `/undo` | 撤销上一轮对话 |
| `/compact` | 手动压缩上下文 |
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
| `/mcp list\|connect\|disconnect` | MCP 服务器管理 |
| `/quit` `/exit` | 退出 |

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

Skills 从以下目录加载：
- 全局目录：`~/.zclaw/skills/`
- 项目目录：`project_root/skills/`

每个 Skill 放在独立目录中，包含 `SKILL.md` 定义文件。

### SKILL.md 格式

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

### 核心功能

| 功能 | 描述 |
|------|------|
| 自动匹配 | 根据用户输入的触发词自动匹配相关 Skills |
| 上下文注入 | 将匹配的 Skill 内容注入到 LLM 上下文 |
| 依赖检查 | 自动检查环境变量和二进制程序是否配置 |
| 热重载 | 支持重新加载 Skills |
| 工具包装 | Skill 可作为 Tool 被 Agent 调用 |

### 使用方式

```python
from src.skills import SkillManager, SkillsConfig

config = SkillsConfig.with_defaults(project_root=PROJECT_ROOT)
manager = SkillManager(config)
manager.initialize()

# 查询匹配的 skills
matches = manager.match_skills("搜索附近的美食")

# 执行 skill
result = manager.execute_skill("amap-lbs-skill", "搜索西直门周边美食")

# 获取注入上下文的 skill 内容
context = manager.get_context("我想去杭州旅游")
```

### 开发新 Skill

1. 在 `~/.zclaw/skills/` 或项目 `skills/` 目录下创建目录
2. 编写 `SKILL.md` 文件，定义名称、描述、触发词和依赖
3. SkillManager 会自动发现并加载

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
- 响应式设计

```bash
python -m src.web.server
# 访问 http://localhost:8080
```

## 🔒 安全特性

- **三级危险等级**: safe（自动批准）、confirm（用户确认）、dangerous（始终确认）
- **路径限制**: allow/deny 目录白名单/黑名单
- **危险命令拦截**: 正则匹配 `rm -rf /`、`sudo` 等危险模式
- **输入校验**: 路径穿越、命令注入、长度限制
- **输出清洗**: API Key 脱敏、控制字符清理
- **审计日志**: JSONL 格式，自动脱敏敏感信息

## 📊 开发进度

| 阶段 | 内容 | 测试 |
|------|------|------|
| P0 | 项目骨架 | 7/7 ✅ |
| P1 | 基础工具 + LLM | 8/9 |
| P2 | 安全系统 | 6/6 ✅ |
| P3 | 增强工具 + 缓存 | 7/7 ✅ |
| P4 | 记忆模块 | 5/5 ✅ |
| P5 | 上下文管理 | 5/5 ✅ |
| P6 | 提示词工程 + 规划器 | 5/5 ✅ |
| P7 | CLI 增强 + 插件系统 | 5/5 ✅ |
| P8 | 记忆系统完善 | 5/5 ✅ |
| P9 | MCP 协议集成 | 6/6 ✅ |
| P10 | Web UI | 21/21 ✅ |
| P11 | 高级编辑能力 | 29/29 ✅ |
| **合计** | | **104/105** |

## 📄 许可证

MIT License
