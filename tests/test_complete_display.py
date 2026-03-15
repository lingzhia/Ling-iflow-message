#!/usr/bin/env python3
"""
测试 COMPLETE 消息显示

验证 iflow_interactive_tool 是否能正确显示 COMPLETE 消息
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.core.message import Message, MessageContent, MessageType as CoreMessageType


async def test_complete_display():
    """测试 COMPLETE 消息显示"""

    print("=" * 60)
    print("测试 COMPLETE 消息显示")
    print("=" * 60)

    # 创建模块
    module = IFlowModule(
        module_id="test_complete_display",
        tmux_session="test_complete_display",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=False,
        log_interactions=False
    )

    # 用于存储收到的消息
    received_messages = []

    async def message_hook(message: Message):
        """接收消息的钩子"""
        reply_type = message.metadata.get('reply_type', 'unknown')
        msg_type = message.metadata.get('msg_type', 'unknown')
        
        received_messages.append({
            'reply_type': reply_type,
            'msg_type': msg_type,
            'content': message.content.text,
            'metadata': message.metadata
        })
        
        print(f"收到消息:")
        print(f"  reply_type: {reply_type}")
        print(f"  msg_type: {msg_type}")
        print(f"  content: {message.content.text[:80]}...")
        print(f"  metadata: {message.metadata}")

    # 设置钩子
    module.set_message_sent_hook(message_hook)

    try:
        # 启动模块
        print("\n🚀 启动模块...")
        await module.start()
        print("✅ 模块已启动")

        # 等待 iflow 准备好
        print("\n⏳ 等待 iflow 准备好...")
        await asyncio.sleep(3)

        # 发送测试消息
        test_message = "测试 COMPLETE 消息显示"
        print(f"\n📤 发送测试消息: {test_message}")
        
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=test_message),
            from_module="test_tool",
            metadata={"scope": "reply_only"}
        )
        
        await module.receive(msg)
        print("✅ 消息已发送")

        # 等待生成结束
        print("\n⏳ 等待生成结束...")
        max_wait_time = 60
        wait_count = 0
        complete_found = False

        while wait_count < max_wait_time and not complete_found:
            await asyncio.sleep(1)
            wait_count += 1

            # 检查是否收到 COMPLETE 消息
            for msg in received_messages:
                if msg['reply_type'] == 'complete':
                    complete_found = True
                    print(f"✅ 检测到 COMPLETE 消息（耗时 {wait_count} 秒）")
                    break

            if wait_count % 5 == 0:
                print(f"   等待中... ({wait_count}s / {max_wait_time}s), 已收到 {len(received_messages)} 条消息")

        # 验证结果
        print("\n" + "=" * 60)
        print("验证结果")
        print("=" * 60)

        # 统计消息类型
        message_stats = {}
        for msg in received_messages:
            reply_type = msg['reply_type']
            if reply_type not in message_stats:
                message_stats[reply_type] = 0
            message_stats[reply_type] += 1

        print(f"\n📊 收到的消息统计:")
        for msg_type, count in message_stats.items():
            print(f"   - {msg_type}: {count} 条")

        # 检查 COMPLETE 消息
        complete_messages = [msg for msg in received_messages if msg['reply_type'] == 'complete']
        print(f"\n🔍 COMPLETE 消息: {len(complete_messages)} 条")

        if len(complete_messages) > 0:
            print("✅ COMPLETE 消息显示功能正常工作！")

            # 显示 COMPLETE 消息详情
            for i, msg in enumerate(complete_messages, 1):
                print(f"\n📋 COMPLETE 消息 #{i}:")
                print(f"   reply_type: {msg['reply_type']}")
                print(f"   msg_type: {msg['msg_type']}")
                print(f"   content: {msg['content']}")
                if msg['metadata']:
                    print(f"   元数据:")
                    for key, value in msg['metadata'].items():
                        print(f"     - {key}: {value}")
        else:
            print("❌ 未收到 COMPLETE 消息")

        # 显示所有收到的消息
        print(f"\n📝 所有收到的消息 ({len(received_messages)} 条):")
        for i, msg in enumerate(received_messages, 1):
            print(f"   {i}. [{msg['reply_type']}] {msg['content'][:60]}...")

        # 最终结论
        print("\n" + "=" * 60)
        print("测试结论")
        print("=" * 60)

        if len(complete_messages) > 0:
            print("✅ COMPLETE 消息显示测试通过！")
            return True
        else:
            print("❌ COMPLETE 消息显示测试失败！")
            return False

    finally:
        # 停止模块
        print("\n🛑 停止模块...")
        await module.stop()
        print("✅ 模块已停止")


async def main():
    """主函数"""
    success = await test_complete_display()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)