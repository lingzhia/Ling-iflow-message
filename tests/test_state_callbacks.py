#!/usr/bin/env python3
"""
测试状态变更回调

测试状态变更时的回调功能。
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


async def test_state_callbacks():
    """测试状态变更回调"""

    print("=" * 60)
    print("测试状态变更回调")
    print("=" * 60)

    # 创建 IFlowModule 实例
    module = IFlowModule(
        tmux_session="test_callbacks",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )

    # 用于存储状态变更
    state_changes = []

    def state_change_handler(old_state, new_state, duration=None):
        """处理状态变更"""
        change = {
            'old_state': old_state.value if old_state else None,
            'new_state': new_state.value,
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }
        state_changes.append(change)
        print(f"\n🔄 状态变更:")
        print(f"   {change['old_state']} -> {change['new_state']}")
        if duration is not None:
            print(f"   持续时间: {duration} 秒")
        print(f"   时间: {change['timestamp']}")

    # 设置状态变更回调
    module.set_state_change_callback(state_change_handler)

    # 用于存储收到的消息
    received_messages = []

    async def message_handler(message):
        """处理收到的消息"""
        print(f"\n📥 收到消息:")
        print(f"   类型: {message.type.value}")
        print(f"   内容: {message.content.text[:100]}...")
        received_messages.append(message)

    # 订阅消息
    module.subscribe(message_handler)

    try:
        # 启动模块
        print("\n正在启动模块...")
        await module.start()
        print(f"✅ 模块已启动")

        # 等待模块完全启动
        print("\n等待模块完全启动...")
        await asyncio.sleep(5)

        # 发送测试消息
        test_message = "请简单介绍一下你自己"
        print(f"\n📤 发送消息: {test_message}")

        response = await module.send(
            content=test_message,
            source="test",
            scope="reply_only",
            chat_id="test_chat",
            user_id="test_user",
            is_group=False
        )

        print(f"\n响应:")
        print(f"   success: {response.success}")
        print(f"   error: {response.error}")
        print(f"   message: {response.message}")

        if not response.success:
            print(f"❌ 消息发送失败: {response.error}")
            return 1

        # 等待回复完成
        print("\n等待回复完成...")
        await asyncio.sleep(30)

        # 验证状态变更
        print("\n" + "=" * 60)
        print("验证状态变更")
        print("=" * 60)

        print(f"\n状态变更次数: {len(state_changes)}")

        # 验证 IDLE -> GENERATING 状态变更
        idle_to_generating = [
            change for change in state_changes
            if change['old_state'] == 'idle' and change['new_state'] == 'generating'
        ]

        if len(idle_to_generating) > 0:
            print(f"✅ 检测到 IDLE -> GENERATING 状态变更（{len(idle_to_generating)} 次）")
        else:
            print("❌ 未检测到 IDLE -> GENERATING 状态变更")
            return 1

        # 验证 GENERATING -> IDLE 状态变更
        generating_to_idle = [
            change for change in state_changes
            if change['old_state'] == 'generating' and change['new_state'] == 'idle'
        ]

        if len(generating_to_idle) > 0:
            print(f"✅ 检测到 GENERATING -> IDLE 状态变更（{len(generating_to_idle)} 次）")
        else:
            print("❌ 未检测到 GENERATING -> IDLE 状态变更")
            return 1

        # 验证持续时间
        print("\n验证持续时间:")
        for i, change in enumerate(generating_to_idle, 1):
            if change['duration'] is not None and change['duration'] > 0:
                print(f"   状态变更 {i}: ✅ 持续时间 = {change['duration']} 秒")
            else:
                print(f"   状态变更 {i}: ❌ 持续时间无效 ({change['duration']})")
                return 1

        # 输出所有状态变更
        print("\n所有状态变更:")
        for i, change in enumerate(state_changes, 1):
            print(f"\n状态变更 {i}:")
            print(f"   {change['old_state']} -> {change['new_state']}")
            if change['duration'] is not None:
                print(f"   持续时间: {change['duration']} 秒")
            print(f"   时间: {change['timestamp']}")

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

    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)

    print(f"\n状态变更次数: {len(state_changes)}")
    print(f"收到消息总数: {len(received_messages)}")

    print("\n✅ 所有测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_state_callbacks()))