#!/usr/bin/env python3
"""
调试 tmux send-keys

测试 tmux send-keys 命令是否工作
"""

import sys
import os
import asyncio
import subprocess
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.modules.iflow.controller import IFlowController

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("debug_tmux_send")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试 tmux send-keys")
    print("=" * 60)

    # 创建控制器
    print("\n[1] 创建控制器...")
    controller = IFlowController(tmux_session="iflow_tmux_send")
    
    # 启动 iflow
    print("\n[2] 启动 iflow...")
    await controller.start_iflow(model="kimi-k2.5")
    print("✅ iflow 已启动")

    # 等待就绪
    print("\n[3] 等待 iflow 就绪...")
    for i in range(30):
        await asyncio.sleep(1)
        if await controller.check_iflow_ready():
            print(f"✅ iflow 已就绪 (耗时 {i+1}秒)")
            break

    # 直接使用 tmux send-keys 发送消息
    print("\n[4] 直接使用 tmux send-keys 发送消息...")
    
    # 方法 1：使用 controller.send_message
    print("   方法 1：使用 controller.send_message...")
    result1 = await controller.send_message("请说 hello")
    print(f"   结果: {result1}")
    
    # 等待 2 秒
    await asyncio.sleep(2)
    
    # 检查 iflow 是否收到消息
    output = await controller.capture_output(lines=50)
    lines = output.split('\n')
    message_lines = [line for line in lines if '请说 hello' in line]
    
    if message_lines:
        print(f"   ✅ iflow 收到消息 (方法 1)")
        for line in message_lines:
            print(f"     {line}")
    else:
        print(f"   ⚠️ iflow 未收到消息 (方法 1)")
    
    # 方法 2：直接使用 subprocess
    print("\n   方法 2：直接使用 subprocess...")
    result = subprocess.run(
        ["tmux", "send-keys", "-t", controller.tmux_session, "请说 hello", "C-m"],
        check=True,
        capture_output=True,
        text=True
    )
    print(f"   subprocess 返回码: {result.returncode}")
    
    # 等待 2 秒
    await asyncio.sleep(2)
    
    # 检查 iflow 是否收到消息
    output = await controller.capture_output(lines=50)
    lines = output.split('\n')
    message_lines = [line for line in lines if '请说 hello' in line]
    
    if message_lines:
        print(f"   ✅ iflow 收到消息 (方法 2)")
        for line in message_lines:
            print(f"     {line}")
    else:
        print(f"   ⚠️ iflow 未收到消息 (方法 2)")

    # 停止 iflow
    print("\n[5] 停止 iflow...")
    await controller.destroy_session()
    print("✅ iflow 已停止")


if __name__ == "__main__":
    asyncio.run(main())