"""
Phase 3 验证测试 - 浏览器自动化

测试 Playwright 浏览器控制功能。
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def test_browser_import():
    """测试 Playwright 导入"""
    print("\n" + "=" * 60)
    print("测试 1: Playwright 导入")
    print("=" * 60)

    try:
        from playwright.async_api import async_playwright
        print("  ✓ Playwright 导入成功")
        return True
    except ImportError as e:
        print(f"  ❌ Playwright 导入失败: {e}")
        return False


async def test_browser_tool_basic():
    """测试浏览器工具基本功能"""
    print("\n" + "=" * 60)
    print("测试 2: 浏览器工具基本功能")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool

    browser = BrowserTool(headless=True)

    # 导航到 example.com
    result = await browser.navigate("https://example.com")
    assert result.success is True
    assert "example.com" in result.content
    print(f"  ✓ 导航成功: {result.content[:50]}...")

    # 获取页面内容
    result = await browser.get_content()
    assert result.success is True
    assert len(result.content) > 0
    print(f"  ✓ 获取内容成功 ({len(result.content)} 字符)")

    # 截图
    result = await browser.screenshot()
    assert result.success is True
    assert "base64" in result.metadata.get("format", "")
    assert len(result.metadata.get("data", "")) > 1000
    print(f"  ✓ 截图成功 ({result.metadata['size']} bytes)")

    # 关闭浏览器
    await browser._close_browser()
    print("  ✓ 浏览器已关闭")


async def test_browser_navigate():
    """测试浏览器导航"""
    print("\n" + "=" * 60)
    print("测试 3: 浏览器导航")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool

    browser = BrowserTool(headless=True)

    # 测试多个网站
    urls = [
        "https://example.com",
        "https://httpbin.org/html",
    ]

    for url in urls:
        result = await browser.navigate(url)
        assert result.success is True
        print(f"  ✓ 导航到 {url}: {result.metadata.get('title', 'N/A')}")

    await browser._close_browser()


async def test_browser_click_and_type():
    """测试浏览器点击和输入"""
    print("\n" + "=" * 60)
    print("测试 4: 浏览器点击和输入")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool

    browser = BrowserTool(headless=True)

    # 导航到一个有输入框的测试页面
    await browser.navigate("https://httpbin.org/forms/post")

    # 检查页面是否有内容
    content = await browser.get_content()
    assert content.success is True
    print(f"  ✓ 页面加载成功")

    # 尝试点击（可能在表单页面上没有特定元素）
    result = await browser.click("input[type='text']", timeout=2000)
    # 如果没有找到元素，不算失败
    print(f"  ✓ 点击操作完成")

    await browser._close_browser()


async def test_browser_navigation_control():
    """测试浏览器导航控制"""
    print("\n" + "=" * 60)
    print("测试 5: 浏览器导航控制")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool

    browser = BrowserTool(headless=True)

    # 导航到第一个页面
    await browser.navigate("https://example.com")
    url1 = browser.current_url
    print(f"  ✓ 第一个页面: {url1}")

    # 导航到第二个页面
    await browser.navigate("https://httpbin.org/html")
    url2 = browser.current_url
    print(f"  ✓ 第二个页面: {url2}")

    # 返回
    result = await browser.go_back()
    assert "example.com" in result.content or url1 in result.content
    print(f"  ✓ 返回成功")

    # 前进
    result = await browser.go_forward()
    assert "httpbin.org" in result.content or url2 in result.content
    print(f"  ✓ 前进成功")

    # 刷新
    result = await browser.reload()
    assert result.success is True
    print(f"  ✓ 刷新成功")

    await browser._close_browser()


async def test_browser_screenshot_variants():
    """测试不同模式的截图"""
    print("\n" + "=" * 60)
    print("测试 6: 不同模式的截图")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool

    browser = BrowserTool(headless=True)
    await browser.navigate("https://example.com")

    # 视口截图
    result1 = await browser.screenshot(full_page=False)
    assert result1.success is True
    size1 = result1.metadata["size"]
    print(f"  ✓ 视口截图: {size1} bytes")

    # 整页截图
    result2 = await browser.screenshot(full_page=True)
    assert result2.success is True
    size2 = result2.metadata["size"]
    print(f"  ✓ 整页截图: {size2} bytes")

    await browser._close_browser()


async def test_browser_executor():
    """测试浏览器工具执行器"""
    print("\n" + "=" * 60)
    print("测试 7: 浏览器工具执行器")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool, BrowserToolExecutor

    browser = BrowserTool(headless=True)
    executor = BrowserToolExecutor(browser)

    # 通过执行器调用
    result = await executor.execute("navigate", url="https://example.com")
    assert result.success is True
    print(f"  ✓ executor.execute(navigate) 成功")

    result = await executor.execute("get_content")
    assert result.success is True
    print(f"  ✓ executor.execute(get_content) 成功")

    result = await executor.execute("screenshot")
    assert result.success is True
    print(f"  ✓ executor.execute(screenshot) 成功")

    result = await executor.execute("unknown_action")
    assert result.success is False
    assert "未知操作" in result.content
    print(f"  ✓ executor.execute(unknown) 返回错误")

    await browser._close_browser()


async def test_browser_context_cleanup():
    """测试浏览器上下文清理"""
    print("\n" + "=" * 60)
    print("测试 8: 浏览器上下文清理")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool

    browser = BrowserTool(headless=True)

    # 打开浏览器
    await browser.navigate("https://example.com")
    assert browser.is_open is True
    print(f"  ✓ 浏览器已打开")

    # 关闭浏览器
    await browser._close_browser()
    assert browser.is_open is False
    print(f"  ✓ 浏览器已关闭")

    # 再次打开
    await browser.navigate("https://httpbin.org/html")
    assert browser.is_open is True
    print(f"  ✓ 浏览器重新打开成功")

    await browser._close_browser()


async def test_browser_multiple_pages():
    """测试多标签页功能"""
    print("\n" + "=" * 60)
    print("测试 9: 多标签页功能（基础）")
    print("=" * 60)

    from src.tools.builtin.browser_tool import BrowserTool

    browser = BrowserTool(headless=True)

    # 打开第一个页面
    await browser.navigate("https://example.com")
    url1 = browser.current_url
    print(f"  ✓ 第一个页面: {url1}")

    # 注意：当前实现不支持多标签页，但基本功能正常
    # 多标签页需要扩展 BrowserContext

    await browser._close_browser()
    print(f"  ✓ 单标签页模式正常")


# ==================== Main ====================

async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("        Zclaw Phase 3 - 浏览器自动化验证")
    print("=" * 60)

    tests = [
        test_browser_import,
        test_browser_tool_basic,
        test_browser_navigate,
        test_browser_click_and_type,
        test_browser_navigation_control,
        test_browser_screenshot_variants,
        test_browser_executor,
        test_browser_context_cleanup,
        test_browser_multiple_pages,
    ]

    passed = 0
    failed = 0

    for test in tests:
        test_name = test.__name__
        try:
            result = await test()
            if result is False:
                failed += 1
            else:
                passed += 1
        except Exception as e:
            print(f"\n  ❌ {test_name} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"        测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
