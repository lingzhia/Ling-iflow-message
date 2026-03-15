#!/usr/bin/env python3
"""
调试 wait_for_complete 方法
"""
import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.modules.iflow.monitor import IFlowState


async def main():
    """主函数"""
    print("=" * 70)
    print("调试 wait_for_complete 方法")
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

        # 等待 iflow 完全启动
        print("\n[2] 等待 iflow 完全启动...")
        await asyncio.sleep(5)
        print(f"✅ iflow 已就绪")

        # 发送消息
        print(f"\n[3] 发送消息: 哈哈哈")
        response = await module.send(
            content="哈哈哈",
            source="test",
            scope="all"
        )
        print(f"✅ 消息已发送: {response.success}")

        # 手动实现 wait_for_complete 逻辑
        print(f"\n[4] 等待回复完成:")
        timeout = 60.0
        elapsed = 0.0
        check_interval = 1.0
        
        message_history = []
        last_message_count = 0
        
        while elapsed < timeout:
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            current_state = module.state
            message_count = len(message_history)
            
            print(f"   {elapsed}s: state={current_state.value}, messages={message_count}")
            
            # 检查是否有新消息
            # 这里我们假设消息会被添加到某个地方
            # 实际上，我们需要检查钩子是否被调用
            
            # 检查是否完成
            if current_state == IFlowState.IDLE and elapsed > 5:
                print(f"✅ 生成完成")
                break
        
        print(f"\n[5] 最终状态:")
        print(f"   state: {module.state.value}")
        print(f"   message_count: {len(message_history)}")

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
