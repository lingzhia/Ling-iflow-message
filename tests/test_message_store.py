#!/usr/bin/env python3
"""
测试 MessageStore

测试消息库的功能：
- 消息记录
- 状态管理
- 来源查询
- 回复数量统计
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.message_store import MessageRecord, MessageStatus


def test_message_store():
    """测试 MessageStore"""
    print("=" * 60)
    print("测试 MessageStore")
    print("=" * 60)
    
    try:
        from src.modules.iflow.message_store import MessageStore
        
        store = MessageStore()
        
        # 测试 1: 添加消息
        print("\n测试 1: 添加消息")
        message_id = "msg_001"
        record = store.add(
            metadata={"chat_id": "test_chat", "user_id": "test_user"},
            message_id=message_id,
            source="wechat",
            content="测试消息",
            scope="reply_only"
        )
        
        assert record.message_id == message_id
        assert record.source == "wechat"
        assert record.content == "测试消息"
        assert record.status == MessageStatus.PENDING
        print("✅ 添加消息成功")
        
        # 测试 2: 更新状态
        print("\n测试 2: 更新状态")
        store.update_status(message_id, MessageStatus.PROCESSING)
        record = store.get(message_id)
        assert record.status == MessageStatus.PROCESSING
        print("✅ 更新状态成功")
        
        # 测试 3: 获取当前来源
        print("\n测试 3: 获取当前来源")
        current_source = store.get_current_source()
        assert current_source == "wechat"
        print(f"✅ 当前来源: {current_source}")
        
        # 测试 4: 获取当前 scope
        print("\n测试 4: 获取当前 scope")
        current_scope = store.get_current_scope()
        assert current_scope == "reply_only"
        print(f"✅ 当前 scope: {current_scope}")
        
        # 测试 5: 增加回复数量
        print("\n测试 5: 增加回复数量")
        store.increment_reply_count(message_id)
        record = store.get(message_id)
        assert record.reply_count == 1
        print(f"✅ 回复数量: {record.reply_count}")
        
        # 测试 6: 添加多个消息
        print("\n测试 6: 添加多个消息")
        for i in range(3):
            store.add(
                metadata={"chat_id": "test_chat", "user_id": "test_user"},
                message_id=f"msg_{i+2:03d}",
                source="tool",
                content=f"测试消息 {i+2}",
                scope="all"
            )
        
        # 测试 7: 获取统计信息
        print("\n测试 7: 获取统计信息")
        stats = store.get_stats()
        print(f"   消息总数: {stats['total']}")
        print(f"   PENDING: {stats['pending']}")
        print(f"   PROCESSING: {stats['processing']}")
        print(f"   COMPLETED: {stats['completed']}")
        print("✅ 获取统计信息成功")
        
        # 测试 8: 完成当前消息
        print("\n测试 8: 完成当前消息")
        completed = store.complete_current()
        assert completed is not None
        assert completed.status == MessageStatus.COMPLETED
        print("✅ 完成当前消息成功")
        
        # 测试 9: 获取最近处理的消息
        print("\n测试 9: 获取最近处理的消息")
        recent = store.get_recent_processing()
        assert recent is not None
        print(f"✅ 最近处理的消息: {recent.message_id}")
        
        # 测试 10: 清空记录
        print("\n测试 10: 清空记录")
        store.clear()
        assert len(store._records) == 0
        print("✅ 清空记录成功")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_message_store()
    sys.exit(0 if success else 1)
