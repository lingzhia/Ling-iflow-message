#!/usr/bin/env python3
"""
完整对话测试

给 iflow 发送多条消息，获取完整对话记录。
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
from src.modules.iflow.monitor import IFlowMonitor, IFlowState, OutboundMessage


async def test_complete_conversation():
    """测试完整对话"""

    print("=" * 60)
    print("完整对话测试")
    print("=" * 60)

    # 创建 controller 和 monitor
    controller = IFlowController("conversation_test")
    monitor = IFlowMonitor(controller, check_interval=0.5)

    # 用于存储所有对话
    conversations = []

    # 当前对话的消息
    current_conversation = {
        'sent_message': None,
        'sent_time': None,
        'replies': []
    }

    async def message_handler(message: OutboundMessage):
        """处理收到的消息"""
        # 添加到当前对话
        current_conversation['replies'].append({
            'type': message.type.value,
            'content': message.content,
            'timestamp': message.timestamp.isoformat()
        })

        # 显示消息
        if message.type.value == 'reply':
            print(f"\n📥 [✦ 回复] {message.content[:100]}...")
        else:
            print(f"\n💭 [✻ 思考] {message.content[:100]}...")

    # 订阅消息
    monitor.subscribe(message_handler)

    # 测试消息列表
    test_messages = [
        "你好，请简单介绍一下你自己",
        "请帮我写一个 Python 的 Hello World 程序",
        "这个程序的作用是什么？",
        "请再写一个计算两个数之和的函数",
        "这个函数的参数是什么？返回值是什么？"
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

            # 重置当前对话
            current_conversation = {
                'sent_message': message,
                'sent_time': datetime.now().isoformat(),
                'replies': []
            }

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
            replies_before = 0

            while waited < max_wait:
                await asyncio.sleep(1)
                waited += 1

                # 检查是否收到新回复
                replies_after = len(current_conversation['replies'])
                if replies_after > replies_before:
                    new_replies = replies_after - replies_before
                    print(f"✅ 收到 {new_replies} 条新回复")
                    replies_before = replies_after
                    # 继续等待，确保所有回复都收到
                    continue

                # 检查状态
                if monitor.state == IFlowState.IDLE and len(current_conversation['replies']) > 0:
                    # 状态已变回 idle，说明可能已经完成
                    print(f"✅ iflow 状态已变回 idle")
                    # 再等待 2 秒，确保稳定
                    await asyncio.sleep(2)
                    if monitor.state == IFlowState.IDLE:
                        break

                if waited % 5 == 0:
                    print(f"   等待中... {waited}秒 (状态: {monitor.state.value})")

            # 保存当前对话
            if len(current_conversation['replies']) > 0:
                conversations.append(current_conversation.copy())
                print(f"✅ 对话 {i} 完成，收到 {len(current_conversation['replies'])} 条回复")
            else:
                print(f"❌ 对话 {i} 未收到回复")

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

    # 输出对话记录
    print("\n" + "=" * 60)
    print("对话记录")
    print("=" * 60)

    for i, conv in enumerate(conversations, 1):
        print(f"\n{'=' * 60}")
        print(f"对话 {i}/{len(conversations)}")
        print(f"{'=' * 60}")

        print(f"\n📤 发送消息 ({conv['sent_time']})")
        print(f"   {conv['sent_message']}")

        print(f"\n📥 回复 (共 {len(conv['replies'])} 条)")
        for j, reply in enumerate(conv['replies'], 1):
            print(f"\n   回复 {j} [{reply['type']}]:")
            print(f"   {reply['content']}")

    # 输出统计
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)

    total_messages = len(conversations)
    total_replies = sum(len(conv['replies']) for conv in conversations)

    print(f"\n发送消息总数: {total_messages}")
    print(f"收到回复总数: {total_replies}")
    print(f"平均每条消息回复数: {total_replies / total_messages:.1f}")

    if total_messages > 0 and total_replies > 0:
        print(f"\n✅ 测试成功")
        return 0
    else:
        print(f"\n❌ 测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(test_complete_conversation()))