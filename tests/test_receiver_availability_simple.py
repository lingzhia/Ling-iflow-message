"""
测试接收方可用性检查和错误回复功能（简化版）
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core import MessageBus, ModuleManager, Message, MessageContent, MessageType
from src.modules import WeChatChannel, IFlowModule


async def test_receiver_availability_check():
    """测试接收方可用性检查"""
    print("开始测试：接收方可用性检查")
    
    # 创建消息总线和模块管理器
    bus = MessageBus()
    manager = ModuleManager(message_bus=bus)
    bus.module_manager = manager
    
    # 创建 WeChat 模拟渠道
    wechat = await manager.create_module(
        module_type="wechat",
        module_id="wechat_test",
        config={
            "name": "test_wechat",
            "corp_id": "test_corp_id",
            "agent_id": "test_agent_id",
            "secret": "test_secret",
            "user_id": "test_user",
            "token": "test_token",
            "encoding_aes_key": "test_key"
        }
    )
    wechat.set_manager(manager)
    await manager.register_module("wechat_test")
    
    # 创建 IFlow 模块（但不启动）
    iflow = await manager.create_module(
        module_type="iflow",
        module_id="iflow_test",
        config={
            "tmux_session": "test_iflow",
            "auto_restart": False
        }
    )
    iflow.manager = manager
    await manager.register_module("iflow_test")
    
    # 绑定消息路由：wechat -> iflow
    bus.bind("wechat_test", "iflow_test")
    
    print(f"✅ 模块注册成功")
    print(f"  - WeChat: {wechat.module_id}, 运行状态: {wechat._running}")
    print(f"  - IFlow: {iflow.module_id}, 运行状态: {iflow._running}")
    
    # 测试 1：模块未运行时，检查接收方可用性
    print("\n测试 1：模块未运行时，检查接收方可用性")
    availability = await manager.check_receiver_availability("iflow_test")
    print(f"接收方可用性: {availability}")
    
    if not availability["available"]:
        print(f"✅ 正确判断接收方不可用")
        print(f"  - 错误类型: {availability['error']}")
        print(f"  - 错误消息: {availability['error_message']}")
        
        if availability["error"] == "MODULE_NOT_RUNNING":
            print("✅ 错误类型正确")
        else:
            print(f"❌ 错误类型不正确，期望 MODULE_NOT_RUNNING，实际为 {availability['error']}")
    else:
        print("❌ 错误地判断接收方可用")
    
    # 测试 2：启动 WeChat 模块后，检查接收方可用性
    print("\n测试 2：启动 WeChat 模块后，检查接收方可用性")
    start_result = await manager.start_module("wechat_test")
    print(f"启动结果: {start_result}")
    
    availability = await manager.check_receiver_availability("iflow_test")
    print(f"接收方可用性: {availability}")
    
    if not availability["available"]:
        print(f"✅ 正确判断接收方不可用（IFlow 未启动）")
        print(f"  - 错误类型: {availability['error']}")
    else:
        print("❌ 错误地判断接收方可用")
    
    # 测试 3：启动 IFlow 模块后，检查接收方可用性
    print("\n测试 3：启动 IFlow 模块后，检查接收方可用性")
    start_result = await manager.start_module("iflow_test")
    print(f"启动结果: {start_result}")
    
    # 等待启动完成
    await asyncio.sleep(2)
    
    availability = await manager.check_receiver_availability("iflow_test")
    print(f"接收方可用性: {availability}")
    
    if availability["available"]:
        print(f"✅ 正确判断接收方可用")
    else:
        print(f"❌ 错误地判断接收方不可用")
        print(f"  - 错误类型: {availability['error']}")
        print(f"  - 错误消息: {availability['error_message']}")
        print(f"  - 详情: {availability.get('details', {})}")
    
    # 测试 4：消息路由测试（接收方未运行时应该返回 False）
    print("\n测试 4：消息路由测试（接收方未运行时应该返回 False）")
    await manager.stop_module("iflow_test")
    await asyncio.sleep(1)
    
    test_message = Message(
        id="test_msg_1",
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="测试消息"),
        from_module="wechat_test",
        to_module="iflow_test"
    )
    
    result = await bus.route(test_message)
    print(f"路由结果: {result}")
    
    if not result:
        print("✅ 正确返回 False（接收方不可用）")
    else:
        print("❌ 错误地返回 True")
    
    # 测试 5：消息路由测试（接收方运行时应该返回 True）
    print("\n测试 5：消息路由测试（接收方运行时应该返回 True）")
    start_result = await manager.start_module("iflow_test")
    await asyncio.sleep(2)
    
    test_message_2 = Message(
        id="test_msg_2",
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="测试消息2"),
        from_module="wechat_test",
        to_module="iflow_test"
    )
    
    result = await bus.route(test_message_2)
    print(f"路由结果: {result}")
    
    if result:
        print("✅ 正确返回 True（接收方可用）")
    else:
        print("❌ 错误地返回 False")
    
    # 清理
    await manager.stop_module("wechat_test")
    await manager.stop_module("iflow_test")
    await manager.destroy_module("wechat_test")
    await manager.destroy_module("iflow_test")
    
    print("\n✅ 测试完成")


async def main():
    """运行所有测试"""
    try:
        await test_receiver_availability_check()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())