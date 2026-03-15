#!/usr/bin/env python3
"""
简单测试

直接测试 iflow 的启动和消息发送
"""

import sys
import os
import asyncio
import subprocess
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("debug_simple_test")


async def main():
    """主函数"""
    print("=" * 60)
    print("简单测试")
    print("=" * 60)

    # 清理残留的 tmux 会话
    print("\n[1] 清理残留的 tmux 会话...")
    result = subprocess.run(
        ["tmux", "kill-session", "-t", "iflow_simple"],
        capture_output=True
    )
    print(f"   kill-session 返回码: {result.returncode}")

    # 创建控制器
    print("\n[2] 创建控制器...")
    controller = IFlowController(tmux_session="iflow_simple")
    
    # 启动 iflow
    print("\n[3] 启动 iflow...")
    result = await controller.start_iflow(model="kimi-k2.5")
    print(f"   启动结果: {result}")

    # 等待就绪
    print("\n[4] 等待 iflow 就绪...")
    for i in range(30):
        await asyncio.sleep(1)
        is_ready = await controller.check_iflow_ready()
        print(f"   {i+1}s: is_ready={is_ready}")
        if is_ready:
            print(f"✅ iflow 已就绪 (耗时 {i+1}秒)")
            break
    else:
        print(f"⚠️ iflow 未就绪")
        await controller.destroy_session()
        return

    # 发送消息
    print("\n[5] 发送消息...")
    result = await controller.send_message("收到请回答")
    print(f"   发送结果: {result}")

    # 等待 5 秒
    print("\n[6] 等待 5 秒...")
    for i in range(5):
        await asyncio.sleep(1)
        print(f"   {i+1}s")

    # 捕获输出
    print("\n[7] 捕获输出...")
    try:
        output = await controller.capture_output(lines=50)
        print(f"   输出长度: {len(output)} 字符")
        
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
    except Exception as e:
        print(f"   ❌ 捕获输出失败: {e}")

    # 停止 iflow
    print("\n[8] 停止 iflow...")
    await controller.destroy_session()
    print("✅ iflow 已停止")


if __name__ == "__main__":
    asyncio.run(main())
