"""
Message Converter

消息转换器，负责平台特定消息格式与标准 Message 格式之间的转换。
"""

import logging
from typing import Dict, Any, Optional, Callable

from ...core.message import Message, MessageContent, MessageType


logger = logging.getLogger(__name__)


class MessageConverter:
    """消息转换器
    
    提供平台特定消息与标准 Message 格式之间的双向转换能力。
    支持通过自定义转换器扩展不同平台的消息格式。
    """
    
    def __init__(self):
        """初始化消息转换器"""
        self._inbound_converters: Dict[str, Callable] = {}
        self._outbound_converters: Dict[str, Callable] = {}
    
    def register_inbound_converter(
        self,
        platform: str,
        converter: Callable[[Dict[str, Any]], Message]
    ) -> None:
        """注册入站消息转换器
        
        Args:
            platform: 平台名称（如 "wechat", "telegram"）
            converter: 转换函数，接收平台消息字典，返回标准 Message
        """
        self._inbound_converters[platform] = converter
        logger.debug(f"注册入站转换器: {platform}")
    
    def register_outbound_converter(
        self,
        platform: str,
        converter: Callable[[Message], Dict[str, Any]]
    ) -> None:
        """注册出站消息转换器
        
        Args:
            platform: 平台名称（如 "wechat", "telegram"）
            converter: 转换函数，接收标准 Message，返回平台消息字典
        """
        self._outbound_converters[platform] = converter
        logger.debug(f"注册出站转换器: {platform}")
    
    def from_platform_message(
        self,
        platform: str,
        platform_msg: Dict[str, Any],
        default_module_id: str,
        default_chat_id: str = ""
    ) -> Optional[Message]:
        """将平台消息转换为标准 Message
        
        Args:
            platform: 平台名称
            platform_msg: 平台特定消息
            default_module_id: 默认模块 ID
            default_chat_id: 默认聊天 ID
            
        Returns:
            标准消息对象，如果转换失败返回 None
        """
        converter = self._inbound_converters.get(platform)
        
        if not converter:
            logger.warning(f"未找到 {platform} 的入站转换器")
            return None
        
        try:
            message = converter(platform_msg)
            
            # 设置默认值
            if not message.from_module:
                message.from_module = default_module_id
            
            if not message.chat_id:
                message.chat_id = platform_msg.get("chat_id", default_chat_id)
            
            return message
            
        except Exception as e:
            logger.error(f"入站消息转换失败 ({platform}): {e}", exc_info=True)
            return None
    
    def to_platform_message(
        self,
        platform: str,
        message: Message,
        default_chat_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """将标准 Message 转换为平台消息
        
        Args:
            platform: 平台名称
            message: 标准消息对象
            default_chat_id: 默认聊天 ID
            
        Returns:
            平台消息字典，如果转换失败返回 None
        """
        converter = self._outbound_converters.get(platform)
        
        if not converter:
            logger.warning(f"未找到 {platform} 的出站转换器")
            return None
        
        try:
            platform_msg = converter(message)
            
            # 设置默认值
            if not platform_msg.get("chat_id"):
                platform_msg["chat_id"] = message.chat_id or default_chat_id
            
            return platform_msg
            
        except Exception as e:
            logger.error(f"出站消息转换失败 ({platform}): {e}", exc_info=True)
            return None
    
    def create_wechat_inbound_message(
        self,
        wechat_msg: Dict[str, Any],
        module_id: str
    ) -> Message:
        """创建企业微信入站消息
        
        Args:
            wechat_msg: 企业微信消息
            module_id: 模块 ID
            
        Returns:
            标准消息对象
        """
        content = wechat_msg.get("content", "")
        chat_id = wechat_msg.get("chat_id", "")
        sender_id = wechat_msg.get("sender_id", "")
        is_group = wechat_msg.get("is_group", False)
        
        return Message(
            id=Message.generate_id(),
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text=content),
            from_module=module_id,
            chat_id=chat_id,
            user_id=sender_id,
            is_group=is_group,
            metadata={
                "msg_type": wechat_msg.get("msg_type", "text")
            }
        )
    
    def create_wechat_outbound_message(
        self,
        message: Message
    ) -> Dict[str, Any]:
        """创建企业微信出站消息
        
        Args:
            message: 标准消息对象
            
        Returns:
            企业微信消息字典
        """
        content = message.content.text if message.content else ""
        
        # 支持多种字段名获取聊天 ID
        # receiver: IFlowModule COMPLETE 消息使用
        # chat_id: 标准字段
        chat_id = (
            message.chat_id or
            message.metadata.get("receiver") or
            message.metadata.get("chat_id", "")
        )
        
        return {
            "content": content,
            "chat_id": chat_id,
            "is_group": message.is_group,
            "msg_type": "text"
        }
    
    def create_iflow_inbound_message(
        self,
        iflow_msg: Dict[str, Any],
        module_id: str
    ) -> Message:
        """创建 iflow 入站消息
        
        Args:
            iflow_msg: iflow 消息
            module_id: 模块 ID
            
        Returns:
            标准消息对象
        """
        content = iflow_msg.get("content", "")
        chat_id = iflow_msg.get("chat_id", "")
        user_id = iflow_msg.get("user_id", "")
        is_group = iflow_msg.get("is_group", False)
        source = iflow_msg.get("source", "")
        scope = iflow_msg.get("scope", "reply_only")
        
        return Message(
            id=Message.generate_id(),
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text=content),
            from_module=module_id,
            chat_id=chat_id,
            user_id=user_id,
            is_group=is_group,
            metadata={
                "msg_type": "iflow_request",
                "source": source,
                "scope": scope
            }
        )
    
    def create_iflow_outbound_message(
        self,
        message: Message
    ) -> Dict[str, Any]:
        """创建 iflow 出站消息
        
        Args:
            message: 标准消息对象
            
        Returns:
            iflow 消息字典
        """
        content = message.content.text if message.content else ""
        
        return {
            "content": content,
            "chat_id": message.metadata.get("chat_id", ""),
            "user_id": message.metadata.get("user_id", ""),
            "is_group": message.metadata.get("is_group", False),
            "receiver": message.metadata.get("receiver", ""),
            "scope": message.metadata.get("scope", "reply_only"),
            "reply_type": message.metadata.get("reply_type", "reply")
        }