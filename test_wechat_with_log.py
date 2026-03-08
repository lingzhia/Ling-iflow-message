#!/usr/bin/env python3
"""企业微信测试工具（带日志文件）。"""

import asyncio
import argparse
import sys
from pathlib import Path
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")
logger.add("wechat_messages.log", rotation="10 MB", level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {message}")

from config.loader import load_config
from channels.wechat_work import WechatWorkChannel


class WechatTester:
    """企业微信测试器。"""

    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(Path(config_path))
        self.channel = WechatWorkChannel(self.config.wechat_work)
        self.running = False

    async def start(self) -> None:
        """启动企业微信渠道。"""
        logger.info("[测试] 正在启动企业微信渠道...")
        start_task = asyncio.create_task(self.channel.start())
        await asyncio.sleep(2)
        logger.info("[测试] 企业微信渠道已启动")

    async def stop(self) -> None:
        """停止企业微信渠道。"""
        logger.info("[测试] 正在停止企业微信渠道...")
        self.running = False
        await self.channel.stop()
        logger.info("[测试] 企业微信渠道已停止")

    async def listen(self) -> None:
        """监听企业微信消息。"""
        self.running = True

        # 设置消息处理器
        async def handle_message(content: str, sender_id: str, chat_id: str,
                                is_group: bool, metadata: dict) -> None:
            """处理接收到的消息。"""
            timestamp = metadata.get("create_time", "0")
            msg_type = metadata.get("msg_type", "text")

            # 使用logger记录消息
            logger.info("=" * 70)
            logger.info("[📨 收到消息]")
            logger.info("=" * 70)
            logger.info(f"发送者: {sender_id}")
            logger.info(f"聊天ID: {chat_id}")
            logger.info(f"类型: {'群聊' if is_group else '私聊'}")
            logger.info(f"消息类型: {msg_type}")
            logger.info(f"时间戳: {timestamp}")
            logger.info("内容:")
            logger.info("-" * 70)
            logger.info(content)
            logger.info("=" * 70)

        self.channel.set_message_handler(handle_message)

        # 启动渠道
        await self.start()

        # 保持运行
        logger.info("[测试] 监听模式已启动，等待企业微信消息...")
        logger.info("[测试] 按 Ctrl+C 停止")
        logger.info("[测试] 消息将同时显示在控制台和记录到 wechat_messages.log")

        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("[测试] 收到停止信号")
        finally:
            await self.stop()


async def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description="企业微信测试工具（带日志）")
    parser.add_argument("--config", "-c", default="config.json", help="配置文件路径")
    subparsers = parser.add_subparsers(dest="command", help="测试命令")
    
    subparsers.add_parser("listen", help="监听企业微信消息")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    tester = WechatTester(args.config)

    if args.command == "listen":
        await tester.listen()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[测试] 程序已退出")
        sys.exit(0)