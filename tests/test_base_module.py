"""
测试 BaseModule 类
"""

import sys
import os
import asyncio
import logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import BaseModule, MessageBus, Message, MessageType, MessageContent


class TestModule(BaseModule):
    """测试模块实现"""
    
    def __init__(self, module_id: str):
        super().__init__(module_id)
        self.started = False
        self.received_messages = []
        self.logger = logging.getLogger(f"test.{module_id}")
    
    async def _on_start(self) -> None:
        """启动时的钩子方法"""
        self.started = True
        self.logger.info(f"[{self.module_id}] 模块已启动")
    
    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        self.started = False
        self.logger.info(f"[{self.module_id}] 模块已停止")
    
    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法"""
        self.received_messages.append(message)
        self.logger.info(f"[{self.module_id}] 收到消息: {message.content.text}")


async def test_module_lifecycle():
    """测试模块生命周期"""
    module = TestModule("test_module")
    
    # 测试启动
    await module.start()
    assert module.running
    assert module.started
    print("✅ test_module_lifecycle - start passed")
    
    # 测试停止
    await module.stop()
    assert not module.running
    assert not module.started
    print("✅ test_module_lifecycle - stop passed")
    
    # 测试多次启动
    await module.start()
    await module.start()  # 不应该报错
    assert module.running
    print("✅ test_module_lifecycle - multiple start passed")
    
    await module.stop()


async def test_message_bus_integration():
    """测试消息总线集成"""
    bus = MessageBus()
    module = TestModule("test_module")
    
    # 测试设置消息总线
    module.set_message_bus(bus)
    assert module.message_bus is bus
    print("✅ test_message_bus_integration - set passed")
    
    # 测试消息总线连接
    bus.register_module(module)
    assert "test_module" in bus.modules
    print("✅ test_message_bus_integration - connect passed")
    
    # 测试发送消息
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Test message"),
        from_module="test",
        to_module="test_module"
    )
    await bus.send_to_module(msg)
    assert len(module.received_messages) == 1
    print("✅ test_message_bus_integration - send passed")


async def test_background_task():
    """测试后台任务管理"""
    module = TestModule("test_module")
    
    # 创建一个简单的后台任务
    async def simple_task():
        for i in range(3):
            await asyncio.sleep(0.1)
    
    # 启动后台任务
    await module.start()
    module.create_background_task(simple_task())
    assert len(module._tasks) == 1
    print("✅ test_background_task - start passed")
    
    # 等待任务完成
    await asyncio.sleep(0.5)
    print("✅ test_background_task - wait passed")
    
    # 停止模块
    await module.stop()
    assert not module._tasks
    print("✅ test_background_task - cleanup passed")


async def test_multiple_background_tasks():
    """测试多个后台任务"""
    module = TestModule("test_module")
    
    # 创建多个后台任务
    async def task1():
        for i in range(2):
            await asyncio.sleep(0.1)
    
    async def task2():
        for i in range(2):
            await asyncio.sleep(0.1)
    
    # 启动多个后台任务
    await module.start()
    module.create_background_task(task1())
    module.create_background_task(task2())
    assert len(module._tasks) == 2
    print("✅ test_multiple_background_tasks - start passed")
    
    # 等待任务完成
    await asyncio.sleep(0.5)
    
    # 停止模块
    await module.stop()
    assert not module._tasks
    print("✅ test_multiple_background_tasks - cleanup passed")


async def test_receive_message():
    """测试接收消息"""
    module = TestModule("test_module")
    
    # 创建测试消息
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Test message"),
        from_module="test",
        to_module="test_module"
    )
    
    # 接收消息
    await module.receive(msg)
    assert len(module.received_messages) == 1
    assert module.received_messages[0].content.text == "Test message"
    print("✅ test_receive_message passed")


async def main():
    """运行所有测试"""
    tests = [
        test_module_lifecycle,
        test_message_bus_integration,
        test_background_task,
        test_multiple_background_tasks,
        test_receive_message,
    ]
    
    print("=" * 60)
    print("开始测试 BaseModule 类")
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