"""
Browser Tool - 浏览器自动化工具

基于 Playwright 实现浏览器自动化，支持：
- 导航到 URL
- 点击元素
- 输入文字
- 截图
- 获取页面内容
"""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from src.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class BrowserTool(BaseTool):
    """
    浏览器自动化工具

    提供浏览器控制能力，让 Agent 能够操作 Web 页面。
    """

    name = "browser"
    description = "控制浏览器执行网页操作，如导航、点击、输入、截图等"
    danger_level = "confirm"  # 默认需要确认

    def __init__(self, headless: bool = True, browser_type: str = "chromium"):
        """
        初始化浏览器工具。

        Args:
            headless: 是否使用无头模式（默认 True）
            browser_type: 浏览器类型（chromium/firefox/webkit）
        """
        self._headless = headless
        self._browser_type = browser_type
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None

    async def _ensure_browser(self) -> Page:
        """确保浏览器已启动并返回当前页面"""
        if self._page is not None:
            return self._page

        self._playwright = await async_playwright().start()

        if self._browser_type == "firefox":
            self._browser = await self._playwright.firefox.launch(headless=self._headless)
        elif self._browser_type == "webkit":
            self._browser = await self._playwright.webkit.launch(headless=self._headless)
        else:
            self._browser = await self._playwright.chromium.launch(headless=self._headless)

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        self._page = await self._context.new_page()

        logger.info(f"浏览器已启动 (headless={self._headless}, type={self._browser_type})")
        return self._page

    async def _close_browser(self) -> None:
        """关闭浏览器"""
        if self._page:
            await self._page.close()
            self._page = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("浏览器已关闭")

    async def navigate(self, url: str) -> ToolResult:
        """
        导航到指定 URL。

        Args:
            url: 目标 URL

        Returns:
            ToolResult: 操作结果
        """
        try:
            page = await self._ensure_browser()
            response = await page.goto(url, wait_until="domcontentloaded")
            title = await page.title()

            # 等待页面基本加载
            await page.wait_for_timeout(500)

            result_content = f"已导航到: {url}\n标题: {title}\n状态: {response.status if response else 'unknown'}"

            return ToolResult(
                success=True,
                content=result_content,
                metadata={"url": url, "title": title},
            )
        except Exception as e:
            logger.error(f"导航失败: {e}")
            return ToolResult(success=False, content=f"导航失败: {e}", error=str(e))

    async def click(self, selector: str, timeout: float = 5000) -> ToolResult:
        """
        点击页面元素。

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）

        Returns:
            ToolResult: 操作结果
        """
        try:
            page = await self._ensure_browser()

            # 等待元素出现
            await page.wait_for_selector(selector, timeout=timeout)

            # 点击元素
            await page.click(selector)

            return ToolResult(
                success=True,
                content=f"已点击元素: {selector}",
                metadata={"selector": selector},
            )
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return ToolResult(success=False, content=f"点击失败: {e}", error=str(e))

    async def type_text(
        self, selector: str, text: str, delay: int = 0
    ) -> ToolResult:
        """
        在输入框中输入文字。

        Args:
            selector: CSS 选择器
            text: 要输入的文字
            delay: 每个字符之间的延迟（毫秒）

        Returns:
            ToolResult: 操作结果
        """
        try:
            page = await self._ensure_browser()

            # 等待元素出现并清空
            await page.wait_for_selector(selector, timeout=5000)
            await page.fill(selector, "")

            # 输入文字
            await page.type(selector, text, delay=delay)

            return ToolResult(
                success=True,
                content=f"已在 {selector} 输入: {text}",
                metadata={"selector": selector, "text_length": len(text)},
            )
        except Exception as e:
            logger.error(f"输入失败: {e}")
            return ToolResult(success=False, content=f"输入失败: {e}", error=str(e))

    async def screenshot(self, full_page: bool = False) -> ToolResult:
        """
        截取当前页面。

        Args:
            full_page: 是否截取整个页面（默认 False，只截取视口）

        Returns:
            ToolResult: 操作结果，包含截图的 base64 编码
        """
        try:
            page = await self._ensure_browser()

            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")

            # 截图
            screenshot_bytes = await page.screenshot(full_page=full_page)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            return ToolResult(
                success=True,
                content=f"截图已生成 ({len(screenshot_bytes)} bytes)",
                metadata={
                    "format": "base64",
                    "size": len(screenshot_bytes),
                    "full_page": full_page,
                    "data": screenshot_base64,
                },
            )
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return ToolResult(success=False, content=f"截图失败: {e}", error=str(e))

    async def get_content(self) -> ToolResult:
        """
        获取当前页面的文本内容。

        Returns:
            ToolResult: 操作结果
        """
        try:
            page = await self._ensure_browser()

            content = await page.content()
            text = await page.inner_text("body")

            # 限制返回长度
            max_length = 10000
            if len(text) > max_length:
                text = text[:max_length] + f"\n... [内容过长，已截断，原始长度: {len(text)}]"

            return ToolResult(
                success=True,
                content=text,
                metadata={"url": page.url, "content_length": len(content)},
            )
        except Exception as e:
            logger.error(f"获取内容失败: {e}")
            return ToolResult(success=False, content=f"获取内容失败: {e}", error=str(e))

    async def evaluate(self, js_code: str) -> ToolResult:
        """
        在页面中执行 JavaScript 代码。

        Args:
            js_code: 要执行的 JavaScript 代码

        Returns:
            ToolResult: 操作结果
        """
        try:
            page = await self._ensure_browser()

            result = await page.evaluate(js_code)

            return ToolResult(
                success=True,
                content=f"执行结果: {result}",
                metadata={"js_code": js_code, "result": str(result)},
            )
        except Exception as e:
            logger.error(f"JavaScript 执行失败: {e}")
            return ToolResult(
                success=False, content=f"JavaScript 执行失败: {e}", error=str(e)
            )

    async def wait_for_selector(
        self, selector: str, timeout: float = 10000, state: str = "visible"
    ) -> ToolResult:
        """
        等待指定元素出现。

        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
            state: 等待状态（visible/hidden/attached/detached）

        Returns:
            ToolResult: 操作结果
        """
        try:
            page = await self._ensure_browser()

            await page.wait_for_selector(
                selector, timeout=timeout, state=state
            )

            return ToolResult(
                success=True,
                content=f"元素已出现: {selector}",
                metadata={"selector": selector, "state": state},
            )
        except Exception as e:
            logger.error(f"等待元素失败: {e}")
            return ToolResult(success=False, content=f"等待元素失败: {e}", error=str(e))

    async def go_back(self) -> ToolResult:
        """返回上一页"""
        try:
            page = await self._ensure_browser()
            await page.go_back()
            await page.wait_for_load_state("domcontentloaded")
            return ToolResult(
                success=True,
                content=f"已返回上一页，当前 URL: {page.url}",
                metadata={"url": page.url},
            )
        except Exception as e:
            logger.error(f"返回失败: {e}")
            return ToolResult(success=False, content=f"返回失败: {e}", error=str(e))

    async def go_forward(self) -> ToolResult:
        """前进到下一页"""
        try:
            page = await self._ensure_browser()
            await page.go_forward()
            await page.wait_for_load_state("domcontentloaded")
            return ToolResult(
                success=True,
                content=f"已前进一页，当前 URL: {page.url}",
                metadata={"url": page.url},
            )
        except Exception as e:
            logger.error(f"前进失败: {e}")
            return ToolResult(success=False, content=f"前进失败: {e}", error=str(e))

    async def reload(self) -> ToolResult:
        """刷新当前页面"""
        try:
            page = await self._ensure_browser()
            await page.reload()
            await page.wait_for_load_state("domcontentloaded")
            return ToolResult(
                success=True,
                content=f"已刷新页面，当前 URL: {page.url}",
                metadata={"url": page.url},
            )
        except Exception as e:
            logger.error(f"刷新失败: {e}")
            return ToolResult(success=False, content=f"刷新失败: {e}", error=str(e))

    @property
    def is_open(self) -> bool:
        """检查浏览器是否已打开"""
        return self._page is not None

    @property
    def current_url(self) -> str | None:
        """获取当前页面 URL"""
        return self._page.url if self._page else None


class BrowserToolExecutor:
    """
    Browser Tool 执行器

    将 BrowserTool 的各种操作封装为标准的工具执行接口。
    """

    def __init__(self, browser_tool: BrowserTool):
        self._browser = browser_tool

    async def execute(self, action: str, **kwargs) -> ToolResult:
        """
        执行浏览器操作。

        Args:
            action: 操作类型（navigate/click/type/screenshot/get_content/evaluate/...）
            **kwargs: 操作参数

        Returns:
            ToolResult: 操作结果
        """
        action_map = {
            "navigate": lambda: self._browser.navigate(kwargs.get("url", "")),
            "click": lambda: self._browser.click(kwargs.get("selector", "")),
            "type": lambda: self._browser.type_text(
                kwargs.get("selector", ""), kwargs.get("text", "")
            ),
            "screenshot": lambda: self._browser.screenshot(
                full_page=kwargs.get("full_page", False)
            ),
            "get_content": lambda: self._browser.get_content(),
            "evaluate": lambda: self._browser.evaluate(kwargs.get("js_code", "")),
            "wait_for": lambda: self._browser.wait_for_selector(
                kwargs.get("selector", ""),
                timeout=kwargs.get("timeout", 10000),
                state=kwargs.get("state", "visible"),
            ),
            "back": lambda: self._browser.go_back(),
            "forward": lambda: self._browser.go_forward(),
            "reload": lambda: self._browser.reload(),
        }

        action_func = action_map.get(action)
        if action_func is None:
            return ToolResult(
                success=False,
                content=f"未知操作: {action}",
                error=f"支持的操作: {list(action_map.keys())}",
            )

        return await action_func()


# 全局浏览器工具实例（用于单例模式）
_browser_instance: BrowserTool | None = None


async def get_browser_tool(headless: bool = True) -> BrowserTool:
    """获取全局浏览器工具实例"""
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = BrowserTool(headless=headless)
    return _browser_instance


async def close_browser_tool() -> None:
    """关闭全局浏览器工具"""
    global _browser_instance
    if _browser_instance:
        await _browser_instance._close_browser()
        _browser_instance = None
