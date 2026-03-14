#!/usr/bin/env python3
"""
测试 InteractionLogger

测试交互记录器的功能：
- 会话日志记录
- 消息发送/接收记录
- 日志持久化存储
- 统计信息
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
import json
import tempfile
import shutil

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def test_interaction_logger():
    """测试 InteractionLogger"""
    print("=" * 60)
    print("测试 InteractionLogger")
    print("=" * 60)
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    log_dir = Path(temp_dir) / "interactions"
    
    try:
        from src.modules.iflow.logger import InteractionLogger
        
        logger = InteractionLogger(
            module_id="test_module",
            log_dir=str(log_dir),
            enabled=True
        )
        
        # 测试 1: 启动会话
        print("\n测试 1: 启动会话")
        logger.start_session()
        assert logger._session_start is not None
        print("✅ 会话启动成功")
        
        # 测试 2: 记录发送消息
        print("\n测试 2: 记录发送消息")
        logger.log_sent(content="测试消息")
        assert len(logger._session_log) == 1
        print("✅ 记录发送消息成功")
        
        # 测试 3: 记录接收消息
        print("\n测试 3: 记录接收消息")
        logger.log_received(content="回复消息")
        assert len(logger._session_log) == 2
        print("✅ 记录接收消息成功")
        
        # 测试 4: 记录多条消息
        print("\n测试 4: 记录多条消息")
        for i in range(3):
            logger.log_sent(content=f"消息 {i+1}")
            logger.log_received(content=f"回复 {i+1}")
        assert len(logger._session_log) == 8
        print("✅ 记录多条消息成功")
        
        # 测试 5: 获取统计信息
        print("\n测试 5: 获取统计信息")
        stats = logger.get_stats()
        print(f"   总交互数: {stats['total_interactions']}")
        print(f"   发送消息数: {stats['sent_count']}")
        print(f"   接收消息数: {stats['received_count']}")
        assert stats['sent_count'] == 4
        assert stats['received_count'] == 4
        print("✅ 获取统计信息成功")
        
        # 测试 6: 获取会话日志
        print("\n测试 6: 获取会话日志")
        session_log = logger.get_session_log()
        assert len(session_log) == 8
        print(f"✅ 获取会话日志成功，共 {len(session_log)} 条记录")
        
        # 测试 7: 保存会话
        print("\n测试 7: 保存会话")
        saved_path = logger.save_session()
        assert saved_path is not None
        assert saved_path.exists()
        print(f"✅ 保存会话成功，文件: {saved_path.name}")
        
        # 测试 8: 验证日志文件内容
        print("\n测试 8: 验证日志文件内容")
        with open(saved_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'interactions' in data
            assert len(data['interactions']) == 8
            # 验证第一条记录
            first_record = data['interactions'][0]
            assert first_record['direction'] == 'sent'
            assert first_record['content'] == '测试消息'
            print("✅ 日志文件内容验证成功")
        
        # 测试 9: 清空会话
        print("\n测试 9: 清空会话")
        logger.clear_session()
        assert len(logger._session_log) == 0
        assert logger._session_start is None
        print("✅ 清空会话成功")
        
        # 测试 10: 禁用记录器
        print("\n测试 10: 禁用记录器")
        logger.set_enabled(False)
        logger.start_session()
        logger.log_sent(content="不应该被记录")
        logger.log_received(content="不应该被记录")
        assert len(logger._session_log) == 0  # 数量不变
        print("✅ 禁用记录器成功")
        
        # 测试 11: 重新启用
        print("\n测试 11: 重新启用")
        logger.set_enabled(True)
        logger.start_session()
        logger.log_sent(content="应该被记录")
        assert len(logger._session_log) == 1
        print("✅ 重新启用成功")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = test_interaction_logger()
    sys.exit(0 if success else 1)
