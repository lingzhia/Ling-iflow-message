#!/usr/bin/env python3
"""
简化版工具测试脚本
"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.core.message import Message, MessageContent, MessageType as CoreMessageType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

async def test_command_line():
    """测试命令行模式"""
    print("=" * 60)
    print("命令行模式测试")
    print("=" * 60)
    
    # 创建模块
    print("\n1. 创建 IFlowModule")
    iflow = IFlowModule(
        tmux_session='iflow_test',
        model='kimi-k2.5'
    )
    
    # 启动模块
    print("2. 启动模块")
    await iflow.start()
    
    # 等待 2 秒
    await asyncio.sleep(2)
    
    # 发送消息
    print("3. 发送消息")
    msg = Message(
        id=Message.generate_id(),
        type=CoreMessageType.TEXT,
        content=MessageContent(type=CoreMessageType.TEXT, text="命令行模式测试消息"),
        from_module='test',
        metadata={"scope": "reply_only"}
    )
    
    await iflow.receive(msg)
    
    # 等待 20 秒
    print("4. 等待回复（20秒）")
    for i in range(20):
        await asyncio.sleep(1)
        if i % 5 == 0:
            print(f"   已等待 {i} 秒，状态: {iflow.state.value}")
    
    # 查看状态
    print("\n5. 查看状态")
    status = await iflow.get_status()
    print(f"   状态: {status['iflow_state']}")
    print(f"   监控统计: {status['monitor_stats']}")
    
    # 停止模块
    print("\n6. 停止模块")
    await iflow.stop()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_command_line())