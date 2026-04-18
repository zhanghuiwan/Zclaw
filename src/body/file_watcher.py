"""
File Watcher - 文件监听器

监控指定目录的文件变化，触发相应的事件处理。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Awaitable

try:
    import watchdog
    from watchdog.observers import Observer
    from watchdog.events import (
        FileSystemEvent,
        FileCreatedEvent,
        FileModifiedEvent,
        FileDeletedEvent,
        FileMovedEvent,
        FileSystemEventHandler,
    )
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

logger = logging.getLogger(__name__)


class FileWatchEventType(Enum):
    """文件变化事件类型"""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"
    ANY = "any"


@dataclass
class FileWatchEvent:
    """文件变化事件"""
    event_type: FileWatchEventType
    path: str
    src_path: str = ""  # 用于 MOVED 事件
    dest_path: str = ""  # 用于 MOVED 事件
    timestamp: datetime | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class FileWatcherEventHandler(FileSystemEventHandler):
    """文件监听事件处理器"""

    def __init__(self, callback: Callable[[FileWatchEvent], Awaitable[Any]]):
        super().__init__()
        self._callback = callback

    def _create_event(self, event_type: FileWatchEventType, path: str, **kwargs) -> FileWatchEvent:
        return FileWatchEvent(
            event_type=event_type,
            path=path,
            timestamp=datetime.now(),
            **kwargs,
        )

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            asyncio.create_task(self._callback(
                self._create_event(FileWatchEventType.CREATED, event.src_path)
            ))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            asyncio.create_task(self._callback(
                self._create_event(FileWatchEventType.MODIFIED, event.src_path)
            ))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            asyncio.create_task(self._callback(
                self._create_event(FileWatchEventType.DELETED, event.src_path)
            ))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            asyncio.create_task(self._callback(
                self._create_event(
                    FileWatchEventType.MOVED,
                    event.src_path,
                    src_path=event.src_path,
                    dest_path=event.dest_path,
                )
            ))

    def on_any_event(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            asyncio.create_task(self._callback(
                self._create_event(FileWatchEventType.ANY, event.src_path)
            ))


class FileWatcher:
    """
    文件监听器

    使用 watchdog 监控目录或文件的变化，触发回调。
    """

    def __init__(self):
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog 未安装，文件监听功能不可用")

        self._observers: dict[str, Observer] = {}
        self._handlers: dict[str, list[Callable[[FileWatchEvent], Awaitable[Any]]]] = {}
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running and WATCHDOG_AVAILABLE

    async def watch(
        self,
        path: str | Path,
        callback: Callable[[FileWatchEvent], Awaitable[Any]],
        recursive: bool = True,
        event_types: list[FileWatchEventType] | None = None,
    ) -> bool:
        """
        开始监听文件变化。

        Args:
            path: 要监听的目录或文件路径
            callback: 变化时调用的回调函数
            recursive: 是否递归监听子目录
            event_types: 要监听的事件类型，None 表示监听所有

        Returns:
            bool: 是否成功
        """
        if not WATCHDOG_AVAILABLE:
            logger.error("watchdog 未安装，无法监听文件")
            return False

        path = str(Path(path).resolve())

        if path in self._observers:
            logger.warning(f"已在监听路径: {path}")
            # 添加额外的处理器
            if path not in self._handlers:
                self._handlers[path] = []
            self._handlers[path].append(callback)
            return True

        async def wrapped_callback(event: FileWatchEvent):
            # 如果指定了事件类型过滤
            if event_types and event.event_type not in event_types:
                return
            for handler in self._handlers.get(path, []):
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"文件监听回调执行失败: {e}")

        handler = FileWatcherEventHandler(callback=wrapped_callback)

        observer = Observer()
        observer.schedule(handler, path, recursive=recursive)
        observer.start()

        self._observers[path] = observer
        self._handlers[path] = [callback]
        self._running = True

        logger.info(f"开始监听: {path} (recursive={recursive})")
        return True

    async def unwatch(self, path: str | Path) -> bool:
        """
        停止监听。

        Args:
            path: 要取消监听的路径

        Returns:
            bool: 是否成功
        """
        path = str(Path(path).resolve())

        if path not in self._observers:
            logger.warning(f"未监听路径: {path}")
            return False

        observer = self._observers.pop(path)
        observer.stop()
        observer.join(timeout=5)

        if path in self._handlers:
            del self._handlers[path]

        if not self._observers:
            self._running = False

        logger.info(f"已停止监听: {path}")
        return True

    async def unwatch_all(self) -> None:
        """停止所有监听"""
        paths = list(self._observers.keys())
        for path in paths:
            await self.unwatch(path)

    def get_watched_paths(self) -> list[str]:
        """获取所有正在监听的路径"""
        return list(self._observers.keys())

    def is_watching(self, path: str | Path) -> bool:
        """检查路径是否正在被监听"""
        return str(Path(path).resolve()) in self._observers
