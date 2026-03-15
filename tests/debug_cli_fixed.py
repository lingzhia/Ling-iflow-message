#!/usr/bin/env python3
"""
测试修复后的命令行模式
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


class MockMessageBus:
    """模拟消息总线（用于测试）"""

    def __init__(self):
        self._iflow_module = None
        self._message_callback = None  # 消息回调（用于接收来自 iflow 的消息）

    async def route(self, message: Message):
        """路由消息
        
        注意：避免将来自 IFlowModule 的消息发送回 IFlowModule，防止循环
        """
        if not self._iflow_module:
            return

        # 检查消息来源
        is_from_iflow = (message.from_module == self._iflow_module.module_id)

        if is_from_iflow:
            # 来自 iflow 的消息，通过回调处理
            if self._message_callback:
                try:
                    await self._message_callback(message)
                except Exception as e:
                    print(f"[MockMessageBus] 消息回调错误: {e}")
        else:
            # 来自其他模块的消息，发送到 iflow
            await self._iflow_module.receive(message)

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module

    def set_message_callback(self, callback):
        """设置消息回调（用于接收来自 iflow 的消息）"""
        self._message_callback = callback


async def main():
    """主函数"""
    print("=" * 70)
    print("测试修复后的命令行模式")
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
    
    # 消息历史
    message_history = []
    
    # 消息回调
    async def on_message(message: Message):
        """接收来自 iflow 的消息"""
        reply_type = message.metadata.get('reply_type', 'unknown')
        message_history.append({
            "type": reply_type,
            "content": message.content.text,
            "metadata": message.metadata
        })
        print(f"📥 收到消息 [{reply_type}]: {message.content.text[:50]}...")
    
    # 设置模块和消息总线
    module.set_message_bus(mock_bus)
    mock_bus.set_iflow_module(module)
    mock_bus.set_message_callback(on_message)

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

        # 发送消息（模拟命令行模式）
        print(f"\n[3] 发送消息: 哈哈哈")
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text="哈哈哈"),
            from_module="tool",
            metadata={"scope": "reply_only"}
        )
        await mock_bus.route(msg)
        print(f"✅ 消息已发送")

        # 等待回复完成（模拟 wait_for_complete）
        print(f"\n[4] 等待回复完成:")
        timeout = 60.0
        elapsed = 0.0
        check_interval = 1.0
        
        while elapsed < timeout:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            current_state = module.state
            message_count = len(message_history)
            
            print(f"   {elapsed}s: state={current_state.value}, messages={message_count}")
            
            # 检查是否完成
            if current_state == IFlowState.IDLE and message_count > 0:
                print(f"✅ 生成完成")
                break
        
        print(f"\n[5] 最终状态:")
        print(f"   state: {module.state.value}")
        print(f"   message_count: {len(message_history)}")
        
        print(f"\n[6] 收到的消息:")
        for i, msg in enumerate(message_history):
            print(f"   [{i+1}] {msg['type']}: {msg['content'][:50]}...")

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
