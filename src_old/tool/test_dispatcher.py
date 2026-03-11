#!/usr/bin/env python3
"""消息分发器测试程序"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from interactive.message_dispatcher import MessageDispatcher
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


# 订阅者回调函数
async def subscriber1_callback(message: str, metadata: dict):
    """订阅者1的回调"""
    print(f"🔵 [订阅者1] 收到消息: {message}")
    print(f"   元数据: {metadata}")
    await asyncio.sleep(0.1)  # 模拟处理时间


async def subscriber2_callback(message: str, metadata: dict):
    """订阅者2的回调"""
    print(f"🟢 [订阅者2] 收到消息: {message}")
    print(f"   元数据: {metadata}")
    await asyncio.sleep(0.2)  # 模拟处理时间


async def subscriber3_callback(message: str, metadata: dict):
    """订阅者3的回调"""
    print(f"🟡 [订阅者3] 收到消息: {message}")
    print(f"   元数据: {metadata}")
    await asyncio.sleep(0.05)  # 模拟处理时间


async def test_basic_subscription():
    """测试基本的订阅和广播功能"""
    print("\n" + "=" * 70)
    print("测试1: 基本订阅和广播")
    print("=" * 70)
    
    # 获取分发器实例
    dispatcher = MessageDispatcher()
    
    # 清除之前的订阅者
    dispatcher.clear_all()
    
    # 注册订阅者
    print("\n[步骤1] 注册订阅者...")
    dispatcher.subscribe("subscriber1", subscriber1_callback)
    dispatcher.subscribe("subscriber2", subscriber2_callback)
    print(f"当前订阅者: {dispatcher.get_subscribers()}")
    print(f"订阅者数量: {dispatcher.get_subscriber_count()}")
    
    # 广播消息
    print("\n[步骤2] 广播第一条消息...")
    success = await dispatcher.broadcast(
        "这是第一条测试消息",
        {"source": "test", "type": "broadcast"}
    )
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)
    
    # 广播第二条消息
    print("\n[步骤3] 广播第二条消息...")
    success = await dispatcher.broadcast(
        "这是第二条测试消息",
        {"source": "iflow", "type": "interactive"}
    )
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)


async def test_unsubscribe():
    """测试取消订阅功能"""
    print("\n" + "=" * 70)
    print("测试2: 取消订阅")
    print("=" * 70)
    
    # 获取分发器实例
    dispatcher = MessageDispatcher()
    
    # 注册订阅者
    print("\n[步骤1] 注册3个订阅者...")
    dispatcher.subscribe("subscriber1", subscriber1_callback)
    dispatcher.subscribe("subscriber2", subscriber2_callback)
    dispatcher.subscribe("subscriber3", subscriber3_callback)
    print(f"当前订阅者: {dispatcher.get_subscribers()}")
    
    await asyncio.sleep(0.5)
    
    # 广播消息
    print("\n[步骤2] 广播消息...")
    success = await dispatcher.broadcast("所有订阅者都应该收到这条消息")
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)
    
    # 取消订阅者2
    print("\n[步骤3] 取消订阅者2...")
    dispatcher.unsubscribe("subscriber2")
    print(f"当前订阅者: {dispatcher.get_subscribers()}")
    
    # 广播消息
    print("\n[步骤4] 再次广播消息（订阅者2不应该收到）...")
    success = await dispatcher.broadcast("订阅者2不应该收到这条消息")
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)


async def test_no_subscribers():
    """测试没有订阅者时的广播"""
    print("\n" + "=" * 70)
    print("测试3: 没有订阅者")
    print("=" * 70)
    
    # 获取分发器实例
    dispatcher = MessageDispatcher()
    
    # 清除所有订阅者
    print("\n[步骤1] 清除所有订阅者...")
    count = dispatcher.clear_all()
    print(f"清除了 {count} 个订阅者")
    
    await asyncio.sleep(0.5)
    
    # 广播消息
    print("\n[步骤2] 广播消息（应该跳过）...")
    success = await dispatcher.broadcast("这条消息不应该发送给任何人")
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)


async def test_error_handling():
    """测试错误处理"""
    print("\n" + "=" * 70)
    print("测试4: 错误处理")
    print("=" * 70)
    
    # 获取分发器实例
    dispatcher = MessageDispatcher()
    dispatcher.clear_all()
    
    # 正常订阅者
    dispatcher.subscribe("normal", subscriber1_callback)
    
    # 错误的订阅者（会抛出异常）
    async def error_callback(message: str, metadata: dict):
        raise Exception("模拟的错误")
    
    dispatcher.subscribe("error_subscriber", error_callback)
    
    print(f"\n[步骤1] 注册了2个订阅者（1个正常，1个会出错）")
    print(f"当前订阅者: {dispatcher.get_subscribers()}")
    
    await asyncio.sleep(0.5)
    
    # 广播消息
    print("\n[步骤2] 广播消息（应该处理错误）...")
    success = await dispatcher.broadcast("测试错误处理")
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)


async def test_metadata():
    """测试元数据传递"""
    print("\n" + "=" * 70)
    print("测试5: 元数据传递")
    print("=" * 70)
    
    # 获取分发器实例
    dispatcher = MessageDispatcher()
    dispatcher.clear_all()
    
    # 注册订阅者
    dispatcher.subscribe("test", subscriber1_callback)
    
    await asyncio.sleep(0.5)
    
    # 广播带有详细元数据的消息
    print("\n[步骤1] 广播带有详细元数据的消息...")
    success = await dispatcher.broadcast(
        "测试元数据",
        {
            "source": "iflow",
            "type": "interactive",
            "timestamp": "2026-03-09T21:00:00Z",
            "user": "test_user",
            "priority": "high"
        }
    )
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)


async def test_singleton():
    """测试单例模式"""
    print("\n" + "=" * 70)
    print("测试6: 单例模式")
    print("=" * 70)
    
    # 创建多个实例
    print("\n[步骤1] 创建多个分发器实例...")
    dispatcher1 = MessageDispatcher()
    dispatcher2 = MessageDispatcher()
    dispatcher3 = MessageDispatcher()
    
    print(f"dispatcher1 ID: {id(dispatcher1)}")
    print(f"dispatcher2 ID: {id(dispatcher2)}")
    print(f"dispatcher3 ID: {id(dispatcher3)}")
    print(f"是否是同一个实例: {dispatcher1 is dispatcher2 is dispatcher3}")
    
    # 使用 dispatcher1 注册订阅者
    print("\n[步骤2] 使用 dispatcher1 注册订阅者...")
    dispatcher1.subscribe("test", subscriber1_callback)
    print(f"dispatcher1 订阅者: {dispatcher1.get_subscribers()}")
    print(f"dispatcher2 订阅者: {dispatcher2.get_subscribers()}")
    print(f"dispatcher3 订阅者: {dispatcher3.get_subscribers()}")
    
    await asyncio.sleep(0.5)
    
    # 使用 dispatcher2 广播消息
    print("\n[步骤3] 使用 dispatcher2 广播消息...")
    success = await dispatcher2.broadcast("测试单例模式")
    print(f"发送成功: {success} 个订阅者")
    
    await asyncio.sleep(1)


async def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("消息分发器测试程序")
    print("=" * 70)
    
    try:
        # 运行所有测试
        await test_basic_subscription()
        await test_unsubscribe()
        await test_no_subscribers()
        await test_error_handling()
        await test_metadata()
        await test_singleton()
        
        # 清理
        print("\n" + "=" * 70)
        print("测试完成，清理资源...")
        print("=" * 70)
        dispatcher = MessageDispatcher()
        count = dispatcher.clear_all()
        print(f"清除了 {count} 个订阅者")
        
        print("\n✅ 所有测试完成！")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被中断")
    except Exception as e:
        print(f"\n\n❌ 测试出错: {e}")
        logger.error("测试出错", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
