#!/usr/bin/env python3
"""企业微信测试工具。

支持功能：
- 监听企业微信消息并打印到控制台
- 主动发送消息到企业微信
- 测试企业微信配置

使用方法：
    # 监听模式
    python test_wechat.py listen

    # 发送消息
    python test_wechat.py send "测试消息"

    # 测试配置
    python test_wechat.py test
"""

import asyncio
import argparse
import sys
from pathlib import Path
from loguru import logger

from config.loader import load_config
from channels.wechat_work import WechatWorkChannel


class WechatTester:
    """企业微信测试器。"""

    def __init__(self, config_path: str = "config.json"):
        """初始化测试器。

        Args:
            config_path: 配置文件路径
        """
        self.config = load_config(Path(config_path))
        self.channel = WechatWorkChannel(self.config.wechat_work)
        self.running = False

    async def start(self) -> None:
        """启动企业微信渠道。"""
        logger.info("[测试] 正在启动企业微信渠道...")
        await self.channel.start()
        logger.info("[测试] 企业微信渠道已启动")

    async def stop(self) -> None:
        """停止企业微信渠道。"""
        logger.info("[测试] 正在停止企业微信渠道...")
        self.running = False
        await self.channel.stop()
        logger.info("[测试] 企业微信渠道已停止")

    async def test_config(self) -> None:
        """测试配置。"""
        logger.info("[测试] 开始测试配置...")

        # 检查必要配置
        required_fields = ["corp_id", "agent_id", "secret"]
        for field in required_fields:
            value = getattr(self.config.wechat_work, field, "")
            if not value:
                logger.error(f"[测试] 配置缺少必要字段: {field}")
                return False

        logger.info("[测试] 配置检查通过")
        logger.info(f"[测试] 企业ID: {self.config.wechat_work.corp_id}")
        logger.info(f"[测试] 应用ID: {self.config.wechat_work.agent_id}")
        logger.info(f"[测试] 用户ID: {self.config.wechat_work.user_id}")

        # 测试连接
        try:
            await self.start()
            logger.info("[测试] 企业微信连接成功 ✓")
            await self.stop()
            return True
        except Exception as e:
            logger.error(f"[测试] 企业微信连接失败: {e}")
            return False

    async def listen(self) -> None:
        """监听企业微信消息。"""
        self.running = True

        # 设置消息处理器
        async def handle_message(content: str, sender_id: str, chat_id: str,
                                is_group: bool, metadata: dict) -> None:
            """处理接收到的消息。"""
            timestamp = metadata.get("create_time", "0")
            msg_type = metadata.get("msg_type", "text")

            print("\n" + "=" * 70)
            print(f"[📨 收到消息]")
            print("=" * 70)
            print(f"发送者: {sender_id}")
            print(f"聊天ID: {chat_id}")
            print(f"类型: {'群聊' if is_group else '私聊'}")
            print(f"消息类型: {msg_type}")
            print(f"时间戳: {timestamp}")
            print(f"内容:")
            print("-" * 70)
            print(content)
            print("=" * 70)
            print()

        self.channel.set_message_handler(handle_message)

        # 启动渠道
        await self.start()

        # 保持运行
        logger.info("[测试] 监听模式已启动，等待企业微信消息...")
        logger.info("[测试] 按 Ctrl+C 停止")

        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("[测试] 收到停止信号")
        finally:
            await self.stop()

    async def send(self, message: str, chat_id: str = None) -> None:
        """发送消息到企业微信。

        Args:
            message: 消息内容
            chat_id: 聊天 ID（可选，默认使用配置的用户ID）
        """
        if not chat_id:
            chat_id = self.config.wechat_work.user_id

        if not chat_id:
            logger.error("[测试] 未指定聊天ID，请在配置中设置 user_id")
            return

        logger.info(f"[测试] 正在发送消息到 {chat_id}...")
        logger.info(f"[测试] 消息内容: {message}")

        await self.start()

        try:
            success = await self.channel.send(message, chat_id)
            if success:
                logger.info("[测试] 消息发送成功 ✓")
            else:
                logger.error("[测试] 消息发送失败 ✗")
        except Exception as e:
            logger.error(f"[测试] 发送消息时出错: {e}")
        finally:
            await self.stop()


async def main():
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="企业微信测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试配置
  python test_wechat.py test

  # 监听消息
  python test_wechat.py listen

  # 发送消息
  python test_wechat.py send "你好"

  # 指定配置文件
  python test_wechat.py --config custom.json send "测试"
        """
    )

    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="配置文件路径（默认: config.json）"
    )

    subparsers = parser.add_subparsers(dest="command", help="测试命令")

    # 测试命令
    subparsers.add_parser("test", help="测试企业微信配置")

    # 监听命令
    listen_parser = subparsers.add_parser("listen", help="监听企业微信消息")

    # 发送命令
    send_parser = subparsers.add_parser("send", help="发送消息到企业微信")
    send_parser.add_argument(
        "message",
        help="要发送的消息内容"
    )
    send_parser.add_argument(
        "--chat-id",
        help="接收者聊天ID（默认使用配置中的user_id）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 创建测试器
    tester = WechatTester(args.config)

    # 执行命令
    if args.command == "test":
        success = await tester.test_config()
        sys.exit(0 if success else 1)

    elif args.command == "listen":
        await tester.listen()

    elif args.command == "send":
        await tester.send(args.message, args.chat_id)


if __name__ == "__main__":
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    # 运行主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[测试] 程序已退出")
        sys.exit(0)
