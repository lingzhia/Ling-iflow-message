#!/usr/bin/env python3
"""
调试监控器消息提取

测试监控器是否正确提取消息
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
logger = logging.getLogger("debug_monitor_messages")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试监控器消息提取")
    print("=" * 60)

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_monitor",
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

    # 监控监控器统计
    print("\n[5] 监控监控器统计...")
    print("   时间     状态       提取消息数  检查次数")
    print("   " + "-" * 55)
    
    start_time = asyncio.get_event_loop().time()
    
    for i in range(60):
        await asyncio.sleep(1)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        state = module.state.value
        
        # 获取监控器统计
        stats = module.monitor.get_stats()
        messages_extracted = stats.get("messages_extracted", 0)
        check_count = stats.get("check_count", 0)
        
        print(f"   {elapsed:5.1f}s   {state:10s}   {messages_extracted:3d}        {check_count:4d}", end='\r', flush=True)
        
        # 检查是否提取到消息
        if messages_extracted > 0:
            print(f"\n\n✅ 已提取 {messages_extracted} 条消息 (耗时 {elapsed:.1f}秒)")
            break
        
        # 检查状态是否变回 IDLE
        if state == "idle" and elapsed > 10:
            print(f"\n\n⚠️ 状态已变回 IDLE 但未提取到消息")
            break
        
        # 每 10 秒换行
        if i > 0 and i % 10 == 0:
            print()

    # 显示最终统计
    stats = module.monitor.get_stats()
    print(f"\n\n[6] 最终统计:")
    print(f"   状态: {module.state.value}")
    print(f"   提取消息数: {stats.get('messages_extracted', 0)}")
    print(f"   检查次数: {stats.get('check_count', 0)}")
    print(f"   状态变化: {stats.get('state_changes', 0)}")
    print(f"   候选消息数: {len(module.monitor._candidate_messages)}")
    print(f"   交互完成: {module.monitor._interaction_complete}")

    # 停止模块
    print("\n[7] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())