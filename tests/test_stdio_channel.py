"""
StdioChannel 测试用例

测试 STDIO 通道的核心功能：
1. 初始化和属性
2. 消息回调注册
3. 消息归一化
4. 发送功能（mock）
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from src.channel.channels.stdio import StdioChannel
from src.channel.channels.base import ChannelMessage


class TestStdioChannel:
    """StdioChannel 测试类"""

    @pytest.fixture
    def channel(self):
        """创建 StdioChannel 实例"""
        ch = StdioChannel(prompt="test> ")
        yield ch
        # 清理
        if ch._running:
            asyncio.run(ch.stop())

    def test_initialization(self, channel):
        """测试初始化"""
        assert channel.channel_name == "stdio"
        assert channel.enabled is True
        assert channel._running is False
        assert len(channel._message_callbacks) == 0

    def test_set_enabled(self, channel):
        """测试设置启用状态"""
        channel.set_enabled(False)
        assert channel.enabled is False
        assert channel._running is False

        channel.set_enabled(True)
        assert channel.enabled is True

    @pytest.mark.asyncio
    async def test_start_stop(self, channel):
        """测试启动和停止"""
        await channel.start()
        assert channel._running is True

        await channel.stop()
        assert channel._running is False

    @pytest.mark.asyncio
    async def test_start_twice(self, channel):
        """测试重复启动（应该警告但不报错）"""
        await channel.start()
        await channel.start()  # 不应该报错

        await channel.stop()

    def test_on_message(self, channel):
        """测试消息回调注册"""
        callback1 = MagicMock()
        callback2 = MagicMock()

        channel.on_message(callback1)
        channel.on_message(callback2)

        assert len(channel._message_callbacks) == 2

    def test_unregister_message_callback(self, channel):
        """测试消息回调注销"""
        callback = MagicMock()
        channel.on_message(callback)

        assert channel.unregister_message_callback(callback) is True
        assert len(channel._message_callbacks) == 0

        # 注销不存在的回调
        assert channel.unregister_message_callback(callback) is False

    @pytest.mark.asyncio
    async def test_process_input(self, channel):
        """测试处理用户输入"""
        callback = MagicMock()
        channel.on_message(callback)

        await channel.process_input("hello world")

        # 验证回调被调用
        callback.assert_called_once()
        msg = callback.call_args[0][0]
        assert isinstance(msg, ChannelMessage)
        assert msg.text == "hello world"
        assert msg.sender_id == "cli_user"

    @pytest.mark.asyncio
    async def test_process_input_empty(self, channel):
        """测试处理空输入"""
        callback = MagicMock()
        channel.on_message(callback)

        await channel.process_input("   ")
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_input_triggers_multiple_callbacks(self, channel):
        """测试多个回调都被触发"""
        callback1 = MagicMock()
        callback2 = MagicMock()
        channel.on_message(callback1)
        channel.on_message(callback2)

        await channel.process_input("test message")

        callback1.assert_called_once()
        callback2.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_input_callback_exception(self, channel):
        """测试回调异常不影响其他回调"""
        callback1 = MagicMock(side_effect=Exception("Test error"))
        callback2 = MagicMock()
        channel.on_message(callback1)
        channel.on_message(callback2)

        # 不应该抛出异常
        await channel.process_input("test")

        # 第二个回调应该仍被调用
        callback2.assert_called_once()

    def test_normalize_message(self, channel):
        """测试消息归一化"""
        # 测试字典输入
        raw = {"text": "hello", "sender_id": "user123"}
        msg = channel.normalize_message(raw)

        assert msg is not None
        assert msg.text == "hello"
        assert msg.sender_id == "user123"
        assert msg.channel == "stdio"

    def test_normalize_message_empty(self, channel):
        """测试空消息归一化"""
        msg = channel.normalize_message({})
        assert msg is None

        msg = channel.normalize_message("")
        assert msg is None

    def test_normalize_message_non_dict(self, channel):
        """测试非字典消息归一化"""
        msg = channel.normalize_message("just a string")
        assert msg is not None
        assert msg.text == "just a string"
        assert msg.sender_id == "cli_user"

    @pytest.mark.asyncio
    async def test_send(self, channel):
        """测试发送消息"""
        await channel.start()

        with patch("sys.stdout") as mock_stdout:
            result = await channel.send("hello")
            assert result is True
            # print 会自动添加换行符
            mock_stdout.write.assert_called()

    @pytest.mark.asyncio
    async def test_send_not_running(self, channel):
        """测试未运行时发送失败"""
        channel._running = False
        result = await channel.send("hello")
        assert result is False

    def test_send_sync(self, channel):
        """测试同步发送"""
        with patch("sys.stdout") as mock_stdout:
            result = channel.send_sync("sync message")
            assert result is True
            mock_stdout.write.assert_called_once_with("sync message")

    def test_print(self, channel):
        """测试打印功能"""
        with patch("builtins.print") as mock_print:
            channel.print("hello", "world", sep=", ")
            mock_print.assert_called_once_with("hello", "world", sep=", ")

    def test_repr(self, channel):
        """测试 __repr__"""
        r = repr(channel)
        assert "StdioChannel" in r
        assert "running=False" in r

    @pytest.mark.asyncio
    async def test_repr_running(self, channel):
        """测试运行时 __repr__"""
        await channel.start()
        r = repr(channel)
        assert "running=True" in r


class TestStdioChannelIntegration:
    """StdioChannel 集成测试（需要 mock stdin）"""

    @pytest.mark.asyncio
    async def test_read_line_eof(self):
        """测试 EOF"""
        channel = StdioChannel()

        with patch("builtins.input", side_effect=EOFError()):
            result = await channel.read_line()
            assert result is None

    @pytest.mark.asyncio
    async def test_read_line_keyboard_interrupt(self):
        """测试 KeyboardInterrupt"""
        channel = StdioChannel()

        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            result = await channel.read_line()
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])