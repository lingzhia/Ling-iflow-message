#!/usr/bin/env python3
"""
IFlowModule 交互式体验工具

模拟消息总线与 IFlowModule 交互：
- 创建模拟消息总线
- 通过钩子拦截 IFlowModule 返回的消息
- 发送的消息格式与消息总线完全一致
- 接收的消息格式与 IFlowModule 返回给消息总线的完全一致

使用方法：
    # 交互模式
    python tools/iflow_interactive_tool.py [选项]

    # 命令行模式（默认保持会话）
    python tools/iflow_interactive_tool.py --message "你好" [选项]

    # 命令行模式（执行后销毁会话）
    python tools/iflow_interactive_tool.py --message "你好" --cleanup

    # 连续执行（复用会话）
    python tools/iflow_interactive_tool.py --message "第一条消息"
    python tools/iflow_interactive_tool.py --message "第二条消息"
    python tools/iflow_interactive_tool.py --message "第三条消息"

选项：
    --config PATH    配置文件路径（默认 config.json）
    --message TEXT   命令行模式：发送消息后退出
    --scope MODE     scope 模式：all 或 reply_only（默认）
    --clean          清理残留的 tmux 会话（默认不复用）
    --keep-alive     保持 tmux 会话（默认，命令行模式）
    --cleanup        销毁 tmux 会话（命令行模式）
"""

import sys
import os
import asyncio
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow import IFlowModule
from src.modules.iflow.monitor import IFlowState
from src.core.message import Message, MessageContent, MessageType as CoreMessageType
from src.core.base import BaseModule

# 设置日志配置
import logging

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 配置日志文件
log_file = log_dir / "iflow_tool.log"

# 创建日志格式器
file_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 文件处理器（记录所有日志）
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)

# 控制台处理器（只显示 WARNING 和 ERROR）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
console_handler.setFormatter(console_formatter)

# 配置根日志
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# 工具专用日志
logger = logging.getLogger("iflow_tool")
logger.setLevel(logging.DEBUG)
logger.info(f"日志文件: {log_file.absolute()}")


class MockMessageBus:
    """模拟消息总线（用于测试）"""

    def __init__(self):
        self._iflow_module = None
        self._message_callback = None  # 消息回调（用于接收来自 iflow 的消息）
        self._processed_message_ids = set()  # 已处理的消息 ID（用于去重）

    def bind(self, from_module, to_module, bidirectional=False):
        """绑定（简化版，不需要路由逻辑）"""
        pass

    async def route(self, message: Message):
        """路由消息
        
        注意：避免将来自 IFlowModule 的消息发送回 IFlowModule，防止循环
        """
        if not self._iflow_module:
            return

        # 检查消息来源
        is_from_iflow = (message.from_module == self._iflow_module.module_id)

        if is_from_iflow:
            # 来自 iflow 的消息，通过回调处理
            # 去重：检查是否已处理
            if message.id in self._processed_message_ids:
                logger.debug(f"[MockMessageBus] 消息已处理，跳过: {message.id}")
                return
            
            # 添加到已处理集合
            self._processed_message_ids.add(message.id)
            
            # 限制集合大小
            if len(self._processed_message_ids) > 1000:
                self._processed_message_ids = set(list(self._processed_message_ids)[-500:])
            
            if self._message_callback:
                try:
                    await self._message_callback(message)
                except Exception as e:
                    logger.error(f"[MockMessageBus] 消息回调错误: {e}", exc_info=True)
        else:
            # 来自其他模块的消息，发送到 iflow
            await self._iflow_module.receive(message)

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module

    def set_message_callback(self, callback):
        """设置消息回调（用于接收来自 iflow 的消息）"""
        self._message_callback = callback


class IFlowInteractiveTool:
    """IFlowModule 交互式体验工具
    
    模拟消息总线与 IFlowModule 交互。
    """

    def __init__(self, config_path: str = "config.json", clean: bool = False, keep_alive: bool = True):
        """初始化工具

        Args:
            config_path: 配置文件路径
            clean: 是否清理残留的 tmux 会话
            keep_alive: 是否保持 tmux 会话（默认 True）
        """
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.mock_bus = MockMessageBus()
        self.module: Optional[IFlowModule] = None
        self.clean = clean  # 是否清理残留的 tmux 会话
        self.keep_alive = keep_alive  # 是否保持 tmux 会话

        # 当前身份和模式
        self.current_source: str = "tool"
        self.current_scope: str = "reply_only"  # 默认只显示回复消息

        # 消息历史
        self.message_history: List[dict] = []
        
        # 中断标志
        self._interrupt_event = asyncio.Event()
    
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        config_file = Path(config_path)
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"已加载配置文件: {config_file}")
                return config
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}，使用默认配置")
        else:
            logger.info(f"配置文件不存在: {config_file}，使用默认配置")
        
        return {
            "iflow": {
                "model": "kimi-k2.5",
                "workspace": "~/.iflow",
                "auto_restart": True,
                "log_interactions": True,
                "log_dir": "logs/interactions"
            }
        }
    
    async def start(self):
        """启动工具"""
        print("=" * 60)
        print("IFlowModule 交互式体验工具")
        print("=" * 60)

        print(f"\n正在创建 IFlowModule 实例...")

        # 工具负责从配置文件读取参数，然后传递给 IFlowModule
        tmux_session = self.config.get("tmux_session")
        model = self.config.get("model", "kimi-k2.5")
        workspace = self.config.get("workspace", "~/.iflow")
        auto_restart = self.config.get("auto_restart", True)
        log_interactions = self.config.get("log_interactions", True)
        log_dir = self.config.get("log_dir", "logs/interactions")

        # 检查并清理残留的 tmux 会话（仅在 clean=True 时）
        if self.clean and tmux_session:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "has-session", "-t", tmux_session,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            if proc.returncode == 0:
                print(f"  检测到残留的 tmux 会话: {tmux_session}")
                proc = await asyncio.create_subprocess_exec(
                    "tmux", "kill-session", "-t", tmux_session,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                await asyncio.sleep(1.0)
                print(f"  已清理残留的 tmux 会话")

        # 检查 iflow 是否已经在运行
        from src.modules.iflow.controller import IFlowController
        temp_controller = IFlowController(tmux_session)
        iflow_running = await temp_controller.check_iflow_running()
        
        if iflow_running and self.keep_alive:
            print(f"  检测到 iflow 已在运行（会话: {tmux_session}）")
            print(f"  将复用现有 iflow 实例，保持会话上下文")
        
        # 创建模块实例
        self.module = IFlowModule(
            tmux_session=tmux_session,
            model=model,
            workspace=workspace,
            auto_restart=auto_restart,
            log_interactions=log_interactions,
            log_dir=log_dir
        )
        
        # 设置模拟消息总线
        self.module.set_message_bus(self.mock_bus)
        self.mock_bus.set_iflow_module(self.module)
        
        # 设置消息回调（用于接收来自 iflow 的消息）
        self.mock_bus.set_message_callback(self._on_iflow_message)
        
        # 设置钩子（拦截返回的消息）
        self.module.set_message_sent_hook(self._on_iflow_message)
        
        print(f"  模块 ID: {self.module.module_id}")
        print(f"  tmux 会话: {self.module.tmux_session or '(启动时分配)'}")
        
        # 启动模块
        print("\n正在启动模块...")
        try:
            await self.module.start()
            print(f"\n✅ 模块已启动")
            print(f"   module_id: {self.module.module_id}")
            print(f"   tmux_session: {self.module.tmux_session}")
            
            # 等待 iflow 完全就绪
            print("正在等待 iflow 完全就绪...")
            ready = await self.module.wait_for_ready(timeout=60)
            if not ready:
                print("⚠️ 警告：iflow 未在预期时间内完全就绪")
            else:
                print("✅ iflow 已完全就绪，可以发送消息")
            
            # 等待监控器稳定（监控器启动后需要时间稳定状态）
            print("正在等待监控器稳定...")
            await asyncio.sleep(3.0)
            print("✅ 监控器已稳定")
        except Exception as e:
            print(f"\n❌ 启动失败: {e}")
            raise
        
        print("=" * 60)
    
    async def stop(self, keep_alive: Optional[bool] = None):
        """停止工具
        
        Args:
            keep_alive: 是否保持 tmux 会话（None 表示使用实例变量）
        """
        # 确定是否保持会话
        should_keep_alive = keep_alive if keep_alive is not None else self.keep_alive
        
        if self.module:
            if should_keep_alive:
                # 保持会话，只停止监控器（不销毁 tmux 和 iflow）
                print("\n正在停止模块（保持 tmux 和 iflow 进程）...")
                
                # 停止监控器
                await self.module.monitor.stop()
                
                # 停止模块但不销毁会话
                self.module._running = False
                
                print("✅ 模块已停止（tmux 和 iflow 进程已保留）")
                print(f"   下次启动将复用现有 iflow 会话（{self.module.tmux_session}）")
            else:
                # 销毁会话
                print("\n正在停止模块...")
                await self.module.stop()
                print("✅ 模块已停止（tmux 会话已销毁）")
    
    async def _on_iflow_message(self, message: Message):
        """接收 IFlowModule 返回的消息（通过钩子）"""
        print(f"  _on_iflow_message 被调用")
        
        reply_type = message.metadata.get('reply_type', 'unknown')
        
        # 记录历史
        self.message_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": reply_type,
            "content": message.content.text,
            "metadata": message.metadata
        })
        
        print(f"  消息已记录: {reply_type}")
        
        # 显示消息（优化界面格式）
        if reply_type == 'complete':
            print("\n" + "=" * 60)
            print("✅ 交互完成")
            print("=" * 60)
            print(f"{message.content.text}")
            print("=" * 60)
        elif reply_type == 'reply':
            print("\n" + "─" * 60)
            print("📤 iflow 回复:")
            print("─" * 60)
            print(f"{message.content.text}")
            print("─" * 60)
        else:
            # 思考消息，根据 scope 决定是否显示
            if self.current_scope == "all":
                print(f"\n💭 [✻ 思考] {message.content.text[:100]}{'...' if len(message.content.text) > 100 else ''}")
    
    async def send_message(self, content: str):
        """发送消息到 IFlowModule（模拟消息总线）"""
        if not self.module:
            print("❌ 模块未启动")
            return
        
        # 检查 iflow 是否就绪（带重试机制，解决竞态条件问题）
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            is_ready = await self.module.controller.check_iflow_ready()
            if is_ready:
                break
            
            if attempt < max_retries - 1:
                print(f"  iflow 未就绪，等待 {retry_delay} 秒后重试... ({attempt + 1}/{max_retries})")
                await asyncio.sleep(retry_delay)
            else:
                print("❌ iflow 未就绪，无法发送消息")
                print("   提示：可能是监控器启动导致的短暂状态变化，请稍后再试")
                return
        
        print(f"发送消息: {content}")
        
        # 优化用户消息显示
        print("\n" + "─" * 60)
        print("📤 用户消息:")
        print("─" * 60)
        print(f"{content}")
        print("─" * 60)
        
        # 创建 Message（模拟消息总线）
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=content),
            from_module=self.current_source,
            metadata={"scope": self.current_scope}
        )
        
        print(f"  调用 mock_bus.route()...")
        await self.mock_bus.route(msg)
        print(f"  mock_bus.route() 完成")
        
        # 等待一下，让消息处理完成
        await asyncio.sleep(1)
    
    async def wait_for_complete(self, timeout: float = 120.0) -> bool:
        """等待回复完成（可中断）
        
        Returns:
            是否正常完成（True: 完成，False: 被中断或超时）
        """
        if not self.module:
            return False
        
        # 清空中断标志
        self._interrupt_event.clear()
        
        print(f"等待回复完成（超时: {timeout}秒，按 Ctrl+C 中断）...")
        
        # 轮询状态
        elapsed = 0.0
        check_interval = 1.0
        
        # 等待至少收到一条消息
        while elapsed < timeout and len(self.message_history) == 0:
            # 检查是否被中断
            if self._interrupt_event.is_set():
                print(f"\n   ⚠️ 等待已被中断")
                return False
            
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            if int(elapsed) % 5 == 0 and elapsed > 0:
                print(f"   等待回复... {int(elapsed)}秒", end='\r', flush=True)
        
        # 如果没有收到消息，返回 False
        if len(self.message_history) == 0:
            print(f"\n   ⚠️ 未收到任何消息")
            return False
        
        print(f"\n   ✅ 收到 {len(self.message_history)} 条消息")
        
        # 等待状态变为 IDLE
        start_time = elapsed
        while elapsed < timeout:
            # 检查是否被中断
            if self._interrupt_event.is_set():
                print(f"\n   ⚠️ 等待已被中断")
                return False
            
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            current_state = self.module.state
            
            if int(elapsed) % 5 == 0:
                print(f"   等待生成完成... {int(elapsed)}秒 (状态: {current_state.value})", end='\r', flush=True)
            
            # 检查状态是否为 IDLE
            if current_state == IFlowState.IDLE:
                # 额外等待 2 秒，确保状态稳定
                await asyncio.sleep(2)
                if self.module.state == IFlowState.IDLE:
                    print(f"\n✅ 生成完成 (耗时 {elapsed:.1f}秒)")
                    return True
        
        # 超时
        logger.warning(f"[Tool] ⚠️ 等待超时 ({timeout}秒)")
        logger.warning(f"[Tool] 最终状态: {self.module.state.value}, 消息数: {len(self.message_history)}")
        print(f"\n   ⚠️ 超时 ({timeout}秒)")
        return False
    
    async def interactive_loop(self):
        """交互式循环"""
        print("\n" + "=" * 60)
        print("交互模式")
        print("=" * 60)
        self._print_help()

        try:
            import prompt_toolkit
            from prompt_toolkit import PromptSession
            from prompt_toolkit.history import InMemoryHistory
            from prompt_toolkit.completion import WordCompleter

            # 使用 prompt_toolkit 提供更好的交互体验
            commands = ['/help', '/source', '/scope', '/status', '/history', '/spam', 'quit', 'exit', 'q']
            completer = WordCompleter(commands, ignore_case=True)
            history = InMemoryHistory()
            
            session = PromptSession(
                history=history,
                completer=completer
            )

            while True:
                try:
                    user_input = await session.prompt_async(f"\n💬 你: ")

                    if not user_input:
                        continue

                    # 命令处理
                    if user_input.startswith('/'):
                        await self._handle_command(user_input)
                        continue

                    if user_input.lower() in ['quit', 'exit', 'q']:
                        break

                    # 发送消息
                    await self.send_message(user_input)
                    completed = await self.wait_for_complete()

                    # 如果未完成（被中断），清空等待提示
                    if not completed:
                        print("   提示：等待已被中断，可以继续输入新消息")

                except KeyboardInterrupt:
                    # 检查是否在等待过程中
                    if self.module and self.module.state == IFlowState.GENERATING:
                        # 在等待过程中中断，设置中断标志并继续循环
                        self._interrupt_event.set()
                        print("\n⚠️ 等待已中断，可以继续输入新消息")
                        # 继续循环，等待用户输入
                    else:
                        # 不在等待过程中，退出
                        print("\n退出...")
                        break
                except EOFError:
                    break

        except ImportError:
            # prompt_toolkit 不可用，使用简单的 input()
            print("提示：安装 prompt_toolkit 可以获得更好的交互体验")
            print("      pip install prompt-toolkit\n")

            while True:
                try:
                    prompt_text = f"\n💬 你: "
                    user_input = input(prompt_text).strip()

                    if not user_input:
                        continue

                    # 命令处理
                    if user_input.startswith('/'):
                        await self._handle_command(user_input)
                        continue

                    if user_input.lower() in ['quit', 'exit', 'q']:
                        break

                    # 发送消息
                    await self.send_message(user_input)
                    completed = await self.wait_for_complete()

                    # 如果未完成（被中断），清空等待提示
                    if not completed:
                        print("   提示：等待已被中断，可以继续输入新消息")

                except KeyboardInterrupt:
                    # 检查是否在等待过程中
                    if self.module and self.module.state == IFlowState.GENERATING:
                        # 在等待过程中中断，设置中断标志并继续循环
                        self._interrupt_event.set()
                        print("\n⚠️ 等待已中断，可以继续输入新消息")
                        # 继续循环，等待用户输入
                    else:
                        # 不在等待过程中，退出
                        print("\n退出...")
                        break
                except EOFError:
                    break
    
    async def _handle_command(self, command: str):
        """处理命令"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None
        
        if cmd == '/help':
            self._print_help()
        
        elif cmd == '/source':
            if arg:
                self.current_source = arg
                print(f"✅ 已切换身份: {arg}")
            else:
                print(f"当前身份: {self.current_source}")
        
        elif cmd == '/scope':
            if arg in ['all', 'reply_only']:
                self.current_scope = arg
                print(f"✅ 已切换模式: {arg}")
            else:
                print(f"当前模式: {self.current_scope}")
                print("可用: all, reply_only")
        
        elif cmd == '/status':
            await self._show_status()
        
        elif cmd == '/history':
            self._show_history()
        
        elif cmd == '/spam':
            await self._spam_test(int(arg) if arg else 3)
        
        else:
            print(f"未知命令: {cmd}")
    
    def _print_help(self):
        """打印帮助"""
        print("命令:")
        print("  直接输入文字     - 发送消息")
        print("  /source <name>   - 切换身份（模拟不同来源）")
        print("  /scope <mode>    - 切换模式: all(全部) / reply_only(仅回复)")
        print("  /status          - 查看状态")
        print("  /history         - 查看消息历史")
        print("  /spam [n]        - 连续发送 n 条消息测试拒绝机制")
        print("  /help            - 显示帮助")
        print("  quit/exit        - 退出")
        print("-" * 40)
        print(f"当前: source={self.current_source}, scope={self.current_scope}")
    
    async def _show_status(self):
        """显示状态"""
        if not self.module:
            print("模块未启动")
            return
        
        status = await self.module.get_status()
        
        print(f"\n📊 模块状态:")
        print(f"   module_id: {status['module_id']}")
        print(f"   running: {status['running']}")
        print(f"   tmux_session: {status['tmux_session']}")
        print(f"   model: {status['model']}")
        print(f"   iflow_state: {status['iflow_state']}")
        print(f"   generating_duration: {status['generating_duration']}秒")
        
        monitor = status.get('monitor_stats', {})
        print(f"   监控统计:")
        print(f"     - 检查次数: {monitor.get('check_count', 0)}")
        print(f"     - 提取消息: {monitor.get('messages_extracted', 0)}")
        print(f"     - 状态变化: {monitor.get('state_changes', 0)}")
        
        store = status.get('message_store', {})
        print(f"   消息库:")
        print(f"     - 总计: {store.get('total', 0)}")
        print(f"     - 处理中: {store.get('processing', 0)}")
        
        logger_stats = status.get('logger_stats', {})
        print(f"   交互记录: {logger_stats.get('total_interactions', 0)} 条")
    
    def _show_history(self):
        """显示消息历史"""
        if not self.message_history:
            print("\n📝 暂无消息历史")
            return
        
        print(f"\n📝 消息历史 ({len(self.message_history)} 条):")
        print("-" * 40)
        
        for msg in self.message_history[-20:]:
            timestamp = msg['timestamp'][11:19]  # 只取时间部分
            msg_type = msg['type']
            content = msg['content'][:40] + '...' if len(msg['content']) > 40 else msg['content']
            print(f"  [{timestamp}] [{msg_type}] {content}")
        
        print("-" * 40)
    
    async def _spam_test(self, count: int):
        """连续发送测试拒绝机制"""
        print(f"\n🧪 连续发送 {count} 条消息测试拒绝机制...")
        print("   说明: 第一条消息成功后，后续消息应被拒绝（生成中状态）")
        
        results = []
        
        # 第一条消息
        print(f"\n  发送第 1 条消息...")
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=f"请帮我数到 {count * 10}"),
            from_module=self.current_source,
            metadata={"scope": self.current_scope}
        )
        await self.mock_bus.route(msg)
        results.append(("send", "✅"))
        
        if self.module.state == IFlowState.GENERATING:
            # 等待进入生成状态
            await asyncio.sleep(1)
            
            # 快速发送后续消息（应该被拒绝）
            for i in range(1, count):
                print(f"  发送第 {i+1} 条消息...")
                msg = Message(
                    id=Message.generate_id(),
                    type=CoreMessageType.TEXT,
                    content=MessageContent(type=CoreMessageType.TEXT, text=f"测试消息 {i+1}"),
                    from_module=self.current_source,
                    metadata={"scope": self.current_scope}
                )
                await self.mock_bus.route(msg)
                
                current_state = self.module.state.value
                print(f"    结果: 消息已发送 (状态: {current_state})")
                
                await asyncio.sleep(0.3)
            
            # 等待生成完成
            print("\n  等待生成完成...")
            await self.wait_for_complete(timeout=60)
        
        print(f"\n📊 测试结果:")
        print(f"   总计: {count} 条")
        print(f"   第一条: 成功")
        print(f"   后续: 已发送（等待 iflow 处理）")


async def main():
    """主函数"""
    config_path = "config.json"
    command_line_message = None
    scope = "reply_only"
    clean = False
    keep_alive = True  # 默认保持会话

    # 解析命令行参数
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ['-h', '--help']:
            print(__doc__)
            sys.exit(0)
        elif arg == '--config' and i + 1 < len(args):
            config_path = args[i + 1]
            i += 1
        elif arg == '--message' and i + 1 < len(args):
            command_line_message = args[i + 1]
            i += 1
        elif arg == '--scope' and i + 1 < len(args):
            scope = args[i + 1]
            i += 1
        elif arg == '--clean':
            clean = True
        elif arg == '--keep-alive':
            keep_alive = True
        elif arg == '--cleanup':
            keep_alive = False
        i += 1

    tool = IFlowInteractiveTool(config_path, clean=clean, keep_alive=keep_alive)

    try:
        await tool.start()
        
        if command_line_message:
            # 命令行模式：发送消息后退出
            tool.current_scope = scope
            await tool.send_message(command_line_message)
            completed = await tool.wait_for_complete()
            
            if not completed:
                print("⚠️ 等待被中断或超时")
            
            # 显示历史
            print("\n" + "=" * 60)
            tool._show_history()
            print("=" * 60)
            
            # 提示会话状态
            if tool.keep_alive:
                print(f"\n💡 提示：tmux 会话已保留，下次执行将继续使用该会话")
            else:
                print(f"\n💡 提示：tmux 会话将被销毁")
        else:
            # 交互模式：进入交互式循环
            await tool.interactive_loop()
    except Exception as e:
        logger.error(f"运行错误: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # 根据配置决定是否停止
        if not tool.keep_alive:
            await tool.stop(keep_alive=False)
        else:
            await tool.stop(keep_alive=True)


if __name__ == "__main__":
    asyncio.run(main())