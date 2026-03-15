#!/usr/bin/env python3
"""
调试命令行模式
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
    """简单消息总线"""
    def __init__(self):
        self._iflow_module = None
        self.message_count = 0

    async def route(self, message: Message):
        """路由消息"""
        self.message_count += 1
        print(f"[消息总线] 收到消息 #{self.message_count}: {message.content.text}")
        if self._iflow_module:
            try:
                print(f"[消息总线] 调用 iflow_module.receive()...")
                await self._iflow_module.receive(message)
                print(f"[消息总线] iflow_module.receive() 完成")
            except Exception as e:
                print(f"[消息总线] 调用失败: {e}")
                import traceback
                traceback.print_exc()

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module


async def main():
    """主函数"""
    print("=" * 70)
    print("调试命令行模式")
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
        print(f"[钩子] 收到消息 [{reply_type}]: {message.content.text[:50]}...")
        received_messages.append({
            "type": reply_type,
            "content": message.content.text,
        })

    module.set_message_sent_hook(message_hook)

    try:
        # 启动模块
        print("\n[1] 启动模块...")
        await module.start()
        print(f"✅ 模块已启动")

        # 等待 iflow 完全启动
        print("\n[2] 等待 iflow 完全启动...")
        await asyncio.sleep(5)
        print(f"✅ iflow 已就绪")

        # 发送测试消息（模拟工具的行为）
        test_message = "哈哈哈"
        print(f"\n[3] 创建消息: {test_message}")

        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=test_message),
            from_module="tool",
            metadata={"scope": "all"}
        )

        # 通过消息总线发送
        print(f"\n[4] 通过消息总线发送...")
        await bus.route(msg)
        print(f"✅ 消息已发送")

        # 等待回复
        print(f"\n[5] 等待回复...")
        for i in range(60):
            await asyncio.sleep(1)
            if received_messages:
                break
            if i % 10 == 0:
                print(f"   等待中... {i}s")

        print(f"✅ 收到 {len(received_messages)} 条消息")

        # 显示结果
        print("\n" + "=" * 70)
        print("收到的消息")
        print("=" * 70)
        for idx, msg in enumerate(received_messages, 1):
            print(f"[{idx}] {msg['type']}: {msg['content']}")

        # 检查 tmux 输出
        print("\n" + "=" * 70)
        print("tmux 输出（最后 20 行）")
        print("=" * 70)
        proc = await asyncio.create_subprocess_exec(
            "tmux", "capture-pane", "-t", "iflow1",
            "-S", "-20", "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        print(stdout.decode())

        # 停止模块
        print("\n停止模块...")
        await module.stop()
        print("✅ 模块已停止")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            await module.stop()
        except:
            pass
        return False


if __name__ == "__main__":
    asyncio.run(main())