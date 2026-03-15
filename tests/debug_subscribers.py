#!/usr/bin/env python3
"""
调试订阅者

检查模块是否正确订阅了监控器
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
logger = logging.getLogger("debug_subscribers")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试订阅者")
    print("=" * 60)

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_subscribers",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
    print(f"  module_id: {module.module_id}")

    # 检查订阅者
    print("\n[2] 检查订阅者...")
    print(f"   监控器订阅者数量: {len(module.monitor._subscribers)}")
    if module.monitor._subscribers:
        print(f"   订阅者: {module.monitor._subscribers}")
    else:
        print(f"   ⚠️ 没有订阅者！")

    # 启动模块
    print("\n[3] 启动模块...")
    await module.start()
    print("✅ 模块已启动")

    # 再次检查订阅者
    print("\n[4] 再次检查订阅者...")
    print(f"   监控器订阅者数量: {len(module.monitor._subscribers)}")
    if module.monitor._subscribers:
        print(f"   订阅者: {module.monitor._subscribers}")
    else:
        print(f"   ⚠️ 没有订阅者！")

    # 等待就绪
    print("\n[5] 等待 iflow 就绪...")
    ready = await module.wait_for_ready(timeout=60)
    if ready:
        print("✅ iflow 已就绪")
    else:
        print("⚠️ iflow 未就绪")
        await module.stop()
        return

    # 发送消息
    print("\n[6] 发送消息...")
    msg = Message(
        id=Message.generate_id(),
        type=CoreMessageType.TEXT,
        content=MessageContent(type=CoreMessageType.TEXT, text="请说 hello"),
        from_module="test",
        metadata={"scope": "reply_only"}
    )
    
    await module.receive(msg)
    print("✅ 消息已发送")

    # 等待生成完成
    print("\n[7] 等待生成完成...")
    for i in range(60):
        await asyncio.sleep(1)
        state = module.state.value
        
        if state == "idle" and i > 10:
            print(f"✅ 生成完成 (耗时 {i+1}秒)")
            break

    # 检查监控器统计
    stats = module.monitor.get_stats()
    print(f"\n[8] 监控器统计:")
    print(f"   提取消息数: {stats.get('messages_extracted', 0)}")
    print(f"   检查次数: {stats.get('check_count', 0)}")
    print(f"   状态变化: {stats.get('state_changes', 0)}")

    # 停止模块
    print("\n[9] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())
