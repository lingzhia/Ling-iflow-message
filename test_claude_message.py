#!/usr/bin/env python3
"""测试Claude消息提取"""

import asyncio
import json
import struct

async def test_claude_message():
    """测试Claude消息提取"""
    
    # 连接到模拟器
    reader, writer = await asyncio.open_connection('localhost', 19999)
    
    # 构建消息
    message = {
        "type": "user_message",
        "id": "msg_test_001",
        "timestamp": asyncio.get_event_loop().time(),
        "content": "请用一句话介绍你的功能",
        "metadata": {
            "user_id": "test_user",
            "chat_id": "test_chat",
            "is_group": False
        }
    }
    
    # 序列化为JSON
    message_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
    
    # 发送消息
    writer.write(struct.pack('>I', len(message_data)))
    writer.write(message_data)
    await writer.drain()
    
    print("✅ 消息已发送: 请用一句话介绍你的功能")
    
    # 接收回复
    try:
        # 读取消息长度
        length_data = await asyncio.wait_for(reader.readexactly(4), timeout=30.0)
        length = struct.unpack('>I', length_data)[0]
        
        # 读取消息内容
        message_data = await asyncio.wait_for(reader.readexactly(length), timeout=30.0)
        response = json.loads(message_data.decode('utf-8'))
        
        print("✅ 收到回复:")
        print(f"   类型: {response.get('type')}")
        print(f"   内容: {response.get('content')}")
        print(f"   元数据: {response.get('metadata')}")
        
    except asyncio.TimeoutError:
        print("❌ 接收超时")
    except Exception as e:
        print(f"❌ 接收失败: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(test_claude_message())