#!/usr/bin/env python3
"""
详细调试命令行模式
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tools.iflow_interactive_tool import IFlowInteractiveTool


async def main():
    """主函数"""
    print("=" * 70)
    print("详细调试命令行模式")
    print("=" * 70)

    # 创建工具
    tool = IFlowInteractiveTool(config_path="config.json", clean=True)

    try:
        # 启动工具
        print("\n[1] 启动工具...")
        await tool.start()
        print(f"✅ 工具已启动")

        # 等待 iflow 完全启动
        print("\n[2] 等待 iflow 完全启动...")
        await asyncio.sleep(5)
        print(f"✅ iflow 已就绪")

        # 检查工具状态
        print(f"\n[3] 工具状态:")
        print(f"   module_id: {tool.module.module_id}")
        print(f"   tmux_session: {tool.module.tmux_session}")
        print(f"   state: {tool.module.state.value}")
        print(f"   message_history: {len(tool.message_history)}")

        # 发送测试消息
        test_message = "哈哈哈"
        print(f"\n[4] 发送测试消息: {test_message}")

        # 检查消息总线
        print(f"\n[5] 检查消息总线:")
        print(f"   mock_bus._iflow_module: {tool.mock_bus._iflow_module}")
        print(f"   tool.module: {tool.module}")

        # 发送消息
        print(f"\n[6] 调用 send_message()...")
        await tool.send_message(test_message)
        print(f"✅ send_message() 完成")

        # 等待 2 秒
        print(f"\n[7] 等待 2 秒...")
        await asyncio.sleep(2)

        # 检查消息历史
        print(f"\n[8] 检查消息历史:")
        print(f"   message_history: {len(tool.message_history)}")
        for idx, msg in enumerate(tool.message_history, 1):
            print(f"   [{idx}] [{msg['type']}]: {msg['content'][:50]}...")

        # 检查 iflow 状态
        print(f"\n[9] 检查 iflow 状态:")
        print(f"   state: {tool.module.state.value}")

        # 检查 tmux 输出
        print(f"\n[10] 检查 tmux 输出:")
        proc = await asyncio.create_subprocess_exec(
            "tmux", "capture-pane", "-t", "iflow1",
            "-S", "-20", "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        print(stdout.decode())

        # 停止工具
        print("\n停止工具...")
        await tool.stop()
        print("✅ 工具已停止")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            await tool.stop()
        except:
            pass
        return False


if __name__ == "__main__":
    asyncio.run(main())