"""
测试 Message 类
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import Message, MessageType, MessageContent
import json


def test_create_text_message():
    """测试创建文本消息"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="test",
        to_module="test"
    )
    assert msg.type == MessageType.TEXT
    assert msg.content.text == "Hello"
    print("✅ test_create_text_message passed")


def test_create_image_message():
    """测试创建图片消息"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.IMAGE,
        content=MessageContent(type=MessageType.IMAGE, url="http://example.com/image.jpg"),
        from_module="test",
        to_module="test"
    )
    assert msg.type == MessageType.IMAGE
    assert msg.content.url == "http://example.com/image.jpg"
    print("✅ test_create_image_message passed")


def test_create_voice_message():
    """测试创建语音消息"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.VOICE,
        content=MessageContent(type=MessageType.VOICE, url="http://example.com/voice.mp3", metadata={"duration": 10}),
        from_module="test",
        to_module="test"
    )
    assert msg.type == MessageType.VOICE
    assert msg.content.url == "http://example.com/voice.mp3"
    assert msg.content.metadata["duration"] == 10
    print("✅ test_create_voice_message passed")


def test_create_video_message():
    """测试创建视频消息"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.VIDEO,
        content=MessageContent(type=MessageType.VIDEO, url="http://example.com/video.mp4"),
        from_module="test",
        to_module="test"
    )
    assert msg.type == MessageType.VIDEO
    assert msg.content.url == "http://example.com/video.mp4"
    print("✅ test_create_video_message passed")


def test_create_file_message():
    """测试创建文件消息"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.FILE,
        content=MessageContent(type=MessageType.FILE, url="http://example.com/file.pdf", metadata={"filename": "file.pdf"}),
        from_module="test",
        to_module="test"
    )
    assert msg.type == MessageType.FILE
    assert msg.content.url == "http://example.com/file.pdf"
    assert msg.content.metadata["filename"] == "file.pdf"
    print("✅ test_create_file_message passed")


def test_create_system_message():
    """测试创建系统消息"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.SYSTEM,
        content=MessageContent(type=MessageType.SYSTEM, text="System notification"),
        from_module="system",
        to_module="test"
    )
    assert msg.type == MessageType.SYSTEM
    assert msg.content.text == "System notification"
    print("✅ test_create_system_message passed")


def test_create_error_message():
    """测试创建错误消息"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.ERROR,
        content=MessageContent(type=MessageType.ERROR, text="Error occurred", metadata={"code": 500}),
        from_module="system",
        to_module="test"
    )
    assert msg.type == MessageType.ERROR
    assert msg.content.text == "Error occurred"
    assert msg.content.metadata["code"] == 500
    print("✅ test_create_error_message passed")


def test_to_dict():
    """测试转换为字典"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="test",
        to_module="test"
    )
    d = msg.to_dict()
    assert d["type"] == "text"
    assert d["content"]["text"] == "Hello"
    assert d["from_module"] == "test"
    assert d["to_module"] == "test"
    print("✅ test_to_dict passed")


def test_to_json():
    """测试转换为 JSON"""
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="test",
        to_module="test"
    )
    json_str = msg.to_json()
    d = json.loads(json_str)
    assert d["type"] == "text"
    assert d["content"]["text"] == "Hello"
    print("✅ test_to_json passed")


def test_from_dict():
    """测试从字典恢复"""
    d = {
        "id": "test_id",
        "type": "text",
        "content": {"type": "text", "text": "Hello"},
        "from_module": "test",
        "to_module": "test",
        "chat_id": "test_chat",
        "user_id": "test_user",
        "is_group": False,
        "timestamp": "2024-01-01T00:00:00",
        "metadata": {}
    }
    msg = Message.from_dict(d)
    assert msg.type == MessageType.TEXT
    assert msg.content.text == "Hello"
    assert msg.from_module == "test"
    assert msg.to_module == "test"
    print("✅ test_from_dict passed")


def test_from_json():
    """测试从 JSON 恢复"""
    json_str = '{"id": "test_id", "type": "text", "content": {"type": "text", "text": "Hello"}, "from_module": "test", "to_module": "test", "chat_id": "test_chat", "user_id": "test_user", "is_group": false, "timestamp": "2024-01-01T00:00:00", "metadata": {}}'
    msg = Message.from_json(json_str)
    assert msg.type == MessageType.TEXT
    assert msg.content.text == "Hello"
    print("✅ test_from_json passed")


def test_serialization_consistency():
    """测试序列化/反序列化一致性"""
    msg1 = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="test",
        to_module="test"
    )
    json_str = msg1.to_json()
    msg2 = Message.from_json(json_str)
    assert msg1.type == msg2.type
    assert msg1.content.text == msg2.content.text
    assert msg1.from_module == msg2.from_module
    assert msg1.to_module == msg2.to_module
    print("✅ test_serialization_consistency passed")


def test_copy():
    """测试复制消息"""
    msg1 = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="test",
        to_module="test"
    )
    msg2 = msg1.copy()
    assert msg1.type == msg2.type
    assert msg1.content.text == msg2.content.text
    assert msg1.from_module == msg2.from_module
    assert msg1.to_module == msg2.to_module
    assert msg1 is not msg2  # 验证是独立对象
    print("✅ test_copy passed")


def test_generate_id():
    """测试生成唯一 ID"""
    ids = [Message.generate_id() for _ in range(100)]
    assert len(ids) == len(set(ids))  # 验证唯一性
    for id_ in ids:
        assert len(id_) == 32  # 验证格式（MD5 哈希）
    print("✅ test_generate_id passed")


def main():
    """运行所有测试"""
    tests = [
        test_create_text_message,
        test_create_image_message,
        test_create_voice_message,
        test_create_video_message,
        test_create_file_message,
        test_create_system_message,
        test_create_error_message,
        test_to_dict,
        test_to_json,
        test_from_dict,
        test_from_json,
        test_serialization_consistency,
        test_copy,
        test_generate_id,
    ]
    
    print("=" * 60)
    print("开始测试 Message 类")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)