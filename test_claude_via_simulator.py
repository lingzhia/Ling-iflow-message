#!/usr/bin/env python3
"""
Claude Code 交互测试

通过 Simulator Channel 发送消息，测试 Claude Code 模块：
1. 验证 tmux 输出捕获
2. 验证消息发送和接收
3. 验证交互记录
"""

import asyncio
import json
import socket
import struct
import sys
import time
import os
import threading
from typing import Optional, Tuple

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class SimulatorClient:
    """Simulator Channel 客户端"""

    def __init__(self, host: str = "localhost", port: int = 19999):
        self.host = host
        self.port = port
        self.conn: Optional[socket.socket] = None

    def connect(self) -> bool:
        """连接到 Simulator Channel"""
        try:
            self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.conn.connect((self.host, self.port))
            print(f"✓ 已连接到 Simulator Channel ({self.host}:{self.port})")
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def send_message(self, message_type: str, content: str, metadata: dict = None) -> dict:
        """发送消息到 Simulator Channel

        Args:
            message_type: 消息类型 (user_message, bot_message 等)
            content: 消息内容
            metadata: 元数据

        Returns:
            响应消息
        """
        if not self.conn:
            raise RuntimeError("未连接到 Simulator Channel")

        msg = {
            "type": message_type,
            "content": content,
            "metadata": metadata or {}
        }

        # 发送消息
        data = json.dumps(msg, ensure_ascii=False).encode('utf-8')
        length = struct.pack('>I', len(data))
        self.conn.sendall(length + data)

        # 接收响应
        response = self.receive_message()
        return response

    def receive_message(self) -> dict:
        """接收 Simulator Channel 的消息"""
        if not self.conn:
            raise RuntimeError("未连接到 Simulator Channel")

        # 接收消息长度
        length_data = self.conn.recv(4)
        if not length_data:
            return {}

        length = struct.unpack('>I', length_data)[0]

        # 接收消息内容
        data = b''
        while len(data) < length:
            chunk = self.conn.recv(length - len(data))
            if not chunk:
                break
            data += chunk

        return json.loads(data.decode('utf-8'))


def test_simulator_connection():
    """测试 Simulator Channel 连接"""
    print("=" * 60)
    print("测试 1: Simulator Channel 连接")
    print("=" * 60)

    # 首先检查 Simulator Channel 是否在运行
    try:
        client = SimulatorClient()
        if client.connect():
            client.disconnect()
            print("✓ Simulator Channel 连接测试通过")
            return True
        else:
            print("✗ 无法连接到 Simulator Channel")
            print("  请先启动机器人: ./manage.py start")
            return False
    except Exception as e:
        print(f"✗ 连接测试失败: {e}")
        return False


def test_claude_module_via_simulator():
    """测试 Claude Code 模块通过 Simulator Channel"""
    print()
    print("=" * 60)
    print("测试 2: Claude Code 交互测试")
    print("=" * 60)

    # 这个测试需要机器人正在运行
    # 由于我们没有真实的 Claude Code CLI，这里只测试消息发送流程

    try:
        client = SimulatorClient()

        if not client.connect():
            print("✗ 无法连接到 Simulator Channel")
            return False

        # 发送一个测试消息
        print("\n发送测试消息...")
        response = client.send_message(
            message_type="user_message",
            content="你好 Claude",
            metadata={"chat_id": "test_chat", "user_id": "test_user"}
        )

        print(f"收到响应: {json.dumps(response, ensure_ascii=False, indent=2)}")

        # 检查响应
        if response.get("type") == "bot_message":
            print("✓ 收到机器人消息")
            return True
        elif response.get("type") == "error":
            print(f"✗ 收到错误: {response.get('content')}")
            return False
        else:
            print(f"? 收到未知类型消息: {response.get('type')}")
            return False

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.disconnect()


def test_tmux_capture():
    """测试 tmux 输出捕获"""
    print()
    print("=" * 60)
    print("测试 3: tmux 输出捕获")
    print("=" * 60)

    try:
        import subprocess

        # 获取所有 tmux 会话
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("✗ 无法获取 tmux 会话列表")
            return False

        sessions = result.stdout.strip().split('\n')
        print(f"当前 tmux 会话: {len(sessions)} 个")

        for session in sessions:
            print(f"  - {session}")

            # 捕获会话输出
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session, "-p", "-S", "-50"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                output = result.stdout
                print(f"    最近50行输出预览:")
                lines = output.split('\n')
                for line in lines[-5:]:
                    if line.strip():
                        print(f"      {line[:60]}")

        print("✓ tmux 输出捕获测试完成")
        return True

    except Exception as e:
        print(f"✗ tmux 捕获测试失败: {e}")
        return False


def test_interaction_flow():
    """测试交互流程"""
    print()
    print("=" * 60)
    print("测试 4: 交互流程测试")
    print("=" * 60)

    # 这个测试验证完整的交互流程
    # 1. 通过 Simulator 发送消息
    # 2. 检查消息是否到达 Claude Code
    # 3. 检查 Claude Code 的响应
    # 4. 检查交互记录

    try:
        client = SimulatorClient()

        if not client.connect():
            print("✗ 无法连接到 Simulator Channel")
            return False

        # 发送测试消息
        test_content = f"测试消息 {int(time.time())}"

        print(f"\n发送消息: {test_content}")
        response = client.send_message(
            message_type="user_message",
            content=test_content,
            metadata={"chat_id": "test_chat", "user_id": "test_user"}
        )

        print(f"收到响应类型: {response.get('type')}")

        if response.get("type") == "bot_message":
            content = response.get("content", "")
            print(f"响应内容: {content[:100]}...")
            print("✓ 交互流程测试通过")
            return True
        else:
            print(f"响应: {json.dumps(response, ensure_ascii=False)[:200]}")
            return False

    except Exception as e:
        print(f"✗ 交互流程测试失败: {e}")
        return False
    finally:
        client.disconnect()


def main():
    """运行所有测试"""
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 12 + "Claude Code Simulator 测试" + " " * 17 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    # 测试 1: 连接测试
    results.append(("Simulator连接", test_simulator_connection()))

    # 测试 2: tmux 捕获测试（不需要连接）
    results.append(("tmux捕获", test_tmux_capture()))

    # 测试 3: 交互测试
    results.append(("交互流程", test_interaction_flow()))

    # 汇总
    print()
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}  {name}")

    print()
    print(f"通过: {passed}/{total}")

    if passed == total:
        print()
        print("所有测试通过！")
        return 0
    else:
        print()
        print("部分测试失败。")
        return 1


if __name__ == "__main__":
    sys.exit(main())