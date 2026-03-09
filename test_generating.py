#!/usr/bin/env python3
"""测试 iflow 生成中状态"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from interactive.iflow_controller import IFlowController
import subprocess

def main():
    print("=== 测试 iflow 生成中状态 ===\n")
    
    # 创建控制器
    controller = IFlowController(tmux_session="iflow")
    
    # 发送消息
    print("1. 发送消息到 iflow...")
    success = controller.send_message("写一个详细的Python异步编程教程")
    
    if not success:
        print("发送失败")
        return
    
    print("消息发送成功\n")
    
    # 立即查看输出
    print("2. 立即查看 tmux 输出...")
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", "iflow", "-p"],
        capture_output=True,
        text=True
    )
    
    lines = result.stdout.split('\n')
    print(f"\n最后 30 行输出:")
    for i, line in enumerate(lines[-30:], len(lines)-29):
        print(f"{i:3d}: {line}")
    
    # 查找生成中标记
    print("\n3. 查找生成中标记...")
    for i, line in enumerate(lines):
        if '生成中' in line or '思考中' in line:
            print(f"找到生成中标记在第 {i+1} 行:")
            print(f"  {line}")
            
            # 查找时间
            import re
            time_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', line)
            if time_match:
                print(f"  时间: {time_match.group(1)}")
            else:
                print("  未找到时间信息")
    
    print("\n4. 再等待 2 秒后查看...")
    time.sleep(2)
    
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", "iflow", "-p"],
        capture_output=True,
        text=True
    )
    
    lines = result.stdout.split('\n')
    print(f"\n最后 30 行输出:")
    for i, line in enumerate(lines[-30:], len(lines)-29):
        print(f"{i:3d}: {line}")
    
    # 再次查找生成中标记
    print("\n5. 查找生成中标记...")
    for i, line in enumerate(lines):
        if '生成中' in line or '思考中' in line:
            print(f"找到生成中标记在第 {i+1} 行:")
            print(f"  {line}")
            
            # 查找时间
            import re
            time_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', line)
            if time_match:
                print(f"  时间: {time_match.group(1)}")
            else:
                print("  未找到时间信息")

if __name__ == '__main__':
    main()