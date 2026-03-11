#!/usr/bin/env python3
"""企业微信测试工具（支持多机器人）。

支持功能：
- 列出所有配置的机器人
- 监听指定机器人的企业微信消息
- 通过指定机器人发送消息
- 测试指定机器人的配置
- 查看机器人与 tmux 会话的绑定关系

使用方法：
    # 列出所有机器人
    python tool/wechat_debug.py list

    # 测试机器人配置
    python tool/wechat_debug.py test bot1

    # 监听机器人消息
    python tool/wechat_debug.py listen bot1

    # 通过机器人发送消息
    python tool/wechat_debug.py send bot1 "测试消息"
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Dict, List

# 添加项目根目录到 sys.path，解决模块导入问题
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
import subprocess

from config.loader import load_config
from config.bots_loader import load_bots_config
from config.schema import BotConfig
from channels.wechat_work import WechatWorkChannel

# 颜色配置
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_BLUE = "\033[36m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


class WechatTester:
    """企业微信测试器。"""

    def __init__(self, config_path: str = None):
        """初始化测试器。

        Args:
            config_path: 配置文件路径（可选，默认使用项目根目录的 config.json）
        """
        if config_path is None:
            config_path = project_root / "config.json"
        else:
            config_path = Path(config_path)
        
        self.config_path = config_path
        self.config = load_config(config_path)
        self.bots_config = load_bots_config(config_path)
        self.channel = None
        self.running = False

    def list_bots(self) -> None:
        """列出所有配置的机器人。"""
        bots = self.bots_config.get_enabled_bots()
        
        if not bots:
            print(f"{COLOR_YELLOW}⚠ 没有配置启用的机器人{COLOR_RESET}")
            return
        
        print(f"\n{COLOR_CYAN}{'='*70}{COLOR_RESET}")
        print(f"{COLOR_CYAN}已配置的机器人 ({len(bots)} 个){COLOR_RESET}")
        print(f"{COLOR_CYAN}{'='*70}{COLOR_RESET}\n")
        
        for i, bot in enumerate(bots):
            status = self._check_bot_status(bot)
            status_icon = f"{COLOR_GREEN}✓{COLOR_RESET}" if status['running'] else f"{COLOR_RED}✗{COLOR_RESET}"
            
            print(f"{COLOR_CYAN}{i + 1}.{COLOR_RESET} {COLOR_BOLD}{COLOR_GREEN}{bot.name}{COLOR_RESET}")
            print(f"   状态: {status_icon} {'运行中' if status['running'] else '未运行'}")
            print(f"   回调端口: {bot.callback_port}")
            print(f"   用户ID: {bot.user_id}")
            print(f"   tmux会话: {bot.tmux_session}")
            print(f"   回调URL: http://be.mmszxc.xin:{bot.callback_port}/wechat/callback")
            
            # 检查端口监听
            port_status = self._check_port(bot.callback_port)
            if port_status:
                print(f"   端口状态: {COLOR_GREEN}✓ 监听中 (PID: {port_status}){COLOR_RESET}")
            else:
                print(f"   端口状态: {COLOR_RED}✗ 未监听{COLOR_RESET}")
            
            print()
    
    def _check_bot_status(self, bot: BotConfig) -> Dict:
        """检查机器人状态。
        
        Args:
            bot: 机器人配置
            
        Returns:
            状态字典
        """
        # 检查 tmux 会话是否存在
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True
            )
            tmux_exists = bot.tmux_session in result.stdout
        except:
            tmux_exists = False
        
        # 检查端口监听
        port_status = self._check_port(bot.callback_port)
        running = port_status is not None
        
        return {
            'running': running,
            'tmux_exists': tmux_exists,
            'port_status': port_status
        }
    
    def _check_port(self, port: int) -> str:
        """检查端口是否被监听。
        
        Args:
            port: 端口号
            
        Returns:
            PID 或 None
        """
        try:
            # 尝试使用 netstat
            result = subprocess.run(
                ["netstat", "-tlnp", "2>/dev/null"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if f":{port}" in line and 'LISTEN' in line:
                        parts = line.split()
                        if len(parts) >= 7:
                            return parts[6]
        except:
            pass
        
        return None

    def _init_channel(self, bot_name: str) -> bool:
        """初始化指定机器人的渠道。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            是否成功
        """
        bot = self.bots_config.get_bot_by_name(bot_name)
        if not bot:
            print(f"{COLOR_RED}✗ 机器人 '{bot_name}' 不存在或未启用{COLOR_RESET}")
            return False
        
        self.channel = WechatWorkChannel(bot)
        return True

    async def test_config(self, bot_name: str) -> bool:
        """测试指定机器人的配置。

        Args:
            bot_name: 机器人名称
            
        Returns:
            是否成功
        """
        if not self._init_channel(bot_name):
            return False
        
        bot = self.bots_config.get_bot_by_name(bot_name)
        
        print(f"\n{COLOR_CYAN}{'='*70}{COLOR_RESET}")
        print(f"{COLOR_CYAN}测试机器人配置: {bot_name}{COLOR_RESET}")
        print(f"{COLOR_CYAN}{'='*70}{COLOR_RESET}\n")
        
        logger.info(f"[测试] 开始测试配置: {bot_name}")

        # 检查必要配置
        required_fields = ["corp_id", "agent_id", "secret", "user_id"]
        missing_fields = []
        
        for field in required_fields:
            value = getattr(bot, field, "")
            if not value:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"{COLOR_RED}✗ 配置检查失败：缺少必要字段: {', '.join(missing_fields)}{COLOR_RESET}")
            return False
        
        print(f"{COLOR_GREEN}✓ 配置检查通过{COLOR_RESET}")
        print(f"  企业ID: {bot.corp_id}")
        print(f"  应用ID: {bot.agent_id}")
        print(f"  用户ID: {bot.user_id}")
        print(f"  回调端口: {bot.callback_port}")
        print(f"  tmux会话: {bot.tmux_session}")
        
        # 检查 tmux 会话
        status = self._check_bot_status(bot)
        print(f"  tmux会话: {COLOR_GREEN}✓ 存在{COLOR_RESET}" if status['tmux_exists'] else f"{COLOR_RED}✗ 不存在{COLOR_RESET}")
        
        # 检查端口
        port_status = self._check_port(bot.callback_port)
        if port_status:
            print(f"  端口监听: {COLOR_GREEN}✓ 监听中 (PID: {port_status}){COLOR_RESET}")
        else:
            print(f"  端口监听: {COLOR_RED}✗ 未监听{COLOR_RESET}")
        
        # 测试连接
        print()
        try:
            await self.start()
            print(f"{COLOR_GREEN}✓ 企业微信连接成功{COLOR_RESET}")
            await self.stop()
            return True
        except Exception as e:
            print(f"{COLOR_RED}✗ 企业微信连接失败: {e}{COLOR_RESET}")
            logger.error(f"[测试] 企业微信连接失败: {e}", exc_info=True)
            return False

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

    async def listen(self, bot_name: str) -> None:
        """监听指定机器人的企业微信消息。

        Args:
            bot_name: 机器人名称
        """
        if not self._init_channel(bot_name):
            return
        
        bot = self.bots_config.get_bot_by_name(bot_name)
        self.running = True

        print(f"\n{COLOR_CYAN}{'='*70}{COLOR_RESET}")
        print(f"{COLOR_CYAN}监听模式: {bot_name}{COLOR_RESET}")
        print(f"{COLOR_CYAN}{'='*70}{COLOR_RESET}\n")
        print(f"{COLOR_BLUE}ℹ 回调URL: http://be.mmszxc.xin:{bot.callback_port}/wechat/callback{COLOR_RESET}")
        print(f"{COLOR_BLUE}ℹ 用户ID: {bot.user_id}{COLOR_RESET}")
        print(f"{COLOR_BLUE}ℹ tmux会话: {bot.tmux_session}{COLOR_RESET}")
        print(f"{COLOR_BLUE}ℹ 按 Ctrl+C 停止{COLOR_RESET}\n")

        # 设置消息处理器
        async def handle_message(content: str, sender_id: str, chat_id: str,
                                is_group: bool, metadata: dict) -> None:
            """处理接收到的消息。"""
            timestamp = metadata.get("create_time", "0")
            msg_type = metadata.get("msg_type", "text")

            print("\n" + "=" * 70)
            print(f"[📨 {bot_name} 收到消息]")
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
        logger.info(f"[测试] {bot_name} 监听模式已启动，等待企业微信消息...")
        logger.info("[测试] 按 Ctrl+C 停止")

        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("[测试] 收到停止信号")
        finally:
            await self.stop()

    async def send(self, bot_name: str, message: str, chat_id: str = None) -> None:
        """通过指定机器人发送消息到企业微信。

        Args:
            bot_name: 机器人名称
            message: 消息内容
            chat_id: 聊天 ID（可选，默认使用机器人配置的用户ID）
        """
        if not self._init_channel(bot_name):
            return
        
        bot = self.bots_config.get_bot_by_name(bot_name)
        
        if not chat_id:
            chat_id = bot.user_id

        if not chat_id:
            print(f"{COLOR_RED}✗ 未指定聊天ID，机器人配置中也没有设置 user_id{COLOR_RESET}")
            return

        print(f"\n{COLOR_CYAN}{'='*70}{COLOR_RESET}")
        print(f"{COLOR_CYAN}发送消息: {bot_name}{COLOR_RESET}")
        print(f"{COLOR_CYAN}{'='*70}{COLOR_RESET}\n")
        print(f"接收者: {chat_id}")
        print(f"消息内容: {message}")
        print()

        await self.start()

        try:
            success = await self.channel.send(message, chat_id)
            if success:
                print(f"{COLOR_GREEN}✓ 消息发送成功{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}✗ 消息发送失败{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}✗ 发送消息时出错: {e}{COLOR_RESET}")
            logger.error(f"[测试] 发送消息时出错: {e}", exc_info=True)
        finally:
            await self.stop()


async def main():
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="企业微信测试工具（支持多机器人）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有机器人
  python tool/wechat_debug.py list

  # 测试机器人配置
  python tool/wechat_debug.py test bot1

  # 监听机器人消息
  python tool/wechat_debug.py listen bot1

  # 通过机器人发送消息
  python tool/wechat_debug.py send bot1 "测试消息"

  # 指定配置文件
  python tool/wechat_debug.py --config custom.json list
        """
    )

    parser.add_argument(
        "--config", "-c",
        default=None,
        help="配置文件路径（默认: 项目根目录/config.json）"
    )

    subparsers = parser.add_subparsers(dest="command", help="测试命令")

    # 列出命令
    subparsers.add_parser("list", help="列出所有配置的机器人")

    # 测试命令
    test_parser = subparsers.add_parser("test", help="测试指定机器人的配置")
    test_parser.add_argument("bot_name", help="机器人名称")

    # 监听命令
    listen_parser = subparsers.add_parser("listen", help="监听指定机器人的消息")
    listen_parser.add_argument("bot_name", help="机器人名称")

    # 发送命令
    send_parser = subparsers.add_parser("send", help="通过指定机器人发送消息")
    send_parser.add_argument("bot_name", help="机器人名称")
    send_parser.add_argument(
        "message",
        help="要发送的消息内容"
    )
    send_parser.add_argument(
        "--chat-id",
        help="接收者聊天ID（默认使用机器人配置中的user_id）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 创建测试器
    tester = WechatTester(args.config)

    # 执行命令
    if args.command == "list":
        tester.list_bots()

    elif args.command == "test":
        success = await tester.test_config(args.bot_name)
        sys.exit(0 if success else 1)

    elif args.command == "listen":
        await tester.listen(args.bot_name)

    elif args.command == "send":
        await tester.send(args.bot_name, args.message, args.chat_id)


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
        print(f"\n{COLOR_YELLOW}ℹ 程序已退出{COLOR_RESET}")
        sys.exit(0)
