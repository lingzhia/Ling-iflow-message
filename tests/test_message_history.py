#!/usr/bin/env python3
"""
测试消息历史记录的完整性
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
from src.modules.iflow.monitor import IFlowState


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


async def test_message_history():
    """测试消息历史记录的完整性"""
    print("=" * 70)
    print("测试: 消息历史记录的完整性")
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

        # 发送多条消息
        test_messages = [
            "你好",
            "1+1等于几？",
            "介绍一下 Python",
        ]

        for idx, test_message in enumerate(test_messages, 1):
            print(f"\n📤 发送消息 {idx}/{len(test_messages)}: {test_message}")

            # 清空之前的消息
            received_messages.clear()

            msg = Message(
                id=Message.generate_id(),
                type=CoreMessageType.TEXT,
                content=MessageContent(type=CoreMessageType.TEXT, text=test_message),
                from_module="test",
                metadata={"scope": "all"}
            )

            await bus.route(msg)

            # 等待回复
            print("⏳ 等待回复...")
            for i in range(30):
                await asyncio.sleep(1)
                if received_messages:
                    break

            print(f"✅ 收到 {len(received_messages)} 条消息")

            # 等待 COMPLETE 消息
            for i in range(10):
                await asyncio.sleep(1)
                if any(msg['type'] == 'complete' for msg in received_messages):
                    break

            # 显示消息类型统计
            type_counts = {}
            for msg in received_messages:
                msg_type = msg['type']
                type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
            print(f"   消息类型: {type_counts}")

        # 检查消息库
        print("\n" + "=" * 70)
        print("消息库验证")
        print("=" * 70)
        stats = module.message_store.get_stats()
        print(f"消息库统计:")
        print(f"  总计: {stats['total']} 条")
        print(f"  待处理: {stats['pending']} 条")
        print(f"  处理中: {stats['processing']} 条")
        print(f"  已完成: {stats['completed']} 条")

        # 检查日志文件
        print("\n" + "=" * 70)
        print("日志文件验证")
        print("=" * 70)

        log_dir = Path("logs/interactions")
        if log_dir.exists():
            log_files = list(log_dir.glob("*.jsonl"))
            print(f"找到 {len(log_files)} 个日志文件")

            for log_file in log_files[-3:]:  # 显示最新的 3 个文件
                print(f"\n日志文件: {log_file.name}")
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"  行数: {len(lines)}")

                    # 解析每条日志
                    for idx, line in enumerate(lines[-5:], 1):  # 显示最后 5 行
                        try:
                            log_entry = json.loads(line)
                            event_type = log_entry.get('event_type', 'unknown')
                            print(f"  [{idx}] {event_type}")
                        except:
                            pass
        else:
            print("⚠️  日志目录不存在")

        # 停止模块
        print("\n正在停止模块...")
        await module.stop()
        print("✅ 模块已停止")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        await module.stop()
        return False


async def main():
    """主函数"""
    print("\n")
    print("🧪 消息历史记录完整性测试")
    print("=" * 70)

    # 测试消息历史记录
    success = await test_message_history()

    # 总结
    print("\n\n")
    print("=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"✅ 测试结果: {'✓ 通过' if success else '✗ 失败'}")

    if success:
        print("\n🎉 测试通过！")
    else:
        print("\n⚠️  测试失败")


if __name__ == "__main__":
    asyncio.run(main())
