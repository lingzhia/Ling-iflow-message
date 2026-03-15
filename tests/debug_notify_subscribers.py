#!/usr/bin/env python3
"""
调试 _notify_subscribers 方法

查看 _notify_subscribers 方法是否被正确调用
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
logger = logging.getLogger("debug_notify_subscribers")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试 _notify_subscribers 方法")
    print("=" * 60)

    notify_called = False
    notify_messages = []

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_notify",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
    # 保存原始方法
    original_notify = module.monitor._notify_subscribers
    
    # 包装方法
    async def wrapped_notify(message):
        nonlocal notify_called
        notify_called = True
        notify_messages.append(message)
        print(f"\n[_notify_subscribers 被调用] type={message.type.value}, content={message.content.text[:50]}...")
        # 调用原始方法
        await original_notify(message)
    
    # 替换方法
    module.monitor._notify_subscribers = wrapped_notify
    
    print(f"  module_id: {module.module_id}")

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
    print("\n[5] 等待 _notify_subscribers 被调用...")
    start_time = asyncio.get_event_loop().time()
    
    for i in range(60):
        await asyncio.sleep(1)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        state = module.state.value
        
        print(f"  {elapsed:5.1f}s  状态: {state:10s}  被调用: {notify_called}  消息数: {len(notify_messages)}", end='\r', flush=True)
        
        # 检查是否被调用
        if notify_called:
            print(f"\n\n✅ _notify_subscribers 被调用 (耗时 {elapsed:.1f}秒)")
            print(f"   收到 {len(notify_messages)} 条消息")
            break
        
        # 检查状态是否变回 IDLE
        if state == "idle" and elapsed > 10:
            print(f"\n\n⚠️ 状态已变回 IDLE 但 _notify_subscribers 未被调用")
            break

    # 显示监控器统计
    stats = module.monitor.get_stats()
    print(f"\n\n[6] 监控器统计:")
    print(f"   提取消息数: {stats.get('messages_extracted', 0)}")
    print(f"   检查次数: {stats.get('check_count', 0)}")
    print(f"   状态变化: {stats.get('state_changes', 0)}")

    # 停止模块
    print("\n[7] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())