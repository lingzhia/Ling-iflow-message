#!/usr/bin/env python3
"""
调试 spinner 字符
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
    print("调试 spinner 字符")
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

        # 等待 30 秒，检查 spinner 字符
        print(f"\n[2] 检查 spinner 字符:")
        await asyncio.sleep(30)
        
        # 捕获输出
        output = await controller.capture_output(lines=100)
        
        # 查找所有特殊字符
        special_chars = set()
        for char in output:
            if ord(char) > 127:  # 非 ASCII 字符
                special_chars.add(char)
        
        print(f"  检测到的特殊字符: {sorted(special_chars)}")
        print(f"  检测到 '⠏': {'⠏' in output}")
        print(f"  检测到 '⠙': {'⠙' in output}")
        print(f"  检测到 '生成中': {'生成中' in output}")
        print(f"  检测到 '输入消息': {'输入消息或@文件路径' in output}")
        
        # 显示输出中的关键行
        lines = output.strip().split('\n')
        print(f"\n  输出中的关键行:")
        for i, line in enumerate(lines):
            if any(char in line for char in special_chars):
                print(f"  [{i}] {line[:80]}")

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
