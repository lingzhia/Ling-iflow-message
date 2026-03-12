"""
CommandHandler 测试
"""

import sys
import os
import asyncio
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.command.handler import CommandHandler


def test_parse_normal_message():
    """测试解析普通消息"""
    handler = CommandHandler()
    result = handler.parse_command("帮我写一个Python脚本")
    
    assert result["is_command"] is False
    assert result["cmd_type"] == "message"
    assert result["cmd_name"] is None
    assert result["cmd_args"] == "帮我写一个Python脚本"
    print("✅ test_parse_normal_message passed")


def test_parse_command_without_args():
    """测试解析无参数命令"""
    handler = CommandHandler()
    result = handler.parse_command("/help")
    
    assert result["is_command"] is True
    assert result["cmd_type"] == "command"
    assert result["cmd_name"] == "/help"
    assert result["cmd_args"] == ""
    print("✅ test_parse_command_without_args passed")


def test_parse_command_with_args():
    """测试解析带参数命令"""
    handler = CommandHandler()
    result = handler.parse_command("/status detailed")
    
    assert result["is_command"] is True
    assert result["cmd_type"] == "command"
    assert result["cmd_name"] == "/status"
    assert result["cmd_args"] == "detailed"
    print("✅ test_parse_command_with_args passed")


def test_parse_command_case_insensitive():
    """测试命令不区分大小写"""
    handler = CommandHandler()
    result = handler.parse_command("/HELP")
    
    assert result["is_command"] is True
    assert result["cmd_name"] == "/help"
    print("✅ test_parse_command_case_insensitive passed")


def test_parse_command_with_leading_spaces():
    """测试带前导空格的命令"""
    handler = CommandHandler()
    result = handler.parse_command("   /new")
    
    assert result["is_command"] is True
    assert result["cmd_name"] == "/new"
    print("✅ test_parse_command_with_leading_spaces passed")


def test_parse_empty_message():
    """测试空消息"""
    handler = CommandHandler()
    result = handler.parse_command("")
    
    assert result["is_command"] is False
    assert result["cmd_type"] == "message"
    print("✅ test_parse_empty_message passed")


async def test_execute_help_command():
    """测试 /help 命令"""
    handler = CommandHandler()
    parsed = handler.parse_command("/help")
    result = await handler.execute(parsed)
    
    assert result is not None
    assert "iFlow" in result
    assert "/new" in result
    assert "/status" in result
    print("✅ test_execute_help_command passed")


async def test_execute_lscmd_command():
    """测试 /lscmd 命令"""
    handler = CommandHandler()
    parsed = handler.parse_command("/lscmd")
    result = await handler.execute(parsed)
    
    assert result is not None
    assert "可用命令列表" in result
    assert "/new" in result
    print("✅ test_execute_lscmd_command passed")


async def test_execute_unknown_command():
    """测试未知命令"""
    handler = CommandHandler()
    parsed = handler.parse_command("/unknown")
    result = await handler.execute(parsed)
    
    assert result is not None
    assert "未知命令" in result
    assert "/unknown" in result
    print("✅ test_execute_unknown_command passed")


async def test_execute_normal_message_returns_none():
    """测试普通消息返回 None"""
    handler = CommandHandler()
    parsed = handler.parse_command("普通消息")
    result = await handler.execute(parsed)
    
    assert result is None
    print("✅ test_execute_normal_message_returns_none passed")


async def test_execute_status_without_bus():
    """测试无消息总线时执行 /status"""
    handler = CommandHandler()
    parsed = handler.parse_command("/status")
    result = await handler.execute(parsed)
    
    assert "消息总线未初始化" in result
    print("✅ test_execute_status_without_bus passed")


async def test_execute_new_without_bus():
    """测试无消息总线时执行 /new"""
    handler = CommandHandler()
    parsed = handler.parse_command("/new")
    result = await handler.execute(parsed)
    
    assert "消息总线未初始化" in result
    print("✅ test_execute_new_without_bus passed")


async def test_execute_sessions_without_bus():
    """测试无消息总线时执行 /sessions"""
    handler = CommandHandler()
    parsed = handler.parse_command("/sessions")
    result = await handler.execute(parsed)
    
    assert "消息总线未初始化" in result
    print("✅ test_execute_sessions_without_bus passed")


async def test_execute_status_with_iflow_module():
    """测试 /status 命令与 iflow 模块"""
    handler = CommandHandler()
    
    # 创建 mock 消息总线
    mock_bus = Mock()
    mock_iflow = Mock()
    mock_iflow.get_status_message = Mock(return_value="iflow 状态: 运行中")
    mock_bus.modules = {"iflow_test": mock_iflow}
    handler.set_message_bus(mock_bus)
    
    parsed = handler.parse_command("/status")
    result = await handler.execute(parsed)
    
    assert "运行中" in result
    print("✅ test_execute_status_with_iflow_module passed")


async def test_execute_new_with_iflow_module():
    """测试 /new 命令与 iflow 模块"""
    handler = CommandHandler()
    
    mock_bus = Mock()
    mock_iflow = Mock()
    mock_iflow.create_new_session = Mock(return_value={"success": True})
    mock_bus.modules = {"iflow_test": mock_iflow}
    handler.set_message_bus(mock_bus)
    
    parsed = handler.parse_command("/new")
    result = await handler.execute(parsed)
    
    assert "已开始新会话" in result
    print("✅ test_execute_new_with_iflow_module passed")


async def test_execute_new_failed():
    """测试 /new 命令失败"""
    handler = CommandHandler()
    
    mock_bus = Mock()
    mock_iflow = Mock()
    mock_iflow.create_new_session = Mock(return_value={"success": False, "message": "创建失败"})
    mock_bus.modules = {"iflow_test": mock_iflow}
    handler.set_message_bus(mock_bus)
    
    parsed = handler.parse_command("/new")
    result = await handler.execute(parsed)
    
    assert "创建失败" in result
    print("✅ test_execute_new_failed passed")


async def test_execute_sessions_with_iflow_module():
    """测试 /sessions 命令与 iflow 模块"""
    handler = CommandHandler()
    
    mock_bus = Mock()
    mock_iflow = Mock()
    mock_iflow.get_sessions_message = Mock(return_value="会话列表:\n1. session-1\n2. session-2")
    mock_bus.modules = {"iflow_test": mock_iflow}
    handler.set_message_bus(mock_bus)
    
    parsed = handler.parse_command("/sessions")
    result = await handler.execute(parsed)
    
    assert "会话列表" in result
    print("✅ test_execute_sessions_with_iflow_module passed")


async def test_execute_status_no_iflow_module():
    """测试 /status 命令但无 iflow 模块"""
    handler = CommandHandler()
    
    mock_bus = Mock()
    mock_bus.modules = {"wechat_test": Mock()}
    handler.set_message_bus(mock_bus)
    
    parsed = handler.parse_command("/status")
    result = await handler.execute(parsed)
    
    assert "没有可用的 iflow 模块" in result
    print("✅ test_execute_status_no_iflow_module passed")


def test_builtin_commands_registered():
    """测试内置命令已注册"""
    handler = CommandHandler()
    
    assert "/help" in handler._commands
    assert "/status" in handler._commands
    assert "/new" in handler._commands
    assert "/sessions" in handler._commands
    assert "/lscmd" in handler._commands
    print("✅ test_builtin_commands_registered passed")


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("CommandHandler 测试")
    print("=" * 60)
    
    # 同步测试
    tests_sync = [
        test_parse_normal_message,
        test_parse_command_without_args,
        test_parse_command_with_args,
        test_parse_command_case_insensitive,
        test_parse_command_with_leading_spaces,
        test_parse_empty_message,
        test_builtin_commands_registered,
    ]
    
    # 异步测试
    tests_async = [
        test_execute_help_command,
        test_execute_lscmd_command,
        test_execute_unknown_command,
        test_execute_normal_message_returns_none,
        test_execute_status_without_bus,
        test_execute_new_without_bus,
        test_execute_sessions_without_bus,
        test_execute_status_with_iflow_module,
        test_execute_new_with_iflow_module,
        test_execute_new_failed,
        test_execute_sessions_with_iflow_module,
        test_execute_status_no_iflow_module,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests_sync:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    for test in tests_async:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"测试汇总: {passed}/{passed + failed} 通过")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)