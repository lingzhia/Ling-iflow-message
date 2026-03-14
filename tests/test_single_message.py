#!/usr/bin/env python3
"""
单消息测试

给 iflow 发送一条消息，测试能否获取完整对话记录。
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


async def test_single_message():
    """测试单消息对话"""

    print("=" * 60)
    print("单消息测试")
    print("=" * 60)

    # 创建工具实例
    tool = IFlowInteractiveTool(config_path="config.json")

    # 测试消息
    test_message = "你好，请简单介绍一下你自己"

    try:
        # 启动工具
        await tool.start()

        print(f"\n{'=' * 60}")
        print(f"发送消息")
        print(f"{'=' * 60}")

        # 记录发送的消息
        sent_time = datetime.now()

        # 发送消息
        await tool.send_message(test_message)

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

        # 输出对话记录
        print("\n" + "=" * 60)
        print("对话记录")
        print("=" * 60)

        print(f"\n📤 发送消息 ({sent_time.isoformat()})")
        print(f"   {test_message}")

        print(f"\n📥 回复 ({received_time.isoformat()})")
        if replies:
            for i, reply in enumerate(replies, 1):
                print(f"\n   回复 {i} [{reply['type']}]:")
                print(f"   内容: {reply['content']}")
                if reply['metadata']:
                    print(f"   元数据: {reply['metadata']}")
        else:
            print("   无回复")

        print(f"\n   状态: {'✅ 完成' if completed else '❌ 未完成'}")

        # 统计信息
        print("\n" + "=" * 60)
        print("统计信息")
        print("=" * 60)

        print(f"收到回复总数: {len(replies)}")

        if completed and len(replies) > 0:
            print(f"\n✅ 收到回复")
            return 0
        else:
            print(f"\n❌ 没有收到回复")
            return 1

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 停止工具
        await tool.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(test_single_message()))