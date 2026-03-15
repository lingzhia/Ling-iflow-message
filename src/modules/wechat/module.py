"""
WeChat Module

企业微信消息模块，集成 WeChatChannel 和 CommandHandler。
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from ...core.base import BaseModule
from ...core.message import Message, MessageType, MessageContent
from .channel import WeChatChannel
from ..command import CommandHandler


logger = logging.getLogger(__name__)


class WeChatModule(BaseModule):
    """企业微信模块
    
    封装企业微信消息通道，实现与消息总线的集成。
    """
    
    def __init__(self, module_id: str, config: Dict[str, Any]):
        """初始化企业微信模块
        
        Args:
            module_id: 模块唯一标识符
            config: 企业微信配置
        """
        super().__init__(module_id)
        
        self.config = config
        self.channel = WeChatChannel(config)
        self.command_handler = CommandHandler()
        
        # 导入通用组件
        from ..common.converter import MessageConverter
        from ..common.notifications import NotificationManager
        self.converter = MessageConverter()
        self.notification_manager = NotificationManager()
        
        # 注册通知处理器
        self.notification_manager.register_notification_handler("startup", self._handle_startup_notification)
        self.notification_manager.register_notification_handler("shutdown", self._handle_shutdown_notification)
        
        # 设置消息处理器
        self.channel.set_message_handler(self._on_wechat_message)
    
    async def _on_start(self) -> None:
        """启动时的钩子方法"""
        logger.info(f"[{self.module_id}] 启动企业微信模块")
        
        # 启动通道
        success = await self.channel.start()
        
        if not success:
            raise RuntimeError(f"[{self.module_id}] 启动企业微信通道失败")
        
        logger.info(f"[{self.module_id}] 企业微信模块启动完成")
        
        # 发送启动通知
        await self._send_startup_notification()
    
    def set_message_bus(self, bus) -> None:
        """设置消息总线
        
        Args:
            bus: 消息总线实例
        """
        super().set_message_bus(bus)
        # 同时设置给 CommandHandler
        self.command_handler.set_message_bus(bus)
    
    async def _send_startup_notification(self) -> None:
        """发送启动通知到企业微信"""
        try:
            user_id = self.config.get("user_id", "")
            if not user_id:
                logger.warning(f"[{self.module_id}] 未配置 user_id，跳过启动通知")
                return
            
            callback_port = self.config.get("callback_port", 8788)
            tmux_session = self.config.get("tmux_session", "iflow")
            workspace = self.config.get("workspace", "~/.iflow")
            
            # 获取 iflow 运行状态
            iflow_running = self._check_iflow_status()
            
            if iflow_running:
                service_info = f"""📁 工作目录: {workspace}
💻 tmux 会话: {tmux_session} ✓
🌐 回调端口: {callback_port}"""
                quick_start = """• 直接发送消息：执行 iFlow 命令
• `/lscmd`：查看所有可用命令"""
                tips = "输入 `/lscmd` 查看完整的命令列表和功能说明。"
                
                await self.notification_manager.send_startup_notification(
                    module_name="iFlow 企业微信机器人",
                    service_info=service_info,
                    quick_start=quick_start,
                    tips=tips
                )
            else:
                service_info = f"""💻 tmux 会话: 无连接
📁 工作目录: {workspace}
🌐 回调端口: {callback_port}"""
                available_commands = """• `/lscmd`：查看所有可用命令"""
                tips = "检查 iflow 是否正常启动。"
                
                await self.notification_manager.send_startup_notification(
                    module_name="iFlow 企业微信机器人",
                    service_info=service_info,
                    tips=tips,
                    error_message="iflow 未运行，无法处理消息",
                    available_commands=available_commands
                )
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送启动通知失败: {e}", exc_info=True)
    
    async def _send_shutdown_notification(self) -> None:
        """发送停止通知到企业微信"""
        try:
            user_id = self.config.get("user_id", "")
            if not user_id:
                logger.warning(f"[{self.module_id}] 未配置 user_id，跳过停止通知")
                return
            
            tmux_session = self.config.get("tmux_session", "iflow")
            workspace = self.config.get("workspace", "~/.iflow")
            
            # 检查 iflow 运行状态
            iflow_running = self._check_iflow_status()
            
            if iflow_running:
                service_info = f"""📁 工作目录: {workspace}
💻 tmux 会话: {tmux_session}"""
            else:
                service_info = f"""💻 tmux 会话: 无连接
📁 工作目录: {workspace}"""
            
            restart_command = "python3 -m src.bot config.json"
            
            await self.notification_manager.send_shutdown_notification(
                module_name="iFlow 企业微信机器人",
                service_info=service_info,
                restart_command=restart_command
            )
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送停止通知失败: {e}", exc_info=True)
    
    def _handle_startup_notification(self, data: Dict[str, Any]) -> bool:
        """处理启动通知
        
        Args:
            data: 通知数据
            
        Returns:
            是否发送成功
        """
        try:
            content = data.get("content", "")
            user_id = self.config.get("user_id", "")
            
            if not content or not user_id:
                return False
            
            # 使用 run_shell_command 在后台执行
            import asyncio
            asyncio.create_task(self.channel.send_message(content, user_id, False))
            
            logger.info(f"[{self.module_id}] 启动通知已发送到 {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 启动通知处理失败: {e}", exc_info=True)
            return False
    
    def _handle_shutdown_notification(self, data: Dict[str, Any]) -> bool:
        """处理停止通知
        
        Args:
            data: 通知数据
            
        Returns:
            是否发送成功
        """
        try:
            content = data.get("content", "")
            user_id = self.config.get("user_id", "")
            
            if not content or not user_id:
                return False
            
            # 使用 run_shell_command 在后台执行
            import asyncio
            asyncio.create_task(self.channel.send_message(content, user_id, False))
            
            logger.info(f"[{self.module_id}] 停止通知已发送到 {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 停止通知处理失败: {e}", exc_info=True)
            return False
    
    def _check_iflow_status(self) -> bool:
        """检查 iflow 运行状态
        
        Returns:
            iflow 是否运行中
        """
        try:
            # 这里简化处理，通过检查绑定关系来判断
            # 实际应该检查 iflow 模块的运行状态
            return True
        except Exception:
            return False
    
    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        logger.info(f"[{self.module_id}] 停止企业微信模块")
        
        # 发送停止通知
        await self._send_shutdown_notification()
        
        # 停止通道
        await self.channel.stop()
        
        logger.info(f"[{self.module_id}] 企业微信模块已停止")
    
    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法
        
        Args:
            message: 接收到的消息
        """
        try:
            # 使用消息转换器转换为平台消息
            platform_msg = self.converter.create_wechat_outbound_message(message)
            
            # 提取消息内容
            content = platform_msg.get("content", "")
            
            if not content:
                logger.warning(f"[{self.module_id}] 收到空消息")
                return
            
            # 获取聊天ID
            chat_id = platform_msg.get("chat_id") or self.config.get("user_id", "")
            is_group = platform_msg.get("is_group", False)
            
            # 发送到企业微信
            success = await self.channel.send_message(content, chat_id, is_group)
            
            if success:
                logger.info(f"[{self.module_id}] 消息已发送到企业微信")
            else:
                logger.error(f"[{self.module_id}] 消息发送失败")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理消息失败: {e}", exc_info=True)
    
    async def _on_wechat_message(self, wechat_msg: Dict[str, Any]) -> None:
        """企业微信消息回调
        
        Args:
            wechat_msg: 企业微信消息
        """
        try:
            content = wechat_msg.get("content", "")
            chat_id = wechat_msg.get("chat_id", "")
            sender_id = wechat_msg.get("sender_id", "")
            is_group = wechat_msg.get("is_group", False)
            
            # 解析命令
            parsed = self.command_handler.parse_command(content)
            
            # 如果是命令，执行命令并回复
            if parsed.get("is_command"):
                result = await self.command_handler.execute(parsed, chat_id)
                if result:
                    await self.channel.send_message(result, chat_id, is_group)
                return
            
            # 使用消息转换器创建标准消息对象
            message = self.converter.create_wechat_inbound_message(wechat_msg, self.module_id)
            
            # 发送到消息总线
            if self.message_bus:
                await self.send_to_bus(message)
                logger.info(f"[{self.module_id}] 企业微信消息已发送到消息总线")
            else:
                logger.warning(f"[{self.module_id}] 消息总线未设置")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理企业微信消息失败: {e}", exc_info=True)
    
    async def send_to_wechat(self, content: str, chat_id: str = None, is_group: bool = False) -> bool:
        """发送消息到企业微信
        
        Args:
            content: 消息内容
            chat_id: 聊天ID（可选）
            is_group: 是否为群聊
            
        Returns:
            是否发送成功
        """
        if chat_id is None:
            chat_id = self.config.get("user_id", "")
        
        return await self.channel.send_message(content, chat_id, is_group)
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态
        
        Returns:
            状态信息字典
        """
        return {
            "module_id": self.module_id,
            "running": self._running,
            "corp_id": self.config.get("corp_id", ""),
            "agent_id": self.config.get("agent_id", ""),
            "user_id": self.config.get("user_id", ""),
            "callback_port": self.config.get("callback_port", 8788)
        }