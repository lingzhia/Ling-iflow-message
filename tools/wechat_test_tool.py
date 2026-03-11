#!/usr/bin/env python3
"""
企业微信测试工具（新版本）

基于新架构的企业微信消息测试工具。

使用方法：
    # 监听消息
    python tools/wechat_test_tool.py listen

    # 发送消息
    python tools/wechat_test_tool.py send "测试消息"
"""

import sys
import os
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules import WeChatModule, IFlowModule
from src.core import MessageBus, Message, MessageType, MessageContent

# 配置日志
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "wechat_test.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("wechat_test")


class WeChatTestTool:
    """企业微信测试工具"""
    
    def __init__(self):
        """初始化测试工具"""
        # 加载配置
        config_path = project_root / "config.json"
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.bus = MessageBus()
        self.wechat_module = None
        self.iflow_module = None
        self.running = False
        self.messages_received = []
        
        # 订阅企业微信消息
        self.bus.subscribe(f"wechat.wechat_test", self._on_wechat_message)
    
    async def _on_wechat_message(self, message: Message):
        """处理接收到的企业微信消息"""
        logger.info(f"\n📨 收到企业微信消息:")
        logger.info(f"   发送者: {message.user_id}")
        logger.info(f"   聊天ID: {message.chat_id}")
        logger.info(f"   内容: {message.content.text}")
        logger.info(f"   时间: {message.timestamp}")
        logger.info("")
        self.messages_received.append(message)
    
    async def listen(self):
        """监听企业微信消息"""
        # 获取第一个启用的机器人配置
        bot_config = None
        for bot in self.config.get("bots", []):
            if bot.get("enabled", False):
                bot_config = bot
                break
        
        if not bot_config:
            logger.error("❌ 没有找到启用的机器人配置")
            return
        
        logger.info(f"🔧 使用机器人: {bot_config['name']}")
        logger.info(f"📡 监听端口: {bot_config['callback_port']}")
        logger.info(f"👤 用户ID: {bot_config['user_id']}")
        logger.info(f"🔗 回调URL: http://be.mmszxc.xin:{bot_config['callback_port']}/wechat/callback")
        logger.info("")
        logger.info("⏳ 等待企业微信消息...")
        logger.info("   (在企业微信中发送消息，我会在这里显示)")
        logger.info("")
        
        # 创建企业微信模块
        self.wechat_module = WeChatModule(
            module_id="wechat_test",
            config=bot_config
        )
        
        # 注册模块
        self.bus.register_module(self.wechat_module)
        
        # 启动模块
        await self.wechat_module.start()
        self.running = True
        
        logger.info("✅ 已启动监听服务")
        logger.info("")
        
        # 保持运行
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n⏹️  停止监听")
        
        # 停止模块
        await self.wechat_module.stop()
        logger.info("✅ 已停止监听服务")
    
    async def send(self, message: str):
        """发送消息到企业微信"""
        # 获取第一个启用的机器人配置
        bot_config = None
        for bot in self.config.get("bots", []):
            if bot.get("enabled", False):
                bot_config = bot
                break
        
        if not bot_config:
            logger.error("❌ 没有找到启用的机器人配置")
            return
        
        logger.info(f"🔧 使用机器人: {bot_config['name']}")
        logger.info(f"📤 发送消息: {message}")
        logger.info(f"👤 接收者: {bot_config['user_id']}")
        logger.info("")
        
        # 创建企业微信模块
        self.wechat_module = WeChatModule(
            module_id="wechat_test",
            config=bot_config
        )
        
        # 注册模块
        self.bus.register_module(self.wechat_module)
        
        # 启动模块
        await self.wechat_module.start()
        
        # 创建消息
        msg = Message(
            id=Message.generate_id(),
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text=message),
            from_module="test",
            to_module="wechat_test"
        )
        
        # 发送消息
        logger.info("⏳ 正在发送...")
        success = await self.wechat_module.send_to_bus(msg)
        
        if success:
            logger.info("✅ 消息发送成功")
        else:
            logger.error("❌ 消息发送失败")
        
        # 停止模块
        await self.wechat_module.stop()
        
        return success


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="企业微信测试工具")
    parser.add_argument("command", choices=["listen", "send"], help="命令：listen 或 send")
    parser.add_argument("message", nargs="?", help="要发送的消息（仅在 send 命令时使用）")
    
    args = parser.parse_args()
    
    tool = WeChatTestTool()
    
    if args.command == "listen":
        await tool.listen()
    elif args.command == "send":
        if not args.message:
            logger.error("❌ 请提供要发送的消息")
            sys.exit(1)
        await tool.send(args.message)


if __name__ == "__main__":
    asyncio.run(main())
