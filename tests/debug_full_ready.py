#!/usr/bin/env python3
"""
调试完整的就绪检查
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
    print("调试完整的就绪检查")
    print("=" * 70)

    # 创建控制器
    controller = IFlowController("iflow1")

    try:
        # 手动启动 iflow
        print("\n[1] 启动 iflow...")
        
        result = await asyncio.create_subprocess_shell(
            f"tmux new-session -d -s {controller.tmux_session} 'iflow --model kimi-k2.5'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(result.communicate(), timeout=30)
        
        if result.returncode != 0:
            print(f"❌ 启动失败: returncode={result.returncode}")
            return False
        
        print("✅ iflow 进程已启动")

        # 持续检查直到就绪
        print(f"\n[2] 持续检查直到就绪:")
        for i in range(60):
            await asyncio.sleep(1)
            
            # 捕获输出
            output = await controller.capture_output(lines=100)
            
            # 检查各个条件
            has_input = "输入消息或@文件路径" in output
            has_welcome = "Hi～今天想做点什么" in output
            has_version = "版本号:" in output
            has_generating = "生成中" in output
            has_waiting = "等待认证中" in output
            
            is_ready = await controller.check_iflow_ready()
            
            # 每 5 秒打印一次状态
            if i % 5 == 0 or is_ready:
                print(f"\n{i}s:")
                print(f"  UI: input={has_input}, welcome={has_welcome}, version={has_version}")
                print(f"  状态: generating={has_generating}, waiting={has_waiting}")
                print(f"  check_iflow_ready: {is_ready}")
                
                # 显示最后 5 行
                lines = output.strip().split('\n')
                if lines:
                    print(f"  最后5行:")
                    for line in lines[-5:]:
                        print(f"    {line[:60]}")
            
            # 如果就绪，退出
            if is_ready:
                print(f"\n✅ iflow 已就绪 (耗时 {i+1}s)")
                break
        
        # 最终检查
        print(f"\n[3] 最终状态:")
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