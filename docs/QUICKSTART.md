# Zclaw 快速入门

## 安装

```bash
# 安装项目（开发模式）
pip install -e .

# 安装依赖
pip install -r requirements.txt
```

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填入你的 API 配置：

```env
ZCLAW_PROVIDER=minmax
ZCLAW_MODEL=MiniMax-M2.7
ZCLAW_API_KEY=your_api_key
ZCLAW_BASE_URL=https://api.minimaxi.com/v1
```

## 快速开始

### 启动 Gateway

```bash
python main.py start
# 或
zclaw start
```

### 连接对话

```bash
python main.py
# 或
zclaw
```

### 其他命令

```bash
python main.py status   # 查看状态
python main.py stop     # 停止
python main.py restart  # 重启
```

## Gateway 架构

```
┌─────────────────────────────────────────┐
│           Gateway (守护进程)            │
│         ws://127.0.0.1:8080             │
└─────────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│zclaw    │    │WebSocket│    │  IM     │
│(CLI)    │    │(Web)    │    │(Future) │
└─────────┘    └─────────┘    └─────────┘
```

Gateway 是独立进程，支持多个客户端同时连接。

## 端口配置

在 `.env` 中配置：

```env
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8080
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `start` | 启动 Gateway |
| `stop` | 停止 Gateway |
| `restart` | 重启 Gateway |
| `status` | 查看状态 |
| `--daemon, -d` | 后台守护进程模式 |
| `--gateway` | 启动 Gateway（兼容旧参数） |
| `--stdio` | STDIO 模式（兼容旧参数） |