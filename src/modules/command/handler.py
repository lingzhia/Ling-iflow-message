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
    
    def __init__(self, message_bus: Optional["MessageBus"] = None):
        """初始化命令处理器
        
        Args:
            message_bus: 消息总线实例
        """
        self.bus = message_bus
        self._commands = {}
        self._register_builtin_commands()
    
    def set_message_bus(self, bus: "MessageBus") -> None:
        """设置消息总线
        
        Args:
            bus: 消息总线实例
        """
        self.bus = bus
    
    def _register_builtin_commands(self) -> None:
        """注册内置命令"""
        self._commands = {
            "/help": self._cmd_help,
            "/status": self._cmd_status,
            "/new": self._cmd_new,
            "/sessions": self._cmd_sessions,
            "/lscmd": self._cmd_lscmd,
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
- `/help`：显示此帮助
- `/lscmd`：列出所有可用命令"""
    
    async def _cmd_status(self, args: str, chat_id: str) -> str:
        """状态命令"""
        if not self.bus:
            return "❌ 消息总线未初始化"
        
        # 查找 iflow 模块
        status_parts = []
        
        for module_id, module in self.bus.modules.items():
            if module_id.startswith("iflow_") and hasattr(module, 'get_status_message'):
                status_parts.append(module.get_status_message())
        
        if not status_parts:
            return "❌ 没有可用的 iflow 模块"
        
        return "\n\n".join(status_parts)
    
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
- `/help` - 显示帮助信息
- `/lscmd` - 列出所有可用命令

**使用提示：**
- 直接发送消息即可与 iflow 对话
- 命令不区分大小写"""
