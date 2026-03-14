#!/usr/bin/env python3
"""
测试工具启动
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

print("Step 1: Importing tool...")
from tools.iflow_interactive_tool import IFlowInteractiveTool
print("Step 1: Done")

print("Step 2: Creating tool instance...")
tool = IFlowInteractiveTool("config.json")
print("Step 2: Done")

async def test():
    print("Step 3: Starting tool...")
    await tool.start()
    print("Step 3: Done")

    print("Step 4: Stopping tool...")
    await tool.stop()
    print("Step 4: Done")

if __name__ == "__main__":
    print("Starting test...")
    asyncio.run(test())
    print("Test completed")