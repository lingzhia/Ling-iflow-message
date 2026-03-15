#!/usr/bin/env python3
"""
调试工具超时问题

测试工具发送消息后，状态是否正确变回 IDLE
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

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.DEBUG,  # 显示所有日志
    format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger("debug_tool_timeout")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试工具超时问题")
    print("=" * 60)

    # 创建模块实例
    print("\n[1] 创建 IFlowModule 实例...")
    module = IFlowModule(
        tmux_session="iflow_debug",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
    print(f"  module_id: {module.module_id}")
    print(f"  tmux_session: {module.tmux_session}")

    # 启动模块
    print("\n[2] 启动模块...")
    try:
        await module.start()
        print(f"✅ 模块已启动")
        
        # 等待 iflow 完全就绪
        print("\n[3] 等待 iflow 完全就绪...")
        ready = await module.wait_for_ready(timeout=60)
        if not ready:
            print("⚠️ 警告：iflow 未在预期时间内完全就绪")
        else:
            print("✅ iflow 已完全就绪")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 发送消息
    print("\n[4] 发送消息...")
    from src.core.message import Message, MessageContent, MessageType as CoreMessageType
    
    msg = Message(
        id=Message.generate_id(),
        type=CoreMessageType.TEXT,
        content=MessageContent(type=CoreMessageType.TEXT, text="请数到 5"),
        from_module="test",
        metadata={"scope": "reply_only"}
    )
    
    await module.receive(msg)
    print("✅ 消息已发送")

    # 监控状态变化
    print("\n[5] 监控状态变化...")
    print("   时间     状态       消息数     生成时长")
    print("   " + "-" * 55)
    
    start_time = asyncio.get_event_loop().time()
    
    for i in range(120):
        await asyncio.sleep(1)
        
        current_time = asyncio.get_event_loop().time() - start_time
        current_state = module.state.value
        generating_duration = module.monitor.generating_duration
        
        # 获取消息统计
        message_count = module.monitor.stats.get("messages_extracted", 0)
        
        print(f"   {current_time:6.1f}s   {current_state:10s}   {message_count:3d}        {generating_duration:6.1f}s", end='\r', flush=True)
        
        # 检查状态是否变回 IDLE
        if module.state == IFlowState.IDLE and current_time > 5:
            print(f"\n\n✅ 状态已变回 IDLE (耗时 {current_time:.1f}秒)")
            break
        
        # 每 10 秒换行，避免覆盖
        if i > 0 and i % 10 == 0:
            print()
    
    print(f"\n\n[6] 最终状态:")
    print(f"   状态: {module.state.value}")
    print(f"   生成时长: {module.monitor.generating_duration:.1f}秒")
    print(f"   消息数: {module.monitor.stats.get('messages_extracted', 0)}")
    print(f"   交互完成: {module.monitor._interaction_complete}")

    # 停止模块
    print("\n[7] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())
