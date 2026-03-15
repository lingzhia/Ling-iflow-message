#!/usr/bin/env python3
"""
监控监控器调用

查看监控器是否正确调用 _extract_messages 方法
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.modules.iflow.controller import IFlowController
from src.core.message import Message, MessageContent, MessageType as CoreMessageType

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("debug_monitor_calls")


async def main():
    """主函数"""
    print("=" * 60)
    print("监控监控器调用")
    print("=" * 60)

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_calls",
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

    # 等待生成完成
    print("\n[5] 等待生成完成...")
    for i in range(60):
        await asyncio.sleep(1)
        
        # 捕获输出
        output = await module.controller.capture_output(lines=200)
        
        # 手动提取消息
        messages = module.monitor._extract_messages(output)
        
        # 显示结果
        state = module.state.value
        has_generating = '生成中' in output
        has_marker = '✦' in output or '✻' in output
        
        print(f"  {i+1}s  状态: {state:10s}  生成中: {has_generating}  标记: {has_marker}  提取: {len(messages)}", end='\r', flush=True)
        
        # 如果提取到消息，显示它们
        if messages:
            print(f"\n\n✅ 提取到 {len(messages)} 条消息:")
            for j, msg in enumerate(messages):
                marker_type = msg.get('marker_type', '?')
                content = msg.get('content', '')
                print(f"  {j+1}. [{marker_type}] {content[:50]}...")
            break
        
        # 如果没有生成中且已等待足够时间，退出
        if not has_generating and i > 10:
            print(f"\n\n⚠️ 生成完成但未提取到消息")
            
            # 显示原始输出
            print("\n原始输出中包含标记的行:")
            lines = output.split('\n')
            for line in lines:
                if '✦' in line or '✻' in line:
                    print(f"  {line}")
            break

    # 停止模块
    print("\n[6] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())