#!/usr/bin/env python3
"""
捕获 tmux 原始输出

查看 iflow 的实际输出，看看是否有消息标记
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
logger = logging.getLogger("debug_capture_output")


async def main():
    """主函数"""
    print("=" * 60)
    print("捕获 tmux 原始输出")
    print("=" * 60)

    # 创建控制器
    print("\n[1] 创建控制器...")
    controller = IFlowController(tmux_session="iflow_capture")
    
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

    # 发送消息
    print("\n[4] 发送消息...")
    await controller.send_message("请说 hello")
    print("✅ 消息已发送")

    # 等待生成完成
    print("\n[5] 等待生成完成...")
    for i in range(60):
        await asyncio.sleep(1)
        output = await controller.capture_output(lines=100)
        
        # 检查是否有消息标记
        has_marker = '✦' in output or '✻' in output
        has_generating = '生成中' in output
        
        print(f"  {i+1}s  标记: {has_marker}  生成中: {has_generating}", end='\r', flush=True)
        
        if not has_generating and i > 10:
            print(f"\n\n✅ 生成完成 (耗时 {i+1}秒)")
            break

    # 捕获最终输出
    print("\n[6] 捕获最终输出...")
    output = await controller.capture_output(lines=200)
    
    # 保存到文件
    output_file = "/tmp/iflow_output.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)
    print(f"✅ 输出已保存到 {output_file}")
    
    # 显示关键部分
    print("\n[7] 显示关键部分...")
    lines = output.split('\n')
    
    # 查找包含标记的行
    marker_lines = [line for line in lines if '✦' in line or '✻' in line]
    if marker_lines:
        print(f"找到 {len(marker_lines)} 行包含标记:")
        for line in marker_lines[:10]:
            print(f"  {line}")
    else:
        print("未找到任何标记行")
    
    # 显示最后 20 行
    print("\n最后 20 行:")
    for line in lines[-20:]:
        print(f"  {line}")

    # 停止 iflow
    print("\n[8] 停止 iflow...")
    await controller.destroy_session()
    print("✅ iflow 已停止")


if __name__ == "__main__":
    asyncio.run(main())
