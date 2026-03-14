#!/usr/bin/env python3
"""
分析 iflow 输出

分析 iflow 的输出格式，理解消息提取逻辑。
"""

import sys
import os
import asyncio
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor


async def test_analyze_output():
    """分析 iflow 输出"""

    print("=" * 60)
    print("分析 iflow 输出")
    print("=" * 60)

    # 创建 controller 和 monitor
    controller = IFlowController("analyze_test")
    monitor = IFlowMonitor(controller, check_interval=0.5)

    try:
        # 启动 iflow
        print("\n正在启动 iflow...")
        success = await controller.start_iflow("kimi-k2.5")
        if not success:
            print("❌ 启动 iflow 失败")
            return 1

        print(f"✅ iflow 已启动")
        print(f"   tmux_session: {controller.tmux_session}")

        # 等待 iflow 完全启动
        print("\n等待 iflow 完全启动...")
        await asyncio.sleep(5)

        # 发送消息
        test_message = "你好，请简单介绍一下你自己"
        print(f"\n📤 发送消息: {test_message}")
        success = await controller.send_message(test_message)
        if not success:
            print("❌ 发送消息失败")
            return 1

        # 等待回复
        print(f"\n等待回复...")
        await asyncio.sleep(20)

        # 捕获输出
        print(f"\n{'=' * 60}")
        print("捕获的输出（带行号）")
        print(f"{'=' * 60}")
        output = await controller.capture_output(100)
        lines = output.split('\n')

        for i, line in enumerate(lines):
            print(f"{i:3d}: {line}")

        # 查找所有 `>` 开头的行
        print(f"\n{'=' * 60}")
        print("所有 `>` 开头的行")
        print(f"{'=' * 60}")
        for i, line in enumerate(lines):
            if line.strip().startswith('>'):
                print(f"行 {i}: {line}")

        # 查找所有标记行
        print(f"\n{'=' * 60}")
        print("所有标记行")
        print(f"{'=' * 60}")
        for i, line in enumerate(lines):
            if '✦' in line or '✻' in line:
                print(f"行 {i}: {line}")

        # 测试接收消息提取
        print(f"\n{'=' * 60}")
        print("测试接收消息提取")
        print(f"{'=' * 60}")
        received_msg, received_line = monitor._extract_received_message(lines)
        print(f"\n接收消息: {received_msg}")
        print(f"接收行号: {received_line}")
        print(f"该行内容: {lines[received_line] if received_line is not None else 'N/A'}")

        # 测试消息提取（不过滤）
        print(f"\n{'=' * 60}")
        print("测试消息提取（不过滤）")
        print(f"{'=' * 60}")

        # 手动测试提取逻辑
        messages = []
        for i, line in enumerate(lines):
            # 检查标记行
            if '✦' in line or '✻' in line:
                # 提取标记内容
                marker_type = '✦' if '✦' in line else '✻'
                marker_content = line.replace('✦', '').replace('✻', '').strip()

                if not marker_content:
                    continue

                print(f"\n找到标记行 {i}: {line}")

                # 收集后续行
                content_lines = [marker_content]
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    next_line_stripped = next_line.strip()

                    # 跳过 TUI 界面行
                    if monitor._is_tui_line(next_line):
                        print(f"  跳过 TUI 行 {j}: {next_line[:50]}")
                        continue

                    # 如果遇到新的标记行，停止
                    if '✦' in next_line or '✻' in next_line:
                        print(f"  遇到新标记行 {j}: {next_line[:50]}")
                        break

                    # 跳过空行
                    if not next_line_stripped:
                        print(f"  跳过空行 {j}")
                        continue

                    # 检查缩进
                    if next_line.startswith('  ') or next_line.startswith('\t'):
                        print(f"  收集缩进行 {j}: {next_line_stripped[:50]}")
                        content_lines.append(next_line_stripped)
                    else:
                        print(f"  遇到非缩进行 {j}: {next_line[:50]}")
                        break

                full_content = '\n'.join(content_lines)
                messages.append({
                    'content': full_content,
                    'marker_type': marker_type,
                    'marker_only': marker_content
                })

                print(f"  提取的消息: {full_content[:100]}...")

        print(f"\n总共提取了 {len(messages)} 个消息")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 停止
        print("\n\n正在停止...")
        await controller.stop_iflow()
        await controller.destroy_session()
        print("✅ 已停止")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(test_analyze_output()))
