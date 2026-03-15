#!/usr/bin/env python3
"""
调试消息回调

测试消息回调是否被正确调用
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
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("debug_callback")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试消息回调")
    print("=" * 60)

    message_received = False
    received_messages = []

    async def on_message(message):
        """消息回调"""
        nonlocal message_received
        message_received = True
        received_messages.append(message)
        reply_type = message.metadata.get('reply_type', 'unknown')
        print(f"\n[回调被调用] type={reply_type}, content={message.content.text[:50]}...")

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_callback",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
    # 设置消息钩子
    module.set_message_sent_hook(on_message)
    print("✅ 消息钩子已设置")

    # 启动模块
    print("\n[2] 启动模块...")
    await module.start()
    print("✅ 模块已启动")

    # 等待就绪
    print("\n[3] 等待 iflow 就绪...")
    ready = await module.wait_for_ready(timeout=60)
    if ready:
        print("✅ iflow 已就绪")
    else:
        print("⚠️ iflow 未就绪")
        await module.stop()
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
    
    await module.receive(msg)
    print("✅ 消息已发送")

    # 等待消息
    print("\n[5] 等待消息回调...")
    start_time = asyncio.get_event_loop().time()
    
    while True:
        await asyncio.sleep(1)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        state = module.state.value
        
        print(f"  {elapsed:5.1f}s  状态: {state:10s}  收到消息: {message_received}", end='\r', flush=True)
        
        # 检查是否收到消息
        if message_received:
            print(f"\n\n✅ 收到消息 (耗时 {elapsed:.1f}秒)")
            print(f"   消息数: {len(received_messages)}")
            break
        
        # 检查状态是否变回 IDLE
        if state == "idle" and elapsed > 10:
            print(f"\n\n⚠️ 状态已变回 IDLE 但未收到消息")
            break
        
        # 超时保护
        if elapsed > 60:
            print(f"\n\n⚠️ 超时 (60秒)")
            break

    # 停止模块
    print("\n[6] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())
