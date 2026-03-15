#!/usr/bin/env python3
"""
测试工具消息与 tmux 输出的一致性
"""
import sys
import os
import asyncio
import json
import re
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


async def capture_tmux_output(tmux_session: str, lines: int = 1000) -> str:
    """捕获 tmux 输出"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "tmux", "capture-pane", "-t", tmux_session,
            "-S", f"-{lines}", "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode == 0:
            return stdout.decode()
        else:
            return ""
    except Exception as e:
        print(f"捕获 tmux 输出失败: {e}")
        return ""


def extract_messages_from_tmux(output: str) -> list:
    """从 tmux 输出中提取消息"""
    messages = []

    # 提取 ✦ 消息（回复消息）
    # 匹配 "✦ " 开头的行
    reply_pattern = r'✦\s+(.*)'
    reply_matches = re.findall(reply_pattern, output)
    for match in reply_matches:
        content = match.strip()
        if content and content != '✦':  # 排除空行
            messages.append({
                "type": "reply",
                "content": content
            })

    # 提取 ✻ 消息（思考消息）
    # 匹配 "✻ " 开头的行
    other_pattern = r'✻\s+(.*)'
    other_matches = re.findall(other_pattern, output)
    for match in other_matches:
        content = match.strip()
        if content and content != '✻':  # 排除空行
            messages.append({
                "type": "other",
                "content": content
            })

    return messages


async def test_tmux_consistency():
    """测试工具消息与 tmux 输出的一致性"""
    print("=" * 70)
    print("测试: 工具消息与 tmux 输出的一致性")
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

        # 发送测试消息
        test_message = "1+1等于几？只回复数字"
        print(f"\n📤 发送消息: {test_message}")

        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=test_message),
            from_module="test",
            metadata={"scope": "all"}
        )

        await bus.route(msg)
        print("✅ 消息已发送")

        # 等待回复
        print("\n⏳ 等待回复...")
        timeout = 60
        for i in range(timeout):
            await asyncio.sleep(1)
            if received_messages:
                break

            # 检查是否收到 COMPLETE 消息
            if any(msg['type'] == 'complete' for msg in received_messages):
                break

        # 捕获 tmux 输出
        print("\n📋 捕获 tmux 输出...")
        tmux_output = await capture_tmux_output("iflow1", 500)
        print(f"✅ tmux 输出长度: {len(tmux_output)} 字符")

        # 显示 tmux 输出的最后 20 行
        print("\n📄 tmux 输出（最后 20 行）:")
        print("-" * 70)
        lines = tmux_output.split('\n')
        for line in lines[-20:]:
            print(line)
        print("-" * 70)

        # 从 tmux 输出中提取消息
        print("\n🔍 分析 tmux 输出...")
        tmux_messages = extract_messages_from_tmux(tmux_output)
        print(f"✅ 从 tmux 提取到 {len(tmux_messages)} 条消息")

        # 显示结果
        print("\n" + "=" * 70)
        print("工具收到的消息")
        print("=" * 70)
        for idx, msg in enumerate(received_messages, 1):
            print(f"\n[{idx}] {msg['type']}: {msg['content'][:80]}...")

        print("\n" + "=" * 70)
        print("tmux 输出中的消息")
        print("=" * 70)
        for idx, msg in enumerate(tmux_messages, 1):
            print(f"\n[{idx}] {msg['type']}: {msg['content'][:80]}...")

        # 对比分析
        print("\n" + "=" * 70)
        print("一致性验证")
        print("=" * 70)

        # 统计工具收到的消息类型
        tool_type_counts = {}
        for msg in received_messages:
            msg_type = msg['type']
            tool_type_counts[msg_type] = tool_type_counts.get(msg_type, 0) + 1

        # 统计 tmux 输出中的消息类型
        tmux_type_counts = {}
        for msg in tmux_messages:
            msg_type = msg['type']
            tmux_type_counts[msg_type] = tmux_type_counts.get(msg_type, 0) + 1

        print(f"\n工具消息统计:")
        for msg_type, count in tool_type_counts.items():
            print(f"  {msg_type}: {count} 条")

        print(f"\ntmux 消息统计:")
        for msg_type, count in tmux_type_counts.items():
            print(f"  {msg_type}: {count} 条")

        # 检查一致性
        print("\n" + "=" * 70)
        print("验证结果")
        print("=" * 70)

        # 检查 REPLY 消息一致性
        tool_reply_count = tool_type_counts.get('reply', 0)
        tmux_reply_count = tmux_type_counts.get('reply', 0)

        if tool_reply_count > 0:
            print(f"✅ REPLY 消息: 工具收到 {tool_reply_count} 条，tmux 有 {tmux_reply_count} 条")
            print(f"   状态: {'✓ 一致' if tool_reply_count == tmux_reply_count else '✗ 不一致'}")
        else:
            print(f"✗ REPLY 消息: 工具未收到")

        # 检查 OTHER 消息一致性
        tool_other_count = tool_type_counts.get('other', 0)
        tmux_other_count = tmux_type_counts.get('other', 0)

        if tool_other_count > 0:
            print(f"✅ OTHER 消息: 工具收到 {tool_other_count} 条，tmux 有 {tmux_other_count} 条")
            print(f"   状态: {'✓ 一致' if tool_other_count == tmux_other_count else '✗ 不一致'}")
        else:
            print(f"⚠️  OTHER 消息: 工具未收到（可能因为 scope 设置）")

        # 检查 COMPLETE 消息
        tool_complete_count = tool_type_counts.get('complete', 0)
        if tool_complete_count > 0:
            print(f"✅ COMPLETE 消息: 工具收到 {tool_complete_count} 条")
            print(f"   状态: ✓ 正常（COMPLETE 消息由工具生成，不在 tmux 输出中）")
        else:
            print(f"✗ COMPLETE 消息: 工具未收到")

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
    print("🧪 工具消息与 tmux 输出一致性测试")
    print("=" * 70)

    # 测试一致性
    success = await test_tmux_consistency()

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