#!/usr/bin/env python3
"""
使用模拟器测试 /snapshot 命令
"""

import asyncio
import struct
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


async def test_snapshot_command():
    """测试 /snapshot 命令"""
    print("=" * 60)
    print("使用模拟器测试 /snapshot 命令")
    print("=" * 60)
    
    try:
        # 连接到模拟器
        reader, writer = await asyncio.open_connection("localhost", 19999)
        print("\n✅ 已连接到模拟器服务器\n")
        
        # 测试 1：发送 /snapshot 命令
        print("测试 1：发送 /snapshot 命令")
        message = {
            "type": "user_message",
            "id": "msg_1",
            "content": "/snapshot",
            "user_id": "test_user",
            "chat_id": "test_chat",
            "timestamp": 1234567890
        }
        
        # 发送消息
        import json
        data = json.dumps(message).encode('utf-8')
        length = struct.pack('!I', len(data))
        writer.write(length + data)
        await writer.drain()
        print(f"✅ 已发送命令: {message['content']}")
        
        # 接收回复
        length_data = await reader.readexactly(4)
        length = struct.unpack('!I', length_data)[0]
        response_data = await reader.readexactly(length)
        response = json.loads(response_data.decode('utf-8'))
        
        print(f"\n收到回复:")
        print(f"类型: {response.get('type')}")
        print(f"内容:\n{response.get('content', '')}")
        
        # 检查是否是命令回复
        if 'content' in response:
            content = response['content']
            if '界面快照' in content or '界面' in content:
                print("\n✅ 测试 1 通过：成功获取界面快照")
            else:
                print(f"\n❌ 测试 1 失败：未获取到预期的界面快照")
        else:
            print(f"\n❌ 测试 1 失败：回复中没有内容")
        
        # 测试 2：发送 /snapshot simulator1 命令
        print("\n" + "=" * 60)
        print("测试 2：发送 /snapshot simulator1 命令")
        message = {
            "type": "user_message",
            "id": "msg_2",
            "content": "/snapshot simulator1",
            "user_id": "test_user",
            "chat_id": "test_chat",
            "timestamp": 1234567891
        }
        
        # 发送消息
        data = json.dumps(message).encode('utf-8')
        length = struct.pack('!I', len(data))
        writer.write(length + data)
        await writer.drain()
        print(f"✅ 已发送命令: {message['content']}")
        
        # 接收回复
        length_data = await reader.readexactly(4)
        length = struct.unpack('!I', length_data)[0]
        response_data = await reader.readexactly(length)
        response = json.loads(response_data.decode('utf-8'))
        
        print(f"\n收到回复:")
        print(f"类型: {response.get('type')}")
        print(f"内容:\n{response.get('content', '')}")
        
        # 检查是否是命令回复
        if 'content' in response:
            content = response['content']
            if '界面快照' in content or '界面' in content:
                print("\n✅ 测试 2 通过：成功获取界面快照")
            else:
                print(f"\n❌ 测试 2 失败：未获取到预期的界面快照")
        else:
            print(f"\n❌ 测试 2 失败：回复中没有内容")
        
        # 关闭连接
        writer.close()
        await writer.wait_closed()
        print("\n✅ 已断开连接")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_snapshot_command())