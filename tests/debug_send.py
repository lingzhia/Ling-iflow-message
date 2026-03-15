#!/usr/bin/env python3
"""
调试消息发送问题
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.modules.iflow.monitor import IFlowState
from src.core.message import Message, MessageContent, MessageType as CoreMessageType


class SimpleMessageBus:
    """简单消息总线"""
    def __init__(self):
        self._iflow_module = None

    async def route(self, message: Message):
        """路由消息"""
        if self._iflow_module:
            await self._iflow_module.receive(message)

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module


async def debug_send():
    """调试消息发送"""
    print("=" * 70)
    print("调试消息发送")
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
        print(f"📥 收到消息 [{reply_type}]: {message.content.text[:50]}...")
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
        print(f"   module_id: {module.module_id}")
        print(f"   tmux_session: {module.tmux_session}")
        print(f"   状态: {module.state.value}")

        # 等待 iflow 完全启动
        print("\n[2] 等待 iflow 完全启动...")
        for i in range(35):
            await asyncio.sleep(1)
            if module.state != IFlowState.GENERATING:
                break
            if i % 5 == 0:
                print(f"   等待中... {i}s")

        print(f"✅ iflow 已就绪")
        print(f"   状态: {module.state.value}")

        # 再等待 3 秒确保 iflow 完全准备好
        print("\n[3] 额外等待 3 秒确保 iflow 完全准备好...")
        await asyncio.sleep(3)

        # 发送测试消息
        test_message = "哈哈哈"
        print(f"\n[4] 发送测试消息: {test_message}")

        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=test_message),
            from_module="test",
            metadata={"scope": "all"}
        )

        # 调用 _on_receive
        print("\n[5] 调用 _on_receive...")
        await module._on_receive(msg)
        print("✅ _on_receive 调用完成")

        # 等待回复
        print("\n[6] 等待回复...")
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
        print("tmux 输出")
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


async def main():
    """主函数"""
    success = await debug_send()
    print("\n" + "=" * 70)
    if success:
        print("✅ 调试完成")
    else:
        print("❌ 调试失败")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())