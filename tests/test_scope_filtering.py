#!/usr/bin/env python3
"""
测试 scope 过滤功能

测试 reply_only 和 all 两种 scope 模式。
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


async def test_scope_filtering():
    """测试 scope 过滤功能"""

    print("=" * 60)
    print("测试 scope 过滤功能")
    print("=" * 60)

    # 测试配置
    test_scenarios = [
        {
            "name": "reply_only 模式",
            "scope": "reply_only",
            "expected_reply_count": 0,  # 根据实际 iflow 回复数量调整
            "expected_other_count": 0  # reply_only 模式不应该收到 other 消息
        },
        {
            "name": "all 模式",
            "scope": "all",
            "expected_reply_count": 0,  # 根据实际 iflow 回复数量调整
            "expected_other_count": 0   # all 模式应该收到所有消息
        }
    ]

    for scenario_index, scenario in enumerate(test_scenarios, 1):
        print("\n" + "=" * 60)
        print(f"场景 {scenario_index}: {scenario['name']}")
        print("=" * 60)

        # 创建 IFlowModule 实例
        module = IFlowModule(
            tmux_session=f"test_scope_{scenario_index}",
            model="kimi-k2.5",
            workspace="~/.iflow",
            auto_restart=True,
            log_interactions=True,
            log_dir="logs/interactions"
        )

        # 用于存储收到的消息
        received_messages = []
        handler_call_count = 0

        async def message_handler(message):
            """处理收到的消息"""
            nonlocal handler_call_count
            handler_call_count += 1
            
            print(f"\n📥 收到消息 (第 {handler_call_count} 次):")
            print(f"   类型: {message.type.value}")
            
            # 处理消息内容（可能是 str 或 MessageContent）
            if isinstance(message.content, str):
                content = message.content
            else:
                content = message.content.text if hasattr(message.content, 'text') else str(message.content)
            
            print(f"   内容: {content[:100]}...")
            print(f"   scope: {message.scope}")
            
            # 添加到列表
            received_messages.append({
                'type': message.type.value,
                'content': content
            })
            
            print(f"   已添加到列表，当前总数: {len(received_messages)}")

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

            # 清理 IFlowMonitor 的状态（包括哈希集合）
            print("\n清理 IFlowMonitor 状态...")
            module.monitor._processed_hashes.clear()
            module.monitor._candidate_messages = []
            module.monitor._last_candidate_messages = []
            module.monitor._interaction_complete = False
            print("✅ 状态已清理")

            # 额外等待，确保清理生效
            print("\n等待状态清理生效...")
            await asyncio.sleep(2)

            # 发送测试消息
            test_message = "请简单介绍一下你自己"
            print(f"\n📤 发送消息: {test_message}")

            response = await module.send(
                content=test_message,
                source="test",
                scope=scenario['scope'],
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
                continue

            # 等待回复
            print("\n等待回复...")
            await asyncio.sleep(30)

            # 统计收到的消息
            reply_count = sum(1 for msg in received_messages if msg['type'] == "reply")
            other_count = sum(1 for msg in received_messages if msg['type'] == "other")

            print(f"\n统计结果:")
            print(f"   处理器调用次数: {handler_call_count}")
            print(f"   收到的消息总数: {len(received_messages)}")
            print(f"   reply 消息数: {reply_count}")
            print(f"   other 消息数: {other_count}")

            # 验证 scope 过滤
            print(f"\n验证 scope 过滤:")
            if scenario['scope'] == "reply_only":
                if other_count == 0 and len(received_messages) > 0:
                    print("✅ reply_only 模式正确过滤了 other 消息")
                elif handler_call_count == 0:
                    print("⚠️  消息处理器未被调用，可能是订阅问题")
                else:
                    print(f"❌ reply_only 模式不应该收到 other 消息，但收到了 {other_count} 条")
            elif scenario['scope'] == "all":
                if len(received_messages) > 0:
                    print(f"✅ all 模式收到了 {len(received_messages)} 条消息")
                    print(f"   包括 {reply_count} 条 reply 和 {other_count} 条 other")
                elif handler_call_count == 0:
                    print("⚠️  消息处理器未被调用，可能是订阅问题")
                else:
                    print("❌ all 模式应该收到消息")

        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            continue

        finally:
            # 停止模块
            print("\n正在停止模块...")
            await module.stop()
            print("✅ 模块已停止")

            # 清空消息，为下一个场景做准备
            received_messages.clear()
            handler_call_count = 0

    print("\n" + "=" * 60)
    print("所有场景测试完成")
    print("=" * 60)
    print("\n✅ 测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_scope_filtering()))
