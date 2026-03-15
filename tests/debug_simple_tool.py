#!/usr/bin/env python3
"""
简化版工具测试

测试工具的基本功能，不使用超时
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

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("simple_tool")


class SimpleTool:
    """简化版工具"""

    def __init__(self):
        self.message_count = 0
        self.module = None

    async def on_message(self, message):
        """消息回调"""
        self.message_count += 1
        reply_type = message.metadata.get('reply_type', 'unknown')
        print(f"[收到消息 #{self.message_count}] type={reply_type}, content={message.content.text[:50]}...")

    async def test(self):
        """测试"""
        print("=" * 60)
        print("简化版工具测试")
        print("=" * 60)

        # 创建模块
        print("\n[1] 创建模块...")
        self.module = IFlowModule(
            tmux_session="iflow_simple",
            model="kimi-k2.5",
            workspace="~/.iflow",
            auto_restart=True,
            log_interactions=True,
            log_dir="logs/interactions"
        )
        
        # 设置消息钩子
        self.module.set_message_sent_hook(self.on_message)
        
        print(f"  module_id: {self.module.module_id}")

        # 启动模块
        print("\n[2] 启动模块...")
        await self.module.start()
        print("✅ 模块已启动")

        # 等待就绪
        print("\n[3] 等待 iflow 就绪...")
        ready = await self.module.wait_for_ready(timeout=60)
        if ready:
            print("✅ iflow 已就绪")
        else:
            print("⚠️ iflow 未就绪")
            return

        # 发送消息
        print("\n[4] 发送消息...")
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text="请说 hello"),
            from_module="test",
            metadata={"scope": "reply_only"}
        )
        
        await self.module.receive(msg)
        print("✅ 消息已发送")

        # 等待完成（不使用超时）
        print("\n[5] 等待完成...")
        start_time = asyncio.get_event_loop().time()
        
        while True:
            await asyncio.sleep(1)
            
            elapsed = asyncio.get_event_loop().time() - start_time
            state = self.module.state.value
            
            print(f"  {elapsed:5.1f}s  状态: {state:10s}  消息数: {self.message_count}", end='\r', flush=True)
            
            # 检查是否完成
            if state == "idle" and elapsed > 5 and self.message_count > 0:
                print(f"\n\n✅ 完成 (耗时 {elapsed:.1f}秒, 收到 {self.message_count} 条消息)")
                break
            
            # 超时保护
            if elapsed > 60:
                print(f"\n\n⚠️ 超时 (60秒)")
                break

        # 停止模块
        print("\n[6] 停止模块...")
        await self.module.stop()
        print("✅ 模块已停止")


async def main():
    """主函数"""
    tool = SimpleTool()
    try:
        await tool.test()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())