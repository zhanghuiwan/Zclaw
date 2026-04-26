# Zclaw Gateway 架构修改计划

## 背景

当前架构存在入口点混乱、Gateway 无进程管理、客户端未分离等问题。本次修改将 Gateway 设计为独立进程，客户端通过 WebSocket 连接，实现与 IM 通讯工具的对接能力。

---

## 修改目标

| 目标 | 说明 |
|------|------|
| Gateway 独立运行 | 作为守护进程在后台运行 |
| 统一客户端入口 | `zclaw` 命令统一管理 gateway 和对话 |
| 进程管理 | 支持 start/stop/status 等生命周期管理 |
| IM 对接准备 | WebSocket 接口支持第三方客户端连接 |

---

## 新架构

```
                    ┌─────────────────────┐
                    │  Gateway (守护进程)  │
                    │  ws://:8080         │
                    │  PID: ~/.Zclaw/gateway.pid
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
   │python main.py│      │    zclaw    │      │  IM 客户端  │
   │   (CLI)     │      │   (CLI)     │      │   (未来)    │
   └─────────────┘      └─────────────┘      └─────────────┘
```

---

## 环境配置

`.env` 新增配置项：

```env
# Gateway 配置
GATEWAY_PORT=8080
GATEWAY_HOST=127.0.0.1
GATEWAY_PID_DIR=~/.Zclaw
```

---

## 分阶段实施计划

---

### 阶段 1：基础设施 — GatewayManager

**目标**：实现 Gateway 进程管理能力

**新增文件**：
- `src/channel/gateway_manager.py`

**核心功能**：
```python
class GatewayManager:
    def start() -> bool
        # 1. 检查是否已运行
        # 2. fork 子进程启动 gateway_server
        # 3. 写入 PID 文件 (~/.Zclaw/gateway.pid)
        # 4. 等待端口可连接
        # 5. 返回成功/失败

    def stop() -> bool
        # 1. 读取 PID 文件
        # 2. 发送 SIGTERM
        # 3. 等待进程退出
        # 4. 删除 PID 文件

    def status() -> dict
        # 返回 {running: bool, pid: int|None, port: int}

    def is_running() -> bool
```

**验证问题**：
| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| `zclaw start` 启动 | 执行 `zclaw start` | 后台启动，输出 "Gateway started (PID: xxx)" |
| `zclaw status` 检查 | 执行 `zclaw status` | 显示 running, PID, port |
| `zclaw start` 重复启动 | 启动后再次执行 | 报错 "Gateway is already running" |
| `zclaw stop` 停止 | 执行 `zclaw stop` | 进程退出，PID 文件删除 |
| `zclaw stop` 未运行 | 未启动时执行 | 报错 "Gateway is not running" |
| 端口可连接 | 启动后 `curl http://127.0.0.1:8080/api/status` | 返回 JSON 状态 |

---

### 阶段 2：基础设施 — 配置读取

**目标**：从 .env 读取 Gateway 配置

**修改文件**：
- `src/config/settings.py`

**新增配置**：
```python
@dataclass
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    pid_dir: str = "~/.Zclaw"
```

**验证问题**：
| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 默认端口 | .env 无 GATEWAY_PORT 时启动 | 使用 8080 |
| 自定义端口 | .env 设置 GATEWAY_PORT=9090 | 使用 9090 |
| PID 目录存在 | ~/.Zclaw 不存在时启动 | 自动创建目录 |

---

### 阶段 3：Gateway 服务端增强

**目标**：Gateway 支持 PID 文件和优雅关闭

**修改文件**：
- `src/web/gateway_server.py`
- `src/channel/gateway.py`

**新增功能**：
- 启动时写入 PID 文件
- 接收 SIGTERM 信号优雅关闭
- 关闭时删除 PID 文件

**验证问题**：
| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| PID 文件创建 | 启动 gateway 后 | ~/.Zclaw/gateway.pid 存在 |
| PID 文件删除 | 优雅关闭后 | PID 文件被删除 |
| SIGTERM 处理 | `kill <PID>` | 进程优雅退出 |
| 强制关闭 | `kill -9 <PID>` | PID 文件仍被清理 |

---

### 阶段 4：客户端 — GatewayClient

**目标**：实现 WebSocket 客户端 REPL

**新增文件**：
- `src/channel/gateway_client.py`

**核心功能**：
```python
class GatewayClient:
    def connect() -> None
        # 连接 ws://127.0.0.1:8080/api/ws/gateway

    async def run_repl() -> None
        # 完整 REPL 循环
        # 接收用户输入 → WebSocket 发送 → 流式接收 → 显示

    async def chat(input: str) -> AsyncGenerator[StreamEvent]
        # 发送消息，yield 事件
```

**事件处理**（与当前 REPL 一致）：
- CONTENT_DELTA → 流式输出
- TOOL_EXECUTE_START/END → 显示工具执行
- USAGE → 统计 token
- DONE → 完成

**验证问题**：
| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 连接成功 | `zclaw` 连接已启动的 gateway | 显示 banner，进入 REPL |
| 连接失败 | gateway 未运行时执行 `zclaw` | 提示 "Gateway not running, run 'zclaw start' first" |
| 对话功能 | REPL 中发送消息 | 与直接 Agent 对话体验一致 |
| 流式输出 | 发送长消息 | 逐字流式显示 |
| 工具执行 | 触发工具调用 | 显示工具执行过程 |
| /help 命令 | REPL 中输入 /help | 显示帮助信息 |
| Ctrl+C | REPL 中按 Ctrl+C | 取消当前生成，不退出 REPL |
| Ctrl+D /quit | 输入 /quit | 退出 REPL（gateway 继续运行） |

---

### 阶段 5：入口点重定向

**目标**：`zclaw` 命令指向新的命令解析器

**修改文件**：
- `src/cli/commands.py` (新增)
- `pyproject.toml`

**新增命令结构**：
```bash
zclaw start          # 启动 gateway
zclaw stop           # 停止 gateway
zclaw status         # 查看状态
zclaw                # 默认：连接 gateway REPL
zclaw --gateway      # 启动 gateway（兼容旧参数）
```

**入口点重定向**：
```toml
# pyproject.toml
[project.scripts]
zclaw = "src.cli.commands:main"
```

**验证问题**：
| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| zclaw 命令存在 | 安装后执行 `zclaw` | 命令可用，显示帮助 |
| zclaw start | 执行 `zclaw start` | 启动 gateway |
| zclaw stop | 执行 `zclaw stop` | 停止 gateway |
| zclaw status | 执行 `zclaw status` | 显示状态 |
| zclaw (无参数) | 执行 `zclaw` | 连接 gateway REPL |
| --help | 执行 `zclaw --help` | 显示帮助信息 |

---

### 阶段 6：main.py 适配

**目标**：`python main.py` 等同于 `zclaw`

**修改文件**：
- `main.py`

**行为**：
```bash
python main.py           # 等同于 zclaw（连接 REPL）
python main.py start     # 等同于 zclaw start
python main.py stop      # 等同于 zclaw stop
python main.py status    # 等同于 zclaw status
```

**验证问题**：
| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| main.py 无参数 | `python main.py` | 提示 gateway 未运行或连接 |
| main.py start | `python main.py start` | 启动 gateway |
| main.py stop | `python main.py stop` | 停止 gateway |
| main.py status | `python main.py status` | 显示状态 |

---

### 阶段 7：清理与废弃

**目标**：移除旧的直接 Agent 对话代码

**删除/注释文件**：
- `src/cli/app.py` 中的 `REPL` 类（保留 Renderer）
- `main.py` 中的 `chat_loop` 函数

**移除启动模式**：
- 移除 `--chat` 参数
- 移除直接 Agent 创建逻辑

**验证问题**：
| 验证项 | 操作 | 预期结果 |
|--------|------|----------|
| 代码清理 | 搜索 `Agent(settings)` | 只存在于 agent_pool.py |
| 无 --chat | `python main.py --chat` | 报错 "unknown option" |
| 无双重 REPL | 搜索 `PromptSession` | 只在 gateway_client.py 中 |

---

## 阶段依赖关系

```
阶段1 ──→ 阶段2 ──→ 阶段3 ──→ 阶段4 ──→ 阶段5 ──→ 阶段6 ──→ 阶段7
  │           │           │           │           │
  ▼           ▼           ▼           ▼           ▼
GatewayManager  配置读取    服务端增强   客户端     入口点     main.py
                                                    │
                                                    ▼
                                                 清理
```

---

## 测试检查清单

### 阶段 1 完成后
- [ ] `zclaw start` 成功启动
- [ ] `zclaw status` 显示正确
- [ ] 重复启动报错
- [ ] `zclaw stop` 成功停止

### 阶段 2 完成后
- [ ] .env 配置生效
- [ ] 默认值正确

### 阶段 3 完成后
- [ ] PID 文件管理正确
- [ ] 信号处理正常

### 阶段 4 完成后
- [ ] REPL 功能完整
- [ ] 流式输出正常
- [ ] 工具调用正常

### 阶段 5 完成后
- [ ] 入口点正确
- [ ] 所有子命令可用

### 阶段 6 完成后
- [ ] main.py 行为一致

### 阶段 7 完成后
- [ ] 无废弃代码
- [ ] 代码整洁

---

## 文档更新

修改完成后需更新：
- `docs/ARCHITECTURE.md` — 反映新架构
- `README.md` — 更新启动方式说明

---

## 回滚计划

如遇问题，可按阶段回滚：
- 阶段 7 回滚：恢复 app.py 和 chat_loop
- 阶段 6 回滚：恢复 main.py 旧逻辑
- 阶段 5 回滚：恢复 pyproject.toml 入口点
- 阶段 4 回滚：删除 gateway_client.py
- 阶段 3 回滚：移除 PID 和信号处理代码
- 阶段 2 回滚：移除配置读取代码
- 阶段 1 回滚：删除 gateway_manager.py