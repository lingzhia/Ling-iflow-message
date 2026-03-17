"""
测试接收方可用性检查和错误回复功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core import MessageBus, ModuleManager, Message, MessageContent, MessageType
from src.modules import WeChatChannel, IFlowModule


async def test_receiver_unavailable_notification():
    """测试接收方不可用时的错误通知"""
    print("开始测试：接收方不可用时的错误通知")
    
    # 创建消息总线和模块管理器
    bus = MessageBus()
    manager = ModuleManager(message_bus=bus)
    
    # 将 ModuleManager 设置到 MessageBus（用于状态检查）
    bus.module_manager = manager
    
    # 创建 WeChat 模拟渠道
    wechat = WeChatChannel(
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
    
    # 创建 IFlow 模块（但不启动）
    iflow = IFlowModule(
        module_id="iflow_test",
        tmux_session="test_iflow",
        auto_restart=False
    )
    iflow.manager = manager
    
    # 注册模块
    await manager.register_module(wechat)
    await manager.register_module(iflow)
    
    # 绑定消息路由：wechat -> iflow
    bus.bind("wechat_test", "iflow_test")
    
    # 创建测试消息
    test_message = Message(
        id="test_msg_1",
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="测试消息"),
        from_module="wechat_test",
        to_module="iflow_test"
    )
    
    # 测试 1：模块未运行时应该拒绝消息
    print("\n测试 1：模块未运行时应该拒绝消息")
    result = await bus.route(test_message)
    print(f"路由结果: {result}")
    
    # 验证 wechat 是否收到错误消息
    received_messages = wechat.get_received_messages()
    print(f"WeChat 收到的消息数量: {len(received_messages)}")
    
    if received_messages:
        error_msg = received_messages[-1]
        print(f"收到的消息: {error_msg}")
        
        # 检查是否是错误消息
        if hasattr(error_msg, 'metadata'):
            msg_type = error_msg.metadata.get('msg_type', '')
            print(f"消息类型: {msg_type}")
            
            if msg_type == 'error_response':
                print("✅ 正确接收到错误回复")
                error_code = error_msg.metadata.get('error_type', '')
                print(f"错误类型: {error_code}")
                assert error_code == "MODULE_NOT_RUNNING", f"期望错误类型为 MODULE_NOT_RUNNING，实际为 {error_code}"
                print("✅ 错误类型正确")
            else:
                print(f"❌ 未收到错误回复，消息类型为: {msg_type}")
        else:
            print("❌ 消息没有 metadata")
    else:
        print("❌ WeChat 没有收到任何消息")
    
    # 测试 2：启动模块后应该可以正常发送
    print("\n测试 2：启动模块后应该可以正常发送")
    await manager.start_module("wechat_test")
    await manager.start_module("iflow_test")
    
    # 等待启动完成
    await asyncio.sleep(2)
    
    # 创建新消息
    test_message_2 = Message(
        id="test_msg_2",
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="测试消息2"),
        from_module="wechat_test",
        to_module="iflow_test"
    )
    
    # 清空之前的消息
    wechat.clear_received_messages()
    
    # 路由消息
    result = await bus.route(test_message_2)
    print(f"路由结果: {result}")
    
    # 检查状态
    is_running = manager.is_module_running("iflow_test")
    is_healthy = manager.is_module_healthy("iflow_test")
    print(f"IFlow 模块运行状态: {is_running}")
    print(f"IFlow 模块健康状态: {is_healthy}")
    
    # 清理
    await manager.stop_module("wechat_test")
    await manager.stop_module("iflow_test")
    await manager.destroy_module("wechat_test")
    await manager.destroy_module("iflow_test")
    
    print("\n✅ 测试完成")


async def main():
    """运行所有测试"""
    try:
        await test_receiver_unavailable_notification()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())