#!/usr/bin/env python3
"""
测试 check_iflow_ready() 方法
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController


async def main():
    """主函数"""
    print("=" * 70)
    print("测试 check_iflow_ready() 方法")
    print("=" * 70)

    # 创建控制器
    controller = IFlowController("iflow1")

    try:
        # 启动 iflow
        print("\n[1] 启动 iflow...")
        success = await controller.start_iflow("kimi-k2.5")
        print(f"   start_iflow() 返回: {success}")

        if not success:
            print("❌ 启动失败")
            return False

        # 测试 check_iflow_ready()
        print(f"\n[2] 测试 check_iflow_ready():")
        for i in range(30):
            await asyncio.sleep(1)
            ready = await controller.check_iflow_ready()
            print(f"   {i+1}s: ready={ready}")
            
            if ready:
                print(f"✅ iflow 已就绪")
                break

        # 最终状态
        print(f"\n[3] 最终状态:")
        print(f"   tmux_session: {controller.tmux_session}")
        print(f"   check_tmux_session: {await controller.check_tmux_session()}")
        print(f"   check_iflow_running: {await controller.check_iflow_running()}")
        print(f"   check_iflow_ready: {await controller.check_iflow_ready()}")

        # 停止 iflow
        print("\n停止 iflow...")
        await controller.destroy_session()
        print("✅ 已停止")

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        try:
            await controller.destroy_session()
        except:
            pass
        return False


if __name__ == "__main__":
    asyncio.run(main())
