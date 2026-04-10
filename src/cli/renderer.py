"""
CLI 输出渲染器

使用 Rich 库实现美观的终端输出。
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from src.llm.models import StreamEventType

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
})


class Renderer:
    """终端输出渲染器。"""

    def __init__(self, console: Console | None = None):
        self._console = console or Console(theme=AGENT_THEME)
        self._width = self._console.width or 80

    @property
    def console(self) -> Console:
        return self._console

    def print_banner(self) -> None:
        banner = Text()
        banner.append("╔══════════════════════════════════════╗\n", style="info")
        banner.append("║", style="info")
        banner.append("         Zclaw v0.1.0               ", style="bold")
        banner.append("║\n", style="info")
        banner.append("║  Claude Code 风格 AI 编程助手       ║\n", style="dim")
        banner.append("╚══════════════════════════════════════╝\n", style="info")
        self._console.print(banner)

    def print_status_info(self, provider: str, model: str, tool_count: int = 0) -> None:
        info = Text()
        info.append("  Provider: ", style="dim")
        info.append(provider, style="info bold")
        info.append("  |  模型: ", style="dim")
        info.append(model, style="info bold")
        if tool_count > 0:
            info.append(f"  |  工具: ", style="dim")
            info.append(f"{tool_count}", style="info bold")
        info.append("\n", style="dim")
        self._console.print(info)

    def print_user_input(self, text: str) -> None:
        display = text[:200] + ("..." if len(text) > 200 else "")
        self._console.print()
        self._console.print(
            Panel(display, title="[user]用户[/]", border_style="cyan", padding=(0, 1))
        )

    def print_assistant_response(self, text: str) -> None:
        self._console.print()
        self._console.print(Markdown(text))
        self._console.print()

    def print_streaming_chunk(self, chunk: str) -> None:
        self._console.print(chunk, end="", highlight=False)

    def print_error(self, message: str) -> None:
        self._console.print(f"\n[error]X 错误:[/] {message}\n")

    def print_warning(self, message: str) -> None:
        self._console.print(f"\n[warning]警告:[/] {message}\n")

    def print_info(self, message: str) -> None:
        self._console.print(f"[dim]i {message}[/]")

    def print_success(self, message: str) -> None:
        self._console.print(f"[success]OK {message}[/]")

    def print_separator(self) -> None:
        self._console.print("-" * self._width, style="border")

    def print_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self._console.print(
            f"  [dim]Token 用量: {prompt_tokens} 输入 + {completion_tokens} 输出 "
            f"= {prompt_tokens + completion_tokens} 总计[/]"
        )

    def print_tool_call_start(self, tool_name: str) -> None:
        self._console.print()

    def print_tool_execute_start(self, tool_name: str, call_id: str) -> None:
        self._console.print(
            f"  [tool]* {tool_name}[/][dim] 执行中...[/]",
        )

    def print_tool_execute_end(
        self, tool_name: str, success: bool, error: str | None = None
    ) -> None:
        if success:
            self._console.print(
                f"  [success]OK {tool_name}[/][dim] 完成[/]"
            )
        else:
            self._console.print(
                f"  [error]X {tool_name}[/][dim] 失败: {error or '未知错误'}[/]"
            )

    def print_tool_result_detail(self, content: str, success: bool) -> None:
        display = content
        if len(display) > 500:
            display = display[:500] + f"\n... (还有 {len(content) - 500} 字符)"
        style = "" if success else "red"
        self._console.print(
            Panel(
                display,
                title="[tool]工具输出[/]",
                border_style="green" if success else "red",
                padding=(0, 1),
                subtitle=f"[dim]{len(content)} 字符[/]",
            )
        )

    def print_loop_round(self, round_num: int) -> None:
        self._console.print(
            f"\n  [dim]--- 循环第 {round_num} 轮 ---[/]",
        )

    def print_newline(self) -> None:
        self._console.print()

    def status_spinner(self, message: str = "思考中..."):
        return self._console.status(f"  {message}", spinner="dots")

    def create_live_display(self, renderable: Any) -> Live:
        return Live(renderable, console=self._console, refresh_per_second=10)

    def print_help(self) -> None:
        help_table = Table(show_header=False, box=None, padding=(0, 2))
        help_table.add_column("command", style="cyan bold", width=20)
        help_table.add_column("description")
        help_table.add_row("/help", "显示此帮助信息")
        help_table.add_row("/clear", "清空对话历史")
        help_table.add_row("/compact", "压缩对话历史（节省上下文）")
        help_table.add_row("/undo", "撤销上一轮对话")
        help_table.add_row("/usage", "显示 token 使用统计")
        help_table.add_row("/tools", "显示已注册的工具列表")
        help_table.add_row("/provider [name]", "切换 LLM Provider")
        help_table.add_row("/model [name]", "切换模型")
        help_table.add_row("/info", "显示当前配置信息")
        help_table.add_row("/quit, /exit", "退出程序")
        self._console.print()
        self._console.print(Panel(help_table, title="  可用命令  ", border_style="info"))
        self._console.print()

    def print_goodbye(self) -> None:
        self._console.print()
        self._console.print("[dim]再见！使用 [/]/exit[/][dim] 或 [/]/quit[/][dim] 退出。 [/]")

    def print_permission_request(
        self, tool_name: str, danger_level: str, arguments: dict[str, Any],
    ) -> None:
        if danger_level == "dangerous":
            border_style = "red bold"
            title = "[red bold]! 需要授权 (危险操作)[/]"
        else:
            border_style = "yellow"
            title = "[yellow]需要授权 (需确认)[/]"
        args_lines = []
        for key, value in arguments.items():
            if isinstance(value, str) and len(value) > 100:
                display_val = value[:100] + f"... ({len(value)} 字符)"
            else:
                display_val = str(value)
            args_lines.append(f"  [cyan]{key}[/]: {display_val}")
        args_text = "\n".join(args_lines)
        self._console.print()
        self._console.print(
            Panel(
                f"[bold]{tool_name}[/]\n\n{args_text}",
                title=title,
                border_style=border_style,
                padding=(0, 1),
            )
        )

    def print_permission_denied(self, tool_name: str, reason: str) -> None:
        self._console.print(
            f"  [error]X {tool_name}[/][dim] 已拒绝: {reason}[/]"
        )

    def print_permission_allowed(self, tool_name: str, auto: bool = False) -> None:
        if auto:
            self._console.print(
                f"  [dim]-> {tool_name}[/][dim] 自动批准[/]"
            )
        else:
            self._console.print(
                f"  [success]-> {tool_name}[/][dim] 用户已批准[/]"
            )

    def print_audit_summary(self, stats: dict[str, Any]) -> None:
        self._console.print()
        self._console.print("[info]审计日志统计:[/]")
        self._console.print(f"  总检查数: {stats.get('total_entries', 0)}")
        self._console.print(f"  [success]已允许: {stats.get('allowed', 0)}[/]")
        self._console.print(f"  [error]已拒绝: {stats.get('denied', 0)}[/]")
        self._console.print(f"  [warning]失败: {stats.get('failed', 0)}[/]")
        self._console.print()

    def print_tool_list(self, tools_info: list[tuple[str, str, str, str]]) -> None:
        table = Table(title="  已注册工具  ", show_header=True, header_style="info")
        table.add_column("名称", style="cyan bold", width=18)
        table.add_column("类别", style="dim", width=10)
        table.add_column("危险等级", width=10)
        table.add_column("描述")
        for name, category, danger, description in tools_info:
            danger_style = "green" if danger == "safe" else ("yellow" if danger == "confirm" else "red")
            table.add_row(name, category, f"[{danger_style}]{danger}[/]", description)
        self._console.print()
        self._console.print(table)
        self._console.print()
