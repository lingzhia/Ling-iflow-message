#!/usr/bin/env python3
"""
调试消息提取

调试 IFlowMonitor 的消息提取逻辑。
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor


async def test_debug_extraction():
    """调试消息提取"""

    print("=" * 60)
    print("调试消息提取")
    print("=" * 60)

    # 创建 controller 和 monitor
    controller = IFlowController("debug_test")
    monitor = IFlowMonitor(controller, check_interval=0.5)

    # 用于存储收到的消息
    received_messages = []

    async def message_handler(message):
        """处理收到的消息"""
        print(f"\n📥 收到消息:")
        print(f"   类型: {message.type.value}")
        print(f"   内容: {message.content.text}")
        received_messages.append(message)

    # 订阅消息
    monitor.subscribe(message_handler)

    try:
        # 启动 iflow
        print("\n正在启动 iflow...")
        success = await controller.start_iflow("kimi-k2.5")
        if not success:
            print("❌ 启动 iflow 失败")
            return 1

        print(f"✅ iflow 已启动")
        print(f"   tmux_session: {controller.tmux_session}")

        # 等待 iflow 完全启动
        print("\n等待 iflow 完全启动...")
        await asyncio.sleep(5)

        # 启动 monitor
        print("\n正在启动 monitor...")
        await monitor.start()
        print(f"✅ monitor 已启动")

        # 发送消息
        test_message = "你好，请简单介绍一下你自己"
        print(f"\n📤 发送消息: {test_message}")
        success = await controller.send_message(test_message)
        if not success:
            print("❌ 发送消息失败")
            return 1

        # 等待回复
        print(f"\n等待回复...")
        await asyncio.sleep(20)

        # 捕获输出
        print(f"\n{'=' * 60}")
        print("捕获的输出")
        print(f"{'=' * 60}")
        output = await controller.capture_output(100)
        print(output)

        # 测试消息提取
        print(f"\n{'=' * 60}")
        print("测试消息提取")
        print(f"{'=' * 60}")
        messages = monitor._extract_messages(output)
        print(f"\n提取的消息数量: {len(messages)}")

        for i, msg in enumerate(messages, 1):
            print(f"\n消息 {i}:")
            print(f"  类型: {msg['marker_type']}")
            print(f"  内容: {msg['content']}")
            print(f"  标记: {msg['marker_only']}")

        # 测试接收消息提取
        print(f"\n{'=' * 60}")
        print("测试接收消息提取")
        print(f"{'=' * 60}")
        lines = output.split('\n')
        received_msg, received_line = monitor._extract_received_message(lines)
        print(f"\n接收消息: {received_msg}")
        print(f"接收行号: {received_line}")

        # 测试 TUI 识别
        print(f"\n{'=' * 60}")
        print("测试 TUI 识别")
        print(f"{'=' * 60}")
        for i, line in enumerate(lines):
            if monitor._is_tui_line(line):
                print(f"行 {i}: {line[:80]}...")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 停止
        print("\n\n正在停止...")
        await monitor.stop()
        await controller.stop_iflow()
        await controller.destroy_session()
        print("✅ 已停止")

    # 输出统计
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

    print(f"\n收到回复总数: {len(received_messages)}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_debug_extraction()))