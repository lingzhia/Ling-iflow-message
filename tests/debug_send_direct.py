#!/usr/bin/env python3
"""
直接测试消息发送
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule


async def main():
    """主函数"""
    print("=" * 70)
    print("直接测试消息发送")
    print("=" * 70)

    # 创建模块实例
    module = IFlowModule(
        tmux_session="iflow1",
        model="kimi-k2.5",
        workspace="~/.iflow",
        auto_restart=True,
        log_interactions=True,
        log_dir="logs/interactions"
    )

    try:
        # 启动模块
        print("\n[1] 启动模块...")
        await module.start()
        print(f"✅ 模块已启动")

        # 等待 iflow 完全启动
        print("\n[2] 等待 iflow 完全启动...")
        await asyncio.sleep(5)
        print(f"✅ iflow 已就绪")

        # 检查 iflow 状态
        print(f"\n[3] 检查 iflow 状态:")
        print(f"   check_iflow_running: {await module.controller.check_iflow_running()}")
        print(f"   state: {module.state.value}")

        # 直接调用 send 方法
        test_message = "哈哈哈"
        print(f"\n[4] 直接调用 send 方法: {test_message}")

        response = await module.send(
            content=test_message,
            source="test",
            scope="all"
        )

        print(f"✅ send 方法返回: {response.success}")
        print(f"   message: {response.message}")
        print(f"   error: {response.error}")

        # 等待 10 秒
        print(f"\n[5] 等待 10 秒...")
        await asyncio.sleep(10)

        # 检查 tmux 输出
        print(f"\n[6] 检查 tmux 输出:")
        proc = await asyncio.create_subprocess_exec(
            "tmux", "capture-pane", "-t", "iflow1",
            "-S", "-20", "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        print(stdout.decode())

        # 停止模块
        print("\n停止模块...")
        await module.stop()
        print("✅ 模块已停止")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            await module.stop()
        except:
            pass
        return False


if __name__ == "__main__":
    asyncio.run(main())