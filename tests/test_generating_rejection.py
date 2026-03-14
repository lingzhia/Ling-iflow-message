#!/usr/bin/env python3
"""
测试生成中拒绝机制

测试在生成中状态时拒绝新消息的功能。
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.core.message import Message, MessageContent, MessageType as CoreMessageType


async def test_generating_rejection():
    """测试生成中拒绝机制"""

    print("=" * 60)
    print("测试生成中拒绝机制")
    print("=" * 60)

    # 创建 IFlowModule 实例
    module = IFlowModule(
        tmux_session="test_rejection",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )

    # 用于存储收到的消息
    received_messages = []

    async def message_handler(message):
        """处理收到的消息"""
        print(f"\n📥 收到消息:")
        print(f"   类型: {message.type.value}")
        print(f"   内容: {message.content.text}")
        received_messages.append(message)

    # 订阅消息
    module.subscribe(message_handler)

    # 用于存储状态变更
    state_changes = []

    # 状态变更回调（通过 IFlowMonitor）
    def state_change_handler(old_state, new_state, duration=None):
        """处理状态变更"""
        change = {
            'old_state': old_state.value if old_state else None,
            'new_state': new_state.value,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }
        state_changes.append(change)
        print(f"\n🔄 状态变更: {change['old_state']} -> {change['new_state']}")
        if duration:
            print(f"   持续时间: {duration} 秒")

    # 设置状态变更回调（通过 monitor）
    module.monitor.set_state_change_callback(state_change_handler)

    try:
        # 启动模块
        print("\n正在启动模块...")
        await module.start()
        print(f"✅ 模块已启动")

        # 等待模块完全启动
        print("\n等待模块完全启动...")
        await asyncio.sleep(5)

        # 第一条消息：让 iflow 进入生成中状态
        print("\n" + "=" * 60)
        print("步骤 1: 发送第一条消息（让 iflow 进入生成中状态）")
        print("=" * 60)

        message1 = "请详细介绍一下 Python 的历史和发展"
        print(f"\n📤 发送消息 1: {message1}")

        response1 = await module.send(
            content=message1,
            source="test",
            scope="reply_only",
            chat_id="test_chat",
            user_id="test_user",
            is_group=False
        )

        print(f"\n响应 1:")
        print(f"   success: {response1.success}")
        print(f"   error: {response1.error}")
        print(f"   message: {response1.message}")

        if not response1.success:
            print("❌ 第一条消息发送失败")
            return 1

        # 等待 iflow 进入生成中状态
        print("\n等待 iflow 进入生成中状态...")
        for i in range(10):
            await asyncio.sleep(1)
            if module.state.value == "generating":
                print(f"✅ iflow 已进入生成中状态（{i+1}秒）")
                break
        else:
            print("⚠️ iflow 未进入生成中状态，继续测试")

        # 等待几秒，让生成中状态持续一段时间
        await asyncio.sleep(3)

        # 第二条消息：在生成中状态时发送，应该被拒绝
        print("\n" + "=" * 60)
        print("步骤 2: 在生成中状态时发送第二条消息（应该被拒绝）")
        print("=" * 60)

        message2 = "这是第二条消息"
        print(f"\n📤 发送消息 2: {message2}")

        response2 = await module.send(
            content=message2,
            source="test",
            scope="reply_only",
            chat_id="test_chat",
            user_id="test_user",
            is_group=False
        )

        print(f"\n响应 2:")
        print(f"   success: {response2.success}")
        print(f"   error: {response2.error}")
        print(f"   message: {response2.message}")
        print(f"   duration: {response2.duration}")

        # 验证拒绝响应
        print("\n验证拒绝响应:")
        if not response2.success:
            print("✅ 消息被正确拒绝")
        else:
            print("❌ 消息应该被拒绝但没有")
            return 1

        if response2.error == "iflow_generating":
            print("✅ 错误类型正确")
        else:
            print(f"❌ 错误类型不正确: {response2.error}")
            return 1

        if "生成中" in response2.message:
            print("✅ 错误消息正确")
        else:
            print(f"❌ 错误消息不正确: {response2.message}")
            return 1

        if response2.duration is not None and response2.duration > 0:
            print(f"✅ 持续时间正确: {response2.duration} 秒")
        else:
            print(f"❌ 持续时间不正确: {response2.duration}")
            return 1

        # 等待第一条消息完成
        print("\n等待第一条消息完成...")
        await asyncio.sleep(30)

        # 第三条消息：在空闲状态时发送，应该成功
        print("\n" + "=" * 60)
        print("步骤 3: 在空闲状态时发送第三条消息（应该成功）")
        print("=" * 60)

        # 等待 iflow 变回空闲状态
        print("\n等待 iflow 变回空闲状态...")
        for i in range(30):
            await asyncio.sleep(1)
            if module.state.value == "idle":
                print(f"✅ iflow 已变回空闲状态（{i+1}秒）")
                break
        else:
            print("⚠️ iflow 未变回空闲状态，继续测试")

        message3 = "你好"
        print(f"\n📤 发送消息 3: {message3}")

        response3 = await module.send(
            content=message3,
            source="test",
            scope="reply_only",
            chat_id="test_chat",
            user_id="test_user",
            is_group=False
        )

        print(f"\n响应 3:")
        print(f"   success: {response3.success}")
        print(f"   error: {response3.error}")
        print(f"   message: {response3.message}")

        # 验证成功响应
        print("\n验证成功响应:")
        if response3.success:
            print("✅ 消息发送成功")
        else:
            print(f"❌ 消息应该成功但失败了: {response3.error}")
            return 1

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 停止模块
        print("\n\n正在停止模块...")
        await module.stop()
        print("✅ 模块已停止")

    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)

    print(f"\n状态变更次数: {len(state_changes)}")
    for i, change in enumerate(state_changes, 1):
        print(f"\n状态变更 {i}:")
        print(f"   {change['old_state']} -> {change['new_state']}")
        if change['duration']:
            print(f"   持续时间: {change['duration']} 秒")

    print(f"\n收到消息总数: {len(received_messages)}")

    print("\n✅ 所有测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_generating_rejection()))