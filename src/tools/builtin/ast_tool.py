"""
语法感知编辑工具

使用 Python AST 进行代码分析和语义编辑。
支持函数/类提取、符号查找、代码结构分析等功能。
"""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

from src.tools.base import BaseTool, DangerLevel, ToolMetadata, ToolParameter, ToolResult


class CodeStructureTool(BaseTool):
    name = "code_structure"
    description = (
        "分析 Python 文件的代码结构，提取类、函数、变量等定义信息。\n"
        "返回一个结构化的概览，包括：类、方法、函数、导入、全局变量的名称、位置和签名。"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="Python 文件路径", required=True),
        ToolParameter(
            name="detail",
            type="string",
            description="详细程度: brief（概要）、normal（含签名）、full（含文档字符串）",
            required=False,
            default="normal",
            enum=["brief", "normal", "full"],
        ),
    ]
    metadata = ToolMetadata(category="analysis", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        detail = kwargs.get("detail", "normal")

        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")
            if not p.suffix == ".py":
                return ToolResult.fail("此工具仅支持 Python (.py) 文件")

            with open(p, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(p))
            analyzer = _ASTAnalyzer(source, detail)
            result = analyzer.analyze(tree)

            return ToolResult.ok(
                f"文件: {path}\n"
                f"{'=' * 60}\n"
                f"{result}"
            )

        except SyntaxError as e:
            return ToolResult.fail(f"语法错误（行 {e.lineno}）: {e.msg}")
        except Exception as e:
            return ToolResult.fail(str(e))


class SymbolFindTool(BaseTool):
    name = "symbol_find"
    description = (
        "在 Python 文件中查找特定符号（函数、类、变量）的定义。\n"
        "返回符号的完整定义代码，包括文档字符串。"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="Python 文件路径", required=True),
        ToolParameter(
            name="symbol",
            type="string",
            description="要查找的符号名称（函数名、类名等）",
            required=True,
        ),
        ToolParameter(
            name="include_body",
            type="boolean",
            description="是否包含完整函数体（默认 true）",
            required=False,
            default=True,
        ),
    ]
    metadata = ToolMetadata(category="analysis", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        symbol = kwargs["symbol"]
        include_body = kwargs.get("include_body", True)

        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")

            with open(p, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
                lines = source.splitlines()

            tree = ast.parse(source, filename=str(p))
            finder = _SymbolFinder(symbol)
            finder.visit(tree)

            if not finder.matches:
                return ToolResult.fail(f"在 {path} 中未找到符号: {symbol}")

            results = []
            for node in finder.matches:
                start_line = node.lineno
                end_line = node.end_lineno or start_line
                kind = type(node).__name__

                # 获取定义签名行
                if include_body:
                    code_lines = lines[start_line - 1:end_line]
                    code = "\n".join(code_lines)
                else:
                    # 只取签名行（到冒号为止）
                    code = lines[start_line - 1]
                    # 对于多行签名（如参数换行）
                    for i in range(start_line, min(end_line, start_line + 20)):
                        if ":" in lines[i]:
                            code = "\n".join(lines[start_line - 1:i + 1])
                            break

                # 获取文档字符串
                docstring = ast.get_docstring(node) if hasattr(node, "body") else None

                info = f"Found: {symbol} (line {start_line}-{end_line}, {kind})\n"
                if docstring:
                    info += f'Doc: """{docstring}"""\n\n'
                info += code

                results.append(info)

            return ToolResult.ok("\n\n---\n\n".join(results))

        except SyntaxError as e:
            return ToolResult.fail(f"语法错误（行 {e.lineno}）: {e.msg}")
        except Exception as e:
            return ToolResult.fail(str(e))


class SymbolEditTool(BaseTool):
    name = "symbol_edit"
    description = (
        "按符号名称替换 Python 文件中的函数或类定义。\n"
        "与 file_edit 不同，此工具基于 AST 定位，更精确和安全。"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="Python 文件路径", required=True),
        ToolParameter(
            name="symbol",
            type="string",
            description="要替换的符号名称（函数名、类名等）",
            required=True,
        ),
        ToolParameter(
            name="new_code",
            type="string",
            description="替换后的完整代码",
            required=True,
        ),
        ToolParameter(
            name="occurrence",
            type="integer",
            description="如果存在同名符号，指定替换第几个（从 1 开始，默认 1）",
            required=False,
            default=1,
        ),
    ]
    metadata = ToolMetadata(category="analysis", danger_level=DangerLevel.CONFIRM, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        symbol = kwargs["symbol"]
        new_code = kwargs["new_code"]
        occurrence = kwargs.get("occurrence", 1)

        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")

            with open(p, "r", encoding="utf-8") as f:
                source = f.read()
                lines = source.splitlines()

            tree = ast.parse(source, filename=str(p))
            finder = _SymbolFinder(symbol)
            finder.visit(tree)

            if not finder.matches:
                return ToolResult.fail(f"在 {path} 中未找到符号: {symbol}")

            if occurrence < 1 or occurrence > len(finder.matches):
                return ToolResult.fail(
                    f"符号 {symbol} 只有 {len(finder.matches)} 个定义，"
                    f"无法选择第 {occurrence} 个"
                )

            node = finder.matches[occurrence - 1]
            start_line = node.lineno - 1  # 0-based
            end_line = node.end_lineno  # exclusive

            # 替换
            old_code = "\n".join(lines[start_line:end_line])
            new_lines = new_code.splitlines()

            new_source = lines[:start_line] + new_lines + lines[end_line:]

            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(new_source))

            return ToolResult.ok(
                f"✅ 符号替换成功\n"
                f"符号: {symbol}\n"
                f"位置: 第 {node.lineno}-{node.end_lineno} 行\n"
                f"旧代码: {len(old_code)} 字符\n"
                f"新代码: {len(new_code)} 字符\n"
                f"文件: {path}"
            )

        except SyntaxError as e:
            return ToolResult.fail(f"语法错误（行 {e.lineno}）: {e.msg}")
        except Exception as e:
            return ToolResult.fail(str(e))


class ImportAnalyzerTool(BaseTool):
    name = "import_analyze"
    description = (
        "分析 Python 文件的导入依赖关系。\n"
        "列出所有导入语句，检测未使用的导入，分析依赖关系。"
    )
    parameters = [
        ToolParameter(name="path", type="string", description="Python 文件路径", required=True),
        ToolParameter(
            name="check_unused",
            type="boolean",
            description="是否检测未使用的导入（默认 true）",
            required=False,
            default=True,
        ),
    ]
    metadata = ToolMetadata(category="analysis", danger_level=DangerLevel.SAFE, timeout_seconds=10)

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs["path"]
        check_unused = kwargs.get("check_unused", True)

        try:
            p = Path(path).expanduser()
            if not p.exists():
                return ToolResult.fail(f"文件未找到: {path}")

            with open(p, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(p))
            analyzer = _ImportAnalyzer(source)
            analyzer.visit(tree)

            result_lines = [f"文件: {path}\n{'=' * 60}"]

            # 标准库导入
            if analyzer.stdlib_imports:
                result_lines.append("\n📦 标准库:")
                for imp in sorted(analyzer.stdlib_imports):
                    result_lines.append(f"  import {imp}")

            # 第三方导入
            if analyzer.third_party_imports:
                result_lines.append("\n📋 第三方库:")
                for imp in sorted(analyzer.third_party_imports):
                    result_lines.append(f"  import {imp}")

            # 项目内导入
            if analyzer.local_imports:
                result_lines.append("\n📁 项目内:")
                for imp in sorted(analyzer.local_imports):
                    result_lines.append(f"  import {imp}")

            # 未使用的导入
            if check_unused:
                unused = analyzer.find_unused_imports(source)
                if unused:
                    result_lines.append(f"\n⚠️  可能未使用的导入 ({len(unused)}):")
                    for imp in sorted(unused):
                        result_lines.append(f"  {imp}")
                else:
                    result_lines.append("\n✅ 没有检测到未使用的导入")

            summary = (
                f"\n统计: {len(analyzer.stdlib_imports)} 标准库, "
                f"{len(analyzer.third_party_imports)} 第三方, "
                f"{len(analyzer.local_imports)} 项目内"
            )
            result_lines.append(summary)

            return ToolResult.ok("\n".join(result_lines))

        except SyntaxError as e:
            return ToolResult.fail(f"语法错误（行 {e.lineno}）: {e.msg}")
        except Exception as e:
            return ToolResult.fail(str(e))


# ============================================================
# AST 辅助类
# ============================================================

class _ASTAnalyzer:
    """AST 分析器，提取代码结构。"""

    def __init__(self, source: str, detail: str = "normal"):
        self.source = source
        self.detail = detail
        self.lines = source.splitlines()

    def analyze(self, tree: ast.Module) -> str:
        parts = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                aliases = ", ".join(f"{a.name} as {a.asname}" if a.asname else a.name for a in node.names)
                parts.append(f"  import {aliases}  (line {node.lineno})")

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                aliases = ", ".join(f"{a.name} as {a.asname}" if a.asname else a.name for a in node.names)
                level = "." * node.level
                parts.append(f"  from {level}{module} import {aliases}  (line {node.lineno})")

            elif isinstance(node, ast.ClassDef):
                parts.append(self._format_class(node))

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parts.append(self._format_function(node))

            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        parts.append(f"  {target.id} = ...  (line {node.lineno})")

        if not parts:
            return "（空文件）"

        return "\n".join(parts)

    def _format_class(self, node: ast.ClassDef) -> str:
        # 获取基类
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))

        base_str = f"({', '.join(bases)})" if bases else ""
        line = f"  class {node.name}{base_str}  (line {node.lineno})"

        # 文档字符串
        docstring = ast.get_docstring(node)
        if self.detail == "full" and docstring:
            line += f'\n    """{docstring}"""'

        # 方法
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async " if isinstance(item, ast.AsyncFunctionDef) else ""
                sig = self._get_function_signature(item)
                methods.append(f"    {prefix}def {sig}  (line {item.lineno})")

        if self.detail != "brief" and methods:
            line += "\n" + "\n".join(methods)

        return line

    def _format_function(self, node) -> str:
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        sig = self._get_function_signature(node)
        decorators = ""

        for dec in node.decorator_list:
            try:
                dec_name = ast.unparse(dec)
                decorators += f"  @{dec_name}  (line {dec.lineno})\n"
            except Exception:
                decorators += f"  @decorator  (line {dec.lineno})\n"

        line = f"{decorators}  {prefix}def {sig}  (line {node.lineno})"

        # 文档字符串
        docstring = ast.get_docstring(node)
        if self.detail == "full" and docstring:
            line += f'\n    """{docstring}"""'

        return line

    def _get_function_signature(self, node) -> str:
        """获取函数签名字符串。"""
        args = node.args

        # 参数列表
        param_parts = []

        # 位置参数
        for arg in args.args:
            annotation = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            default = ""
            if arg in (args.defaults or []):
                idx = args.args.index(arg) - (len(args.args) - len(args.defaults))
                if 0 <= idx < len(args.defaults):
                    try:
                        default = f" = {ast.unparse(args.defaults[idx])}"
                    except Exception:
                        default = " = ..."
            param_parts.append(f"{arg.arg}{annotation}{default}")

        # *args
        if args.vararg:
            annotation = f": {ast.unparse(args.vararg.annotation)}" if args.vararg.annotation else ""
            param_parts.append(f"*{args.vararg.arg}{annotation}")

        # **kwargs
        if args.kwarg:
            annotation = f": {ast.unparse(args.kwarg.annotation)}" if args.kwarg.annotation else ""
            param_parts.append(f"**{args.kwarg.arg}{annotation}")

        # 返回类型
        return_type = ""
        if node.returns:
            try:
                return_type = f" -> {ast.unparse(node.returns)}"
            except Exception:
                return_type = " -> ..."

        return f"{node.name}({', '.join(param_parts)}){return_type}"


class _SymbolFinder(ast.NodeVisitor):
    """在 AST 中查找指定名称的符号定义。"""

    def __init__(self, symbol_name: str):
        self.symbol_name = symbol_name
        self.matches: list[ast.AST] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        if node.name == self.symbol_name:
            self.matches.append(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name == self.symbol_name:
            self.matches.append(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if node.name == self.symbol_name:
            self.matches.append(node)


# Python 标准库模块名（常见子集）
_STDLIB_MODULES = {
    "abc", "aifc", "argparse", "array", "ast", "asyncio", "atexit", "base64",
    "binascii", "bisect", "builtins", "bz2", "calendar", "cgi", "cmath",
    "cmd", "code", "codecs", "collections", "colorsys", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "copyreg", "csv", "ctypes", "curses",
    "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis", "distutils",
    "doctest", "email", "enum", "errno", "faulthandler", "fcntl", "filecmp",
    "fileinput", "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
    "getpass", "gettext", "glob", "grp", "gzip", "hashlib", "heapq", "hmac",
    "html", "http", "imaplib", "importlib", "inspect", "io", "ipaddress",
    "itertools", "json", "keyword", "lib2to3", "linecache", "locale", "logging",
    "lzma", "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "numbers", "operator", "optparse",
    "os", "pathlib", "pdb", "pickle", "pipes", "pkgutil", "platform", "plistlib",
    "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty", "pwd",
    "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline",
    "reprlib", "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
    "selectors", "shelve", "shlex", "shutil", "signal", "site", "smtplib",
    "socket", "socketserver", "sqlite3", "ssl", "stat", "statistics", "string",
    "stringprep", "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig",
    "syslog", "tabnanny", "tarfile", "tempfile", "termios", "test", "textwrap",
    "threading", "time", "timeit", "tkinter", "token", "tokenize", "trace",
    "traceback", "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing",
    "unicodedata", "unittest", "urllib", "uu", "uuid", "venv", "warnings",
    "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib",
    "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
}


class _ImportAnalyzer(ast.NodeVisitor):
    """分析文件中的导入语句。"""

    def __init__(self, source: str):
        self.source = source
        self.stdlib_imports: set[str] = set()
        self.third_party_imports: set[str] = set()
        self.local_imports: set[str] = set()
        self._all_imports: list[tuple[str, str]] = []  # (name, module)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            module = alias.name
            self._all_imports.append((name, module))
            self._classify_import(module)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        if node.level > 0:
            # 相对导入 → 项目内
            for alias in node.names:
                name = alias.asname or alias.name
                self.local_imports.add(name)
                self._all_imports.append((name, f"{'.' * node.level}{module}"))
        else:
            for alias in node.names:
                name = alias.asname or alias.name
                self._all_imports.append((name, module))
                self._classify_import(module)

    def _classify_import(self, module: str):
        """分类导入：标准库、第三方、项目内。"""
        top_level = module.split(".")[0]
        if top_level in _STDLIB_MODULES:
            self.stdlib_imports.add(module)
        elif top_level.startswith("."):
            self.local_imports.add(module)
        else:
            # 非标准库的都归为第三方（可能包含项目内模块）
            self.third_party_imports.add(module)

    def find_unused_imports(self, source: str) -> list[str]:
        """检测可能未使用的导入（简单启发式）。"""
        unused = []
        for name, module in self._all_imports:
            # 构建一个正则，排除 import 行本身
            # 只搜索 name 在非 import 上下文中的出现
            pattern = re.compile(rf'\b{re.escape(name)}\b')

            # 找到所有出现位置
            matches = pattern.finditer(source)

            # 排除 import 行中的出现
            actual_uses = 0
            for m in matches:
                line_start = source.rfind("\n", 0, m.start()) + 1
                line_end = source.find("\n", m.start())
                if line_end == -1:
                    line_end = len(source)
                line = source[line_start:line_end]

                # 如果不在 import 行中，算作使用
                stripped = line.strip()
                if not stripped.startswith("import ") and not stripped.startswith("from "):
                    actual_uses += 1

            if actual_uses == 0:
                unused.append(name)

        return unused


AST_TOOLS = [
    CodeStructureTool(),
    SymbolFindTool(),
    SymbolEditTool(),
    ImportAnalyzerTool(),
]
