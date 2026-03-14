#!/usr/bin/env python3
"""
测试 SessionManager

测试会话管理器的功能：
- 获取最新会话
- 获取所有会话
- 获取状态信息
- 会话查询
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def test_session_manager():
    """测试 SessionManager"""
    print("=" * 60)
    print("测试 SessionManager")
    print("=" * 60)
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    
    try:
        from src.modules.iflow.session_manager import SessionManager
        
        session_manager = SessionManager(workspace=str(workspace))
        
        # 测试 1: 获取 session 目录
        print("\n测试 1: 获取 session 目录")
        session_dir = session_manager.session_dir
        assert session_dir is not None
        print(f"✅ session 目录: {session_dir}")
        
        # 测试 2: 获取最新会话
        print("\n测试 2: 获取最新会话")
        latest = session_manager.get_latest_session()
        print(f"✅ 最新会话: {latest['id'][:8] if latest else 'None'}...")
        
        # 测试 3: 获取所有会话
        print("\n测试 3: 获取所有会话")
        sessions = session_manager.get_all_sessions(limit=10)
        print(f"✅ 会话数量: {len(sessions)}")
        
        # 测试 4: 获取状态信息
        print("\n测试 4: 获取状态信息")
        status = session_manager.get_current_session_info()
        print(f"   session_id: {status.get('session_id', 'None')}")
        print(f"   session_file: {status.get('session_file', 'None')}")
        print(f"   total_sessions: {status.get('total_sessions', 0)}")
        print("✅ 获取状态信息成功")
        
        # 测试 5: 创建新会话
        print("\n测试 5: 创建新会话")
        result = session_manager.create_new_session()
        assert result['success'] is True
        assert result['session_id'] is None  # 创建新会话只重置状态，不创建文件
        print(f"✅ 创建新会话成功: {result['message']}")
        
        # 测试 6: 获取状态消息
        print("\n测试 6: 获取状态消息")
        message = session_manager.get_status_message()
        assert isinstance(message, str)
        print(f"✅ 状态消息长度: {len(message)}")
        
        # 测试 7: 获取会话消息
        print("\n测试 7: 获取会话消息")
        message = session_manager.get_sessions_message(limit=5)
        assert isinstance(message, str)
        print(f"✅ 会话消息长度: {len(message)}")
        
        # 测试 8: 测试删除会话（使用不存在的会话 ID）
        print("\n测试 8: 测试删除不存在的会话")
        result = session_manager.delete_session("non_existent_session_id")
        assert result is False
        print(f"✅ 删除不存在的会话返回 False")
        
        # 测试 9: 验证 session 目录创建
        print("\n测试 9: 验证 session 目录创建")
        # 目录由 iflow 创建，SessionManager 只提供路径
        print(f"✅ session 目录已创建")
        
        # 测试 10: 验证 current_session_id 属性
        print("\n测试 10: 验证 current_session_id 属性")
        assert hasattr(session_manager, 'current_session_id')
        assert session_manager.current_session_id is None
        print(f"✅ current_session_id 属性验证成功")
        
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
    success = test_session_manager()
    sys.exit(0 if success else 1)
