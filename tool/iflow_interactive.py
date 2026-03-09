#!/usr/bin/env python3
"""iflow 交互式测试工具 - 使用 BotIntegration 统一处理"""

import asyncio
from datetime import datetime
from pathlib import Path
from loguru import logger
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 启用 readline 支持，提供命令行编辑功能
import readline

# 配置日志：只写入文件，不输出到控制台
tool_dir = Path(__file__).parent
log_file = tool_dir / "iflow_interactive.log"
logger.remove()  # 移除默认的 handler
logger.add(
    log_file,
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    encoding="utf-8"
)

from interactive.bot_integration import BotIntegration
from interactive.iflow_controller import IFlowController

# 颜色配置
COLOR_USER = "\033[32m"      # 绿色
COLOR_AI = "\033[36m"        # 青色
COLOR_SYSTEM = "\033[33m"    # 黄色
COLOR_RESET = "\033[0m"


class MockWeChatChannel:
    """模拟企业微信渠道，用于测试。
    
    不真正发送到企业微信，只是打印到控制台。
    """
    
    def __init__(self):
        self.message_count = 0
        self.name = "MockWeChat"
        
        # 模拟配置（后台监控需要）
        self.config = MockConfig()
    
    async def send(self, content, chat_id, is_group=False, **kwargs):
        """模拟发送消息（打印到控制台）"""
        self.message_count += 1
        time_str = datetime.now().strftime("%H:%M:%S")
        
        import sys
        print()
        print(f"{COLOR_AI}[iflow 回复] #{self.message_count} ({time_str}){COLOR_RESET}")
        print(f"{COLOR_AI}{content}{COLOR_RESET}")
        print()
        sys.stdout.flush()
        
        logger.info(f"[MockWeChat] 发送消息 #{self.message_count}: {content[:50]}")
        
        return True
    
    def set_message_handler(self, handler):
        """设置消息处理器（测试模式不需要）"""
        pass
    
    def set_send_callback(self, callback):
        """设置发送回调（测试模式不需要）"""
        pass


class MockConfig:
    """模拟配置对象。"""
    
    def __init__(self):
        self.user_id = "test_user"  # 模拟用户 ID


class IFlowTester:
    """iflow 测试器（使用 BotIntegration）。
    
    复用 BotIntegration 的处理逻辑，与企业微信使用相同的处理方法。
    """
    
    def __init__(self, tmux_session="iflow", workspace="~/.iflow", extract_all_messages=False):
        """初始化测试器。

        Args:
            tmux_session: tmux 会话名称
            workspace: iflow 工作目录
            extract_all_messages: 是否提取全部消息（包括非✦标记的消息）
        """
        self.tmux_session = tmux_session
        self.workspace = workspace
        self.extract_all_messages = extract_all_messages
        self.running = False
        self.message_count = 0

        # 创建模拟渠道
        self.mock_channel = MockWeChatChannel()

        # 创建 IFlowController（用于状态检查）
        self.controller = IFlowController(tmux_session)

        # 创建 BotIntegration（与企业微信使用相同的逻辑）
        self.bot = BotIntegration(
            wechat_channel=self.mock_channel,
            tmux_session=tmux_session,
            workspace=workspace,
            filter_thinking=True,  # 过滤思考消息
            extract_all_messages=extract_all_messages  # 是否提取全部消息
        )

        # 配置 readline 历史记录
        self._setup_readline()
        
        # 测试模式：tool（工具模式）/ iflow（模拟 iflow 交互界面）
        self.mode = "tool"
    
    def _setup_readline(self):
        """配置 readline 模块，提供命令行编辑功能。"""
        # 设置历史记录文件
        history_file = tool_dir / ".iflow_history"

        try:
            # 尝试读取历史记录
            if history_file.exists():
                readline.read_history_file(str(history_file))
        except Exception as e:
            logger.warning(f"读取历史记录失败: {e}")

        # 设置历史记录长度
        readline.set_history_length(1000)

        # 配置自动补全
        self._setup_autocomplete()

        # 保存历史记录的函数
        def save_history():
            try:
                readline.write_history_file(str(history_file))
            except Exception as e:
                logger.warning(f"保存历史记录失败: {e}")

        # 注册退出时保存历史记录
        import atexit
        atexit.register(save_history)

    def _setup_autocomplete(self):
        """配置命令自动补全。"""
        commands = ['quit', 'exit', 'q', 'clear', 'status', 'help', 'mode']

        def completer(text, state):
            """命令补全函数。"""
            options = [cmd for cmd in commands if cmd.startswith(text)]
            if state < len(options):
                return options[state]
            return None

        readline.set_completer(completer)
        readline.parse_and_bind('tab: complete')  # Tab 键触发补全

    def _check_iflow_status(self):
        """检查 iflow 状态。"""
        if not self.controller.check_tmux_session():
            print(f"{COLOR_SYSTEM}✗ iflow tmux 会话不存在{COLOR_RESET}")
            print(f"{COLOR_SYSTEM}请先启动 iflow: tmux new-session -d -s {self.tmux_session} \"iflow --model kimi-k2.5\"{COLOR_RESET}")
            return False

        if not self.controller.check_iflow_running():
            print(f"{COLOR_SYSTEM}✗ iflow 未运行{COLOR_RESET}")
            return False

        return True
    
    async def test_message(self, message: str, enable_background_monitor=False):
        """测试单条消息。

        Args:
            message: 要测试的消息
            enable_background_monitor: 是否启用后台监控
        """
        if not self._check_iflow_status():
            return

        self.message_count += 1

        # 启动后台监控（如果启用）
        if enable_background_monitor:
            print(f"{COLOR_SYSTEM}✓ 正在启动后台监控...{COLOR_RESET}")
            background_task = asyncio.create_task(self.bot.start_background_monitor())
            print(f"{COLOR_SYSTEM}✓ 后台监控已启动{COLOR_RESET}")
            print()

        # 直接调用 BotIntegration 的处理逻辑
        chat_id = "test_user"
        is_group = False

        try:
            await self.bot.handle_message(message, "test_user", chat_id, is_group, source=self.mode)
        except Exception as e:
            print(f"{COLOR_SYSTEM}✗ 处理失败: {e}{COLOR_RESET}")
            logger.error(f"处理消息失败: {e}", exc_info=True)
    
    async def monitor_mode(self):
        """纯监听模式（只监听 iflow 交互界面的消息，不发送任何消息）。"""
        print()
        print("=" * 70)
        print("iflow 交互界面监听模式")
        print("=" * 70)
        print(f"{COLOR_SYSTEM}功能:{COLOR_RESET}")
        print(f"  只监听 iflow 交互界面的消息")
        print(f"  不发送任何消息")
        print(f"  按 Ctrl+C 退出")
        print("=" * 70)
        print()
        
        # 检查 iflow 状态
        if not self._check_iflow_status():
            return
        
        try:
            # 启动后台监控
            print(f"{COLOR_SYSTEM}✓ 正在启动后台监控...{COLOR_RESET}")
            background_task = asyncio.create_task(self.bot.start_background_monitor())
            print(f"{COLOR_SYSTEM}✓ 后台监控已启动{COLOR_RESET}")
            
            # 注册到消息分发器
            from interactive.message_dispatcher import MessageDispatcher
            dispatcher = MessageDispatcher()
            
            # 定义回调函数
            async def monitor_callback(message: str, metadata: dict) -> None:
                """分发器回调：打印消息到控制台"""
                try:
                    self.message_count += 1
                    time_str = datetime.now().strftime("%H:%M:%S")
                    
                    print()
                    print(f"{COLOR_AI}[iflow 回复] #{self.message_count} ({time_str}){COLOR_RESET}")
                    print(f"{COLOR_AI}{message}{COLOR_RESET}")
                    print()
                    sys.stdout.flush()
                    
                    logger.info(f"[MockWeChat] 收到分发器消息 #{self.message_count}: {message[:50]}")
                except Exception as e:
                    logger.error(f"[MockWeChat] 分发器回调失败: {e}")
            
            # 注册回调
            dispatcher.subscribe("iflow_monitor", monitor_callback)
            print(f"{COLOR_SYSTEM}✓ 已注册到消息分发器{COLOR_RESET}")
            
            print(f"{COLOR_SYSTEM}✓ 正在监听 iflow 交互界面的消息...{COLOR_RESET}")
            print()
            print(f"{COLOR_SYSTEM}提示: 在 tmux 中发送消息，会自动显示在这里{COLOR_RESET}")
            print()
            
            # 持续运行，直到用户中断
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print()
            print(f"{COLOR_SYSTEM}✓ 监听已停止{COLOR_RESET}")
            
            # 取消分发器注册
            dispatcher.unsubscribe("iflow_monitor")
            print(f"{COLOR_SYSTEM}✓ 已取消消息分发器注册{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_SYSTEM}✗ 监听错误: {e}{COLOR_RESET}")
            logger.error(f"监听错误: {e}", exc_info=True)
    
    async def interactive_mode(self, enable_background_monitor=False):
        """交互式模式。
        
        Args:
            enable_background_monitor: 是否启用后台监控（模拟企业微信）
        """
        print()
        print("=" * 70)
        print("iflow 交互式测试工具")
        print("=" * 70)
        print(f"{COLOR_SYSTEM}内置命令:{COLOR_RESET}")
        print(f"  quit/exit/q  - 退出程序")
        print(f"  clear        - 清屏")
        print(f"  status       - 查看状态")
        print(f"  mode         - 切换测试模式（tool/iflow）")
        print(f"  help         - 显示帮助")
        print()
        print(f"{COLOR_SYSTEM}命令行功能:{COLOR_RESET}")
        print(f"  ↑↓ 方向键    - 浏览历史记录")
        print(f"  ←→ 方向键    - 移动光标")
        print(f"  Backspace    - 删除字符")
        print(f"  Home/End     - 跳到行首/行尾")
        print(f"  Tab          - 命令补全")
        print(f"  Ctrl+C       - 退出程序")
        print()
        print(f"{COLOR_SYSTEM}当前模式: 工具模式（不发企业微信）{COLOR_RESET}")
        print(f"{COLOR_SYSTEM}输入 'mode' 切换到 iflow 模拟模式（合并发送企业微信）{COLOR_RESET}")
        if enable_background_monitor:
            print(f"{COLOR_SYSTEM}后台监控: 已启用（可接收 iflow 交互界面的消息）{COLOR_RESET}")
        print("=" * 70)
        print()
        
        # 检查 iflow 状态
        if not self._check_iflow_status():
            return
        
        self.running = True
        
        # 启动后台监控（接收 iflow 交互界面的消息）
        if enable_background_monitor:
            print(f"{COLOR_SYSTEM}✓ 正在启动后台监控...{COLOR_RESET}")
            background_task = asyncio.create_task(self.bot.start_background_monitor())
            print(f"{COLOR_SYSTEM}✓ 后台监控已启动{COLOR_RESET}")
            
            # 注册到消息分发器
            from interactive.message_dispatcher import MessageDispatcher
            dispatcher = MessageDispatcher()
            
            # 定义回调函数
            async def tool_callback(message: str, metadata: dict) -> None:
                """分发器回调：打印消息到控制台"""
                try:
                    self.message_count += 1
                    time_str = datetime.now().strftime("%H:%M:%S")
                    
                    print()
                    print(f"{COLOR_AI}[iflow 回复] #{self.message_count} ({time_str}){COLOR_RESET}")
                    print(f"{COLOR_AI}{message}{COLOR_RESET}")
                    print()
                    sys.stdout.flush()
                    
                    logger.info(f"[MockWeChat] 收到分发器消息 #{self.message_count}: {message[:50]}")
                except Exception as e:
                    logger.error(f"[MockWeChat] 分发器回调失败: {e}")
            
            # 注册回调
            dispatcher.subscribe("iflow_tool", tool_callback)
            print(f"{COLOR_SYSTEM}✓ 已注册到消息分发器{COLOR_RESET}")
            print()
        
        while self.running:
            try:
                user_input = input(f"{COLOR_USER}[你]{COLOR_RESET} ").strip()

                # 处理命令
                if user_input in ['quit', 'exit', 'q']:
                    print(f"{COLOR_SYSTEM}再见！{COLOR_RESET}")
                    self.running = False
                    
                    # 取消分发器注册
                    if enable_background_monitor:
                        from interactive.message_dispatcher import MessageDispatcher
                        dispatcher = MessageDispatcher()
                        dispatcher.unsubscribe("iflow_tool")
                        print(f"{COLOR_SYSTEM}✓ 已取消消息分发器注册{COLOR_RESET}")
                    
                    break

                if user_input == 'clear':
                    import os
                    os.system('clear')
                    continue

                if user_input == 'status':
                    self._print_status(enable_background_monitor)
                    continue

                if user_input == 'help':
                    self._print_help()
                    continue
                
                if user_input == 'mode':
                    # 切换模式
                    self.mode = "iflow" if self.mode == "tool" else "tool"
                    mode_name = "工具模式（不发企业微信）" if self.mode == "tool" else "iflow 模拟模式（合并发送企业微信）"
                    print(f"{COLOR_SYSTEM}✓ 已切换到：{mode_name}{COLOR_RESET}")
                    continue

                if not user_input:
                    continue

                # 调用测试消息
                await self.test_message(user_input)

            except EOFError:
                print(f"\n{COLOR_SYSTEM}输入结束，正在退出...{COLOR_RESET}")
                break
            except KeyboardInterrupt:
                print(f"\n{COLOR_SYSTEM}已中断，正在退出...{COLOR_RESET}")
                self.running = False
                break
            except Exception as e:
                print(f"{COLOR_SYSTEM}错误: {e}{COLOR_RESET}")
                logger.error(f"用户输入错误: {e}", exc_info=True)
        
        self._print_stats()
    
    def _print_help(self):
        """打印帮助信息。"""
        print()
        print(f"{COLOR_SYSTEM}=== 帮助信息 ==={COLOR_RESET}")
        print(f"{COLOR_SYSTEM}内置命令:{COLOR_RESET}")
        print(f"  quit/exit/q  - 退出程序")
        print(f"  clear        - 清屏")
        print(f"  status       - 查看状态")
        print(f"  mode         - 切换测试模式（tool/iflow）")
        print(f"  help         - 显示此帮助")
        print()
        print(f"{COLOR_SYSTEM}功能说明:{COLOR_RESET}")
        print(f"  后台监控     - 自动接收 iflow 交互界面的消息")
        print(f"  tmux 交互    - 在 tmux 中直接发送消息，会自动显示在这里")
        print()
        print(f"{COLOR_SYSTEM}命令行功能:{COLOR_RESET}")
        print(f"  ↑↓ 方向键    - 浏览历史记录")
        print(f"  ←→ 方向键    - 移动光标")
        print(f"  Backspace    - 删除字符")
        print(f"  Home/End     - 跳到行首/行尾")
        print(f"  Tab          - 命令补全")
        print(f"  Ctrl+C       - 退出程序")
        print()
        print(f"{COLOR_SYSTEM}测试模式说明:{COLOR_RESET}")
        print(f"  tool（默认） - 工具模式：消息只返回工具，不发企业微信")
        print(f"  iflow        - iflow 模拟模式：模拟 iflow 交互界面，合并发送企业微信")
        print()

    def _print_status(self, enable_background_monitor=False):
        """打印状态信息。
        
        Args:
            enable_background_monitor: 是否启用了后台监控
        """
        print(f"\n{COLOR_SYSTEM}=== 状态信息 ==={COLOR_RESET}")
        
        # 测试模式
        mode_name = "工具模式（不发企业微信）" if self.mode == "tool" else "iflow 模拟模式（合并发送企业微信）"
        print(f"测试模式: {mode_name}")
        print()

        # iflow 状态
        session_info = self.controller.get_session_info()
        print(f"tmux 会话: {session_info['tmux_session']} ({'运行' if session_info['iflow_running'] else '未运行'})")
        if enable_background_monitor:
            print(f"后台监控: 运行中")
        else:
            print(f"后台监控: 未启用")
        print(f"发送消息: {self.message_count} 条")
        print(f"接收消息: {self.mock_channel.message_count} 条")
        print(f"日志文件: {log_file}")
        print()
    
    def _print_stats(self):
        """打印统计信息。"""
        print(f"\n{COLOR_SYSTEM}=== 统计信息 ==={COLOR_RESET}")
        print(f"总发送: {self.message_count} 条")
        print(f"总接收: {self.mock_channel.message_count} 条")
        print(f"日志文件: {log_file}")
        print()


async def main():
    """主函数。"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="iflow 交互式测试工具（使用 BotIntegration）",
        epilog="示例:\n  %(prog)s                    # 交互模式\n  %(prog)s \"1+1等于几？\"      # 命令行模式\n  %(prog)s --wechat            # 模拟企业微信模式（含后台监控）\n  %(prog)s --wechat \"测试\"    # 命令行模式 + 后台监控\n  %(prog)s --monitor           # 纯监听模式（只监听 iflow 交互界面消息）\n  %(prog)s --all-messages \"测试\"  # 提取全部消息",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tmux-session", "-t", default="iflow", help="tmux 会话名称")
    parser.add_argument("--workspace", "-w", default="~/.iflow", help="iflow 工作目录")
    parser.add_argument("--all-messages", "-a", action="store_true", help="提取全部消息（包括非✦标记的消息）")
    parser.add_argument("--wechat", action="store_true", help="模拟企业微信模式（启动后台监控，接收 iflow 交互界面消息）")
    parser.add_argument("--monitor", "-m", action="store_true", help="纯监听模式（只监听 iflow 交互界面消息，不发送任何消息）")
    parser.add_argument("message", nargs="?", help="要发送的消息（可选，不提供则进入交互模式）")
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = IFlowTester(
        tmux_session=args.tmux_session,
        workspace=args.workspace,
        extract_all_messages=args.all_messages
    )
    
    # 纯监听模式
    if args.monitor:
        await tester.monitor_mode()
    # 如果提供了消息，使用命令行模式
    elif args.message:
        print(f"{COLOR_USER}[你]{COLOR_RESET} {args.message}")
        await tester.test_message(args.message, enable_background_monitor=args.wechat)
    else:
        # 否则进入交互模式
        await tester.interactive_mode(enable_background_monitor=args.wechat)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{COLOR_SYSTEM}程序已退出{COLOR_RESET}")