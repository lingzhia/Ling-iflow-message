#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""企业微信模拟器 - 通过 WechatBot 测试消息交互。

使用 WechatBot 的测试模式，模拟企业微信消息交互。
不启动 HTTP 服务器，直接调用消息处理逻辑。

使用方法：
    # 发送消息
    python tool/wechat_simulator.py send bot1 "测试消息"

    # 交互模式
    python tool/wechat_simulator.py interactive bot1

    # 监听模式（只监听 iflow 回复）
    python tool/wechat_simulator.py listen bot1

    # 批量发送（发送多条消息）
    python tool/wechat_simulator.py send-sequence bot1 "第一条\n第二条\n第三条"

    # 命令模式（发送命令）
    python tool/wechat_simulator.py send bot1 "/run 帮我写一个Python脚本"
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Optional
from loguru import logger

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from wechat_bot import WechatBot

# 颜色配置
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[36m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"


class WechatSimulator:
    """企业微信模拟器。"""

    def __init__(self, bot_name: str, config_path: str = None):
        """初始化模拟器。

        Args:
            bot_name: 机器人名称
            config_path: 配置文件路径（可选）
        """
        self.bot_name = bot_name
        self.config_path = config_path or (project_root / "config.json")
        self.bot: Optional[WechatBot] = None
        self.message_count = 0

    async def start(self) -> None:
        """启动机器人（测试模式）。"""
        try:
            self.bot = WechatBot(
                config_path=str(self.config_path),
                bot_name=self.bot_name,
                test_mode=True  # 测试模式
            )
            await self.bot.start()
            logger.info(f"[WechatSimulator] 机器人已启动（测试模式）: {self.bot_name}")
        except Exception as e:
            logger.error(f"[WechatSimulator] 启动机器人失败: {e}")
            print(f"{COLOR_YELLOW}[错误] 启动机器人失败: {e}{COLOR_RESET}")
            raise

    async def stop(self) -> None:
        """停止机器人。"""
        if self.bot:
            await self.bot.stop()
            logger.info(f"[WechatSimulator] 机器人已停止: {self.bot_name}")

    async def send_message(self, message: str) -> None:
        """发送消息。

        Args:
            message: 消息内容
        """
        if not self.bot:
            raise RuntimeError("机器人未启动，请先调用 start()")

        self.message_count += 1
        print()
        print(f"{COLOR_CYAN}[发送消息 #{self.message_count}]{COLOR_RESET}")
        print(f"{COLOR_BLUE}内容: {message}{COLOR_RESET}")
        print()

        try:
            await self.bot.send_message(message)
            logger.info(f"[WechatSimulator] 消息已发送: {message[:50]}...")
        except Exception as e:
            logger.error(f"[WechatSimulator] 发送消息失败: {e}")
            print(f"{COLOR_YELLOW}[错误] 发送消息失败: {e}{COLOR_RESET}")

    async def listen_mode(self) -> None:
        """监听模式（只监听 iflow 回复）。"""
        print()
        print("=" * 70)
        print("企业微信模拟器 - 监听模式")
        print("=" * 70)
        print(f"{COLOR_BLUE}机器人: {self.bot_name}{COLOR_RESET}")
        print(f"{COLOR_BLUE}模式: 只监听 iflow 回复{COLOR_RESET}")
        print(f"{COLOR_BLUE}提示: 按 Ctrl+C 停止{COLOR_RESET}")
        print("=" * 70)
        print()

        try:
            await self.bot.listen()
        except Exception as e:
            logger.error(f"[WechatSimulator] 监听失败: {e}")
            print(f"{COLOR_YELLOW}[错误] 监听失败: {e}{COLOR_RESET}")
            raise

    async def interactive_mode(self) -> None:
        """交互模式。"""
        print()
        print("=" * 70)
        print("企业微信模拟器 - 交互模式")
        print("=" * 70)
        print(f"{COLOR_BLUE}机器人: {self.bot_name}{COLOR_RESET}")
        print()
        print(f"{COLOR_CYAN}内置命令:{COLOR_RESET}")
        print(f"  quit/exit/q  - 退出程序")
        print(f"  clear        - 清屏")
        print(f"  help         - 显示帮助")
        print()
        print(f"{COLOR_CYAN}命令行功能:{COLOR_RESET}")
        print(f"  ↑↓ 方向键    - 浏览历史记录")
        print(f"  ←→ 方向键    - 移动光标")
        print(f"  Backspace    - 删除字符")
        print(f"  Home/End     - 跳到行首/行尾")
        print(f"  Ctrl+C       - 退出程序")
        print()
        print("=" * 70)
        print()

        # 启用 readline 支持
        import readline
        history_file = project_root / "tool" / ".wechat_simulator_history"

        try:
            if history_file.exists():
                readline.read_history_file(str(history_file))
        except Exception as e:
            logger.warning(f"读取历史记录失败: {e}")

        readline.set_history_length(1000)

        def save_history():
            try:
                readline.write_history_file(str(history_file))
            except Exception as e:
                logger.warning(f"保存历史记录失败: {e}")

        import atexit
        atexit.register(save_history)

        running = True
        while running:
            try:
                user_input = input(f"{COLOR_GREEN}[你]{COLOR_RESET} ").strip()

                # 处理命令
                if user_input in ['quit', 'exit', 'q']:
                    print(f"{COLOR_YELLOW}再见！{COLOR_RESET}")
                    running = False
                    break

                if user_input == 'clear':
                    import os
                    os.system('clear')
                    continue

                if user_input == 'help':
                    self._print_help()
                    continue

                if not user_input:
                    continue

                # 发送消息
                await self.send_message(user_input)

            except EOFError:
                print(f"\n{COLOR_YELLOW}输入结束，正在退出...{COLOR_RESET}")
                break
            except KeyboardInterrupt:
                print(f"\n{COLOR_YELLOW}已中断，正在退出...{COLOR_RESET}")
                running = False
                break
            except Exception as e:
                print(f"{COLOR_YELLOW}错误: {e}{COLOR_RESET}")
                logger.error(f"用户输入错误: {e}", exc_info=True)

        print()
        print(f"{COLOR_CYAN}统计信息:{COLOR_RESET}")
        print(f"  发送消息: {self.message_count} 条")
        print()

    def _print_help(self) -> None:
        """打印帮助信息。"""
        print()
        print(f"{COLOR_CYAN}=== 帮助信息 ==={COLOR_RESET}")
        print(f"{COLOR_CYAN}内置命令:{COLOR_RESET}")
        print(f"  quit/exit/q  - 退出程序")
        print(f"  clear        - 清屏")
        print(f"  help         - 显示此帮助")
        print()
        print(f"{COLOR_CYAN}功能说明:{COLOR_RESET}")
        print(f"  发送消息     - 直接输入消息发送到 iflow")
        print(f"  接收回复     - 自动显示 iflow 的回复")
        print()
        print(f"{COLOR_CYAN}命令行功能:{COLOR_RESET}")
        print(f"  ↑↓ 方向键    - 浏览历史记录")
        print(f"  ←→ 方向键    - 移动光标")
        print(f"  Backspace    - 删除字符")
        print(f"  Home/End     - 跳到行首/行尾")
        print(f"  Ctrl+C       - 退出程序")
        print()


async def main():
    """主函数。"""
    parser = argparse.ArgumentParser(
        description="企业微信模拟器（通过 WechatBot 测试消息交互）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 发送消息
  python tool/wechat_simulator.py send bot1 "测试消息"

  # 交互模式
  python tool/wechat_simulator.py interactive bot1

  # 监听模式（只监听 iflow 回复）
  python tool/wechat_simulator.py listen bot1

  # 批量发送（发送多条消息）
  python tool/wechat_simulator.py send-sequence bot1 "第一条\n第二条\n第三条"

  # 命令模式（发送命令）
  python tool/wechat_simulator.py send bot1 "/run 帮我写一个Python脚本"

  # 指定配置文件
  python tool/wechat_simulator.py --config custom.json interactive bot1
        """
    )

    parser.add_argument(
        "--config", "-c",
        default=None,
        help="配置文件路径（默认: 项目根目录/config.json）"
    )

    subparsers = parser.add_subparsers(dest="command", help="测试命令")

    # 发送命令
    send_parser = subparsers.add_parser("send", help="发送消息")
    send_parser.add_argument("bot_name", help="机器人名称")
    send_parser.add_argument("message", help="要发送的消息内容")

    # 交互命令
    interactive_parser = subparsers.add_parser("interactive", help="交互模式")
    interactive_parser.add_argument("bot_name", help="机器人名称")

    # 监听命令
    listen_parser = subparsers.add_parser("listen", help="监听模式")
    listen_parser.add_argument("bot_name", help="机器人名称")

    # 批量发送命令
    send_sequence_parser = subparsers.add_parser("send-sequence", help="批量发送消息")
    send_sequence_parser.add_argument("bot_name", help="机器人名称")
    send_sequence_parser.add_argument(
        "messages",
        help="要发送的多条消息（用换行符分隔）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 创建模拟器
    simulator = WechatSimulator(args.bot_name, args.config)

    # 启动机器人
    await simulator.start()

    # 执行命令
    try:
        if args.command == "send":
            await simulator.send_message(args.message)
            # 等待一下，让回复有时间显示
            await asyncio.sleep(2)

        elif args.command == "interactive":
            await simulator.interactive_mode()

        elif args.command == "listen":
            await simulator.listen_mode()

        elif args.command == "send-sequence":
            messages = args.messages.split('\n')
            for message in messages:
                message = message.strip()
                if message:
                    await simulator.send_message(message)
                    # 等待一下，让回复有时间显示
                    await asyncio.sleep(2)
    except Exception as e:
        logger.error(f"执行命令失败: {e}")
        print(f"{COLOR_YELLOW}[错误] 执行命令失败: {e}{COLOR_RESET}")
        sys.exit(1)
    finally:
        # 停止机器人
        await simulator.stop()


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
        print(f"\n{COLOR_YELLOW}程序已退出{COLOR_RESET}")
        sys.exit(0)
