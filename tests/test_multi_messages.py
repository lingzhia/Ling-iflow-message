#!/usr/bin/env python3
"""
多消息测试

给 iflow 发送多条消息，测试能否获取完整对话记录。
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tools.iflow_interactive_tool import IFlowInteractiveTool


async def test_multi_messages():
    """测试多消息对话"""

    print("=" * 60)
    print("多消息测试")
    print("=" * 60)

    # 创建工具实例
    tool = IFlowInteractiveTool(config_path="config.json")

    # 测试消息列表
    test_messages = [
        "你好，请简单介绍一下你自己",
        "请帮我写一个 Python 的 Hello World 程序",
        "这个程序的作用是什么？",
        "请再写一个计算两个数之和的函数",
        "这个函数的参数是什么？返回值是什么？"
    ]

    # 记录对话
    conversations = []

    try:
        # 启动工具
        await tool.start()

        # 发送多条消息
        for i, message in enumerate(test_messages, 1):
            print(f"\n{'=' * 60}")
            print(f"消息 {i}/{len(test_messages)}")
            print(f"{'=' * 60}")

            # 记录发送的消息
            sent_time = datetime.now()

            # 发送消息
            await tool.send_message(message)

            # 等待回复完成
            completed = await tool.wait_for_complete(timeout=120.0)

            # 记录回复
            received_time = datetime.now()
            replies = []

            # 获取最新的回复（从 message_history 中）
            if tool.message_history:
                # 只获取当前对话的回复
                # 过滤掉之前的回复（根据时间戳）
                for msg in tool.message_history:
                    msg_time = datetime.fromisoformat(msg['timestamp'])
                    if msg_time >= sent_time:
                        replies.append({
                            'type': msg['type'],
                            'content': msg['content'],
                            'timestamp': msg['timestamp'],
                            'metadata': msg['metadata']
                        })

            # 记录对话
            conversations.append({
                'index': i,
                'sent_message': message,
                'sent_time': sent_time.isoformat(),
                'received_time': received_time.isoformat(),
                'replies': replies,
                'completed': completed
            })

            print(f"\n✅ 消息 {i} 完成")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 停止工具
        await tool.stop()

    # 输出对话记录
    print("\n" + "=" * 60)
    print("对话记录")
    print("=" * 60)

    for conv in conversations:
        print(f"\n{'=' * 60}")
        print(f"消息 {conv['index']}/{len(conversations)}")
        print(f"{'=' * 60}")

        print(f"\n📤 发送消息 ({conv['sent_time']})")
        print(f"   {conv['sent_message']}")

        print(f"\n📥 回复 ({conv['received_time']})")
        if conv['replies']:
            for i, reply in enumerate(conv['replies'], 1):
                print(f"\n   回复 {i} [{reply['type']}]:")
                print(f"   内容: {reply['content']}")
                if reply['metadata']:
                    print(f"   元数据: {reply['metadata']}")
        else:
            print("   无回复")

        print(f"\n   状态: {'✅ 完成' if conv['completed'] else '❌ 未完成'}")

    # 统计信息
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)

    total_messages = len(conversations)
    completed_messages = sum(1 for conv in conversations if conv['completed'])
    total_replies = sum(len(conv['replies']) for conv in conversations)

    print(f"发送消息总数: {total_messages}")
    print(f"完成消息数: {completed_messages}")
    print(f"失败消息数: {total_messages - completed_messages}")
    print(f"收到回复总数: {total_replies}")

    if completed_messages == total_messages and total_replies > 0:
        print(f"\n✅ 所有消息都收到了回复")
        return 0
    else:
        print(f"\n❌ 部分消息没有收到回复")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(test_multi_messages()))
