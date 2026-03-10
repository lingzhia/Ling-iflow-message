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
import subprocess
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
COLOR_RED = "\033[31m"
COLOR_RESET = "\033[0m"


def print_success(message: str) -> None:
    """打印成功消息。"""
    print(f"{COLOR_GREEN}✓{COLOR_RESET} {message}")


def print_warning(message: str) -> None:
    """打印警告消息。"""
    print(f"{COLOR_YELLOW}⚠{COLOR_RESET} {message}")


def print_error(message: str) -> None:
    """打印错误消息。"""
    print(f"{COLOR_RED}✗{COLOR_RESET} {message}")


def print_info(message: str) -> None:
    """打印信息消息。"""
    print(f"{COLOR_BLUE}ℹ{COLOR_RESET} {message}")


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
        """启动机器人（测试模式）。
        
        注意：测试模式下不调用 WechatBot.start()，因为它会进入无限循环。
        而是只初始化组件并启动后台监控。
        """
        try:
            self.bot = WechatBot(
                config_path=str(self.config_path),
                bot_name=self.bot_name,
                test_mode=True  # 测试模式
            )
            
            # 设置运行标志
            self.bot.running = True
            
            # 直接调用测试模式的初始化逻辑，避免进入无限循环
            await self.bot._start_test_mode()
            
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


async def auto_setup(bot_name: str, config_path: str) -> None:
    """自动设置 iflow 和 wechat_bot。
    
    功能：
    1. 检查 iflow 是否运行，如果没有运行就启动
    2. 检查 wechat_bot 是否运行（非测试模式），如果运行了就停止并重新以测试模式启动
    3. 如果 wechat_bot 没有运行，就以测试模式启动
    
    Args:
        bot_name: 机器人名称
        config_path: 配置文件路径
    """
    print()
    print("=" * 70)
    print(f"{COLOR_CYAN}自动设置模式{COLOR_RESET}")
    print("=" * 70)
    print()
    
    # 加载配置
    import json
    config_file = Path(config_path)
    if not config_file.exists():
        print_error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 查找机器人配置
    bot_config = None
    for bot in config.get('bots', []):
        if bot.get('name') == bot_name:
            bot_config = bot
            break
    
    if not bot_config:
        print_error(f"机器人配置不存在: {bot_name}")
        sys.exit(1)
    
    tmux_session = bot_config.get('tmux_session', 'iflow')
    
    # 1. 检查并启动 iflow
    print_info(f"检查 iflow CLI (tmux 会话: {tmux_session})...")
    
    if check_tmux_session(tmux_session):
        print_success(f"iflow CLI 已在 tmux 会话 '{tmux_session}' 中运行")
    else:
        print_info(f"启动 iflow CLI...")
        
        # 查找对应的 tmux 配置
        tmux_config = None
        for session in config.get('tmux_sessions', []):
            if session.get('name') == tmux_session:
                tmux_config = session
                break
        
        if not tmux_config:
            print_error(f"未找到 tmux 会话配置: {tmux_session}")
            sys.exit(1)
        
        model = tmux_config.get('model', 'kimi-k2.5')
        cmd = f"iflow --model {model}"
        
        try:
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", tmux_session, cmd],
                check=True
            )
            print_success(f"iflow CLI 已启动: {tmux_session}")
        except subprocess.CalledProcessError as e:
            print_error(f"启动 iflow CLI 失败: {e}")
            sys.exit(1)
    
    print()
    
    # 2. 检查并启动 wechat_bot（测试模式）
    print_info(f"检查 wechat_bot (机器人: {bot_name})...")
    
    process_manager = ProcessManager(project_root)
    
    if process_manager.is_running(bot_name):
        print_warning(f"wechat_bot 已运行 (机器人: {bot_name})")
        print_info(f"停止并重新以测试模式启动...")
        
        if process_manager.stop_bot(bot_name):
            print_success(f"已停止 wechat_bot")
        else:
            print_error(f"停止 wechat_bot 失败")
            sys.exit(1)
        
        # 等待一下，确保进程完全停止
        await asyncio.sleep(1)
    
    # 以测试模式启动 wechat_bot
    print_info(f"以测试模式启动 wechat_bot...")
    
    try:
        # 使用 subprocess 启动测试模式的 wechat_bot
        python_path = sys.executable
        bot_script = project_root / "wechat_bot.py"
        
        # 日志文件
        log_file = project_root / "logs" / f"wechat_bot_{bot_name}_auto.log"
        
        cmd = [
            python_path,
            str(bot_script),
            "--bot", bot_name,
            "--config", config_path,
            "--test-mode"  # 添加测试模式参数
        ]
        
        # 打开日志文件
        log_handle = open(log_file, 'a')
        
        # 后台运行，输出到日志文件
        process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=log_handle,
            start_new_session=True,
            cwd=str(project_root)
        )
        
        pid = process.pid
        print_success(f"wechat_bot 已启动 (测试模式, PID: {pid})")
        print_info(f"日志文件: {log_file}")
        
        # 等待一下，确保进程启动成功
        await asyncio.sleep(3)
        
        # 检查进程是否仍在运行
        if not process_manager.is_running(bot_name):
            print_error(f"wechat_bot 启动失败")
            print_info(f"请查看日志文件: {log_file}")
            
            # 显示最后几行日志
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        print_info(f"最近日志:")
                        for line in lines[-20:]:
                            print(f"  {line.rstrip()}")
            except Exception:
                pass
            
            sys.exit(1)
        
        # 额外等待，确保初始化完成
        print_info(f"等待 wechat_bot 初始化...")
        await asyncio.sleep(2)
        
    except Exception as e:
        print_error(f"启动 wechat_bot 失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print()
    print_success(f"自动设置完成！")
    print(f"{COLOR_BLUE}iflow CLI:{COLOR_RESET} {tmux_session}")
    print(f"{COLOR_BLUE}wechat_bot:{COLOR_RESET} {bot_name} (测试模式, PID: {pid})")
    print()
    print_info(f"按 {COLOR_YELLOW}Ctrl+C{COLOR_RESET} 可以停止测试并清理资源")
    print()


def check_tmux_session(session_name: str) -> bool:
    """检查 tmux 会话是否存在。
    
    Args:
        session_name: 会话名称
        
    Returns:
        是否存在
    """
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


class ProcessManager:
    """简化的进程管理器（用于检查 wechat_bot 是否运行）。"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.pids_dir = project_root / ".pids"
        self.pids_dir.mkdir(exist_ok=True)
    
    def get_pid_file(self, bot_name: str) -> Path:
        """获取 PID 文件路径。"""
        return self.pids_dir / f"bot_{bot_name}.pid"
    
    def is_running(self, bot_name: str) -> bool:
        """检查机器人是否运行。"""
        pid_file = self.get_pid_file(bot_name)
        
        if not pid_file.exists():
            return False
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            return self._process_exists(pid)
        except Exception:
            return False
    
    def stop_bot(self, bot_name: str) -> bool:
        """停止机器人进程。
        
        返回 True 表示进程已停止（或本就不在运行），
        返回 False 表示停止失败（进程仍在运行）。
        """
        import os
        import signal
        
        # 首先尝试通过 PID 文件停止
        pid_file = self.get_pid_file(bot_name)
        
        if pid_file.exists():
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                if self._process_exists(pid):
                    # 尝试优雅停止
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        # 进程已退出，清理 PID 文件
                        pid_file.unlink()
                        return True
                    
                    # 等待进程结束
                    import time
                    for _ in range(5):
                        time.sleep(0.5)
                        if not self._process_exists(pid):
                            pid_file.unlink()
                            return True
                    else:
                        # 强制终止
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            # 进程已退出
                            pass
                    
                    pid_file.unlink()
                    return True
                else:
                    # PID 文件存在但进程不存在，进程已退出
                    # 清理 PID 文件并返回成功
                    pid_file.unlink()
                    return True
            except Exception:
                # 读取 PID 文件失败，尝试通过进程名查找
                pass
        
        # 如果 PID 文件不存在或读取失败，尝试通过进程名查找
        try:
            # 查找 wechat_bot 进程（包含 bot_name）
            result = subprocess.run(
                ["pgrep", "-f", f"wechat_bot.py.*--bot.*{bot_name}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                # 找到进程，需要停止
                pids = result.stdout.strip().split('\n')
                stopped = False
                for pid_str in pids:
                    try:
                        pid = int(pid_str)
                        if self._process_exists(pid):
                            # 先尝试 SIGTERM
                            try:
                                os.kill(pid, signal.SIGTERM)
                            except ProcessLookupError:
                                continue
                            
                            # 等待进程结束
                            import time
                            for _ in range(3):
                                time.sleep(0.5)
                                if not self._process_exists(pid):
                                    stopped = True
                                    break
                            else:
                                # 强制终止
                                try:
                                    os.kill(pid, signal.SIGKILL)
                                except ProcessLookupError:
                                    stopped = True
                    except (ValueError, OSError):
                        continue
                
                return stopped
            else:
                # 没有找到进程，说明进程已不在运行
                return True
        except Exception:
            pass
        
        # 未知状态，认为失败
        return False
    
    def _process_exists(self, pid: int) -> bool:
        """检查进程是否存在。"""
        try:
            import os
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False


async def main():
    """主函数。"""
    # 创建父 parser，包含共享参数
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--config", "-c",
        default=None,
        help="配置文件路径（默认: 项目根目录/config.json）"
    )
    parent_parser.add_argument(
        "--auto", "-a",
        action="store_true",
        help="自动设置模式：自动检查并启动 iflow 和 wechat_bot（测试模式）"
    )

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

  # 自动设置模式（推荐）
  python tool/wechat_simulator.py interactive bot1 --auto
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="测试命令")

    # 发送命令
    send_parser = subparsers.add_parser("send", help="发送消息", parents=[parent_parser])
    send_parser.add_argument("bot_name", help="机器人名称")
    send_parser.add_argument("message", help="要发送的消息内容")

    # 交互命令
    interactive_parser = subparsers.add_parser("interactive", help="交互模式", parents=[parent_parser])
    interactive_parser.add_argument("bot_name", help="机器人名称")

    # 监听命令
    listen_parser = subparsers.add_parser("listen", help="监听模式", parents=[parent_parser])
    listen_parser.add_argument("bot_name", help="机器人名称")

    # 批量发送命令
    send_sequence_parser = subparsers.add_parser("send-sequence", help="批量发送消息", parents=[parent_parser])
    send_sequence_parser.add_argument("bot_name", help="机器人名称")
    send_sequence_parser.add_argument(
        "messages",
        help="要发送的多条消息（用换行符分隔）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 自动设置模式
    if args.auto:
        config_path = args.config or str(project_root / "config.json")
        await auto_setup(args.bot_name, config_path)

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
        
        # 如果使用了 auto 模式，清理资源
        if args.auto:
            print()
            print_info(f"正在清理资源...")
            
            # 停止测试模式的 wechat_bot
            config_path = args.config or str(project_root / "config.json")
            process_manager = ProcessManager(project_root)
            
            if process_manager.is_running(args.bot_name):
                print_info(f"停止测试模式的 wechat_bot: {args.bot_name}")
                if process_manager.stop_bot(args.bot_name):
                    print_success(f"已停止 wechat_bot")
                else:
                    print_warning(f"停止 wechat_bot 失败")
            
            print()
            print_success(f"清理完成！")
            print()


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
