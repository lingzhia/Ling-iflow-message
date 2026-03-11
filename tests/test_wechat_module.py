"""
测试 WeChatModule
"""

import sys
import os
import asyncio
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules import WeChatModule


async def test_wechat_module_creation():
    """测试 WeChatModule 创建"""
    # 创建 WeChatModule（测试配置）
    config = {
        "corp_id": "test_corp_id",
        "agent_id": 1000001,
        "secret": "test_secret",
        "token": "test_token",
        "encoding_aes_key": "test_key",
        "callback_port": 8788,
        "user_id": "test_user"
    }
    
    wechat = WeChatModule(
        module_id="wechat_test",
        config=config
    )
    
    assert wechat.module_id == "wechat_test"
    assert wechat.config["corp_id"] == "test_corp_id"
    print("✅ test_wechat_module_creation passed")


async def test_wechat_module_attributes():
    """测试 WeChatModule 属性"""
    config = {
        "corp_id": "test_corp_id",
        "agent_id": 1000001,
        "secret": "test_secret",
        "token": "test_token",
        "encoding_aes_key": "test_key",
        "callback_port": 8788,
        "user_id": "test_user"
    }
    
    wechat = WeChatModule(
        module_id="wechat_test",
        config=config
    )
    
    # 检查子模块
    assert hasattr(wechat, 'channel')
    print("✅ test_wechat_module_attributes passed")


async def main():
    """运行所有测试"""
    tests = [
        test_wechat_module_creation,
        test_wechat_module_attributes,
    ]
    
    print("=" * 60)
    print("开始测试 WeChatModule")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)