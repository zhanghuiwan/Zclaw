"""
CLI 输出渲染器

参考 Claude Code 风格美化终端输出。
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.status import Status
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.rule import Rule

from src.llm.models import StreamEventType

# Claude Code 风格主题配色
AGENT_THEME = Theme({
    "user": "cyan bold",
    "assistant": "green",
    "system": "yellow dim",
    "error": "red bold",
    "tool": "magenta",
    "info": "blue",
    "dim": "dim",
    "success": "green bold",
    "warning": "yellow bold",
    "border": "bright_black",
    # Claude Code 风格扩展
    "assistant_header": "bold cyan",
    "tool_header": "bold magenta",
    "thinking": "dim yellow",
    "progress": "cyan",
})


class Renderer:
    """终端输出渲染器 - Claude Code 风格。"""

    def __init__(self, console: Console | None = None):
        self._console = console or Console(theme=AGENT_THEME, width=120)
        self._width = self._console.width or 120
        self._progress: Progress | None = None

    @property
    def console(self) -> Console:
        return self._console

    # ==================== Banner & Header ====================

    def print_banner(self) -> None:
        """Claude Code 风格 Banner"""
        banner = Text()
        # 顶部边框
        banner.append("┌" + "─" * 58 + "┐\n", style="info")
        # 标题
        banner.append("│", style="info")
        banner.append("  🏹 Zclaw v0.6.1", style="bold cyan")
        banner.append(" " * 33 + "│\n", style="info")
        # 副标题
        banner.append("│", style="info")
        banner.append("  AI Agent 编程助手", style="dim")
        banner.append(" " * 36 + "│\n", style="info")
        # 底部边框
        banner.append("└" + "─" * 58 + "┘\n", style="info")

        self._console.print(banner)
        self._console.print()

    def print_welcome(self) -> None:
        """欢迎信息"""
        welcome = Text()
        welcome.append("  输入 ", style="dim")
        welcome.append("/help", style="cyan bold")
        welcome.append(" 查看可用命令，", style="dim")
        welcome.append("/quit", style="cyan bold")
        welcome.append(" 退出\n", style="dim")
        welcome.append("  开始你的第一个问题吧！", style="dim")
        self._console.print(welcome)
        self._console.print()

    def print_status_info(self, provider: str, model: str, tool_count: int = 0) -> None:
        """状态信息 - Claude Code 风格"""
        info = Text()
        info.append("  Provider: ", style="dim")
        info.append(provider, style="cyan bold")
        info.append("  |  模型: ", style="dim")
        info.append(model, style="green bold")
        if tool_count > 0:
            info.append("  |  工具: ", style="dim")
            info.append(f"{tool_count}", style="magenta bold")
        self._console.print(info)

    # ==================== User Input ====================

    def print_user_input(self, text: str) -> None:
        """显示用户输入"""
        display = text[:200] + ("..." if len(text) > 200 else "")
        self._console.print()
        # 用户输入头部
        header = Text()
        header.append("  📝 ", style="cyan")
        header.append("User", style="bold cyan")
        header.append("  ", style="dim")
        header.append("输入", style="dim")
        self._console.print(header)
        # 输入内容面板
        self._console.print(
            Panel(
                display,
                border_style="cyan",
                padding=(0, 1),
                width=self._width - 4,
            )
        )
        self._console.print()

    # ==================== Assistant Response ====================

    def print_assistant_header(self) -> None:
        """助手响应头部"""
        header = Text()
        header.append("  🤖 ", style="green")
        header.append("Assistant", style="bold green")
        header.append("  ", style="dim")
        header.append("响应", style="dim")
        self._console.print(header)

    def print_assistant_response(self, text: str) -> None:
        """显示助手响应 - Markdown 渲染"""
        self._console.print()
        md = Markdown(text, code_theme="monokai", width=self._width - 4)
        self._console.print(md)
        self._console.print()

    def print_streaming_chunk(self, chunk: str) -> None:
        """流式输出块"""
        self._console.print(chunk, end="", highlight=False)

    def print_streaming_done(self) -> None:
        """流式输出完成"""
        self._console.print()
        self._console.print()

    # ==================== Tool Execution ====================

    def print_tool_header(self) -> None:
        """工具执行头部"""
        self._console.print()

    def print_tool_call_start(self, tool_name: str) -> None:
        """工具调用开始"""
        self._console.print()

    def print_tool_execute_start(self, tool_name: str, call_id: str) -> None:
        """工具执行开始 - Claude Code 风格"""
        with self._console.status(
            f"  [magenta]⚻ {tool_name}[/] 执行中...",
            spinner="dots",
            spinner_style="cyan",
        ) as status:
            # 保持状态用于后续更新
            self._current_tool_status = status

    def print_tool_execute_end(
        self, tool_name: str, success: bool, error: str | None = None
    ) -> None:
        """工具执行结束 - Claude Code 风格"""
        if success:
            self._console.print(
                f"  [success]✓[/] [magenta]{tool_name}[/] [success]完成[/]"
            )
        else:
            self._console.print(
                f"  [error]✗[/] [magenta]{tool_name}[/] [error]失败:[/] {error or '未知错误'}"
            )

    def print_tool_result_detail(self, content: str, success: bool) -> None:
        """工具结果详情"""
        display = content
        if len(display) > 500:
            display = display[:500] + f"\n... (还有 {len(content) - 500} 字符)"
        border_color = "green" if success else "red"
        self._console.print(
            Panel(
                display,
                title="[tool]工具输出[/]",
                border_style=border_color,
                padding=(0, 1),
                subtitle=f"[dim]{len(content)} 字符[/]",
                width=self._width - 4,
            )
        )

    def print_loop_round(self, round_num: int) -> None:
        """循环轮次"""
        self._console.print()
        rule = Rule(title=f"[cyan] 第 {round_num} 轮 ", style="cyan dim")
        self._console.print(rule)

    # ==================== Messages & Output ====================

    def print_newline(self) -> None:
        """空行"""
        self._console.print()

    def print_separator(self) -> None:
        """分隔线"""
        self._console.print()
        self._console.print(Rule(style="dim"))
        self._console.print()

    def status_spinner(self, message: str = "思考中..."):
        """状态旋转器"""
        return self._console.status(
            f"  [cyan]{message}[/]",
            spinner="dots",
            spinner_style="yellow",
        )

    def create_live_display(self, renderable: Any) -> Live:
        """创建实时显示"""
        return Live(
            renderable,
            console=self._console,
            refresh_per_second=10,
            transient=True,
        )

    def create_progress(self) -> Progress:
        """创建进度条"""
        self._progress = Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self._console,
        )
        return self._progress

    # ==================== Messages ====================

    def print_error(self, message: str) -> None:
        """错误消息"""
        self._console.print()
        self._console.print(
            Panel(
                f"[error]{message}[/]",
                title="[error]✗ 错误[/]",
                border_style="red",
                padding=(0, 1),
                width=self._width - 4,
            )
        )
        self._console.print()

    def print_warning(self, message: str) -> None:
        """警告消息"""
        self._console.print()
        self._console.print(
            Panel(
                f"[warning]{message}[/]",
                title="[warning]⚠ 警告[/]",
                border_style="yellow",
                padding=(0, 1),
                width=self._width - 4,
            )
        )
        self._console.print()

    def print_info(self, message: str) -> None:
        """信息消息"""
        info = Text()
        info.append("  ℹ ", style="blue")
        info.append(message, style="dim")
        self._console.print(info)

    def print_success(self, message: str) -> None:
        """成功消息"""
        success = Text()
        success.append("  ✓ ", style="green bold")
        success.append(message, style="green")
        self._console.print(success)

    def print_thinking(self, message: str = "思考中...") -> Status:
        """显示思考状态"""
        return self._console.status(
            f"  [thinking]◐ {message}[/]",
            spinner="dots",
            spinner_style="yellow",
        )

    # ==================== Usage & Stats ====================

    def print_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Token 使用量"""
        total = prompt_tokens + completion_tokens
        usage = Text()
        usage.append("  📊 ", style="dim")
        usage.append("Token 用量: ", style="dim")
        usage.append(f"{prompt_tokens}", style="cyan")
        usage.append(" 输入 + ", style="dim")
        usage.append(f"{completion_tokens}", style="green")
        usage.append(" 输出 = ", style="dim")
        usage.append(f"{total}", style="bold")
        usage.append(" 总计", style="dim")
        self._console.print(usage)

    def print_audit_summary(self, stats: dict[str, Any]) -> None:
        """审计日志统计"""
        self._console.print()
        table = Table(
            title="[info]审计日志统计[/]",
            show_header=False,
            box=None,
            padding=(0, 2),
            width=40,
        )
        table.add_column("指标", style="dim")
        table.add_column("数值", style="bold")
        table.add_row("总检查数", str(stats.get("total_entries", 0)))
        table.add_row("已允许", f"[green]{stats.get('allowed', 0)}[/]")
        table.add_row("已拒绝", f"[red]{stats.get('denied', 0)}[/]")
        table.add_row("失败", f"[warning]{stats.get('failed', 0)}[/]")
        self._console.print(table)
        self._console.print()

    # ==================== Help & Commands ====================

    def print_help(self) -> None:
        """帮助信息 - Claude Code 风格"""
        help_table = Table(
            title="[cyan]📋 可用命令[/]",
            show_header=True,
            header_style="bold cyan",
            box=None,
            padding=(0, 2),
            width=self._width - 4,
        )
        help_table.add_column("命令", style="cyan bold", width=18)
        help_table.add_column("描述", style="dim")

        commands = [
            ("/help", "显示此帮助信息"),
            ("/clear", "清空对话历史"),
            ("/compact", "压缩对话历史（节省上下文）"),
            ("/undo", "撤销上一轮对话"),
            ("/usage", "显示 token 使用统计"),
            ("/tools", "显示已注册的工具列表"),
            ("/provider [name]", "切换 LLM Provider"),
            ("/model [name]", "切换模型"),
            ("/info", "显示当前配置信息"),
            ("/session", "会话管理"),
            ("/plugin", "插件管理"),
            ("/mcp", "MCP 服务器管理"),
            ("/cost", "费用追踪"),
            ("/plan", "计划管理"),
            ("/quit, /exit", "退出程序"),
        ]

        for cmd, desc in commands:
            help_table.add_row(cmd, desc)

        self._console.print()
        self._console.print(help_table)
        self._console.print()
        self._console.print(
            Text("  💡 提示: 使用 ", style="dim")
            + Text("Tab", style="cyan bold")
            + Text(" 自动补全命令，", style="dim")
            + Text("↑/↓", style="cyan bold")
            + Text(" 调取历史记录", style="dim")
        )
        self._console.print()

    def print_tool_list(self, tools_info: list[tuple[str, str, str, str]]) -> None:
        """工具列表"""
        table = Table(
            title="[magenta]🔧 已注册工具[/]",
            show_header=True,
            header_style="bold magenta",
            box=True,
            padding=(0, 1),
            width=self._width,
        )
        table.add_column("名称", style="cyan bold", width=18)
        table.add_column("类别", style="dim", width=10)
        table.add_column("危险等级", width=12)
        table.add_column("描述")

        for name, category, danger, description in tools_info:
            if danger == "safe":
                danger_display = "[green]✓ safe[/]"
            elif danger == "confirm":
                danger_display = "[yellow]⚠ confirm[/]"
            else:
                danger_display = "[red]✗ dangerous[/]"
            table.add_row(name, category, danger_display, description[:50])

        self._console.print()
        self._console.print(table)
        self._console.print()

    def print_goodbye(self) -> None:
        """告别消息"""
        self._console.print()
        goodbye = Text()
        goodbye.append("  👋 ", style="cyan")
        goodbye.append("再见！", style="bold cyan")
        goodbye.append(" 感谢使用 Zclaw", style="dim")
        self._console.print(goodbye)
        self._console.print()

    # ==================== Permission ====================

    def print_permission_request(
        self, tool_name: str, danger_level: str, arguments: dict[str, Any],
    ) -> None:
        """权限请求提示"""
        if danger_level == "dangerous":
            border_style = "red bold"
            title = "[red bold]⚠ 需要授权 (危险操作)[/]"
            icon = "🔴"
        else:
            border_style = "yellow"
            title = "[yellow]⚡ 需要授权 (需确认)[/]"
            icon = "🟡"

        args_lines = []
        for key, value in arguments.items():
            if isinstance(value, str) and len(value) > 100:
                display_val = value[:100] + f"... ({len(value)} 字符)"
            else:
                display_val = str(value)
            args_lines.append(f"  [cyan]{key}[/]: {display_val}")

        args_text = "\n".join(args_lines) if args_lines else "  无参数"

        self._console.print()
        self._console.print(
            Panel(
                f"[bold]{icon} {tool_name}[/]\n\n{args_text}",
                title=title,
                border_style=border_style,
                padding=(0, 1),
                width=self._width - 4,
            )
        )
        self._console.print()

    def print_permission_denied(self, tool_name: str, reason: str) -> None:
        """权限拒绝"""
        denied = Text()
        denied.append("  ✗ ", style="red bold")
        denied.append(f"{tool_name}", style="magenta")
        denied.append(" 已拒绝: ", style="red")
        denied.append(reason, style="dim")
        self._console.print(denied)

    def print_permission_allowed(self, tool_name: str, auto: bool = False) -> None:
        """权限允许"""
        if auto:
            allowed = Text()
            allowed.append("  → ", style="green")
            allowed.append(f"{tool_name}", style="magenta")
            allowed.append(" 自动批准", style="dim")
            self._console.print(allowed)
        else:
            allowed = Text()
            allowed.append("  ✓ ", style="green bold")
            allowed.append(f"{tool_name}", style="magenta")
            allowed.append(" 用户已批准", style="green")
            self._console.print(allowed)

    # ==================== Code Block ====================

    def print_code_block(self, code: str, language: str = "bash") -> None:
        """代码块输出"""
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        self._console.print(
            Panel(
                syntax,
                border_style="cyan",
                padding=(0, 1),
                width=self._width - 4,
            )
        )

    def print_inline_code(self, code: str, style: str = "cyan") -> Text:
        """行内代码"""
        result = Text()
        result.append(f"`{code}`", style=style)
        return result
