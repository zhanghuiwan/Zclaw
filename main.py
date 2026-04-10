"""
Zclaw - 简易对话入口

使用方式:
    1. 复制 .env.example 为 .env，填入你的 API 配置
    2. 运行: python main.py
    3. 直接输入问题开始对话

支持命令:
    /clear  - 清空对话历史
    /undo   - 撤销上一轮对话
    /info   - 显示当前配置
    /quit   - 退出
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import load_settings_from_env, _find_env_file
from src.core.agent import Agent
from src.cli.renderer import Renderer
from src.llm.models import StreamEventType

logger = logging.getLogger(__name__)

# 颜色辅助（不依赖 rich 的简单 ANSI）
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════╗
║         Zclaw v0.1.0 - Chat Mode     ║
║     Claude Code 风格 AI 编程助手      ║
╚══════════════════════════════════════╝{RESET}
""")


def print_status(provider: str, model: str):
    print(f"  {DIM}Provider: {CYAN}{BOLD}{provider}{RESET}  |  "
          f"{DIM}模型: {CYAN}{BOLD}{model}{RESET}")
    print(f"  {DIM}输入消息后按 Enter 开始对话。{RESET}")
    print(f"  {DIM}输入 /help 查看命令，/quit 退出。{RESET}\n")


def print_help():
    print(f"""
{CYAN}{BOLD}  可用命令:{RESET}
    {CYAN}/help{RESET}       显示帮助信息
    {CYAN}/clear{RESET}      清空对话历史
    {CYAN}/undo{RESET}       撤销上一轮对话
    {CYAN}/info{RESET}       显示当前配置
    {CYAN}/quit{RESET}       退出程序
    {CYAN}/exit{RESET}       退出程序
""")


def print_error(msg: str):
    print(f"\n{RED}{BOLD}  错误:{RESET} {RED}{msg}{RESET}\n")


def print_info(msg: str):
    print(f"{DIM}  {msg}{RESET}")


def print_success(msg: str):
    print(f"{GREEN}  OK {msg}{RESET}")


async def auto_approve_permission(request):
    """自动批准安全工具，拒绝危险工具。"""
    from src.security.permission import DangerLevel

    tool_name = request.tool_name
    danger = request.danger_level

    if danger == DangerLevel.SAFE:
        print(f"  {DIM}-> {tool_name} 自动批准 (安全){RESET}")
        return True
    elif danger == DangerLevel.CONFIRM:
        # 对于需要确认的工具，自动批准（简洁模式）
        print(f"  {YELLOW}-> {tool_name} 自动批准 (需确认){RESET}")
        return True
    else:  # DANGEROUS
        print(f"  {RED}-> {tool_name} 已阻止 (危险操作){RESET}")
        print(f"    {DIM}参数: {request.arguments}{RESET}")
        return False


async def chat_loop(agent: Agent, renderer: Renderer):
    """主对话循环。"""
    print_banner()

    # 显示配置状态
    provider_name = agent._settings.llm.default_provider
    provider_config = agent._settings.llm.providers[provider_name]
    print_status(provider_name, provider_config.model)

    # 设置权限回调（简洁模式自动审批安全工具）
    agent.permission_manager.set_confirm_callback(auto_approve_permission)

    # 命令行历史
    history = InMemoryHistory()

    # 创建 prompt session（禁用自动提交，手动处理输出）
    session = PromptSession(
        history=history,
        enable_history_search=False,
    )

    while True:
        try:
            user_input = await session.prompt_async("> ")
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{DIM}  再见！{RESET}\n")
            break

        user_input = user_input.strip()
        if not user_input:
            print(f"{CYAN}> {RESET}", end="", flush=True)
            continue

        # 处理命令
        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]
            if cmd in ("/quit", "/exit", "/q"):
                print(f"\n{DIM}  再见！{RESET}\n")
                break
            elif cmd == "/help":
                print_help()
            elif cmd == "/clear":
                agent.clear_history()
                print_success("对话历史已清空。")
            elif cmd == "/undo":
                msgs = agent.loop.messages
                if len(msgs) >= 2:
                    last_user_idx = None
                    for i in range(len(msgs) - 1, -1, -1):
                        if msgs[i].role.value == "user":
                            last_user_idx = i
                            break
                    if last_user_idx and last_user_idx > 0:
                        removed = msgs[last_user_idx:]
                        agent.loop._messages = msgs[:last_user_idx]
                        print_success(f"已撤销 {len(removed)} 条消息。")
                    else:
                        print_info("没有可撤销的操作。")
                else:
                    print_info("没有可撤销的操作。")
            elif cmd == "/info":
                s = agent._settings
                pc = s.llm.providers[s.llm.default_provider]
                print(f"""
{CYAN}{BOLD}  当前配置:{RESET}
    Provider:      {s.llm.default_provider}
    模型:         {pc.model}
    Base URL:      {pc.base_url}
    最大上下文:   {pc.max_context_tokens} tokens
    温度:         {s.llm.temperature}
    最大 Tokens:  {s.llm.max_tokens}
    最大轮次:     {s.agent.max_loop_rounds}
    工具:         {len(agent.tools)} 个已注册
    状态:         {agent.state.value}
""")
            else:
                print_info(f"未知命令: {cmd}。输入 /help 查看可用命令。")

            print(f"\n{CYAN}> {RESET}", end="", flush=True)
            continue

        # 处理对话
        print()  # 空行分隔
        round_prompt = 0
        round_completion = 0

        try:
            async for event in agent.chat_stream(user_input):
                if event.type == StreamEventType.CONTENT_DELTA:
                    # 直接输出，不做任何处理（流式）
                    print(event.data, end="", flush=True)
                elif event.type == StreamEventType.USAGE:
                    round_prompt += event.data.prompt_tokens
                    round_completion += event.data.completion_tokens
                elif event.type == StreamEventType.TOOL_EXECUTE_START:
                    print(f"\n  {YELLOW}* {event.data['name']}{RESET} 执行中...", flush=True)
                elif event.type == StreamEventType.TOOL_EXECUTE_END:
                    name = event.data["name"]
                    if event.data["success"]:
                        print(f"  {GREEN}OK {name}{RESET} 完成")
                    else:
                        print(f"  {RED}X {name}{RESET} 失败: {event.data.get('error', '未知')}")
                elif event.type == StreamEventType.LOOP_START:
                    if event.data["round"] > 1:
                        print(f"\n  {DIM}--- 第 {event.data['round']} 轮 ---{RESET}")
                elif event.type == StreamEventType.DONE:
                    pass

        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg or "connection" in error_msg:
                print_error(f"无法连接到 LLM 服务。\n  {error_msg}")
            elif "401" in error_msg or "auth" in error_msg.lower():
                print_error(f"API Key 认证失败。\n  {error_msg}")
            else:
                print_error(error_msg)

        # 显示 token 用量
        total = round_prompt + round_completion
        if total > 0:
            print(f"\n{DIM}  Tokens: {round_prompt}+{round_completion} = {total}{RESET}")

        print(f"\n{CYAN}> {RESET}", end="", flush=True)


def main():
    """主入口函数。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="Zclaw Chat",
        description="Zclaw - 简易对话模式 (使用 .env 配置)",
    )
    parser.add_argument(
        "--env", "-e",
        type=str,
        default=None,
        help="指定 .env 文件路径",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="开启详细日志",
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default=None,
        help="非交互模式：单次提问后退出",
    )
    args = parser.parse_args()

    # 日志配置
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # 检查 .env 文件
    env_path = Path(args.env) if args.env else None
    if env_path is None:
        from src.config.settings import _find_env_file
        env_path = _find_env_file()
        if env_path is None:
            # 尝试 main.py 同级目录
            main_env = Path(__file__).resolve().parent / ".env"
            if main_env.exists():
                env_path = main_env

    if env_path is None or not env_path.exists():
        print_error(
            "未找到 .env 文件！\n"
            "  请在项目目录下创建 .env 文件。\n"
            "  可以复制 .env.example 作为模板:\n"
            "    cp .env.example .env\n"
            "  然后编辑 .env 填入你的 API 配置。"
        )
        sys.exit(1)

    print_info(f"从以下路径加载配置: {env_path}")

    # 加载配置
    try:
        settings = load_settings_from_env(env_path=env_path)
    except Exception as e:
        print_error(f"加载配置失败: {e}")
        sys.exit(1)

    # 初始化 Agent
    try:
        agent = Agent(settings)
    except Exception as e:
        print_error(f"初始化 Agent 失败: {e}")
        sys.exit(1)

    renderer = Renderer()

    # 非交互模式
    if args.prompt:
        asyncio.run(_single_prompt(agent, args.prompt, renderer))
        return

    # 交互模式
    try:
        asyncio.run(chat_loop(agent, renderer))
    except KeyboardInterrupt:
        print(f"\n\n{DIM}  再见！{RESET}\n")


async def _single_prompt(agent: Agent, prompt: str, renderer: Renderer):
    """非交互模式：单次提问。"""
    try:
        async for event in agent.chat_stream(prompt):
            if event.type == StreamEventType.CONTENT_DELTA:
                print(event.data, end="", flush=True)
            elif event.type == StreamEventType.TOOL_EXECUTE_START:
                print(f"\n  {event.data['name']} 执行中...", flush=True)
            elif event.type == StreamEventType.TOOL_EXECUTE_END:
                name = event.data["name"]
                status = "完成" if event.data["success"] else f"失败: {event.data.get('error')}"
                print(f"  {name} {status}")
            elif event.type == StreamEventType.LOOP_START:
                if event.data["round"] > 1:
                    print(f"\n  --- 第 {event.data['round']} 轮 ---")
    except Exception as e:
        print_error(str(e))
        sys.exit(1)
    print()  # final newline


if __name__ == "__main__":
    main()
