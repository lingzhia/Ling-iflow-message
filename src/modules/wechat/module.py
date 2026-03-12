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
            
            startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            callback_port = self.config.get("callback_port", 8788)
            
            # 获取 iflow 运行状态
            iflow_running = self._check_iflow_status()
            
            if iflow_running:
                notification = f"""**🤖 iFlow 企业微信机器人已启动**

📅 启动时间: {startup_time}
📁 工作目录: {self.config.get("workspace", "~/.iflow")}
💻 tmux 会话: {self.config.get("tmux_session", "iflow")} ✓
🌐 回调端口: {callback_port}

✅ 服务运行正常，可以开始使用！

---
📋 快速开始：
• 直接发送消息：执行 iFlow 命令
• `/lscmd`：查看所有可用命令

💡 提示：输入 `/lscmd` 查看完整的命令列表和功能说明。"""
            else:
                notification = f"""**🤖 iFlow 企业微信机器人已启动**

📅 启动时间: {startup_time}
💻 tmux 会话: 无连接
📁 工作目录: {self.config.get("workspace", "~/.iflow")}
🌐 回调端口: {callback_port}

⚠️ iflow 未运行，无法处理消息

---
📋 可用命令：
• `/lscmd`：查看所有可用命令

💡 提示：检查 iflow 是否正常启动。"""
            
            success = await self.channel.send_message(notification, user_id, False)
            
            if success:
                logger.info(f"[{self.module_id}] 启动通知已发送到 {user_id}")
            else:
                logger.error(f"[{self.module_id}] 启动通知发送失败")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送启动通知失败: {e}", exc_info=True)
    
    async def _send_shutdown_notification(self) -> None:
        """发送停止通知到企业微信"""
        try:
            user_id = self.config.get("user_id", "")
            if not user_id:
                logger.warning(f"[{self.module_id}] 未配置 user_id，跳过停止通知")
                return
            
            shutdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 检查 iflow 运行状态
            iflow_running = self._check_iflow_status()
            
            if iflow_running:
                notification = f"""**🛑 iFlow 企业微信机器人已停止**

📅 关闭时间: {shutdown_time}
📁 工作目录: {self.config.get("workspace", "~/.iflow")}
💻 tmux 会话: {self.config.get("tmux_session", "iflow")}

---
如需重新启动，请执行:
```bash
python3 -m src.bot config.json
```"""
            else:
                notification = f"""**🛑 iFlow 企业微信机器人已停止**

📅 关闭时间: {shutdown_time}
💻 tmux 会话: 无连接
📁 工作目录: {self.config.get("workspace", "~/.iflow")}

---
如需重新启动，请执行:
```bash
python3 -m src.bot config.json
```"""
            
            success = await self.channel.send_message(notification, user_id, False)
            
            if success:
                logger.info(f"[{self.module_id}] 停止通知已发送到 {user_id}")
            else:
                logger.error(f"[{self.module_id}] 停止通知发送失败")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送停止通知失败: {e}", exc_info=True)
    
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
            # 提取消息内容
            content = message.content.text if message.content else ""
            
            if not content:
                logger.warning(f"[{self.module_id}] 收到空消息")
                return
            
            # 获取聊天ID
            chat_id = message.chat_id or self.config.get("user_id", "")
            is_group = message.is_group
            
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
            
            # 普通消息：创建消息对象并发送到消息总线
            message = Message(
                id=Message.generate_id(),
                type=MessageType.TEXT,
                content=MessageContent.text(content),
                from_module=self.module_id,
                chat_id=chat_id,
                user_id=sender_id,
                is_group=is_group,
                metadata={
                    "msg_type": wechat_msg.get("msg_type", "text")
                }
            )
            
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