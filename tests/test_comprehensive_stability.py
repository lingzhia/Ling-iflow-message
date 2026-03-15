#!/usr/bin/env python3
"""
综合稳定性测试 - 运行所有测试多次
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

    async def route(self, message: Message):
        """路由消息"""
        if self._iflow_module:
            await self._iflow_module.receive(message)

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module


async def run_single_test(test_name: str, test_message: str, scope: str = "all") -> dict:
    """运行单次测试"""
    print(f"\n{'='*70}")
    print(f"测试: {test_name}")
    print(f"{'='*70}")

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
        })

    module.set_message_sent_hook(message_hook)

    try:
        # 启动模块
        await module.start()
        await asyncio.sleep(3)

        # 发送测试消息
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=test_message),
            from_module="test",
            metadata={"scope": scope}
        )

        await bus.route(msg)

        # 等待回复
        for i in range(60):
            await asyncio.sleep(1)
            if received_messages:
                break

        # 等待 COMPLETE 消息
        for i in range(10):
            await asyncio.sleep(1)
            if any(msg['type'] == 'complete' for msg in received_messages):
                break

        # 统计消息类型
        type_counts = {}
        for msg in received_messages:
            msg_type = msg['type']
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1

        # 停止模块
        await module.stop()

        return {
            "success": True,
            "message_count": len(received_messages),
            "type_counts": type_counts,
            "has_reply": type_counts.get('reply', 0) > 0,
            "has_other": type_counts.get('other', 0) > 0,
            "has_complete": type_counts.get('complete', 0) > 0,
        }

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        try:
            await module.stop()
        except:
            pass
        return {
            "success": False,
            "error": str(e)
        }


async def main():
    """主函数"""
    print("\n")
    print("🧪 综合稳定性测试")
    print("=" * 70)

    # 定义测试用例
    test_cases = [
        ("测试 1: 简单数学问题", "1+1等于几？只回复数字", "reply_only"),
        ("测试 2: 简单问候", "你好", "all"),
        ("测试 3: 简单问题", "介绍一下 Python", "all"),
        ("测试 4: 简单数学问题", "2+2等于几？只回复数字", "reply_only"),
        ("测试 5: 简单问候", "早上好", "all"),
    ]

    # 运行多次测试
    results = []

    for round_num in range(1, 3):  # 运行 2 轮
        print(f"\n\n{'#'*70}")
        print(f"第 {round_num} 轮测试")
        print(f"{'#'*70}")

        for test_name, test_message, scope in test_cases:
            result = await run_single_test(test_name, test_message, scope)
            result["round"] = round_num
            result["test_name"] = test_name
            results.append(result)

            if result["success"]:
                print(f"✅ {test_name}")
                print(f"   消息数量: {result['message_count']}")
                print(f"   消息类型: {result['type_counts']}")
                print(f"   REPLY: {'✓' if result['has_reply'] else '✗'}")
                print(f"   OTHER: {'✓' if result['has_other'] else '✗'}")
                print(f"   COMPLETE: {'✓' if result['has_complete'] else '✗'}")
            else:
                print(f"❌ {test_name}: {result['error']}")

            # 等待一下再进行下一个测试
            await asyncio.sleep(2)

    # 统计结果
    print("\n\n")
    print("=" * 70)
    print("测试总结")
    print("=" * 70)

    total_tests = len(results)
    success_tests = sum(1 for r in results if r["success"])
    failure_tests = total_tests - success_tests

    print(f"\n总测试数: {total_tests}")
    print(f"成功: {success_tests}")
    print(f"失败: {failure_tests}")
    print(f"成功率: {success_tests/total_tests*100:.1f}%")

    # 统计消息类型
    all_reply_tests = sum(1 for r in results if r["success"] and r["has_reply"])
    all_other_tests = sum(1 for r in results if r["success"] and r["has_other"])
    all_complete_tests = sum(1 for r in results if r["success"] and r["has_complete"])

    print(f"\n消息功能测试:")
    print(f"  REPLY 消息: {all_reply_tests}/{total_tests} ({all_reply_tests/total_tests*100:.1f}%)")
    print(f"  OTHER 消息: {all_other_tests}/{total_tests} ({all_other_tests/total_tests*100:.1f}%)")
    print(f"  COMPLETE 消息: {all_complete_tests}/{total_tests} ({all_complete_tests/total_tests*100:.1f}%)")

    # 详细结果
    print("\n详细结果:")
    for idx, result in enumerate(results, 1):
        status = "✅" if result["success"] else "❌"
        print(f"  [{idx}] {status} {result['test_name']} (第{result['round']}轮)")
        if result["success"]:
            print(f"      消息: {result['type_counts']}")

    # 最终结论
    print("\n" + "=" * 70)
    if success_tests == total_tests and all_reply_tests == total_tests and all_complete_tests == total_tests:
        print("🎉 所有测试通过！工具和 iflow 模块功能完全正常！")
    elif success_tests == total_tests:
        print("✅ 所有测试成功，但部分功能未达到预期")
    else:
        print("⚠️  部分测试失败，需要进一步检查")


if __name__ == "__main__":
    asyncio.run(main())