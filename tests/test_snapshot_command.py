#!/usr/bin/env python3
"""
测试 /snapshot 命令
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core import MessageBus, ModuleManager
from src.modules.command import CommandHandler


async def test_snapshot_command():
    """测试 /snapshot 命令"""
    print("=" * 60)
    print("测试 /snapshot 命令")
    print("=" * 60)
    
    # 创建消息总线和模块管理器
    bus = MessageBus()
    manager = ModuleManager(bus)
    bus.module_manager = manager
    
    # 创建命令处理器
    handler = CommandHandler(bus, manager)
    
    # 测试 1：没有 iflow 模块时的情况
    print("\n测试 1：没有 iflow 模块时的情况")
    result = await handler.execute(
        handler.parse_command("/snapshot"),
        chat_id="test"
    )
    print(f"结果: {result}")
    assert "没有可用的 iflow 模块" in result or "消息总线未初始化" in result
    print("✅ 测试 1 通过")
    
    # 测试 2：命令解析
    print("\n测试 2：命令解析")
    parsed = handler.parse_command("/snapshot")
    print(f"解析结果: {parsed}")
    assert parsed["is_command"] == True
    assert parsed["cmd_name"] == "/snapshot"
    print("✅ 测试 2 通过")
    
    # 测试 3：带参数的命令解析
    print("\n测试 3：带参数的命令解析")
    parsed = handler.parse_command("/snapshot bot1")
    print(f"解析结果: {parsed}")
    assert parsed["is_command"] == True
    assert parsed["cmd_name"] == "/snapshot"
    assert parsed["cmd_args"] == "bot1"
    print("✅ 测试 3 通过")
    
    # 测试 4：测试 _clean_tmux_output 方法
    print("\n测试 4：测试 _clean_tmux_output 方法")
    test_output = "\x1B[31mError message\x1B[0m\n\nNormal line\n\nAnother line"
    cleaned = handler._clean_tmux_output(test_output)
    print(f"原始输出: {repr(test_output)}")
    print(f"清理后: {repr(cleaned)}")
    assert "\x1B" not in cleaned  # 确保移除了 ANSI 控制序列
    print("✅ 测试 4 通过")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_snapshot_command())