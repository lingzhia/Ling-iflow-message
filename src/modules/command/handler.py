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
        
        # 未知命令
        return f"❌ 未知命令: {cmd_name}\n\n发送 /help 查看可用命令"
    
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
- `/help`：显示此帮助
- `/lscmd`：列出所有可用命令"""
    
    async def _cmd_status(self, args: str, chat_id: str) -> str:
        """状态命令 - 查看所有模块状态"""
        if not self.bus:
            return "❌ 消息总线未初始化"
        
        status_lines = ["**服务状态** 📊\n"]
        
        # 获取所有模块状态
        if self.manager:
            all_status = self.manager.get_all_status()
            
            if not all_status:
                status_lines.append("❌ 没有可用的模块")
                return "\n".join(status_lines)
            
            # 按模块类型分组
            iflow_modules = []
            wechat_modules = []
            simulator_modules = []
            other_modules = []
            
            for module_id, status in all_status.items():
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
                    running_icon = "✅" if status['running'] else "❌"
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
                    
                    status_lines.append(f"- {running_icon} {module_id}")
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
                    running_icon = "✅" if status['running'] else "❌"
                    healthy_icon = "✅" if status['healthy'] else "❌"
                    
                    status_lines.append(f"- {running_icon} {module_id}")
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
                    running_icon = "✅" if status['running'] else "❌"
                    healthy_icon = "✅" if status['healthy'] else "❌"
                    
                    status_lines.append(f"- {running_icon} {module_id}")
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
                    running_icon = "✅" if status['running'] else "❌"
                    healthy_icon = "✅" if status['healthy'] else "❌"
                    
                    status_lines.append(f"- {running_icon} {module_id}")
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

**使用提示：**
- 直接发送消息即可与 iflow 对话
- 命令不区分大小写
- 模块 ID 可省略，将显示所有模块的信息"""
    
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
