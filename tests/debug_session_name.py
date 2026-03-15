#!/usr/bin/env python3
"""
调试会话名称

检查模块的会话名称是否一致
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
logger = logging.getLogger("debug_session_name")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试会话名称")
    print("=" * 60)

    # 创建模块
    print("\n[1] 创建模块...")
    module = IFlowModule(
        tmux_session="iflow_name",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )
    
    print(f"   tmux_session: {module.tmux_session}")
    print(f"   module_id: {module.module_id}")

    # 启动模块
    print("\n[2] 启动模块...")
    await module.start()
    print("✅ 模块已启动")
    print(f"   tmux_session: {module.tmux_session}")
    print(f"   module_id: {module.module_id}")
    print(f"   controller.tmux_session: {module.controller.tmux_session}")

    # 等待就绪
    print("\n[3] 等待 iflow 就绪...")
    ready = await module.wait_for_ready(timeout=60)
    if ready:
        print("✅ iflow 已就绪")
    else:
        print("⚠️ iflow 未就绪")
        await module.stop()
        return

    # 检查 tmux 会话
    print("\n[4] 检查 tmux 会话...")
    output = await module.controller.capture_output(lines=10)
    print(f"   输出长度: {len(output)} 字符")
    if output:
        print(f"   ✅ 可以捕获输出")
    else:
        print(f"   ❌ 无法捕获输出")

    # 直接使用 controller 发送消息
    print("\n[5] 直接使用 controller 发送消息...")
    result = await module.controller.send_message("收到请回答")
    print(f"   发送结果: {result}")

    # 等待 2 秒
    await asyncio.sleep(2)

    # 检查 iflow 是否收到消息
    print("\n[6] 检查 iflow 是否收到消息...")
    output = await module.controller.capture_output(lines=50)
    
    # 查找包含消息的行
    lines = output.split('\n')
    message_lines = [line for line in lines if '收到请回答' in line]
    
    if message_lines:
        print(f"   ✅ iflow 收到消息 (直接使用 controller):")
        for line in message_lines:
            print(f"     {line}")
    else:
        print(f"   ⚠️ iflow 未收到消息 (直接使用 controller)")

    # 停止模块
    print("\n[7] 停止模块...")
    await module.stop()
    print("✅ 模块已停止")


if __name__ == "__main__":
    asyncio.run(main())
