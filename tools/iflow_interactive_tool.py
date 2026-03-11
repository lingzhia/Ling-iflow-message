#!/usr/bin/env python3
"""
IFlowModule 交互式体验工具

模拟消息总线，手动测试 IFlowModule 的核心功能：
- 发送消息到 iflow
- 接收 iflow 的回复

使用方法：
    python tools/iflow_interactive_tool.py
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules import IFlowModule
from src.modules.iflow.controller import IFlowController
from src.core.message import Message, MessageType, MessageContent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("iflow_interactive")


class MockMessageBus:
    """模拟消息总线"""
    
    def __init__(self):
        self.messages_received = []  # 收到的消息（iflow 的回复）
    
    def register_module(self, module):
        """注册模块（模拟）"""
        pass
    
    def bind(self, from_module, to_module):
        """绑定模块（模拟）"""
        pass
    
    async def route(self, message: Message) -> bool:
        """路由消息（模拟）"""
        # 这里是 iflow 发出的回复
        self.messages_received.append(message)
        content = message.content.text if hasattr(message.content, 'text') else str(message.content)
        print(f"\n📤 收到 iflow 回复:")
        print(f"   {content[:200]}{'...' if len(content) > 200 else ''}")
        return True
    
    async def publish(self, topic: str, message: Message) -> bool:
        """发布消息（模拟）"""
        self.messages_received.append(message)
        content = message.content.text if hasattr(message.content, 'text') else str(message.content)
        print(f"\n📤 收到 iflow 广播 [{topic}]:")
        print(f"   {content[:200]}{'...' if len(content) > 200 else ''}")
        return True
    
    async def send_to_module(self, message: Message) -> bool:
        """发送消息到模块（模拟）"""
        return await self.route(message)


class IFlowInteractiveTool:
    """IFlowModule 交互式体验工具"""
    
    def __init__(self, tmux_session: str = "iflow"):
        self.tmux_session = tmux_session
        self.iflow_module: Optional[IFlowModule] = None
        self.mock_bus: Optional[MockMessageBus] = None
    
    async def start(self):
        """启动工具"""
        print("=" * 60)
        print("IFlowModule 交互式体验工具")
        print("=" * 60)
        print(f"tmux 会话: {self.tmux_session}")
        
        # 检查 tmux 会话是否存在
        print("\n检查 tmux 会话...")
        temp_controller = IFlowController(self.tmux_session)
        
        tmux_exists = await temp_controller.check_tmux_session()
        if not tmux_exists:
            print(f"❌ tmux 会话 '{self.tmux_session}' 不存在")
            print(f"   请先启动 iflow: tmux new-session -d -s {self.tmux_session} 'iflow'")
            sys.exit(1)
        
        iflow_running = await temp_controller.check_iflow_running()
        if not iflow_running:
            print(f"⚠️  iflow 未在 tmux 会话中运行")
            print(f"   请确保 iflow 已启动")
        else:
            print(f"✅ tmux 会话 '{self.tmux_session}' 存在，iflow 运行中")
        
        # 创建模拟消息总线
        self.mock_bus = MockMessageBus()
        
        # 创建 IFlowModule
        print("\n正在创建 IFlowModule...")
        self.iflow_module = IFlowModule(
            module_id="iflow_interactive",
            tmux_session=self.tmux_session,
            auto_start=False  # 假设 iflow 已在运行
        )
        
        # 设置消息总线
        self.iflow_module.set_message_bus(self.mock_bus)
        
        # 启动模块
        print("正在启动 IFlowModule...")
        await self.iflow_module.start()
        
        print("\n✅ IFlowModule 已启动")
        print("=" * 60)
    
    async def stop(self):
        """停止工具"""
        if self.iflow_module:
            print("\n正在停止 IFlowModule...")
            await self.iflow_module.stop()
            print("✅ IFlowModule 已停止")
    
    async def send_message(self, content: str):
        """发送消息到 iflow"""
        print(f"\n📥 发送消息到 iflow:")
        print(f"   {content}")
        
        # 创建消息
        message = Message(
            id=Message.generate_id(),
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text=content),
            from_module="user",
            to_module="iflow_interactive"
        )
        
        # 模拟消息总线调用 receive
        await self.iflow_module.receive(message)
        
        print("   ✅ 消息已发送到 iflow")
    
    async def wait_for_reply(self, timeout: float = 30.0):
        """等待 iflow 回复"""
        print(f"\n⏳ 等待 iflow 回复 (超时: {timeout}秒)...")
        
        initial_count = len(self.mock_bus.messages_received)
        elapsed = 0.0
        interval = 0.5
        
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval
            
            # 检查是否有新消息
            if len(self.mock_bus.messages_received) > initial_count:
                print(f"   ✅ 收到回复 (耗时: {elapsed:.1f}秒)")
                return True
            
            # 显示等待进度
            if int(elapsed) % 5 == 0 and elapsed > 0:
                print(f"   等待中... {int(elapsed)}秒")
        
        print(f"   ⚠️ 超时，未收到回复")
        return False
    
    async def interactive_loop(self):
        """交互式循环"""
        print("\n" + "=" * 60)
        print("交互模式")
        print("=" * 60)
        print("输入消息发送到 iflow，输入 'quit' 退出")
        print("=" * 60)
        
        while True:
            try:
                # 读取用户输入
                print()
                user_input = input("👤 你: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("退出交互模式...")
                    break
                
                # 发送消息
                await self.send_message(user_input)
                
                # 等待回复
                await self.wait_for_reply(timeout=60.0)
                
            except KeyboardInterrupt:
                print("\n收到中断信号，退出...")
                break
            except EOFError:
                print("\n退出...")
                break


async def main():
    """主函数"""
    # 支持命令行参数指定 tmux 会话
    tmux_session = "iflow"
    if len(sys.argv) > 1:
        tmux_session = sys.argv[1]
    
    tool = IFlowInteractiveTool(tmux_session)
    
    try:
        await tool.start()
        await tool.interactive_loop()
    finally:
        await tool.stop()


if __name__ == "__main__":
    asyncio.run(main())