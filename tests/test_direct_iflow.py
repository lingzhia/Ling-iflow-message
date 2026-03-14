#!/usr/bin/env python3
"""
直接测试 iflow

直接使用 IFlowController 和 IFlowMonitor 测试消息发送和接收。
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor
from src.modules.iflow.monitor import IFlowState, OutboundMessage


async def test_direct_iflow():
    """直接测试 iflow"""

    print("=" * 60)
    print("直接测试 iflow")
    print("=" * 60)

    # 创建 controller 和 monitor
    controller = IFlowController("test_iflow")
    monitor = IFlowMonitor(controller, check_interval=0.5)

    # 用于存储收到的消息
    received_messages = []

    async def message_handler(message: OutboundMessage):
        """处理收到的消息"""
        print(f"\n📥 收到消息:")
        print(f"   类型: {message.type.value}")
        print(f"   内容: {message.content}")
        print(f"   时间: {message.timestamp}")
        received_messages.append({
            'type': message.type.value,
            'content': message.content,
            'timestamp': message.timestamp.isoformat(),
            'metadata': message.metadata
        })
        print(f"   当前消息总数: {len(received_messages)}")

    # 订阅消息
    monitor.subscribe(message_handler)

    # 测试消息列表
    test_messages = [
        "你好，请简单介绍一下你自己",
        "请帮我写一个 Python 的 Hello World 程序",
        "这个程序的作用是什么？"
    ]

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

        # 发送多条消息
        for i, message in enumerate(test_messages, 1):
            print(f"\n{'=' * 60}")
            print(f"消息 {i}/{len(test_messages)}")
            print(f"{'=' * 60}")

            # 记录发送前的消息数量
            messages_before = len(received_messages)

            # 发送消息
            print(f"\n📤 发送消息: {message}")
            success = await controller.send_message(message)
            if not success:
                print("❌ 发送消息失败")
                continue

            # 等待回复
            print(f"\n等待回复...")
            max_wait = 60  # 最多等待 60 秒
            waited = 0
            while waited < max_wait:
                await asyncio.sleep(1)
                waited += 1

                # 检查是否收到新消息
                messages_after = len(received_messages)
                if messages_after > messages_before:
                    new_messages = messages_after - messages_before
                    print(f"✅ 收到 {new_messages} 条新回复")
                    break

                # 检查状态
                if monitor.state == IFlowState.IDLE:
                    # 状态已变回 idle，说明可能已经完成
                    print(f"✅ iflow 状态已变回 idle")
                    break

                if waited % 5 == 0:
                    print(f"   等待中... {waited}秒 (状态: {monitor.state.value})")

            # 检查是否收到新消息
            messages_after = len(received_messages)
            if messages_after == messages_before:
                print(f"❌ 未收到回复 (等待了 {waited} 秒)")
            else:
                new_messages = messages_after - messages_before
                print(f"✅ 成功收到 {new_messages} 条回复")

            # 捕获输出查看
            output = await controller.capture_output(50)
            print(f"\n最近的输出 (最后 20 行):")
            print(output[-1000:])

            # 等待一下，确保状态稳定
            await asyncio.sleep(2)

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

    print(f"\n发送消息总数: {len(test_messages)}")
    print(f"收到回复总数: {len(received_messages)}")

    # 输出所有回复
    if received_messages:
        print("\n所有回复:")
        for i, msg in enumerate(received_messages, 1):
            print(f"\n回复 {i}:")
            print(f"  类型: {msg['type']}")
            print(f"  内容: {msg['content']}")
            print(f"  时间: {msg['timestamp']}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_direct_iflow()))
