"""
Integration Tests

Test the integration of the entire architecture.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_flow():
    """Test basic message flow"""
    from src.core import MessageBus, Message, MessageType, BaseModule, MessageContent
    from src.modules import IFlowModule, WeChatModule
    
    # Create message bus
    bus = MessageBus()
    logger.info("✓ Message bus created successfully")
    
    # Create iflow module (test mode, don't start actual iflow)
    iflow_module = IFlowModule(
        module_id="iflow_test",
        tmux_session="iflow_test",
        model="kimi-k2.5",
        auto_start=False  # Test mode, don't start actual iflow
    )
    
    # Register iflow module
    bus.register_module(iflow_module)
    logger.info("✓ IFlowModule registered successfully")
    
    # Create wechat module (test config)
    wechat_config = {
        "corp_id": "test_corp_id",
        "agent_id": 1000001,
        "secret": "test_secret",
        "token": "test_token",
        "encoding_aes_key": "test_key",
        "callback_port": 8788,
        "user_id": "test_user"
    }
    
    wechat_module = WeChatModule(
        module_id="wechat_test",
        config=wechat_config
    )
    
    # Register wechat module
    bus.register_module(wechat_module)
    logger.info("✓ WeChatModule registered successfully")
    
    # Establish binding
    bus.bind("wechat_test", "iflow_test")
    logger.info("✓ Binding established: wechat_test -> iflow_test")
    
    # Start all modules
    await bus.start_all()
    logger.info("✓ All modules started successfully")
    
    # Test message format
    test_message = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Test message"),
        from_module="wechat_test",
        to_module="iflow_test"
    )
    logger.info(f"✓ Test message created: {test_message}")
    
    # Test serialization/deserialization
    json_str = test_message.to_json()
    restored_message = Message.from_json(json_str)
    assert restored_message.content == test_message.content
    logger.info("✓ Message serialization/deserialization test passed")
    
    # View bus status
    logger.info(f"\nMessage bus status:")
    logger.info(f"  Registered modules: {bus.list_modules()}")
    logger.info(f"  Bindings: {bus.list_bindings()}")
    logger.info(f"  Stats: {bus.get_stats()}")
    
    # Wait for a while
    logger.info("\nWaiting 5 seconds...")
    await asyncio.sleep(5)
    
    # Stop all modules
    await bus.stop_all()
    logger.info("✓ All modules stopped")
    
    logger.info("\n✅ Basic flow test passed!")


async def test_multiple_instances():
    """Test multiple instances scenario"""
    from src.core import MessageBus
    from src.modules import IFlowModule
    
    # Create message bus
    bus = MessageBus()
    logger.info("✓ Message bus created successfully")
    
    # Create multiple iflow instances
    instances = []
    for i in range(1, 4):
        module = IFlowModule(
            module_id=f"iflow_test_{i}",
            tmux_session=f"iflow_test_{i}",
            model="kimi-k2.5",
            auto_start=False
        )
        bus.register_module(module)
        instances.append(module)
        logger.info(f"✓ IFlowModule {i} registered successfully")
    
    # View bus status
    logger.info(f"\nMessage bus status:")
    logger.info(f"  Registered modules: {bus.list_modules()}")
    logger.info(f"  Module count: {len(bus.list_modules())}")
    
    logger.info("\n✅ Multiple instances test passed!")


async def test_message_routing():
    """Test message routing"""
    from src.core import MessageBus, Message, MessageType
    
    # Create message bus
    bus = MessageBus()
    
    # Create mock modules
    class MockModule:
        def __init__(self, module_id):
            self.module_id = module_id
            self.messages_received = []
        
        async def receive(self, message):
            self.messages_received.append(message)
    
    module1 = MockModule("module1")
    module2 = MockModule("module2")
    
    # Register modules
    bus.modules["module1"] = module1
    bus.modules["module2"] = module2
    
    # Establish binding
    bus.bind("module1", "module2")
    
    # Create test message
    message = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content="Test routing message",
        from_module="module1",
        to_module="module2"
    )
    
    # Route message
    await bus.route(message)
    
    # Verify
    assert len(module2.messages_received) == 1
    assert module2.messages_received[0].content == "Test routing message"
    
    logger.info("✅ Message routing test passed!")


async def test_pub_sub():
    """Test publish-subscribe mechanism"""
    from src.core import MessageBus, Message, MessageType
    
    # Create message bus
    bus = MessageBus()
    
    # Create subscribers
    messages_received = []
    
    async def subscriber1(message):
        messages_received.append(("sub1", message))
    
    async def subscriber2(message):
        messages_received.append(("sub2", message))
    
    # Subscribe to topics
    bus.subscribe("test_topic", subscriber1)
    bus.subscribe("test_topic", subscriber2)
    
    # Create test message
    message = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content="Test broadcast message",
        from_module="test_module"
    )
    
    # Publish message
    await bus.publish("test_topic", message)
    
    # Verify
    assert len(messages_received) == 2
    assert messages_received[0][0] == "sub1"
    assert messages_received[1][0] == "sub2"
    
    logger.info("✅ Publish-subscribe test passed!")


async def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("Starting Integration Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Basic Flow Test", test_basic_flow),
        ("Multiple Instances Test", test_multiple_instances),
        ("Message Routing Test", test_message_routing),
        ("Publish-Subscribe Test", test_pub_sub),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Test: {name}")
        logger.info(f"{'=' * 60}")
        
        try:
            await test_func()
            passed += 1
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            failed += 1
    
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Tests completed: {passed} passed, {failed} failed")
    logger.info(f"{'=' * 60}")
    
    if failed == 0:
        logger.info("✅ All tests passed!")
    else:
        logger.error("❌ Some tests failed")


if __name__ == "__main__":
    asyncio.run(main())
