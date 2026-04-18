# AGENTS.md

## 启动行为
1. 检查待办队列（~/.zclaw/todo.md）
2. 检查是否有未完成的 Heartbeat 任务
3. 问候用户并等待指令

## 工具权限

### 自动批准
- file_read
- directory
- file_search
- grep
- glob

### 需要确认
- file_write
- shell
- git_commit
- git_push
- browser_navigate

### 禁止
- 格式化磁盘
- rm -rf / 系统目录

## Cron 任务
- "0 9 * * 1-5": 每天9点检查邮件并汇总
- "0 */4 * * *": 每4小时检查服务器状态

## Heartbeat 配置
- 间隔：300 秒（5分钟）
- 任务：
  - 检查待办队列
  - 检查新消息
