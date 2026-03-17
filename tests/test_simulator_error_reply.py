"""
使用模拟器渠道测试异常自动回复功能
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from tools.test_client import TestClient


async def test_error_reply():
    """测试异常自动回复功能"""
    client = TestClient(host="localhost", port=19999)

    print("=== 测试异常自动回复功能 ===\n")

    # 连接到模拟器
    print("1. 连接到模拟器...")
    if not await client.connect():
        print("❌ 连接失败")
        return
    print("✅ 连接成功\n")

    # 发送测试消息（此时 iflow 正常运行）
    print("2. 发送测试消息（iflow 正常运行）...")
    success = await client.send_message("你好，请介绍一下你自己")
    if success:
        print("✅ 消息发送成功，等待回复...")
        await asyncio.sleep(2)
        print(f"✅ 收到 {client.received_count} 条回复\n")
    else:
        print("❌ 消息发送失败\n")

    # 等待一下，确保消息处理完成
    await asyncio.sleep(3)

    # 停止 iflow 模块（模拟异常情况）
    print("3. 停止 iflow 模块（模拟异常情况）...")
    import subprocess
    subprocess.run(["tmux", "kill-session", "-t", "simulator1+iflow"], capture_output=True)
    print("✅ iflow 模块已停止\n")

    # 等待 ModuleManager 检测到异常
    print("4. 等待 ModuleManager 检测到异常（5秒）...")
    await asyncio.sleep(5)

    # 再次发送消息（此时 iflow 异常，应该收到错误回复）
    print("5. 再次发送消息（iflow 异常，应该收到错误回复）...")
    received_before = client.received_count
    success = await client.send_message("这是第二条消息")
    if success:
        print("✅ 消息发送成功，等待回复...")
        await asyncio.sleep(3)
        received_after = client.received_count

        if received_after > received_before:
            print(f"✅ 收到 {received_after - received_before} 条回复")
            print("\n✅ 异常自动回复功能正常工作！")
        else:
            print("❌ 没有收到回复")
    else:
        print("❌ 消息发送失败")

    # 断开连接
    print("\n6. 断开连接...")
    await client.disconnect()
    print("✅ 测试完成")


if __name__ == "__main__":
    try:
        asyncio.run(test_error_reply())
    except KeyboardInterrupt:
        print("\n测试被中断")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
