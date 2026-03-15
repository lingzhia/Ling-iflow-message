#!/usr/bin/env python3
"""
调试消息路由

检查消息是否被正确路由到 iflow
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
logger = logging.getLogger("debug_message_route")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试消息路由")
    print("=" * 60)

    receive_called = False

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_route",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
    print(f"  创建时的 module_id: {module.module_id}")
    
    # 保存原始 receive 方法
    original_receive = module.receive
    
    # 包装 receive 方法
    async def wrapped_receive(message):
        nonlocal receive_called
        receive_called = True
        print(f"\n[receive 被调用] module_id={module.module_id}, message.content={message.content.text}, from_module={message.from_module}")
        # 调用原始方法
        await original_receive(message)
    
    # 替换 receive 方法
    module.receive = wrapped_receive
    
    print(f"  module_id: {module.module_id}")

    # 启动模块
    print("\n[2] 启动模块...")
    await module.start()
    print(f"✅ 模块已启动")
    print(f"   启动后的 module_id: {module.module_id}")

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
        content=MessageContent(type=CoreMessageType.TEXT, text="收到请回答"),
        from_module="tool",
        metadata={"scope": "all"}
    )
    
    print(f"   消息 from_module: {msg.from_module}")
    print(f"   模块 module_id: {module.module_id}")
    
    await module.receive(msg)
    print("✅ 消息已发送")

    # 等待 2 秒
    await asyncio.sleep(2)

    # 检查 iflow 是否收到消息
    print("\n[5] 检查 iflow 是否收到消息...")
    output = await module.controller.capture_output(lines=50)
    
    # 查找包含消息的行
    lines = output.split('\n')
    message_lines = [line for line in lines if '收到请回答' in line]
    
    if message_lines:
        print(f"✅ iflow 收到消息:")
        for line in message_lines:
            print(f"   {line}")
    else:
        print(f"⚠️ iflow 未收到消息")
        print(f"   iflow 输出最后 10 行:")
        for line in lines[-10:]:
            print(f"     {line}")

    # 停止模块
    print("\n[6] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())