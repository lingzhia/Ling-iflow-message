"""渠道基类。"""

from typing import Optional, Dict, Any, Callable, Awaitable
from abc import ABC, abstractmethod


class BaseChannel(ABC):
    """渠道基类。"""
    
    def __init__(self, config: Any, bus: Optional[Any] = None):
        """初始化渠道。
        
        Args:
            config: 渠道配置
            bus: 消息总线（可选）
        """
        self.config = config
        self._bus = bus
        self._running = False
        self._message_handler: Optional[Callable] = None
    
    @abstractmethod
    async def start(self) -> None:
        """启动渠道。"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止渠道。"""
        pass
    
    @abstractmethod
    async def send(self, content: str, chat_id: Optional[str] = None, **kwargs) -> bool:
        """发送消息。
        
        Args:
            content: 消息内容
            chat_id: 聊天 ID（可选）
            **kwargs: 其他参数
            
        Returns:
            是否发送成功
        """
        pass
    
    def set_message_handler(self, handler: Callable) -> None:
        """设置消息处理器。
        
        Args:
            handler: 消息处理器函数，签名为：
                    async def handler(content: str, sender_id: str, chat_id: str, 
                                     is_group: bool, metadata: Optional[dict] = None) -> None
        """
        self._message_handler = handler
    
    async def _handle_message(self, content: str, sender_id: str, chat_id: str, 
                             is_group: bool, metadata: Optional[dict] = None) -> None:
        """处理接收到的消息。
        
        Args:
            content: 消息内容
            sender_id: 发送者 ID
            chat_id: 聊天 ID
            is_group: 是否为群聊
            metadata: 元数据
        """
        if self._message_handler:
            await self._message_handler(content, sender_id, chat_id, is_group, metadata)