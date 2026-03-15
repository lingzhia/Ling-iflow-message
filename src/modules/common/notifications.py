"""
Notification Manager

通知管理器，负责模块启动、停止等事件的通知管理。
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable


logger = logging.getLogger(__name__)


class NotificationManager:
    """通知管理器
    
    负责管理模块启动、停止等事件的通知。
    支持通知模板和自定义通知处理器。
    """
    
    def __init__(self):
        """初始化通知管理器"""
        self._notification_handlers: Dict[str, Callable] = {}
        self._templates: Dict[str, str] = {}
        
        # 注册默认模板
        self._register_default_templates()
    
    def _register_default_templates(self) -> None:
        """注册默认通知模板"""
        self._templates["startup"] = """**🤖 {module_name} 已启动**

📅 启动时间: {startup_time}
{service_info}

✅ 服务运行正常，可以开始使用！

---
📋 快速开始：
{quick_start}

💡 提示：{tips}"""
        
        self._templates["startup_with_error"] = """**🤖 {module_name} 已启动**

📅 启动时间: {startup_time}
{service_info}

⚠️ {error_message}

---
📋 可用命令：
{available_commands}

💡 提示：{tips}"""
        
        self._templates["shutdown"] = """**🛑 {module_name} 已停止**

📅 关闭时间: {shutdown_time}
{service_info}

---
如需重新启动，请执行:
```bash
{restart_command}
```"""
    
    def register_notification_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any]], bool]
    ) -> None:
        """注册通知处理器
        
        Args:
            event_type: 事件类型（如 "startup", "shutdown"）
            handler: 通知处理器函数，接收通知数据字典，返回是否成功
        """
        self._notification_handlers[event_type] = handler
        logger.debug(f"注册通知处理器: {event_type}")
    
    def unregister_notification_handler(self, event_type: str) -> None:
        """注销通知处理器
        
        Args:
            event_type: 事件类型
        """
        if event_type in self._notification_handlers:
            del self._notification_handlers[event_type]
            logger.debug(f"注销通知处理器: {event_type}")
    
    def register_template(self, name: str, template: str) -> None:
        """注册通知模板
        
        Args:
            name: 模板名称
            template: 模板内容（支持 {variable} 占位符）
        """
        self._templates[name] = template
        logger.debug(f"注册通知模板: {name}")
    
    def get_template(self, name: str) -> Optional[str]:
        """获取通知模板
        
        Args:
            name: 模板名称
            
        Returns:
            模板内容，如果不存在返回 None
        """
        return self._templates.get(name)
    
    def render_template(self, name: str, **kwargs) -> Optional[str]:
        """渲染通知模板
        
        Args:
            name: 模板名称
            **kwargs: 模板变量
            
        Returns:
            渲染后的通知内容，如果模板不存在返回 None
        """
        template = self._templates.get(name)
        if not template:
            logger.warning(f"通知模板不存在: {name}")
            return None
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"渲染模板失败，缺少变量: {e}")
            return None
    
    async def send_notification(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """发送通知
        
        Args:
            event_type: 事件类型
            data: 通知数据
            
        Returns:
            是否发送成功
        """
        handler = self._notification_handlers.get(event_type)
        
        if not handler:
            logger.warning(f"未找到 {event_type} 的通知处理器")
            return False
        
        try:
            return await handler(data) if hasattr(handler, '__await__') else handler(data)
        except Exception as e:
            logger.error(f"发送通知失败 ({event_type}): {e}", exc_info=True)
            return False
    
    async def send_startup_notification(
        self,
        module_name: str,
        service_info: str = "",
        quick_start: str = "",
        tips: str = "",
        error_message: Optional[str] = None,
        available_commands: str = ""
    ) -> bool:
        """发送启动通知
        
        Args:
            module_name: 模块名称
            service_info: 服务信息
            quick_start: 快速开始说明
            tips: 提示信息
            error_message: 错误消息（如果有）
            available_commands: 可用命令（如果有错误时）
            
        Returns:
            是否发送成功
        """
        startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 选择模板
        template_name = "startup_with_error" if error_message else "startup"
        
        # 渲染通知内容
        content = self.render_template(
            template_name,
            module_name=module_name,
            startup_time=startup_time,
            service_info=service_info,
            quick_start=quick_start,
            tips=tips,
            error_message=error_message,
            available_commands=available_commands
        )
        
        if not content:
            return False
        
        # 发送通知
        return await self.send_notification("startup", {
            "content": content,
            "event_type": "startup",
            "timestamp": startup_time
        })
    
    async def send_shutdown_notification(
        self,
        module_name: str,
        service_info: str = "",
        restart_command: str = ""
    ) -> bool:
        """发送停止通知
        
        Args:
            module_name: 模块名称
            service_info: 服务信息
            restart_command: 重启命令
            
        Returns:
            是否发送成功
        """
        shutdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 渲染通知内容
        content = self.render_template(
            "shutdown",
            module_name=module_name,
            shutdown_time=shutdown_time,
            service_info=service_info,
            restart_command=restart_command
        )
        
        if not content:
            return False
        
        # 发送通知
        return await self.send_notification("shutdown", {
            "content": content,
            "event_type": "shutdown",
            "timestamp": shutdown_time
        })
    
    async def send_custom_notification(
        self,
        event_type: str,
        content: str,
        **metadata
    ) -> bool:
        """发送自定义通知
        
        Args:
            event_type: 事件类型
            content: 通知内容
            **metadata: 附加元数据
            
        Returns:
            是否发送成功
        """
        return await self.send_notification(event_type, {
            "content": content,
            "event_type": event_type,
            **metadata
        })