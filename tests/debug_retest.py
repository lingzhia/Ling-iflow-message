#!/usr/bin/env python3
"""
重新测试命令行模式
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
    print("重新测试命令行模式")
    print("=" * 70)

    # 清理残留的 tmux 会话
    print("\n[0] 清理残留的 tmux 会话...")
    proc = await asyncio.create_subprocess_exec(
        "tmux", "kill-session", "-t", "iflow1",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    print("✅ 已清理")

    # 等待一下
    await asyncio.sleep(2)

    # 创建工具
    tool = IFlowInteractiveTool(config_path="config.json", clean=False)

    try:
        # 启动工具
        print("\n[1] 启动工具...")
        await tool.start()
        print(f"✅ 工具已启动")

        # 等待 iflow 完全启动
        print("\n[2] 等待 iflow 完全启动...")
        await asyncio.sleep(5)
        print(f"✅ iflow 已就绪")

        # 发送测试消息
        test_message = "哈哈哈"
        print(f"\n[3] 发送测试消息: {test_message}")

        # 直接发送消息
        await tool.send_message(test_message)
        print(f"✅ 消息已发送")

        # 等待 20 秒
        print(f"\n[4] 等待 20 秒...")
        for i in range(20):
            await asyncio.sleep(1)
            if tool.message_history:
                print(f"   收到消息！({i+1}s)")
                break
            if i % 5 == 0:
                print(f"   等待中... {i+1}s")

        print(f"✅ 收到 {len(tool.message_history)} 条消息")

        # 显示结果
        print("\n" + "=" * 70)
        print("收到的消息")
        print("=" * 70)
        for idx, msg in enumerate(tool.message_history, 1):
            print(f"[{idx}] [{msg['type']}]: {msg['content'][:80]}...")

        # 检查 tmux 输出
        print("\n" + "=" * 70)
        print("tmux 输出（最后 20 行）")
        print("=" * 70)
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
