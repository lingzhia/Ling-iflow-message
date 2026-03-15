#!/usr/bin/env python3
"""
使用 --clean 选项测试工具
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tools.iflow_interactive_tool import IFlowInteractiveTool

# 设置日志级别
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("debug_tool_with_clean")


async def main():
    """主函数"""
    print("=" * 60)
    print("使用 --clean 选项测试工具")
    print("=" * 60)

    # 创建工具
    print("\n[1] 创建工具...")
    tool = IFlowInteractiveTool(config_path="config.json", clean=True)

    # 启动工具
    print("\n[2] 启动工具...")
    await tool.start()

    # 发送消息
    print("\n[3] 发送消息...")
    await tool.send_message("收到请回答")

    # 等待完成
    print("\n[4] 等待完成...")
    result = await tool.wait_for_complete(timeout=60)
    print(f"   等待结果: {result}")

    # 显示历史
    print("\n[5] 显示历史...")
    tool._show_history()

    # 停止工具
    print("\n[6] 停止工具...")
    await tool.stop()


if __name__ == "__main__":
    asyncio.run(main())