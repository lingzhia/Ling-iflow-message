"""
WeChat Module

企业微信消息模块，集成 WeChatChannel。
"""

import logging
from typing import Dict, Any

from ...core.base import BaseModule
from ...core.message import Message, MessageType
from .channel import WeChatChannel


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
    
    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        logger.info(f"[{self.module_id}] 停止企业微信模块")
        
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
            # 创建消息对象
            message = Message(
                id=Message.generate_id(),
                type=MessageType.TEXT,
                content=wechat_msg.get("content", ""),
                from_module=self.module_id,
                chat_id=wechat_msg.get("chat_id", ""),
                user_id=wechat_msg.get("sender_id", ""),
                is_group=wechat_msg.get("is_group", False),
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