#!/usr/bin/env python3
"""
分析 iflow 启动过程
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
    print("分析 iflow 启动过程")
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
        print(f"   module_id: {module.module_id}")
        print(f"   tmux_session: {module.tmux_session}")

        # 分析启动过程
        print(f"\n[2] 分析 iflow 启动过程:")
        
        # 每秒检查一次 iflow 状态
        for i in range(20):
            await asyncio.sleep(1)
            
            # 检查 iflow 是否运行
            is_running = await module.controller.check_iflow_running()
            
            # 检查监控器状态
            monitor_state = module.monitor.state.value
            monitor_init = module.monitor._is_initialized
            monitor_ready = module.monitor._is_ready if hasattr(module.monitor, '_is_ready') else "N/A"
            
            # 捕获 tmux 输出
            output = await module.controller.capture_output(lines=50)
            
            print(f"  {i+1}s: running={is_running}, monitor_state={monitor_state}, monitor_init={monitor_init}, monitor_ready={monitor_ready}")
            
            # 显示 tmux 输出的关键部分
            if "输入消息或@文件路径" in output:
                print(f"      ✅ UI 已就绪")
            if "Hi～今天想做点什么" in output:
                print(f"      ✅ 欢迎消息已显示")
            if "版本号:" in output:
                print(f"      ✅ 版本号已显示")
            
            # 显示输出中的特殊状态
            if "生成中" in output or "⠏" in output or "⠙" in output:
                print(f"      ⚠️ 检测到：生成中")
            if "思考:" in output:
                print(f"      ⚠️ 检测到：思考模式")
            
            # 检查是否在输入状态
            if ">   输入消息或@文件路径" in output and "生成中" not in output:
                print(f"      ✅ 看起来已准备好接受消息")

        # 最终状态
        print(f"\n[3] 最终状态:")
        print(f"   iflow_running: {await module.controller.check_iflow_running()}")
        print(f"   monitor_state: {module.monitor.state.value}")
        print(f"   monitor_initialized: {module.monitor._is_initialized}")
        print(f"   monitor_ready: {module.monitor._is_ready if hasattr(module.monitor, '_is_ready') else 'N/A'}")

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
