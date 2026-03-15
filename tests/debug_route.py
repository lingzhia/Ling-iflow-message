#!/usr/bin/env python3
"""
调试 MockMessageBus.route()
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.core.message import Message, MessageContent, MessageType as CoreMessageType


class MockMessageBus:
    """模拟消息总线（用于测试）"""

    def __init__(self):
        self._iflow_module = None

    async def route(self, message: Message):
        """路由消息（直接调用 IFlowModule）
        
        注意：避免将来自 IFlowModule 的消息发送回 IFlowModule，防止循环
        """
        print(f"[MockMessageBus] 收到消息:")
        print(f"  id: {message.id}")
        print(f"  type: {message.type}")
        print(f"  content: {message.content.text}")
        print(f"  from_module: {message.from_module}")
        print(f"  metadata: {message.metadata}")
        
        if self._iflow_module:
            print(f"  _iflow_module.module_id: {self._iflow_module.module_id}")
            print(f"  from_module != module_id: {message.from_module != self._iflow_module.module_id}")
            
            if message.from_module != self._iflow_module.module_id:
                print(f"  调用 iflow_module.receive()...")
                await self._iflow_module.receive(message)
            else:
                print(f"  跳过：来自 IFlowModule 的消息")
        else:
            print(f"  跳过：_iflow_module 为 None")

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module


async def main():
    """主函数"""
    print("=" * 70)
    print("调试 MockMessageBus.route()")
    print("=" * 70)

    # 创建模块实例
    module = IFlowModule(
        tmux_session="iflow1",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )

    # 创建模拟消息总线
    mock_bus = MockMessageBus()
    
    # 设置模块和消息总线
    module.set_message_bus(mock_bus)
    mock_bus.set_iflow_module(module)

    try:
        # 启动模块
        print("\n[1] 启动模块...")
        await module.start()
        print(f"✅ 模块已启动")
        print(f"   module_id: {module.module_id}")

        # 等待 iflow 完全启动
        print("\n[2] 等待 iflow 完全启动...")
        await asyncio.sleep(5)
        print(f"✅ iflow 已就绪")

        # 检查 iflow 状态
        print(f"\n[3] 检查 iflow 状态:")
        print(f"   check_iflow_running: {await module.controller.check_iflow_running()}")
        print(f"   state: {module.state.value}")

        # 创建测试消息（模拟工具发送）
        print(f"\n[4] 创建测试消息:")
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text="哈哈哈"),
            from_module="tool",  # 来自工具
            metadata={"scope": "reply_only"}
        )
        print(f"   消息创建成功")

        # 通过模拟消息总线发送
        print(f"\n[5] 通过模拟消息总线发送:")
        await mock_bus.route(msg)
        print(f"✅ 路由完成")

        # 等待 10 秒
        print(f"\n[6] 等待 10 秒...")
        await asyncio.sleep(10)

        # 检查 tmux 输出
        print(f"\n[7] 检查 tmux 输出:")
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