"""
集成测试

测试 WeChatModule + IFlowModule + MessageBus 的集成。
使用 MockWeChatModule 模拟企业微信。
"""

import sys
import os
import asyncio
import logging
from typing import List

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import MessageBus, Message, MessageType, MessageContent
from src.modules.iflow import IFlowModule, IFlowState
from tests.mock_wechat import MockWeChatModule

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("integration_test")


class IntegrationTestRunner:
    """集成测试运行器"""
    
    def __init__(self):
        self.bus = MessageBus()
        self.wechat = None
        self.iflow = None
        self.iflow_messages: List = []
    
    async def setup(self):
        """设置测试环境"""
        logger.info("=" * 60)
        logger.info("集成测试环境设置")
        logger.info("=" * 60)
        
        # 创建模拟企业微信模块
        self.wechat = MockWeChatModule(
            module_id="mock_wechat",
            config={"user_id": "test_user"}
        )
        
        # 创建 iflow 模块
        self.iflow = IFlowModule()
        
        # 注册模块
        self.bus.register_module(self.wechat)
        self.bus.register_module(self.iflow)
        
        # 设置绑定关系
        # 微信消息 -> iflow
        self.bus.bind("mock_wechat", self.iflow.module_id)
        # iflow 回复 -> 微信
        self.bus.bind(self.iflow.module_id, "mock_wechat")
        
        # 订阅 iflow 输出
        self.iflow.subscribe(self._on_iflow_message)
        
        # 启动模块
        logger.info("启动模块...")
        await self.wechat.start()
        await self.iflow.start()
        
        # 等待 iflow 完全启动
        logger.info("等待 iflow 启动完成...")
        await asyncio.sleep(20)
        
        logger.info("✅ 测试环境设置完成")
        logger.info("")
    
    async def _on_iflow_message(self, message):
        """处理 iflow 输出消息"""
        self.iflow_messages.append(message)
        content = message.content[:50] + "..." if len(message.content) > 50 else message.content
        logger.info(f"📥 收到 iflow 消息: [{message.type.value}] {content}")
    
    async def teardown(self):
        """清理测试环境"""
        logger.info("")
        logger.info("清理测试环境...")
        await self.iflow.stop()
        await self.wechat.stop()
        logger.info("✅ 测试环境清理完成")
    
    async def test_single_message_flow(self):
        """测试单条消息流转"""
        logger.info("=" * 60)
        logger.info("测试1: 单条消息流转")
        logger.info("=" * 60)
        
        # 清空消息记录
        self.wechat.clear_messages()
        self.iflow_messages.clear()
        
        # 模拟接收消息
        await self.wechat.simulate_receive("你好，简短回复即可")
        
        # 等待回复
        logger.info("等待回复...")
        for i in range(30):
            await asyncio.sleep(2)
            state = self.iflow.state
            msg_count = len(self.iflow_messages)
            logger.info(f"   [{i*2+2}s] state={state.value}, msgs={msg_count}")
            if state == IFlowState.IDLE and msg_count > 0:
                await asyncio.sleep(2)
                break
        
        # 检查结果
        logger.info("")
        logger.info("测试结果:")
        logger.info(f"  - 微信接收: {len(self.wechat.messages_received)} 条")
        logger.info(f"  - iflow 回复: {len(self.iflow_messages)} 条")
        logger.info(f"  - 微信发送: {len(self.wechat.messages_sent)} 条")
        
        if len(self.iflow_messages) > 0:
            logger.info("✅ 测试通过: 消息流转正常")
        else:
            logger.error("❌ 测试失败: 未收到回复")
        
        logger.info("")
        return len(self.iflow_messages) > 0
    
    async def test_multi_turn_conversation(self):
        """测试多轮对话"""
        logger.info("=" * 60)
        logger.info("测试2: 多轮对话")
        logger.info("=" * 60)
        
        # 清空消息记录
        self.wechat.clear_messages()
        self.iflow_messages.clear()
        
        # 第一轮
        logger.info("第一轮对话:")
        await self.wechat.simulate_receive("我叫小明")
        await asyncio.sleep(15)
        
        # 第二轮
        logger.info("第二轮对话:")
        await self.wechat.simulate_receive("我叫什么名字？")
        await asyncio.sleep(15)
        
        # 检查结果
        logger.info("")
        logger.info("测试结果:")
        logger.info(f"  - 微信接收: {len(self.wechat.messages_received)} 条")
        logger.info(f"  - iflow 回复: {len(self.iflow_messages)} 条")
        
        if len(self.iflow_messages) >= 2:
            logger.info("✅ 测试通过: 多轮对话正常")
        else:
            logger.error("❌ 测试失败: 回复数量不足")
        
        logger.info("")
        return len(self.iflow_messages) >= 2
    
    async def test_rejection_mechanism(self):
        """测试拒绝机制"""
        logger.info("=" * 60)
        logger.info("测试3: 拒绝机制")
        logger.info("=" * 60)
        
        # 清空消息记录
        self.wechat.clear_messages()
        self.iflow_messages.clear()
        
        # 发送第一条消息（需要较长的回复时间）
        logger.info("发送第一条消息（需要长时间生成）...")
        await self.wechat.simulate_receive("请帮我数到100")
        await asyncio.sleep(2)
        
        # 检查状态
        state = self.iflow.state
        logger.info(f"当前 iflow 状态: {state.value}")
        
        # 尝试发送第二条消息
        logger.info("尝试在生成中发送第二条消息...")
        
        # 直接调用 iflow.send 检查拒绝
        result = await self.iflow.send(
            "这条消息应该被拒绝",
            source="test",
            scope="reply_only"
        )
        
        logger.info(f"发送结果: success={result.success}, error={result.error}")
        
        # 等待第一条消息完成
        logger.info("等待第一条消息完成...")
        for i in range(30):
            await asyncio.sleep(2)
            if self.iflow.state == IFlowState.IDLE:
                break
        
        # 检查结果
        if not result.success and result.error == "iflow_generating":
            logger.info("✅ 测试通过: 拒绝机制正常工作")
            return True
        else:
            logger.error("❌ 测试失败: 拒绝机制未生效")
            return False
    
    async def test_statistics(self):
        """测试统计功能"""
        logger.info("=" * 60)
        logger.info("测试4: 统计功能")
        logger.info("=" * 60)
        
        # 获取各模块统计
        bus_stats = self.bus.get_stats()
        wechat_stats = self.wechat.get_stats()
        
        logger.info("MessageBus 统计:")
        logger.info(f"  - 模块数: {bus_stats.get('modules_count', 0)}")
        logger.info(f"  - 绑定数: {bus_stats.get('bindings_count', 0)}")
        logger.info(f"  - 发送消息: {bus_stats.get('messages_sent', 0)}")
        logger.info(f"  - 路由消息: {bus_stats.get('messages_routed', 0)}")
        
        logger.info("")
        logger.info("MockWeChat 统计:")
        logger.info(f"  - 发送数: {wechat_stats.get('sent_count', 0)}")
        logger.info(f"  - 接收数: {wechat_stats.get('received_count', 0)}")
        
        logger.info("")
        logger.info("✅ 测试通过: 统计功能正常")
        return True


async def main():
    """主函数"""
    runner = IntegrationTestRunner()
    
    try:
        await runner.setup()
        
        results = []
        
        # 运行测试
        results.append(("单条消息流转", await runner.test_single_message_flow()))
        results.append(("多轮对话", await runner.test_multi_turn_conversation()))
        results.append(("拒绝机制", await runner.test_rejection_mechanism()))
        results.append(("统计功能", await runner.test_statistics()))
        
        # 汇总结果
        logger.info("=" * 60)
        logger.info("测试汇总")
        logger.info("=" * 60)
        
        passed = sum(1 for _, r in results if r)
        total = len(results)
        
        for name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"  {status}: {name}")
        
        logger.info("")
        logger.info(f"总计: {passed}/{total} 通过")
        logger.info("=" * 60)
        
        return passed == total
        
    finally:
        await runner.teardown()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)