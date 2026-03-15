#!/usr/bin/env python3
"""
实时监控调试

实时查看监控器的行为
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
logger = logging.getLogger("debug_real_time")


async def main():
    """主函数"""
    print("=" * 60)
    print("实时监控调试")
    print("=" * 60)

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_realtime",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
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

    # 实时监控
    print("\n[5] 实时监控...")
    print("   时间     状态       候选数  提取数")
    print("   " + "-" * 45)
    
    start_time = asyncio.get_event_loop().time()
    
    for i in range(60):
        await asyncio.sleep(1)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        state = module.state.value
        
        # 获取监控器统计
        stats = module.monitor.get_stats()
        messages_extracted = stats.get("messages_extracted", 0)
        
        # 获取候选消息数
        candidate_count = len(module.monitor._candidate_messages)
        
        print(f"   {elapsed:5.1f}s   {state:10s}   {candidate_count:3d}    {messages_extracted:3d}", end='\r', flush=True)
        
        # 检查是否提取到消息
        if messages_extracted > 0:
            print(f"\n\n✅ 已提取 {messages_extracted} 条消息 (耗时 {elapsed:.1f}秒)")
            break
        
        # 检查状态是否变回 IDLE
        if state == "idle" and elapsed > 10:
            print(f"\n\n⚠️ 状态已变回 IDLE")
            break

    # 停止模块
    print("\n[6] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())