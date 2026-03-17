"""
Command Handler

命令处理器，解析和执行用户命令。
"""

import logging
from typing import Dict, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...core import MessageBus


logger = logging.getLogger(__name__)


class CommandHandler:
    """命令处理器
    
    解析和执行用户命令，如 /new、/status、/sessions 等。
    """
    
    def __init__(self, message_bus: Optional["MessageBus"] = None, manager: Optional[Any] = None):
        """初始化命令处理器
        
        Args:
            message_bus: 消息总线实例
            manager: 模块管理器实例
        """
        self.bus = message_bus
        self.manager = manager
        self.bot = None  # bot 实例，用于渠道控制
        self._commands = {}
        self._register_builtin_commands()
    
    def set_message_bus(self, bus: "MessageBus") -> None:
        """设置消息总线
        
        Args:
            bus: 消息总线实例
        """
        self.bus = bus
    
    def set_manager(self, manager: Any) -> None:
        """设置模块管理器
        
        Args:
            manager: 模块管理器实例
        """
        self.manager = manager
    
    def set_bot(self, bot: Any) -> None:
        """设置 bot 实例
        
        Args:
            bot: bot 实例
        """
        self.bot = bot
    
    def _register_builtin_commands(self) -> None:
        """注册内置命令"""
        self._commands = {
            "/help": self._cmd_help,
            "/status": self._cmd_status,
            "/new": self._cmd_new,
            "/sessions": self._cmd_sessions,
            "/lscmd": self._cmd_lscmd,
            "/history": self._cmd_history,
            "/metrics": self._cmd_metrics,
            "/channel": self._cmd_channel,
            "/snapshot": self._cmd_snapshot,
            "/tmux": self._cmd_tmux,
        }
    
    def parse_command(self, content: str) -> Dict[str, Any]:
        """解析用户消息，提取命令
        
        Args:
            content: 用户发送的消息
            
        Returns:
            解析结果字典，格式：
            {
                "is_command": bool,
                "cmd_type": str,  # "command" or "message"
                "cmd_name": Optional[str],
                "cmd_args": Optional[str],
                "raw_content": str
            }
        """
        content = content.strip()
        
        # 检查是否为命令（以 / 开头）
        if content.startswith("/"):
            parts = content.split(maxsplit=1)
            cmd_name = parts[0].lower()
            cmd_args = parts[1] if len(parts) > 1 else ""
            
            return {
                "is_command": True,
                "cmd_type": "command",
                "cmd_name": cmd_name,
                "cmd_args": cmd_args,
                "raw_content": content
            }
        
        # 普通消息
        return {
            "is_command": False,
            "cmd_type": "message",
            "cmd_name": None,
            "cmd_args": content,
            "raw_content": content
        }
    
    async def execute(self, parsed: Dict[str, Any], chat_id: str = "") -> Optional[str]:
        """执行命令
        
        Args:
            parsed: 解析后的命令
            chat_id: 聊天 ID
            
        Returns:
            命令执行结果（回复消息），如果不是命令则返回 None
        """
        if not parsed.get("is_command"):
            return None
        
        cmd_name = parsed.get("cmd_name", "")
        cmd_args = parsed.get("cmd_args", "")
        
        # 检查命令是否存在
        if cmd_name in self._commands:
            try:
                result = await self._commands[cmd_name](cmd_args, chat_id)
                return result
            except Exception as e:
                logger.error(f"执行命令 {cmd_name} 失败: {e}", exc_info=True)
                return f"❌ 执行命令失败: {e}"
        
        # 未知命令：透传给 iflow 处理
        logger.info(f"未知命令，透传给 iflow: {cmd_name} {cmd_args}")
        return None
    
    async def _cmd_help(self, args: str, chat_id: str) -> str:
        """帮助命令"""
        return """**iFlow 企业微信助手** 🤖

*支持连续对话，自动保持上下文*

**可用命令：**
- 直接发送消息：执行 iFlow 命令（自动恢复上次会话）
- `/new`：开始新会话（清除上下文）
- `/sessions`：查看历史会话
- `/status`：查看服务状态
- `/history [模块ID]`：查看模块状态历史（最近 10 条）
- `/metrics [模块ID]`：查看模块性能指标
- `/snapshot [channel_name]`：查看 tmux 界面快照
- `/channel list`：列出所有渠道
- `/channel [status|start|stop|restart] [channel_name]`：渠道管理
- `/help`：显示此帮助
- `/lscmd`：列出所有可用命令

**故障排查：**
- 如果请求没有响应，使用 `/snapshot` 查看 tmux 界面
- 判断是 iflow 异常了还是 iflow 还在生成中

**iFlow 命令支持：**
- 未知的斜杠命令会自动透传给 iflow 处理
- 例如：`/run`、`/config`、`/exit` 等会直接传递给 iflow"""
    
    async def _cmd_status(self, args: str, chat_id: str) -> str:
        """状态命令 - 查看所有已启动模块的状态"""
        if not self.bus:
            return "❌ 消息总线未初始化"
        
        status_lines = ["**服务状态** 📊\n"]
        
        # 获取所有模块状态
        if self.manager:
            all_status = self.manager.get_all_status()
            
            if not all_status:
                status_lines.append("❌ 没有可用的模块")
                return "\n".join(status_lines)
            
            # 只显示已启动的模块
            started_modules = {
                module_id: status 
                for module_id, status in all_status.items()
                if status['running']
            }
            
            if not started_modules:
                status_lines.append("ℹ️ 当前没有启动的模块")
                return "\n".join(status_lines)
            
            # 按模块类型分组（只显示已启动的）
            iflow_modules = []
            wechat_modules = []
            simulator_modules = []
            other_modules = []
            
            for module_id, status in started_modules.items():
                if module_id.startswith("iflow_"):
                    iflow_modules.append((module_id, status))
                elif module_id.startswith("wechat_"):
                    wechat_modules.append((module_id, status))
                elif module_id.startswith("simulator_"):
                    simulator_modules.append((module_id, status))
                else:
                    other_modules.append((module_id, status))
            
            # 显示 IFlow 模块状态
            if iflow_modules:
                status_lines.append("**IFlow 模块** 🤖")
                for module_id, status in iflow_modules:
                    # 只显示已启动的模块，所以running_icon总是✅
                    healthy_icon = "✅" if status['healthy'] else "❌"
                    
                    # 获取 IFlow 专用状态
                    iflow_status = self.manager.get_iflow_status(module_id)
                    state_info = ""
                    if iflow_status:
                        state = iflow_status.get('state', 'unknown')
                        if state == 'generating':
                            state_info = f" [⏳ 生成中 {iflow_status.get('generating_duration', 0)}s]"
                        elif state == 'idle':
                            state_info = " [💤 空闲]"
                    
                    status_lines.append(f"- ✅ {module_id}")
                    status_lines.append(f"  健康状态: {healthy_icon}{state_info}")
                    status_lines.append(f"  启动时间: {status.get('started_at', 'N/A')}")
                    
                    # 获取性能指标
                    metrics = self.manager.get_metrics(module_id)
                    if metrics:
                        if metrics.startup_duration > 0:
                            status_lines.append(f"  启动耗时: {metrics.startup_duration:.2f}s")
                        if metrics.message_count > 0:
                            status_lines.append(f"  处理消息: {metrics.message_count} 条")
                            status_lines.append(f"  平均处理时间: {metrics.avg_processing_time:.3f}s")
                            status_lines.append(f"  最大处理时间: {metrics.max_processing_time:.3f}s")
                        if metrics.error_count > 0:
                            status_lines.append(f"  错误次数: {metrics.error_count}")
                    
                    # 获取模块元数据
                    metadata = self.manager.get_metadata(module_id)
                    if metadata:
                        status_lines.append(f"  版本: {metadata.version}")
                        if metadata.description:
                            status_lines.append(f"  描述: {metadata.description}")
                    
                    # 获取 IFlow 模块的会话信息
                    module = self.bus.modules.get(module_id)
                    if module and hasattr(module, 'session_manager'):
                        session_info = module.session_manager.get_current_session_info()
                        if session_info['has_session']:
                            session_id = session_info['session_id']
                            status_lines.append(f"  当前会话: `{session_id[:8]}...`")
                    status_lines.append("")
            
            # 显示企业微信模块状态
            if wechat_modules:
                status_lines.append("**企业微信渠道** 💬")
                for module_id, status in wechat_modules:
                    # 只显示已启动的模块，所以running_icon总是✅
                    healthy_icon = "✅" if status['healthy'] else "❌"
                    
                    status_lines.append(f"- ✅ {module_id}")
                    status_lines.append(f"  健康状态: {healthy_icon}")
                    
                    # 获取性能指标
                    metrics = self.manager.get_metrics(module_id)
                    if metrics:
                        if metrics.startup_duration > 0:
                            status_lines.append(f"  启动耗时: {metrics.startup_duration:.2f}s")
                        if metrics.message_count > 0:
                            status_lines.append(f"  处理消息: {metrics.message_count} 条")
                    
                    # 获取模块元数据
                    metadata = self.manager.get_metadata(module_id)
                    if metadata:
                        status_lines.append(f"  版本: {metadata.version}")
                    
                    # 获取企业微信模块的详细信息
                    module = self.bus.modules.get(module_id)
                    if module and hasattr(module, 'get_status'):
                        module_status = await module.get_status()
                        status_lines.append(f"  Corp ID: {module_status.get('corp_id', 'N/A')}")
                        status_lines.append(f"  Agent ID: {module_status.get('agent_id', 'N/A')}")
                        status_lines.append(f"  回调端口: {module_status.get('callback_port', 'N/A')}")
                    status_lines.append("")
            
            # 显示模拟器模块状态
            if simulator_modules:
                status_lines.append("**模拟器渠道** 🔧")
                for module_id, status in simulator_modules:
                    # 只显示已启动的模块，所以running_icon总是✅
                    healthy_icon = "✅" if status['healthy'] else "❌"
                    
                    status_lines.append(f"- ✅ {module_id}")
                    status_lines.append(f"  健康状态: {healthy_icon}")
                    
                    # 获取性能指标
                    metrics = self.manager.get_metrics(module_id)
                    if metrics:
                        if metrics.startup_duration > 0:
                            status_lines.append(f"  启动耗时: {metrics.startup_duration:.2f}s")
                        if metrics.message_count > 0:
                            status_lines.append(f"  处理消息: {metrics.message_count} 条")
                    
                    # 获取模拟器模块的详细信息
                    module = self.bus.modules.get(module_id)
                    if module and hasattr(module, 'get_status'):
                        module_status = await module.get_status()
                        status_lines.append(f"  监听地址: {module_status.get('host', 'N/A')}:{module_status.get('port', 'N/A')}")
                        status_lines.append(f"  连接数: {module_status.get('connections', 0)}")
                    status_lines.append("")
            
            # 显示其他模块
            if other_modules:
                status_lines.append("**其他模块** 📦")
                for module_id, status in other_modules:
                    # 只显示已启动的模块，所以running_icon总是✅
                    healthy_icon = "✅" if status['healthy'] else "❌"
                    
                    status_lines.append(f"- ✅ {module_id}")
                    status_lines.append(f"  健康状态: {healthy_icon}")
                    
                    # 获取性能指标
                    metrics = self.manager.get_metrics(module_id)
                    if metrics and metrics.startup_duration > 0:
                        status_lines.append(f"  启动耗时: {metrics.startup_duration:.2f}s")
                status_lines.append("")
        
        else:
            # 如果没有 manager，使用旧的方式查询 IFlow 模块状态
            status_lines.append("⚠️ 模块管理器未初始化")
            for module_id, module in self.bus.modules.items():
                if module_id.startswith("iflow_") and hasattr(module, 'get_status_message'):
                    status_lines.append(module.get_status_message())
        
        return "\n".join(status_lines)
    
    async def _cmd_new(self, args: str, chat_id: str) -> str:
        """新建会话命令"""
        if not self.bus:
            return "❌ 消息总线未初始化"
        
        # 查找 iflow 模块并创建新会话
        for module_id, module in self.bus.modules.items():
            if module_id.startswith("iflow_") and hasattr(module, 'create_new_session'):
                result = module.create_new_session()
                if result.get("success"):
                    return "✅ 已开始新会话，下次命令将从空白上下文开始"
                else:
                    return f"❌ 创建新会话失败: {result.get('message', '未知错误')}"
        
        return "❌ 没有可用的 iflow 模块"
    
    async def _cmd_sessions(self, args: str, chat_id: str) -> str:
        """查看会话列表命令"""
        if not self.bus:
            return "❌ 消息总线未初始化"
        
        # 查找 iflow 模块
        for module_id, module in self.bus.modules.items():
            if module_id.startswith("iflow_") and hasattr(module, 'get_sessions_message'):
                return module.get_sessions_message(limit=10)
        
        return "❌ 没有可用的 iflow 模块"
    
    async def _cmd_lscmd(self, args: str, chat_id: str) -> str:
        """列出所有命令"""
        return """**可用命令列表** 📋

**会话管理：**
- `/new` - 开始新会话（清除上下文）
- `/sessions` - 查看历史会话

**状态查询：**
- `/status` - 查看服务状态
- `/history [模块ID]` - 查看模块状态历史（最近 10 条）
- `/metrics [模块ID]` - 查看模块性能指标
- `/help` - 显示帮助信息
- `/lscmd` - 列出所有可用命令

**故障排查：**
- `/snapshot [channel_name]` - 查看 tmux 界面快照

**渠道管理：**
- `/channel list` - 列出所有渠道
- `/channel status [channel_name]` - 查看渠道状态
- `/channel start <channel_name>` - 启动渠道
- `/channel stop <channel_name>` - 停止渠道
- `/channel restart <channel_name>` - 重启渠道

**使用提示：**
- 直接发送消息即可与 iflow 对话
- 命令不区分大小写
- 模块 ID 可省略，将显示所有模块的信息
- 未知的斜杠命令会自动透传给 iflow 处理（如 `/run`、`/config` 等）"""
    
    async def _cmd_history(self, args: str, chat_id: str) -> str:
        """查看状态历史命令"""
        if not self.manager:
            return "❌ 模块管理器未初始化"
        
        module_id = args.strip() if args.strip() else None
        
        if module_id:
            # 查看指定模块的历史
            if module_id not in self.manager.modules:
                return f"❌ 模块不存在: {module_id}"
            
            history = self.manager.get_state_history(module_id, limit=10)
            
            if not history:
                return f"ℹ️ 模块 {module_id} 没有状态历史记录"
            
            lines = [f"**{module_id} 状态历史** 📜\n"]
            for i, transition in enumerate(history, 1):
                timestamp = transition.timestamp.strftime("%H:%M:%S")
                lines.append(f"{i}. {timestamp} | {transition.from_state} → {transition.to_state}")
                if transition.reason:
                    lines.append(f"   原因: {transition.reason}")
                if transition.details:
                    details_str = ", ".join([f"{k}={v}" for k, v in transition.details.items()])
                    lines.append(f"   详情: {details_str}")
            
            return "\n".join(lines)
        else:
            # 查看所有模块的历史
            lines = ["**所有模块状态历史** 📜\n"]
            
            for module_id in self.manager.modules.keys():
                history = self.manager.get_state_history(module_id, limit=5)
                
                if history:
                    lines.append(f"**{module_id}**")
                    for transition in history:
                        timestamp = transition.timestamp.strftime("%H:%M:%S")
                        lines.append(f"  {timestamp}: {transition.from_state} → {transition.to_state}")
                    lines.append("")
            
            if len(lines) == 1:
                return "ℹ️ 没有任何状态历史记录"
            
            return "\n".join(lines)
    
    async def _cmd_metrics(self, args: str, chat_id: str) -> str:
        """查看性能指标命令"""
        if not self.manager:
            return "❌ 模块管理器未初始化"
        
        module_id = args.strip() if args.strip() else None
        
        if module_id:
            # 查看指定模块的指标
            if module_id not in self.manager.modules:
                return f"❌ 模块不存在: {module_id}"
            
            metrics = self.manager.get_metrics(module_id)
            
            if not metrics:
                return f"ℹ️ 模块 {module_id} 没有性能指标"
            
            lines = [f"**{module_id} 性能指标** 📊\n"]
            lines.append(f"启动时间: {metrics.start_time.strftime('%Y-%m-%d %H:%M:%S') if metrics.start_time else 'N/A'}")
            lines.append(f"启动耗时: {metrics.startup_duration:.2f}s")
            lines.append(f"处理消息: {metrics.message_count} 条")
            lines.append(f"平均处理时间: {metrics.avg_processing_time:.3f}s")
            lines.append(f"最大处理时间: {metrics.max_processing_time:.3f}s")
            lines.append(f"错误次数: {metrics.error_count}")
            lines.append(f"最后消息时间: {metrics.last_message_time.strftime('%Y-%m-%d %H:%M:%S') if metrics.last_message_time else 'N/A'}")
            
            return "\n".join(lines)
        else:
            # 查看所有模块的指标
            lines = ["**所有模块性能指标** 📊\n"]
            
            all_metrics = self.manager.get_all_metrics()
            
            if not all_metrics:
                return "ℹ️ 没有任何性能指标"
            
            for module_id, metrics in all_metrics.items():
                lines.append(f"**{module_id}**")
                lines.append(f"  启动耗时: {metrics.startup_duration:.2f}s")
                lines.append(f"  处理消息: {metrics.message_count} 条")
                if metrics.message_count > 0:
                    lines.append(f"  平均处理时间: {metrics.avg_processing_time:.3f}s")
                    lines.append(f"  最大处理时间: {metrics.max_processing_time:.3f}s")
                if metrics.error_count > 0:
                    lines.append(f"  错误次数: {metrics.error_count}")
                lines.append("")
            
            return "\n".join(lines)
    
    async def _cmd_channel(self, args: str, chat_id: str) -> str:
        """渠道管理命令
        
        用法:
        /channel list - 列出所有渠道
        /channel status [channel_name] - 查看渠道状态
        /channel start <channel_name> - 启动渠道
        /channel stop <channel_name> - 停止渠道
        /channel restart <channel_name> - 重启渠道
        """
        if not self.bot:
            return "❌ Bot 实例未初始化"
        
        parts = args.strip().split()
        if len(parts) < 1:
            return """**渠道管理命令** 🔧

用法:
- `/channel list` - 列出所有渠道
- `/channel status [channel_name]` - 查看渠道状态
- `/channel start <channel_name>` - 启动渠道
- `/channel stop <channel_name>` - 停止渠道
- `/channel restart <channel_name>` - 重启渠道

示例:
- `/channel list` - 列出所有渠道
- `/channel status` - 查看所有渠道状态
- `/channel status bot1` - 查看 bot1 渠道状态
- `/channel start bot2` - 启动 bot2 渠道
- `/channel stop bot2` - 停止 bot2 渠道
- `/channel restart bot2` - 重启 bot2 渠道"""
        
        action = parts[0].lower()
        channel_name = parts[1] if len(parts) > 1 else None
        
        if action == "list":
            # 列出所有渠道
            channels = self.bot.list_channels()
            if not channels:
                return "❌ 没有可用的渠道"
            
            lines = ["**可用渠道列表** 📋\n"]
            for channel in channels:
                channel_info = self.bot.get_channel_info(channel)
                if channel_info:
                    channel_type = "企业微信" if "corp_id" in channel_info else "模拟器"
                    enabled = channel_info.get("enabled", False)
                    enabled_icon = "✅" if enabled else "❌"
                    lines.append(f"- {enabled_icon} {channel} ({channel_type})")
            
            return "\n".join(lines)
        
        elif action == "status":
            # 查看渠道状态
            if channel_name:
                # 查看指定渠道状态
                if not self.bot.get_channel_info(channel_name):
                    return f"❌ 渠道不存在: {channel_name}"
                
                channel_status = self.bot.get_channel_status(channel_name)
                lines = [f"**{channel_name} 渠道状态** 📊\n"]
                
                for module_id, module_status in channel_status.get("modules", {}).items():
                    running = module_status.get("running", False)
                    healthy = module_status.get("healthy", False)
                    
                    running_icon = "✅" if running else "❌"
                    healthy_icon = "✅" if healthy else "❌"
                    
                    lines.append(f"- {running_icon} {module_id}")
                    lines.append(f"  健康状态: {healthy_icon}")
                    lines.append(f"  启动时间: {module_status.get('started_at', 'N/A')}")
                    lines.append("")
                
                return "\n".join(lines)
            else:
                # 查看所有渠道状态
                all_status = self.bot.get_all_channels_status()
                if not all_status:
                    return "❌ 没有可用的渠道"
                
                lines = ["**所有渠道状态** 📊\n"]
                for channel_name, channel_status in all_status.items():
                    lines.append(f"**{channel_name}**")
                    
                    for module_id, module_status in channel_status.get("modules", {}).items():
                        running = module_status.get("running", False)
                        running_icon = "✅" if running else "❌"
                        lines.append(f"  {running_icon} {module_id}")
                    
                    lines.append("")
                
                return "\n".join(lines)
        
        elif action in ["start", "stop", "restart"]:
            if not channel_name:
                return f"❌ 请指定渠道名: /channel {action} <channel_name>"
            
            if not self.bot.get_channel_info(channel_name):
                return f"❌ 渠道不存在: {channel_name}"
            
            try:
                if action == "start":
                    results = await self.bot.start_channel(channel_name)
                    action_text = "启动"
                elif action == "stop":
                    results = await self.bot.stop_channel(channel_name)
                    action_text = "停止"
                else:  # restart
                    results = await self.bot.restart_channel(channel_name)
                    action_text = "重启"
                
                # 格式化结果
                lines = [f"**{channel_name} 渠道{action_text}结果** 📋\n"]
                
                success_count = 0
                fail_count = 0
                
                for module_id, success in results.items():
                    if success:
                        lines.append(f"✅ {module_id}: 成功")
                        success_count += 1
                    else:
                        lines.append(f"❌ {module_id}: 失败")
                        fail_count += 1
                
                lines.append("")
                lines.append(f"总计: {success_count} 成功, {fail_count} 失败")
                
                return "\n".join(lines)
            
            except Exception as e:
                logger.error(f"执行渠道操作失败: {e}", exc_info=True)
                return f"❌ {action_text}渠道失败: {e}"
        
        else:
            return f"❌ 未知操作: {action}\n\n发送 /channel 查看帮助"
    
    async def _cmd_snapshot(self, args: str, chat_id: str) -> str:
        """查看 tmux 界面快照
        
        功能：捕获并返回 tmux 会话的当前界面内容
        用途：当请求没有响应时，用户可以查看 tmux 中的情况
              判断是 iflow 异常了还是 iflow 还在生成中
        
        使用方法：
        - /snapshot              # 查看当前渠道的 tmux 界面
        - /snapshot bot1         # 查看指定渠道的 tmux 界面
        """
        if not self.bus:
            return "❌ 消息总线未初始化"
        
        # 解析参数
        target = args.strip() if args.strip() else None
        
        # 确定要查看的目标
        if target:
            # 用户指定了目标
            if target.startswith("iflow_"):
                # 直接指定了 iflow 模块
                module_id = target
            else:
                # 指定了渠道名，转换为 iflow 模块名
                module_id = f"iflow_{target}"
        else:
            # 未指定目标，尝试从消息上下文推断
            # 暂时使用第一个 iflow 模块
            iflow_modules = [mid for mid in self.bus.modules.keys() if mid.startswith("iflow_")]
            if not iflow_modules:
                return "❌ 没有可用的 iflow 模块"
            module_id = iflow_modules[0]
        
        # 检查模块是否存在
        if module_id not in self.bus.modules:
            return f"❌ 模块不存在: {module_id}"
        
        module = self.bus.modules[module_id]
        
        # 检查模块是否有 controller
        if not hasattr(module, 'controller'):
            return f"❌ 模块 {module_id} 没有 controller"
        
        controller = module.controller
        
        # 检查 tmux 会话是否存在
        tmux_session = controller.tmux_session
        if not tmux_session:
            return f"❌ 模块 {module_id} 没有 tmux 会话"
        
        try:
            # 捕获 tmux 输出（最后 50 行）
            output = await controller.capture_output(lines=50)
            
            if not output:
                return f"❌ 无法捕获 tmux 会话 {tmux_session} 的输出"
            
            # 清理输出（移除控制字符）
            cleaned_output = self._clean_tmux_output(output)
            
            # 截断过长的输出
            max_lines = 100
            lines = cleaned_output.split('\n')
            if len(lines) > max_lines:
                lines = lines[-max_lines:]
                truncated = True
            else:
                truncated = False
            
            # 格式化输出
            result_lines = [
                f"**{module_id} 界面快照** 📸",
                f"```\n",
                "\n".join(lines),
                f"```",
            ]
            
            if truncated:
                result_lines.append(f"\n*（仅显示最后 {max_lines} 行，共捕获 {len(output.split(chr(10)))} 行）*")
            
            return "\n".join(result_lines)
        
        except Exception as e:
            logger.error(f"捕获 tmux 快照失败: {e}", exc_info=True)
            return f"❌ 捕获 tmux 快照失败: {e}"
    
    def _clean_tmux_output(self, output: str) -> str:
        """清理 tmux 输出，移除控制字符
        
        Args:
            output: 原始 tmux 输出
            
        Returns:
            清理后的输出
        """
        import re
        
        # 移除 ANSI 控制序列
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', output)
        
        # 移除其他控制字符
        cleaned = ''.join(char for char in cleaned if char.isprintable() or char in '\n\r\t')
        
        # 移除连续的空行
        lines = cleaned.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            if line.strip() == '':
                if not prev_empty:
                    cleaned_lines.append(line)
                    prev_empty = True
            else:
                cleaned_lines.append(line)
                prev_empty = False
        
        return '\n'.join(cleaned_lines)
    
    async def _cmd_tmux(self, args: str, chat_id: str) -> str:
        """tmux 管理命令
        
        用法:
        /tmux list - 列出所有 tmux 会话
        /tmux create <name> - 创建新的 tmux 会话
        /tmux kill <name> - 杀死指定的 tmux 会话
        /tmux - 列出所有 tmux 会话（简写）
        """
        parts = args.strip().split()
        
        if not parts:
            action = "list"
        else:
            action = parts[0].lower()
            args_str = ' '.join(parts[1:]) if len(parts) > 1 else ""
        
        if action == "list":
            # 列出所有 tmux 会话
            import subprocess
            
            try:
                result = subprocess.run(
                    ["tmux", "list-sessions"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    sessions = result.stdout.strip()
                    if not sessions:
                        return "✅ 当前没有运行的 tmux 会话"
                    
                    lines = ["**tmux 会话列表** 📋\n"]
                    lines.append(sessions)
                    return "\n".join(lines)
                else:
                    return f"❌ 获取 tmux 会话列表失败: {result.stderr}"
            except Exception as e:
                return f"❌ 执行 tmux 命令失败: {e}"
        
        elif action == "create":
            # 创建新的 tmux 会话
            session_name = args_str.strip()
            if not session_name:
                return "❌ 请指定会话名称\n用法: /tmux create <会话名>"
            
            import subprocess
            
            try:
                # 检查会话是否已存在
                check_result = subprocess.run(
                    ["tmux", "has-session", "-t", session_name],
                    capture_output=True
                )
                
                if check_result.returncode == 0:
                    return f"❌ 会话 '{session_name}' 已存在"
                
                # 创建新会话
                create_result = subprocess.run(
                    ["tmux", "new-session", "-d", "-s", session_name],
                    capture_output=True,
                    text=True
                )
                
                if create_result.returncode == 0:
                    return f"✅ 已创建 tmux 会话: {session_name}"
                else:
                    return f"❌ 创建会话失败: {create_result.stderr}"
            except Exception as e:
                return f"❌ 创建会话失败: {e}"
        
        elif action == "kill":
            # 杀死 tmux 会话
            session_name = args_str.strip()
            if not session_name:
                return "❌ 请指定会话名称\n用法: /tmux kill <会话名>"
            
            import subprocess
            
            try:
                # 检查会话是否存在
                check_result = subprocess.run(
                    ["tmux", "has-session", "-t", session_name],
                    capture_output=True
                )
                
                if check_result.returncode != 0:
                    return f"❌ 会话 '{session_name}' 不存在"
                
                # 杀死会话
                kill_result = subprocess.run(
                    ["tmux", "kill-session", "-t", session_name],
                    capture_output=True,
                    text=True
                )
                
                if kill_result.returncode == 0:
                    return f"✅ 已杀死的 tmux 会话: {session_name}"
                else:
                    return f"❌ 杀死会话失败: {kill_result.stderr}"
            except Exception as e:
                return f"❌ 杀死会话失败: {e}"
        
        else:
            # 显示帮助信息
            return """**tmux 管理命令** 🔧

用法:
- `/tmux list` - 列出所有 tmux 会话
- `/tmux create <会话名>` - 创建新的 tmux 会话
- `/tmux kill <会话名>` - 杀死指定的 tmux 会话
- `/tmux` - 列出所有 tmux 会话（简写）

示例:
- `/tmux` - 查看所有 tmux 会话
- `/tmux create test` - 创建名为 test 的会话
- `/tmux kill test` - 杀死名为 test 的会话

注意:
- 创建的 tmux 会话需要手动启动 iflow
- 杀死会话会同时停止该会话中的所有进程
- 请谨慎使用 kill 命令"""

    
    
