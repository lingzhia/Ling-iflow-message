#!/usr/bin/env python3
"""
调试 _on_receive 方法

查看 _on_receive 方法是否被正确调用
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
logger = logging.getLogger("debug_on_receive")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试 _on_receive 方法")
    print("=" * 60)

    on_receive_called = False

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_on_receive",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
    # 保存原始方法
    original_on_receive = module._on_receive
    
    # 包装方法
    async def wrapped_on_receive(message):
        nonlocal on_receive_called
        on_receive_called = True
        print(f"\n[_on_receive 被调用] content={message.content.text}")
        # 调用原始方法
        await original_on_receive(message)
    
    # 替换方法
    module._on_receive = wrapped_on_receive
    
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
        metadata={"scope": "all"}
    )
    
    await module.receive(msg)
    print("✅ 消息已发送")

    # 等待 2 秒
    await asyncio.sleep(2)

    # 检查 iflow 是否收到消息
    print("\n[5] 检查 iflow 是否收到消息...")
    output = await module.controller.capture_output(lines=50)
    
    # 查找包含消息的行
    lines = output.split('\n')
    message_lines = [line for line in lines if '请说 hello' in line]
    
    if message_lines:
        print(f"✅ iflow 收到消息:")
        for line in message_lines:
            print(f"   {line}")
    else:
        print(f"⚠️ iflow 未收到消息")

    # 停止模块
    print("\n[6] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())