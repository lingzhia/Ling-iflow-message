"""
测试 IFlowModule
"""

import sys
import os
import asyncio
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules import IFlowModule


async def test_iflow_module_creation():
    """测试 IFlowModule 创建"""
    # 创建 IFlowModule（不自动启动 iflow）
    iflow = IFlowModule(
        module_id="iflow_test",
        tmux_session="iflow_test",
        model="kimi-k2.5",
        auto_restart=False  # 测试模式不启动实际的 iflow
    )
    
    assert iflow.module_id == "iflow_test"
    assert iflow.tmux_session == "iflow_test"
    assert iflow.model == "kimi-k2.5"
    print("✅ test_iflow_module_creation passed")


async def test_iflow_module_attributes():
    """测试 IFlowModule 属性"""
    iflow = IFlowModule(
        module_id="iflow_test",
        tmux_session="iflow_test",
        model="kimi-k2.5",
        auto_restart=False
    )
    
    # 检查子模块
    assert hasattr(iflow, 'controller')
    assert hasattr(iflow, 'monitor')
    print("✅ test_iflow_module_attributes passed")


async def main():
    """运行所有测试"""
    tests = [
        test_iflow_module_creation,
        test_iflow_module_attributes,
    ]
    
    print("=" * 60)
    print("开始测试 IFlowModule")
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