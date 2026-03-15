#!/usr/bin/env python3
"""
测试发送消息"明天会更好"
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
logger = logging.getLogger("debug_test_message")


async def main():
    """主函数"""
    print("=" * 60)
    print("测试发送消息：明天会更好")
    print("=" * 60)

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="test_session",
        model="kimi-k2.5",
        workspace="~/.iflow"
    )

    # 启动模块
    print("\n[2] 启动模块...")
    try:
        await module.start()
        print("✅ 模块已启动")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return

    # 等待就绪
    print("\n[3] 等待 iflow 就绪...")
    ready = await module.wait_for_ready(timeout=60)
    if not ready:
        print("❌ iflow 未就绪")
        await module.stop()
        return
    print("✅ iflow 已就绪")

    # 订阅消息
    print("\n[4] 订阅消息...")
    messages = []
    
    async def on_message(message):
        messages.append(message)
        print(f"  收到消息: {message.type.value} - {message.content.text[:50]}...")
    
    module.subscribe(on_message)

    # 发送消息
    print("\n[5] 发送消息：明天会更好")
    response = await module.send("明天会更好", source="test", scope="all")
    
    if response.success:
        print("✅ 消息已发送")
    else:
        print(f"❌ 消息发送失败: {response.message}")
        await module.stop()
        return

    # 等待回复
    print("\n[6] 等待回复（最多 60 秒）...")
    import time
    start_time = time.time()
    
    while time.time() - start_time < 60:
        await asyncio.sleep(1)
        if messages:
            break
    
    # 显示结果
    print(f"\n[7] 结果:")
    print(f"  收到 {len(messages)} 条消息")
    
    for i, msg in enumerate(messages[:5], 1):
        print(f"  {i}. [{msg.type.value}] {msg.content.text[:80]}...")
    
    if messages:
        print("\n✅ 测试成功")
    else:
        print("\n⚠️ 未收到任何回复")

    # 停止模块
    print("\n[8] 停止模块...")
    await module.stop()
    print("✅ 已停止")


if __name__ == "__main__":
    asyncio.run(main())