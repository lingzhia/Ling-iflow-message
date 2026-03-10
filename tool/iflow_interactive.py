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
COLOR_CYAN = "\033[96m"      # 亮青色
COLOR_YELLOW = "\033[93m"    # 亮黄色
COLOR_GREEN = "\033[92m"     # 亮绿色
COLOR_RED = "\033[91m"       # 亮红色
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
    
    def __init__(self, tmux_session=None, workspace=None, extract_all_messages=False, config_path=None):
        """初始化测试器。

        Args:
            tmux_session: tmux 会话名称（可选，如果为空则显示选择列表）
            workspace: iflow 工作目录（可选）
            extract_all_messages: 是否提取全部消息（包括非✦标记的消息）
            config_path: 配置文件路径（可选）
        """
        self.tmux_session = tmux_session
        self.workspace = workspace
        self.extract_all_messages = extract_all_messages
        self.running = False
        self.message_count = 0

        # 加载配置
        self.config_path = config_path or (Path(__file__).parent.parent / "config.json")
        self.config = self._load_config()
        self.bots_config = self._load_bots_config()

        # 如果未指定 tmux_session，显示选择列表
        if not tmux_session:
            self.tmux_session = self._select_session()
            if not self.tmux_session:
                return

        # 从配置中获取工作目录
        if not workspace:
            workspace = self._get_workspace_for_session(self.tmux_session)
            self.workspace = workspace  # 更新 self.workspace

        # 创建模拟渠道
        self.mock_channel = MockWeChatChannel()

        # 创建 IFlowController（用于状态检查）
        self.controller = IFlowController(self.tmux_session)

        # 创建 BotIntegration（与企业微信使用相同的逻辑）
        self.bot = BotIntegration(
            wechat_channel=self.mock_channel,
            tmux_session=self.tmux_session,
            workspace=workspace,
            filter_thinking=True,  # 过滤思考消息
            extract_all_messages=extract_all_messages  # 是否提取全部消息
        )

        # 配置 readline 历史记录
        self._setup_readline()
        
        # 测试模式：tool（工具模式）/ iflow（模拟 iflow 交互界面）
        self.mode = "tool"
    
    def _load_config(self) -> dict:
        """加载配置文件。
        
        Returns:
            配置字典
        """
        try:
            from config.loader import load_config
            config = load_config(self.config_path)
            # 如果返回的是 Pydantic 模型，转换为字典
            if hasattr(config, 'model_dump'):
                return config.model_dump()
            elif hasattr(config, 'dict'):
                return config.dict()
            return config
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}")
            return {}
    
    def _load_bots_config(self) -> dict:
        """加载机器人配置。
        
        Returns:
            机器人配置字典
        """
        try:
            from config.bots_loader import load_bots_config
            return load_bots_config(self.config_path)
        except Exception as e:
            logger.warning(f"加载机器人配置失败: {e}")
            return {}
    
    def _select_session(self) -> str:
        """选择 tmux 会话。
        
        Returns:
            选中的会话名称，如果取消则返回 None
        """
        sessions = self.config.get('tmux_sessions', [])
        bots = self.bots_config.get_enabled_bots()
        
        # 构建会话到机器人的映射
        session_to_bot = {}
        for bot in bots:
            if bot.enabled and bot.tmux_session:
                session_to_bot[bot.tmux_session] = bot
        
        # 获取所有正在运行的 tmux 会话
        import subprocess
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True
            )
            running_sessions = result.stdout.strip().split('\n') if result.returncode == 0 else []
        except:
            running_sessions = []
        
        print()
        print("=" * 70)
        print("选择 tmux 会话")
        print("=" * 70)
        
        if not sessions and not running_sessions:
            print(f"{COLOR_SYSTEM}⚠ 配置文件中未配置 tmux 会话，也没有正在运行的会话{COLOR_RESET}")
            print(f"{COLOR_SYSTEM}请先在 config.json 中配置 tmux_sessions 或启动会话{COLOR_RESET}")
            return None
        
        # 显示配置的会话
        if sessions:
            print(f"{COLOR_CYAN}配置的会话:{COLOR_RESET}")
            for i, session in enumerate(sessions):
                name = session.get('name', '')
                bot_info = session_to_bot.get(name, None)
                status_icon = f"{COLOR_GREEN}✓{COLOR_RESET}" if name in running_sessions else f"{COLOR_RED}✗{COLOR_RESET}"
                
                print(f"  {i + 1}. {status_icon} {name}")
                if bot_info:
                    print(f"     → {COLOR_YELLOW}{bot_info.name}{COLOR_RESET} (端口: {bot_info.callback_port})")
                print(f"     工作目录: {session.get('workspace', 'N/A')}")
                print(f"     模型: {session.get('model', 'N/A')}")
                print()
        
        # 显示正在运行但未配置的会话
        for session in running_sessions:
            if session not in [s.get('name', '') for s in sessions]:
                print(f"{COLOR_YELLOW}* {session} (未配置){COLOR_RESET}")
        
        print(f"{COLOR_SYSTEM}0. 取消{COLOR_RESET}")
        print()
        
        try:
            choice = input("请选择会话编号: ").strip()
            if choice == '0':
                return None
            
            choice_num = int(choice)
            
            # 从配置的会话中选择
            if 1 <= choice_num <= len(sessions):
                selected = sessions[choice_num - 1]
                return selected.get('name', '')
            
            # 从正在运行的会话中选择
            elif len(sessions) < choice_num <= len(sessions) + len(running_sessions):
                running_only = running_sessions[len(sessions):]
                if choice_num - len(sessions) - 1 < len(running_only):
                    return running_only[choice_num - len(sessions) - 1]
            
            print(f"{COLOR_SYSTEM}✗ 无效的选择{COLOR_RESET}")
            return None
            
        except (ValueError, IndexError):
            print(f"{COLOR_SYSTEM}✗ 无效的选择{COLOR_RESET}")
            return None
    
    def _get_workspace_for_session(self, session_name: str) -> str:
        """获取会话的工作目录。
        
        Args:
            session_name: 会话名称
            
        Returns:
            工作目录
        """
        # 从配置中查找
        sessions = self.config.get('tmux_sessions', [])
        for session in sessions:
            if session.get('name') == session_name:
                return session.get('workspace', '~/.iflow')
        
        # 从机器人配置中查找
        bots = self.bots_config.get_enabled_bots()
        for bot in bots:
            if bot.tmux_session == session_name and bot.workspace:
                return bot.workspace
        
        return '~/.iflow'
    
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

        # 显示绑定关系信息
        bots = self.bots_config.get_enabled_bots()
        bound_bot = None
        for bot in bots:
            if bot.tmux_session == self.tmux_session:
                bound_bot = bot
                break
        
        if bound_bot:
            print()
            print(f"{COLOR_CYAN}当前会话绑定:{COLOR_RESET}")
            print(f"  会话名称: {self.tmux_session}")
            print(f"  机器人: {COLOR_YELLOW}{bound_bot.name}{COLOR_RESET}")
            print(f"  回调端口: {bound_bot.callback_port}")
            print(f"  工作目录: {self.workspace}")
            print()
        
        return True
    
    async def test_message(self, message: str, source: str = None):
        """测试单条消息。

        Args:
            message: 要测试的消息
            source: 消息来源（tool/wechat/""），默认为 tool
        """
        if not self._check_iflow_status():
            return

        self.message_count += 1

        # 直接调用 BotIntegration 的处理逻辑
        chat_id = "test_user"
        is_group = False
        
        # 如果未指定 source，使用默认的 mode
        if source is None:
            source = self.mode

        try:
            await self.bot.handle_message(message, "test_user", chat_id, is_group, source=source)
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
    
    async def interactive_mode(self):
        """交互式模式。"""
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
        print("=" * 70)
        print()
        
        # 检查 iflow 状态
        if not self._check_iflow_status():
            return
        
        self.running = True
        
        while self.running:
            try:
                user_input = input(f"{COLOR_USER}[你]{COLOR_RESET} ").strip()

                # 处理命令
                if user_input in ['quit', 'exit', 'q']:
                    print(f"{COLOR_SYSTEM}再见！{COLOR_RESET}")
                    self.running = False
                    break

                if user_input == 'clear':
                    import os
                    os.system('clear')
                    continue

                if user_input == 'status':
                    self._print_status()
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

    def _print_status(self):
        """打印状态信息。"""
        print(f"\n{COLOR_SYSTEM}=== 状态信息 ==={COLOR_RESET}")
        
        # 测试模式
        mode_name = "工具模式（不发企业微信）" if self.mode == "tool" else "iflow 模拟模式（合并发送企业微信）"
        print(f"测试模式: {mode_name}")
        print()

        # iflow 状态
        session_info = self.controller.get_session_info()
        print(f"tmux 会话: {session_info['tmux_session']} ({'运行' if session_info['iflow_running'] else '未运行'})")
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
        epilog="示例:\n  %(prog)s                    # 交互模式（可选择会话）\n  %(prog)s -t iflow         # 指定会话\n  %(prog)s \"1+1等于几？\"      # 命令行模式（tool来源）\n  %(prog)s -u \"测试\"          # 命令行模式（无标记，模拟 iflow 交互界面）\n  %(prog)s -m                  # 纯监听模式（只监听 iflow 交互界面消息）\n  %(prog)s -a \"测试\"          # 提取全部消息",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tmux-session", "-t", default=None, help="tmux 会话名称（不指定则显示选择列表）")
    parser.add_argument("--workspace", "-w", default=None, help="iflow 工作目录（不指定则从配置获取）")
    parser.add_argument("--all-messages", "-a", action="store_true", help="提取全部消息（包括非✦标记的消息）")
    parser.add_argument("--monitor", "-m", action="store_true", help="纯监听模式（只监听 iflow 交互界面消息，不发送任何消息）")
    parser.add_argument("--unmarked", "-u", action="store_true", help="发送无标记消息（模拟直接在 iflow 交互界面输入）")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有可用的会话")
    parser.add_argument("message", nargs="?", help="要发送的消息（可选，不提供则进入交互模式）")
    
    args = parser.parse_args()
    
    # 如果只是列出会话
    if args.list:
        tester = IFlowTester(
            tmux_session="",  # 空字符串会触发会话选择列表
            workspace=None,
            extract_all_messages=args.all_messages
        )
        # 用户选择了 0（取消）或没有选择任何会话
        return
    
    # 创建测试器
    tester = IFlowTester(
        tmux_session=args.tmux_session,
        workspace=args.workspace,
        extract_all_messages=args.all_messages
    )
    
    # 如果用户取消了选择
    if not tester.tmux_session:
        return
    
    # 纯监听模式
    if args.monitor:
        await tester.monitor_mode()
    # 如果提供了消息，使用命令行模式
    elif args.message:
        print(f"{COLOR_USER}[你]{COLOR_RESET} {args.message}")
        
        # 确定消息来源
        source = "tool"  # 默认为 tool
        if args.unmarked:
            source = ""  # 无标记消息，模拟直接在 iflow 交互界面输入
        
        await tester.test_message(args.message, source=source)
    else:
        # 否则进入交互模式
        await tester.interactive_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{COLOR_SYSTEM}程序已退出{COLOR_RESET}")