"""
MockWeChatModule

模拟企业微信模块，用于集成测试。
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import sys
import os

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.base import BaseModule
from src.core.message import Message, MessageType, MessageContent


logger = logging.getLogger(__name__)


class MockWeChatModule(BaseModule):
    """模拟企业微信模块
    
    用于集成测试，模拟企业微信的消息收发行为。
    不依赖真实的企业微信 API。
    """
    
    def __init__(self, module_id: str = "mock_wechat", config: Dict[str, Any] = None):
        """初始化模拟企业微信模块
        
        Args:
            module_id: 模块唯一标识符
            config: 配置（可选）
        """
        super().__init__(module_id)
        
        self.config = config or {}
        self.messages_sent: List[Dict[str, Any]] = []      # 发送的消息记录
        self.messages_received: List[Dict[str, Any]] = []  # 接收的消息记录
        self.default_chat_id = self.config.get("user_id", "test_user")
        
        logger.info(f"[{self.module_id}] MockWeChatModule 初始化完成")
    
    async def _on_start(self) -> None:
        """启动时的钩子方法"""
        logger.info(f"[{self.module_id}] ✅ MockWeChatModule 启动")
    
    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        logger.info(f"[{self.module_id}] ✅ MockWeChatModule 停止")
    
    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法
        
        模拟将消息发送到企业微信（实际只是记录）。
        
        Args:
            message: 接收到的消息
        """
        content = ""
        if message.content:
            if hasattr(message.content, 'text'):
                content = message.content.text
            elif isinstance(message.content, str):
                content = message.content
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "message_id": message.id,
            "content": content,
            "from_module": message.from_module,
            "chat_id": message.chat_id,
            "is_group": message.is_group
        }
        
        self.messages_sent.append(record)
        
        logger.info(f"[{self.module_id}] 📤 模拟发送消息:")
        logger.info(f"   内容: {content[:50]}{'...' if len(content) > 50 else ''}")
        logger.info(f"   目标: {message.chat_id or self.default_chat_id}")
    
    async def simulate_receive(
        self,
        content: str,
        chat_id: str = None,
        sender_id: str = None,
        is_group: bool = False,
        msg_type: str = "text"
    ) -> Message:
        """模拟接收来自企业微信的消息
        
        Args:
            content: 消息内容
            chat_id: 聊天ID
            sender_id: 发送者ID
            is_group: 是否为群聊
            msg_type: 消息类型
            
        Returns:
            创建的消息对象
        """
        chat_id = chat_id or self.default_chat_id
        sender_id = sender_id or f"{chat_id}_sender"
        
        # 创建消息对象
        message = Message(
            id=Message.generate_id(),
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text=content),
            from_module=self.module_id,
            chat_id=chat_id,
            user_id=sender_id,
            is_group=is_group,
            metadata={
                "msg_type": msg_type,
                "simulated": True
            }
        )
        
        # 记录接收
        record = {
            "timestamp": datetime.now().isoformat(),
            "message_id": message.id,
            "content": content,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "is_group": is_group,
            "msg_type": msg_type
        }
        self.messages_received.append(record)
        
        logger.info(f"[{self.module_id}] 📥 模拟接收消息:")
        logger.info(f"   内容: {content[:50]}{'...' if len(content) > 50 else ''}")
        logger.info(f"   来源: {sender_id}")
        
        # 发送到消息总线
        if self.message_bus:
            await self.send_to_bus(message)
            logger.info(f"[{self.module_id}] 消息已发送到消息总线")
        else:
            logger.warning(f"[{self.module_id}] 消息总线未设置，消息未转发")
        
        return message
    
    async def send_to_wechat(
        self,
        content: str,
        chat_id: str = None,
        is_group: bool = False
    ) -> bool:
        """模拟发送消息到企业微信
        
        Args:
            content: 消息内容
            chat_id: 聊天ID
            is_group: 是否为群聊
            
        Returns:
            始终返回 True（模拟成功）
        """
        chat_id = chat_id or self.default_chat_id
        
        record = {
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "chat_id": chat_id,
            "is_group": is_group
        }
        self.messages_sent.append(record)
        
        logger.info(f"[{self.module_id}] 📤 模拟发送消息到企业微信:")
        logger.info(f"   内容: {content[:50]}{'...' if len(content) > 50 else ''}")
        logger.info(f"   目标: {chat_id}")
        
        return True
    
    def get_sent_messages(self) -> List[Dict[str, Any]]:
        """获取发送的消息列表
        
        Returns:
            发送消息列表
        """
        return self.messages_sent.copy()
    
    def get_received_messages(self) -> List[Dict[str, Any]]:
        """获取接收的消息列表
        
        Returns:
            接收消息列表
        """
        return self.messages_received.copy()
    
    def clear_messages(self) -> None:
        """清空消息记录"""
        self.messages_sent.clear()
        self.messages_received.clear()
        logger.info(f"[{self.module_id}] 消息记录已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "module_id": self.module_id,
            "running": self._running,
            "sent_count": len(self.messages_sent),
            "received_count": len(self.messages_received),
            "default_chat_id": self.default_chat_id
        }
    
    def get_last_sent(self) -> Optional[Dict[str, Any]]:
        """获取最后发送的消息
        
        Returns:
            最后发送的消息，如果没有则返回 None
        """
        return self.messages_sent[-1] if self.messages_sent else None
    
    def get_last_received(self) -> Optional[Dict[str, Any]]:
        """获取最后接收的消息
        
        Returns:
            最后接收的消息，如果没有则返回 None
        """
        return self.messages_received[-1] if self.messages_received else None
