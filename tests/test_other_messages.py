#!/usr/bin/env python3
"""
专门测试 OTHER 消息（✻ 思考消息）的收发和记录
"""
import sys
import os
import asyncio
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.core.message import Message, MessageContent, MessageType as CoreMessageType


class SimpleMessageBus:
    """简单消息总线（用于测试）"""
    def __init__(self):
        self._iflow_module = None
        self.received_messages = []

    async def route(self, message: Message):
        """路由消息"""
        if self._iflow_module:
            await self._iflow_module.receive(message)

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module


async def test_other_messages():
    """测试 OTHER 消息（✻ 思考消息）"""
    print("=" * 70)
    print("测试: OTHER 消息（✻ 思考消息）的收发和记录")
    print("=" * 70)

    # 创建消息总线
    bus = SimpleMessageBus()

    # 创建模块实例
    module = IFlowModule(
        tmux_session="iflow1",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )

    # 设置消息总线
    module.set_message_bus(bus)
    bus.set_iflow_module(module)

    # 设置钩子
    received_messages = []

    async def message_hook(message: Message):
        """消息钩子"""
        reply_type = message.metadata.get('reply_type', 'unknown')
        print(f"\n📥 收到消息 [{reply_type}]:")
        print(f"   内容: {message.content.text[:100]}...")
        print(f"   完整内容长度: {len(message.content.text)} 字符")
        print(f"   元数据: {json.dumps(message.metadata, ensure_ascii=False, indent=2)}")
        received_messages.append({
            "type": reply_type,
            "content": message.content.text,
            "metadata": message.metadata,
            "timestamp": datetime.now().isoformat()
        })

    module.set_message_sent_hook(message_hook)

    try:
        # 启动模块
        print("\n正在启动模块...")
        await module.start()
        print(f"✅ 模块已启动")

        await asyncio.sleep(3)

        # 发送一个需要思考的问题
        test_message = "详细解释一下量子力学的工作原理，包括薛定谔方程和波函数的概念"
        print(f"\n📤 发送消息: {test_message}")

        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=test_message),
            from_module="test",
            metadata={"scope": "all"}  # 使用 all 模式以接收思考消息
        )

        await bus.route(msg)
        print("✅ 消息已发送")

        # 等待回复（思考消息会先发送）
        print("\n⏳ 等待回复...")
        timeout = 120
        for i in range(timeout):
            await asyncio.sleep(1)
            if len(received_messages) >= 2:  # 期望至少收到 thinking + reply
                break

        # 显示结果
        print("\n" + "=" * 70)
        print("测试结果")
        print("=" * 70)
        print(f"✅ 收到 {len(received_messages)} 条消息")

        # 分类统计
        type_counts = {}
        for msg in received_messages:
            msg_type = msg['type']
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

        print(f"\n消息类型统计:")
        for msg_type, count in type_counts.items():
            print(f"  {msg_type}: {count} 条")

        for idx, msg in enumerate(received_messages, 1):
            print(f"\n消息 {idx}:")
            print(f"  类型: {msg['type']}")
            print(f"  内容: {msg['content'][:100]}...")
            print(f"  时间: {msg['timestamp']}")

        # 验证是否有 OTHER 消息
        has_other = any(msg['type'] == 'other' for msg in received_messages)
        has_complete = any(msg['type'] == 'complete' for msg in received_messages)
        has_reply = any(msg['type'] == 'reply' for msg in received_messages)

        print("\n" + "=" * 70)
        print("验证结果")
        print("=" * 70)
        print(f"✅ OTHER 消息（思考消息）: {'✓ 已收到' if has_other else '✗ 未收到'}")
        print(f"✅ REPLY 消息（回复消息）: {'✓ 已收到' if has_reply else '✗ 未收到'}")
        print(f"✅ COMPLETE 消息（完成通知）: {'✓ 已收到' if has_complete else '✗ 未收到'}")

        # 停止模块
        print("\n正在停止模块...")
        await module.stop()
        print("✅ 模块已停止")

        return received_messages, has_other, has_reply, has_complete

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        await module.stop()
        return [], False, False, False


async def main():
    """主函数"""
    print("\n")
    print("🧪 OTHER 消息（✻ 思考消息）专项测试")
    print("=" * 70)

    # 测试 OTHER 消息
    messages, has_other, has_reply, has_complete = await test_other_messages()

    # 总结
    print("\n\n")
    print("=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"✅ 总消息数: {len(messages)}")
    print(f"✅ OTHER 消息: {'✓ 通过' if has_other else '✗ 失败'}")
    print(f"✅ REPLY 消息: {'✓ 通过' if has_reply else '✗ 失败'}")
    print(f"✅ COMPLETE 消息: {'✓ 通过' if has_complete else '✗ 失败'}")

    all_passed = has_other and has_reply and has_complete
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试未通过")


if __name__ == "__main__":
    asyncio.run(main())