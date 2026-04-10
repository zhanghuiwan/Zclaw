"""
插件加载器

从指定目录扫描并加载自定义工具插件。
"""
from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PluginInfo:
    """插件信息"""
    def __init__(self, name: str, path: Path, module_name: str):
        self.name = name
        self.path = path
        self.module_name = module_name

    def __repr__(self) -> str:
        return f"Plugin(name='{self.name}', path={self.path})"


class PluginLoader:
    """
    插件加载器。

    从指定目录扫描 .py 文件，加载其中 BaseTool 子类。
    """

    def __init__(self, plugins_dir: str = ".Zclaw/plugins"):
        # 相对路径解析为项目根目录
        path = Path(plugins_dir)
        if not path.is_absolute() and not str(path).startswith("~"):
            src_dir = Path(__file__).resolve().parent
            project_root = src_dir.parent.parent
            self._plugins_dir = project_root / path
        else:
            self._plugins_dir = path.expanduser().resolve()
        self._loaded: dict[str, PluginInfo] = {}
        self._tools: list[Any] = []  # 已加载的工具实例

    @property
    def plugins_dir(self) -> Path:
        return self._plugins_dir

    @property
    def loaded_plugins(self) -> dict[str, PluginInfo]:
        return dict(self._loaded)

    @property
    def loaded_tools(self) -> list:
        return list(self._tools)

    def scan(self) -> list[PluginInfo]:
        """扫描插件目录，返回所有可加载的插件信息（不加载）。"""
        plugins = []
        if not self._plugins_dir.exists():
            logger.debug(f"Plugins directory not found: {self._plugins_dir}")
            return plugins

        for py_file in sorted(self._plugins_dir.glob("*.py")):
            name = py_file.stem
            plugins.append(PluginInfo(
                name=name,
                path=py_file,
                module_name=f"plugins.{name}",
            ))
        logger.debug(f"Scanned {len(plugins)} plugin(s) from {self._plugins_dir}")
        return plugins

    def load_all(self) -> list:
        """加载所有插件中的工具。"""
        self._tools.clear()
        self._loaded.clear()
        for info in self.scan():
            tools = self.load_plugin(info)
            if tools:
                self._loaded[info.name] = info
                self._tools.extend(tools)
        if self._tools:
            logger.info(f"Loaded {len(self._tools)} tool(s) from {len(self._loaded)} plugin(s)")
        return self._tools

    def load_plugin(self, info: PluginInfo) -> list:
        """加载单个插件，返回其中的工具实例列表。"""
        try:
            spec = importlib.util.spec_from_file_location(
                info.module_name,
                str(info.path),
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            tools = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if self._is_tool_class(attr):
                    instance = attr()
                    tools.append(instance)
                    logger.debug(f"Loaded tool: {instance.name} from plugin {info.name}")
            return tools
        except Exception as e:
            logger.error(f"Failed to load plugin {info.name}: {e}")
            return []

    def _is_tool_class(self, obj: Any) -> bool:
        """检查对象是否是 BaseTool 的子类。"""
        try:
            from src.tools.base import BaseTool
            return isinstance(obj, type) and issubclass(obj, BaseTool) and obj is not BaseTool
        except ImportError:
            return False

    def unload(self, name: str) -> bool:
        """卸载一个插件。"""
        if name not in self._loaded:
            return False
        info = self._loaded[name]
        # 移除该插件的工具
        self._tools = [t for t in self._tools if not (hasattr(t, '_plugin_name') and t._plugin_name == name)]
        del self._loaded[name]
        logger.info(f"Unloaded plugin: {name}")
        return True

    def reload(self) -> int:
        """重新加载所有插件。"""
        count = len(self._loaded)
        self.load_all()
        return count

    def __repr__(self) -> str:
        return f"PluginLoader(plugins={len(self._loaded)}, tools={len(self._tools)})"
