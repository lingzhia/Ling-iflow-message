#!/usr/bin/env python3
"""
调试消息提取

直接测试 _extract_messages 方法
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
logger = logging.getLogger("debug_extract_messages")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试消息提取")
    print("=" * 60)

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_extract",
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
        state = module.state.value
        has_generating = '生成中' in (await module.controller.capture_output(lines=100))
        
        if not has_generating and i > 10:
            print(f"✅ 生成完成 (耗时 {i+1}秒)")
            break
    
    # 提取消息
    print("\n[6] 提取消息...")
    output = await module.controller.capture_output(lines=200)
    messages = module.monitor._extract_messages(output)
    
    print(f"✅ 提取到 {len(messages)} 条消息")
    
    # 显示消息
    if messages:
        print("\n消息内容:")
        for i, msg in enumerate(messages):
            marker_type = msg.get('marker_type', '?')
            content = msg.get('content', '')
            print(f"  {i+1}. [{marker_type}] {content}")
    else:
        print("\n未提取到任何消息")
        
        # 显示原始输出
        print("\n原始输出（最后 30 行）:")
        lines = output.split('\n')
        for line in lines[-30:]:
            if '✦' in line or '✻' in line:
                print(f"  ★ {line}")
            else:
                print(f"    {line}")

    # 停止模块
    print("\n[7] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())