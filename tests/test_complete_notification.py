#!/usr/bin/env python3
"""
结束通知功能测试

验证 iflow 生成结束后是否正确发送 COMPLETE 消息。
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.module import IFlowModule
from src.core.bus import MessageBus
from src.core.message import Message


async def test_complete_notification():
    """测试结束通知功能"""

    print("=" * 60)
    print("结束通知功能测试")
    print("=" * 60)

    # 创建消息总线
    bus = MessageBus()

    # 用于存储收到的消息
    received_messages = []

    async def bus_handler(message: Message):
        """处理消息总线上的消息"""
        received_messages.append({
            'id': message.id,
            'type': message.type.value,
            'content': message.content.text if message.content else "",
            'from_module': message.from_module,
            'metadata': message.metadata or {}
        })
        print(f"✅ 收到消息总线消息: {message.metadata.get('msg_type', 'unknown')}")

    # 订阅消息总线
    bus.subscribe("test_complete", bus_handler)

    # 创建 iflow 模块
    module = IFlowModule(
        module_id="test_complete",
        tmux_session="test_complete",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=False,
        log_interactions=False
    )

    # 清理监控器状态（防止之前的测试干扰）
    module.monitor._processed_hashes.clear()
    module.monitor._candidate_messages = []
    module.monitor._last_candidate_messages = []
    module.monitor._interaction_complete = False
    module.monitor._stable_start_time = None
    module.monitor._generating_state_started = False
    print("✅ 监控器状态已清理")

    # 设置消息总线
    module.message_bus = bus

    # 注册模块到消息总线
    bus.register_module(module)
    print("✅ 模块已注册到消息总线")

    # 用于存储订阅的消息
    subscribed_messages = []

    async def subscribe_handler(message):
        """处理订阅的消息"""
        subscribed_messages.append({
            'type': message.type.value,
            'content': message.content,
            'receiver': message.receiver,
            'scope': message.scope,
            'metadata': message.metadata
        })
        print(f"✅ 收到订阅消息: type={message.type.value}, content={message.content[:50]}...")

    # 订阅 iflow 输出
    module.subscribe(subscribe_handler)

    # 监控状态变更
    state_changes = []

    async def state_change_handler(old_state, new_state, duration=0):
        """处理状态变更"""
        state_changes.append({
            'old_state': old_state.value,
            'new_state': new_state.value,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        })
        print(f"🔄 状态变更: {old_state.value} -> {new_state.value}, duration={duration}s")

    # 设置状态变更回调
    module.monitor.set_state_change_callback(state_change_handler)
    print("✅ 状态变更回调已设置")

    try:
        # 启动模块
        print("\n🚀 启动 iflow 模块...")
        await module.start()
        print("✅ iflow 模块已启动")

        # 等待 iflow 准备好
        print("\n⏳ 等待 iflow 准备好...")
        await asyncio.sleep(3)

        # 发送测试消息
        test_message = "计算 1+1 等于几？只回复数字。"
        print(f"\n📤 发送测试消息: {test_message}")
        response = await module.send(
            content=test_message,
            source="test_complete",
            scope="reply_only"
        )

        if not response.success:
            print(f"❌ 消息发送失败: {response.error}")
            return

        print(f"✅ 消息已发送 (id={response.message_id})")

        # 等待生成结束
        print("\n⏳ 等待生成结束...")
        max_wait_time = 60  # 最多等待60秒
        wait_count = 0
        complete_found = False

        while wait_count < max_wait_time and not complete_found:
            await asyncio.sleep(1)
            wait_count += 1

            # 检查是否收到 COMPLETE 消息
            for msg in subscribed_messages:
                if msg['type'] == 'complete':
                    complete_found = True
                    print(f"✅ 检测到 COMPLETE 消息（耗时 {wait_count} 秒）")
                    break

            if wait_count % 5 == 0:
                print(f"   等待中... ({wait_count}s / {max_wait_time}s), 已收到 {len(subscribed_messages)} 条消息")
                # 打印监控器状态
                print(f"   监控器状态: state={module.monitor.state.value}, interaction_complete={module.monitor._interaction_complete}, candidates={len(module.monitor._candidate_messages)}")
                # 打印状态变更历史
                if state_changes:
                    print(f"   状态变更历史: {state_changes}")

        # 验证结果
        print("\n" + "=" * 60)
        print("验证结果")
        print("=" * 60)

        # 统计消息类型
        message_stats = {}
        for msg in subscribed_messages:
            msg_type = msg['type']
            if msg_type not in message_stats:
                message_stats[msg_type] = 0
            message_stats[msg_type] += 1

        print(f"\n📊 收到的消息统计:")
        for msg_type, count in message_stats.items():
            print(f"   - {msg_type}: {count} 条")

        # 检查是否有 COMPLETE 消息
        complete_messages = [msg for msg in subscribed_messages if msg['type'] == 'complete']
        print(f"\n🔍 COMPLETE 消息: {len(complete_messages)} 条")

        if len(complete_messages) > 0:
            print("✅ 结束通知功能正常工作！")

            # 显示 COMPLETE 消息详情
            for i, msg in enumerate(complete_messages, 1):
                print(f"\n📋 COMPLETE 消息 #{i}:")
                print(f"   内容: {msg['content']}")
                print(f"   接收方: {msg['receiver']}")
                print(f"   范围: {msg['scope']}")
                if msg['metadata']:
                    print(f"   元数据:")
                    for key, value in msg['metadata'].items():
                        print(f"     - {key}: {value}")
        else:
            print("❌ 未收到 COMPLETE 消息，结束通知功能可能有问题！")

        # 检查消息总线是否有 COMPLETE 消息
        bus_complete_messages = [msg for msg in received_messages if msg['metadata'].get('msg_type') == 'iflow_complete']
        print(f"\n🔍 消息总线 COMPLETE 消息: {len(bus_complete_messages)} 条")

        if len(bus_complete_messages) > 0:
            print("✅ COMPLETE 消息已发送到消息总线！")

            # 显示消息总线 COMPLETE 消息详情
            for i, msg in enumerate(bus_complete_messages, 1):
                print(f"\n📋 消息总线 COMPLETE 消息 #{i}:")
                print(f"   内容: {msg['content']}")
                print(f"   来源模块: {msg['from_module']}")
                if msg['metadata']:
                    print(f"   元数据:")
                    for key, value in msg['metadata'].items():
                        print(f"     - {key}: {value}")
        else:
            print("❌ 消息总线未收到 COMPLETE 消息！")

        # 显示所有收到的消息
        print(f"\n📝 所有收到的订阅消息 ({len(subscribed_messages)} 条):")
        for i, msg in enumerate(subscribed_messages, 1):
            print(f"   {i}. [{msg['type']}] {msg['content'][:60]}...")

        print(f"\n📝 所有收到的消息总线消息 ({len(received_messages)} 条):")
        for i, msg in enumerate(received_messages, 1):
            print(f"   {i}. [{msg['metadata'].get('msg_type', 'unknown')}] {msg['content'][:60]}...")

        # 最终结论
        print("\n" + "=" * 60)
        print("测试结论")
        print("=" * 60)

        if len(complete_messages) > 0 and len(bus_complete_messages) > 0:
            print("✅ 结束通知功能测试通过！")
            print("   - 订阅者收到 COMPLETE 消息")
            print("   - 消息总线收到 COMPLETE 消息")
            return True
        elif len(complete_messages) > 0:
            print("⚠️  结束通知功能部分正常")
            print("   - 订阅者收到 COMPLETE 消息")
            print("   - 消息总线未收到 COMPLETE 消息（需要修复）")
            return False
        else:
            print("❌ 结束通知功能测试失败！")
            print("   - 订阅者未收到 COMPLETE 消息")
            print("   - 消息总线未收到 COMPLETE 消息")
            return False

    finally:
        # 停止模块
        print("\n🛑 停止 iflow 模块...")
        await module.stop()
        print("✅ iflow 模块已停止")

        # 取消订阅
        bus.unsubscribe("test_complete", bus_handler)


async def main():
    """主函数"""
    success = await test_complete_notification()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
