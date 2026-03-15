#!/usr/bin/env python3
"""
调试 tmux 会话

检查 tmux 会话状态
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
logger = logging.getLogger("debug_tmux_session")


async def main():
    """主函数"""
    print("=" * 60)
    print("调试 tmux 会话")
    print("=" * 60)

    # 创建控制器
    print("\n[1] 创建控制器...")
    controller = IFlowController(tmux_session="iflow_session")
    
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

    # 检查 tmux 会话
    print("\n[4] 检查 tmux 会话...")
    result = subprocess.run(
        ["tmux", "list-sessions"],
        check=True,
        capture_output=True,
        text=True
    )
    print(f"   所有 tmux 会话:")
    print(f"   {result.stdout}")

    # 检查目标会话
    print(f"\n[5] 检查目标会话 '{controller.tmux_session}'...")
    result = subprocess.run(
        ["tmux", "has-session", "-t", controller.tmux_session],
        capture_output=True,
        text=True
    )
    print(f"   has-session 返回码: {result.returncode}")
    if result.returncode == 0:
        print(f"   ✅ 会话存在")
    else:
        print(f"   ❌ 会话不存在")
        print(f"   stderr: {result.stderr}")

    # 捕获输出
    print(f"\n[6] 捕获输出...")
    output = await controller.capture_output(lines=50)
    print(f"   输出长度: {len(output)} 字符")
    print(f"   最后 10 行:")
    lines = output.split('\n')
    for line in lines[-10:]:
        print(f"     {line}")

    # 发送消息
    print(f"\n[7] 发送消息...")
    result = await controller.send_message("收到请回答")
    print(f"   发送结果: {result}")

    # 等待 2 秒
    await asyncio.sleep(2)

    # 捕获输出
    print(f"\n[8] 再次捕获输出...")
    output = await controller.capture_output(lines=50)
    
    # 查找包含消息的行
    lines = output.split('\n')
    message_lines = [line for line in lines if '收到请回答' in line]
    
    if message_lines:
        print(f"   ✅ iflow 收到消息:")
        for line in message_lines:
            print(f"     {line}")
    else:
        print(f"   ⚠️ iflow 未收到消息")
        print(f"   最后 10 行:")
        for line in lines[-10:]:
            print(f"     {line}")

    # 停止 iflow
    print("\n[9] 停止 iflow...")
    await controller.destroy_session()
    print("✅ iflow 已停止")


if __name__ == "__main__":
    asyncio.run(main())
