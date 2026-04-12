"""
CLI 应用入口

实现 REPL（Read-Eval-Print Loop）交互界面。
参考 Claude Code 风格美化界面。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style

from src.cli.renderer import Renderer
from src.config.settings import load_settings, Settings
from src.core.agent import Agent
from src.core.state import AgentState
from src.llm.models import StreamEventType
from src.security.permission import PermissionRequest

logger = logging.getLogger(__name__)

# Claude Code 风格提示符样式
PROMPT_STYLE = Style.from_dict({
    "prompt": "ansicyan bold",
    "prompt.tool": "ansimagenta bold",
    "prompt.user": "ansigreen bold",
})


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


class REPL:
    """Read-Eval-Print Loop 交互界面 - Claude Code 风格。"""

    def __init__(self, agent: Agent, settings: Settings, renderer: Renderer):
        self._agent = agent
        self._settings = settings
        self._renderer = renderer

        self._agent.permission_manager.set_confirm_callback(self._on_permission_request)

        # 费用追踪
        from src.cli.cost_tracker import CostTracker
        self._cost_tracker = CostTracker()

        # 历史文件放在项目根目录的 .Zclaw/ 下
        src_dir = Path(__file__).resolve().parent  # src/cli/
        project_root = src_dir.parent.parent  # 项目根目录
        zclaw_dir = project_root / ".Zclaw"
        zclaw_dir.mkdir(parents=True, exist_ok=True)
        history_path = zclaw_dir / "history"

        kb = KeyBindings()

        @kb.add("c-c")
        def _(event):
            buf = event.current_buffer
            if not buf.text:
                event.app.exit(result=None)
            else:
                buf.reset()

        @kb.add("c-a")
        def _(event):
            """Ctrl+A: 移动到行首"""
            buf = event.current_buffer
            buf.cursor_position = 0

        @kb.add("c-e")
        def _(event):
            """Ctrl+E: 移动到行尾"""
            buf = event.current_buffer
            buf.cursor_position = len(buf.text)

        # 命令补全器
        commands = [
            "/help", "/clear", "/undo", "/compact", "/usage", "/tools",
            "/provider", "/model", "/info", "/memory", "/session",
            "/plugin", "/cost", "/plan", "/mcp", "/quit", "/exit",
        ]
        memory_cmds = ["/memory list", "/memory search ", "/memory forget "]
        session_cmds = ["/session save ", "/session load ", "/session delete ", "/session list"]
        mcp_cmds = ["/mcp list", "/mcp connect ", "/mcp disconnect ", "/mcp reconnect "]
        provider_cmds = ["/provider ", "/model "]
        plugin_cmds = ["/plugin reload", "/plugin list"]
        all_commands = commands + memory_cmds + session_cmds + mcp_cmds + provider_cmds + plugin_cmds

        cmd_completer = WordCompleter(all_commands, ignore_case=True, sentence=True)

        self._session = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            key_bindings=kb,
            multiline=False,
            completer=cmd_completer,
        )

        self._busy = False
        self._current_task: asyncio.Task | None = None

    async def run(self) -> None:
        # Claude Code 风格 Banner
        self._renderer.print_banner()
        self._renderer.print_welcome()

        provider_name = self._settings.llm.default_provider
        provider_config = self._settings.llm.providers[provider_name]
        self._renderer.print_status_info(
            provider_name, provider_config.model, tool_count=len(self._agent.tools)
        )

        # P9: 启动时自动连接 MCP 服务器
        mcp_count = await self._agent.init_mcp()
        if mcp_count > 0:
            self._renderer.print_success(f"MCP: 已加载 {mcp_count} 个外部工具")
            self._renderer.print_info(f"当前总工具数: {len(self._agent.tools)}")

        self._renderer.print_newline()

        while True:
            try:
                # Claude Code 风格提示符
                if self._busy:
                    prompt = [(("class:prompt", " ◐ "))]
                else:
                    prompt = [(("class:prompt", " > "))]
                user_input = await self._session.prompt_async(prompt)
                if user_input is None:
                    break
                user_input = user_input.strip()
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    should_exit = await self._handle_command(user_input)
                    if should_exit:
                        break
                    continue
                await self._handle_chat(user_input)
            except KeyboardInterrupt:
                if self._current_task and not self._current_task.done():
                    self._current_task.cancel()
                    self._renderer.print_warning("生成已取消。")
                self._busy = False
                continue
            except EOFError:
                break
            except Exception as e:
                logger.exception(f"未预期的错误: {e}")
                self._renderer.print_error(f"未预期的错误: {e}")
                self._busy = False

        self._renderer.print_goodbye()
        # P9: 断开 MCP 连接
        await self._agent.shutdown_mcp()

    async def _handle_chat(self, user_input: str) -> None:
        if self._busy:
            self._renderer.print_warning("正在处理上一个请求，请稍候...")
            return
        self._busy = True
        self._renderer.print_user_input(user_input)
        round_prompt = 0
        round_completion = 0
        assistant_started = False
        try:
            async for event in self._agent.chat_stream(user_input):
                if event.type == StreamEventType.CONTENT_DELTA:
                    # 首次内容时打印头部
                    if not assistant_started:
                        self._renderer.print_assistant_header()
                        assistant_started = True
                    self._renderer.print_streaming_chunk(event.data)
                elif event.type == StreamEventType.USAGE:
                    round_prompt += event.data.prompt_tokens
                    round_completion += event.data.completion_tokens
                elif event.type == StreamEventType.TOOL_CALL_START:
                    self._renderer.print_tool_call_start(event.data.get("name", ""))
                elif event.type == StreamEventType.TOOL_CALL_END:
                    pass
                elif event.type == StreamEventType.TOOL_EXECUTE_START:
                    self._renderer.print_tool_execute_start(
                        event.data["name"], event.data["id"],
                    )
                elif event.type == StreamEventType.TOOL_EXECUTE_END:
                    self._renderer.print_tool_execute_end(
                        event.data["name"],
                        success=event.data["success"],
                        error=event.data.get("error"),
                    )
                elif event.type == StreamEventType.LOOP_START:
                    self._renderer.print_loop_round(event.data["round"])
                elif event.type == StreamEventType.DONE:
                    if not assistant_started:
                        self._renderer.print_assistant_header()
                    self._renderer.print_streaming_done()
                    self._renderer.print_usage(round_prompt, round_completion)
                    self._cost_tracker.record_round(round_prompt, round_completion)
        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg or "connection" in error_msg:
                self._renderer.print_error(f"无法连接到 LLM 服务，请检查网络。\n  {error_msg}")
            elif "401" in error_msg or "auth" in error_msg.lower():
                self._renderer.print_error(f"API Key 认证失败，请检查配置。\n  {error_msg}")
            else:
                self._renderer.print_error(error_msg)
        finally:
            self._busy = False

    async def _handle_command(self, command: str) -> bool:
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit", "/q"):
            return True
        elif cmd == "/help":
            self._renderer.print_help()
        elif cmd == "/clear":
            self._agent.clear_history()
            self._renderer.print_success("对话历史已清空。")
        elif cmd == "/compact":
            if self._agent.context_manager:
                original = len(self._agent.loop.messages)
                self._agent.loop._messages = self._agent.context_manager.prepare_messages(
                    self._agent.loop.messages, force_compress=True
                )
                new = len(self._agent.loop.messages)
                self._renderer.print_success(f"已压缩: {original} -> {new} 条消息")
            else:
                self._renderer.print_warning("上下文管理器不可用。")
        elif cmd == "/undo":
            msgs = self._agent.loop.messages
            if len(msgs) >= 2:
                last_user_idx = None
                for i in range(len(msgs) - 1, -1, -1):
                    if msgs[i].role.value == "user":
                        last_user_idx = i
                        break
                if last_user_idx and last_user_idx > 0:
                    removed = msgs[last_user_idx:]
                    self._agent.loop._messages = msgs[:last_user_idx]
                    self._renderer.print_success(
                        f"已撤销: 从位置 {last_user_idx} 移除了 {len(removed)} 条消息。"
                    )
                else:
                    self._renderer.print_warning("没有可撤销的操作。")
            else:
                self._renderer.print_warning("没有可撤销的操作。")
        elif cmd == "/usage":
            usage = self._agent.loop.usage
            self._renderer.console.print()
            self._renderer.print_usage(usage.prompt_tokens, usage.completion_tokens)
            self._renderer.print_info(f"轮次: {self._agent.loop.round}")
            self._renderer.print_info(f"消息数: {len(self._agent.loop.messages)}")
            self._renderer.print_info(f"工具调用: {self._agent.loop.tool_call_count}")
            stats = self._agent.tools.get_stats()
            self._renderer.print_info(f"工具执行: {stats['total_executions']}")
            self._renderer.console.print()
        elif cmd == "/tools":
            tools_info = []
            for name, tool in sorted(self._agent.tools.all_tools.items()):
                tools_info.append((
                    name, tool.category, tool.danger_level.value,
                    tool.description[:60] + ("..." if len(tool.description) > 60 else ""),
                ))
            self._renderer.print_tool_list(tools_info)
        elif cmd == "/provider":
            if not args:
                providers = self._agent.llm.available_providers
                current = self._settings.llm.default_provider
                self._renderer.console.print()
                for p in providers:
                    marker = " <- 当前" if p == current else ""
                    config = self._settings.llm.providers[p]
                    self._renderer.console.print(
                        f"  [info]{p}[/] ({config.model}){marker}"
                    )
                self._renderer.console.print()
            else:
                target = args.strip()
                if target in self._agent.llm.available_providers:
                    self._settings.llm.default_provider = target
                    config = self._settings.llm.providers[target]
                    self._renderer.print_success(
                        f"已切换到 Provider '{target}' (模型: {config.model})"
                    )
                else:
                    available = self._agent.llm.available_providers
                    self._renderer.print_error(
                        f"未知的 Provider '{target}'。可用: {available}"
                    )
        elif cmd == "/memory":
            if not args:
                stats = self._agent.memory.get_stats()
                self._renderer.console.print()
                self._renderer.console.print("[info]记忆统计:[/]")
                self._renderer.console.print(f"  总计: {stats['total']}")
                for mtype, count in stats.get("by_type", {}).items():
                    self._renderer.console.print(f"  {mtype}: {count}")
                self._renderer.console.print()
                self._renderer.print_info("用法: /memory list, /memory search <关键词>, /memory forget <id>")
            elif args.strip() == "list":
                memories = self._agent.memory.list_memories()
                if not memories:
                    self._renderer.print_info("没有存储的记忆。")
                else:
                    for mem in memories[:20]:
                        self._renderer.console.print(
                            f"  [{mem.type.value}]{mem.id}[/] {mem.content[:60]}"
                        )
            elif args.strip().startswith("search "):
                query = args.strip()[7:]
                results = self._agent.memory.recall(query)
                if not results:
                    self._renderer.print_info(f"没有匹配的记忆: {query}")
                else:
                    for mem in results:
                        self._renderer.console.print(
                            f"  [{mem.type.value}]{mem.id}[/] {mem.content[:80]}"
                        )
            elif args.strip().startswith("forget "):
                mem_id = args.strip()[7:]
                if self._agent.memory.forget(mem_id):
                    self._renderer.print_success(f"已删除记忆 {mem_id}")
                else:
                    self._renderer.print_error(f"未找到记忆: {mem_id}")
            else:
                self._renderer.print_warning("用法: /memory [list|search <关键词>|forget <id>]")

        elif cmd == "/session":
            if not args:
                sessions = self._agent.session_manager.list_sessions()
                if not sessions:
                    self._renderer.print_info("没有已保存的会话。")
                else:
                    self._renderer.console.print()
                    self._renderer.console.print("[info]已保存的会话:[/]")
                    for s in sessions:
                        self._renderer.console.print(
                            f"  {s['session_id']} | {s['saved_at'][:19]} | {s['message_count']} msgs"
                        )
                    self._renderer.console.print()
            elif args.strip().startswith("save "):
                name = args.strip()[5:]
                session_id = self._agent.session_manager.save(
                    self._agent.loop.messages,
                    name=name,
                    session_id=self._agent.session_id,
                )
                self._renderer.print_success(f"会话已保存: {session_id}")
            elif args.strip().startswith("load "):
                sid = args.strip()[5:]
                messages = self._agent.session_manager.load(sid)
                if messages is None:
                    self._renderer.print_error(f"未找到会话: {sid}")
                else:
                    # 恢复消息
                    self._agent.loop.clear_history()
                    from src.llm.models import Message, MessageRole, ToolCall
                    for m_data in messages:
                        role = MessageRole(m_data["role"])
                        tool_calls = None
                        if m_data.get("tool_calls"):
                            tool_calls = [
                                ToolCall(
                                    id=tc["id"],
                                    name=tc["name"],
                                    arguments=tc["arguments"],
                                )
                                for tc in m_data["tool_calls"]
                            ]
                        msg = Message(role=role, content=m_data["content"], tool_calls=tool_calls)
                        self._agent.loop.add_message(msg)
                    self._renderer.print_success(f"会话已加载: {sid} ({len(messages)} 条消息)")
            elif args.strip().startswith("delete "):
                sid = args.strip()[7:]
                if self._agent.session_manager.delete(sid):
                    self._renderer.print_success(f"会话已删除: {sid}")
                else:
                    self._renderer.print_error(f"未找到会话: {sid}")
            else:
                self._renderer.print_warning("用法: /session [save <名称>|load <id>|delete <id>|list]")

        elif cmd == "/plugin":
            if not args:
                plugins = self._agent.plugin_loader.loaded_plugins
                tools = self._agent.plugin_loader.loaded_tools
                self._renderer.console.print()
                if not plugins:
                    self._renderer.print_info("没有已加载的插件。")
                else:
                    self._renderer.console.print("[info]插件:[/]")
                    for name, info in plugins.items():
                        self._renderer.console.print(f"  {name} ({info.path.name})")
                    if tools:
                        self._renderer.console.print(f"\n  Tools: {[t.name for t in tools]}")
                self._renderer.console.print()
                self._renderer.print_info("用法: /plugin reload")
            elif args.strip() == "reload":
                count = self._agent.plugin_loader.reload()
                self._renderer.print_success(f"已重新加载 {count} 个插件")
            else:
                self._renderer.print_warning("用法: /plugin [reload|list]")

        # P9: MCP 服务器管理命令
        elif cmd == "/mcp":
            if not args:
                servers = self._agent.mcp_manager.list_servers()
                self._renderer.console.print()
                if not servers:
                    self._renderer.print_info("没有配置的 MCP 服务器。")
                    self._renderer.print_info(
                        "可在 ~/.Zclaw/mcp_servers.json 中配置服务器。"
                    )
                else:
                    self._renderer.console.print("[info]MCP 服务器:[/]")
                    for s in servers:
                        status_marker = "[green]●[/]" if s["status"] == "已连接" else "[dim]○[/]"
                        self._renderer.console.print(
                            f"  {status_marker} {s['name']} ({s['transport']}) "
                            f"- {s['status']}, {s['tools']} 个工具"
                        )
                        if s.get("command"):
                            self._renderer.console.print(f"    [dim]命令: {s['command']}[/]")
                self._renderer.console.print()
                self._renderer.print_info("用法: /mcp connect <名称>, /mcp disconnect <名称>, /mcp reconnect <名称>")
            elif args.strip() == "connect" or args.strip().startswith("connect "):
                parts = args.strip().split(maxsplit=1)
                if len(parts) < 2:
                    self._renderer.print_warning("用法: /mcp connect <服务器名称>")
                else:
                    name = parts[1]
                    try:
                        wrappers = await self._agent.mcp_manager.connect_server(name)
                        if wrappers:
                            self._agent.tools.register_many(wrappers)
                            self._renderer.print_success(
                                f"已连接 '{name}', 注册 {len(wrappers)} 个工具"
                            )
                        else:
                            self._renderer.print_info(f"'{name}' 没有提供工具")
                    except Exception as e:
                        self._renderer.print_error(f"连接 '{name}' 失败: {e}")
            elif args.strip() == "disconnect" or args.strip().startswith("disconnect "):
                parts = args.strip().split(maxsplit=1)
                if len(parts) < 2:
                    self._renderer.print_warning("用法: /mcp disconnect <服务器名称>")
                else:
                    name = parts[1]
                    count = await self._agent.mcp_manager.disconnect_server(name)
                    if count:
                        self._renderer.print_success(f"已断开 '{name}'")
                    else:
                        self._renderer.print_info(f"'{name}' 未连接")
            elif args.strip() == "reconnect" or args.strip().startswith("reconnect "):
                parts = args.strip().split(maxsplit=1)
                if len(parts) < 2:
                    self._renderer.print_warning("用法: /mcp reconnect <服务器名称>")
                else:
                    name = parts[1]
                    try:
                        wrappers = await self._agent.mcp_manager.reconnect(name)
                        self._renderer.print_success(
                            f"已重连 '{name}', {len(wrappers)} 个工具"
                        )
                    except Exception as e:
                        self._renderer.print_error(f"重连 '{name}' 失败: {e}")
            else:
                self._renderer.print_warning("用法: /mcp [connect|disconnect|reconnect <名称>]")

        elif cmd == "/cost":
            summary = self._cost_tracker.get_summary()
            self._renderer.console.print()
            self._renderer.console.print("[info]费用追踪:[/]")
            for line in summary.split("\n"):
                self._renderer.console.print(f"  {line}")
            self._renderer.console.print()

        elif cmd == "/plan":
            if not args:
                if self._agent.planner.has_plan:
                    self._renderer.console.print()
                    self._renderer.console.print(self._agent.planner.plan.format_status())
                else:
                    self._renderer.print_info("没有活跃的计划。")
            elif args.strip() == "clear":
                self._agent.planner.clear_plan()
                self._renderer.print_success("计划已清空。")
            else:
                self._renderer.print_warning("用法: /plan [clear]")

        elif cmd == "/model":
            if args:
                new_model = args.strip()
                provider_name = self._settings.llm.default_provider
                self._settings.llm.providers[provider_name].model = new_model
                provider = self._agent.llm.get_provider(provider_name)
                provider.model = new_model
                self._renderer.print_success(
                    f"已切换到模型 '{new_model}' (Provider: '{provider_name}')"
                )
            else:
                provider_name = self._settings.llm.default_provider
                current_model = self._settings.llm.providers[provider_name].model
                self._renderer.print_info(f"当前模型: {current_model}")
        elif cmd == "/info":
            self._renderer.console.print()
            self._renderer.console.print("[info]当前配置:[/]")
            self._renderer.print_info(f"Provider: {self._settings.llm.default_provider}")
            provider_name = self._settings.llm.default_provider
            config = self._settings.llm.providers[provider_name]
            self._renderer.print_info(f"模型: {config.model}")
            self._renderer.print_info(f"Base URL: {config.base_url}")
            self._renderer.print_info(f"最大上下文: {config.max_context_tokens} tokens")
            self._renderer.print_info(f"温度: {self._settings.llm.temperature}")
            self._renderer.print_info(f"最大 Tokens: {self._settings.llm.max_tokens}")
            self._renderer.print_info(f"Agent 状态: {self._agent.state.value}")
            self._renderer.print_info(f"轮次: {self._agent.loop.round}")
            self._renderer.print_info(f"消息数: {len(self._agent.loop.messages)}")
            self._renderer.print_info(f"工具调用: {self._agent.loop.tool_call_count}")
            self._renderer.print_info(f"已注册工具: {len(self._agent.tools)}")
            self._renderer.print_info(
                f"总 Token 数: {self._agent.loop.usage.total_tokens}"
            )
            if self._agent.context_manager:
                info = self._agent.context_manager.get_usage_info(self._agent.loop.messages)
                self._renderer.print_info(f"Context: {info['used_tokens']}/{info['max_tokens']} tokens ({info['usage_ratio']})")
            self._renderer.console.print()
        else:
            self._renderer.print_warning(f"未知命令: {cmd}。输入 /help 查看可用命令。")
        return False

    async def _on_permission_request(self, request: PermissionRequest) -> bool:
        self._renderer.print_permission_request(
            tool_name=request.tool_name,
            danger_level=request.danger_level,
            arguments=request.arguments,
        )
        try:
            answer = await self._session.prompt_async(
                [("class:prompt", "  是否允许? [y/N] ")],
            )
        except (KeyboardInterrupt, EOFError):
            return False
        answer = (answer or "").strip().lower()
        approved = answer in ("y", "yes")
        if approved:
            self._renderer.print_permission_allowed(request.tool_name, auto=False)
        else:
            self._renderer.print_permission_denied(request.tool_name, "用户拒绝")
        return approved


def main():
    """CLI 入口函数。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="Zclaw",
        description="Zclaw - Claude Code 风格的 AI Agent 工具",
    )
    parser.add_argument("-c", "--config", type=str, default=None, help="配置文件路径")
    parser.add_argument("-p", "--provider", type=str, default=None, help="LLM Provider")
    parser.add_argument("-m", "--model", type=str, default=None, help="使用的模型")
    parser.add_argument("-v", "--verbose", action="store_true", help="开启详细日志")
    parser.add_argument("--prompt", type=str, default=None, help="非交互模式: 单次提问")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    overrides = {}
    if args.provider:
        overrides.setdefault("llm", {})["default_provider"] = args.provider

    try:
        settings = load_settings(
            config_path=Path(args.config) if args.config else None,
            overrides=overrides if overrides else None,
            use_env=True,
        )
    except Exception as e:
        print(f"加载配置失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.model:
        default_provider = settings.llm.default_provider
        settings.llm.providers[default_provider].model = args.model

    try:
        agent = Agent(settings)
    except Exception as e:
        print(f"初始化 Agent 失败: {e}", file=sys.stderr)
        sys.exit(1)

    renderer = Renderer()

    if args.prompt:
        asyncio.run(_non_interactive(agent, args.prompt, renderer))
        return

    repl = REPL(agent, settings, renderer)
    try:
        asyncio.run(repl.run())
    except KeyboardInterrupt:
        print("\n再见！")


async def _non_interactive(agent, prompt: str, renderer: Renderer) -> None:
    round_prompt = 0
    round_completion = 0
    try:
        async for event in agent.chat_stream(prompt):
            if event.type == StreamEventType.CONTENT_DELTA:
                renderer.print_streaming_chunk(event.data)
            elif event.type == StreamEventType.USAGE:
                round_prompt += event.data.prompt_tokens
                round_completion += event.data.completion_tokens
            elif event.type == StreamEventType.TOOL_EXECUTE_START:
                renderer.print_tool_execute_start(event.data["name"], event.data["id"])
            elif event.type == StreamEventType.TOOL_EXECUTE_END:
                renderer.print_tool_execute_end(
                    event.data["name"],
                    success=event.data["success"],
                    error=event.data.get("error"),
                )
            elif event.type == StreamEventType.LOOP_START:
                renderer.print_loop_round(event.data["round"])
    except Exception as e:
        renderer.print_error(str(e))
        sys.exit(1)
    renderer.print_newline()
    renderer.print_usage(round_prompt, round_completion)


if __name__ == "__main__":
    main()
