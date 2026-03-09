"""消息分发器 - 实现观察者模式，支持多订阅者接收 iflow 交互界面消息"""

from typing import Callable, Dict, Optional, Any
from loguru import logger
import asyncio


class MessageDispatcher:
    """消息分发器（单例模式）。
    
    管理 iflow 交互界面消息的订阅者，当检测到新消息时，
    将消息广播给所有已注册的订阅者。
    
    使用示例：
        # 获取分发器实例
        dispatcher = MessageDispatcher()
        
        # 注册订阅者
        async def callback(message: str, metadata: dict):
            print(f"收到消息: {message}")
        
        dispatcher.subscribe("wechat_bot", callback)
        
        # 广播消息
        await dispatcher.broadcast("你好", {"source": "iflow"})
        
        # 取消订阅
        dispatcher.unsubscribe("wechat_bot")
    """
    
    _instance: Optional['MessageDispatcher'] = None
    
    def __new__(cls):
        """实现单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers: Dict[str, Callable] = {}
            cls._instance._metadata: Dict[str, Dict] = {}
            logger.info("[MessageDispatcher] 创建分发器实例")
        return cls._instance
    
    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[str, Dict[str, Any]], Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """注册订阅者。
        
        Args:
            subscriber_id: 订阅者唯一标识
            callback: 回调函数，接收 message 和 metadata 参数
            metadata: 订阅者元数据（可选）
            
        Returns:
            是否注册成功
            
        Raises:
            ValueError: 如果 subscriber_id 已存在
        """
        if subscriber_id in self._subscribers:
            logger.warning(f"[MessageDispatcher] 订阅者 {subscriber_id} 已存在，将覆盖")
        
        self._subscribers[subscriber_id] = callback
        self._metadata[subscriber_id] = metadata or {}
        
        logger.info(
            f"[MessageDispatcher] 订阅者 {subscriber_id} 已注册，"
            f"当前订阅者数量: {len(self._subscribers)}"
        )
        return True
    
    def unsubscribe(self, subscriber_id: str) -> bool:
        """取消订阅。
        
        Args:
            subscriber_id: 订阅者唯一标识
            
        Returns:
            是否取消成功
        """
        if subscriber_id not in self._subscribers:
            logger.warning(f"[MessageDispatcher] 订阅者 {subscriber_id} 不存在")
            return False
        
        del self._subscribers[subscriber_id]
        del self._metadata[subscriber_id]
        
        logger.info(
            f"[MessageDispatcher] 订阅者 {subscriber_id} 已取消订阅，"
            f"当前订阅者数量: {len(self._subscribers)}"
        )
        return True
    
    def has_subscriber(self, subscriber_id: str) -> bool:
        """检查订阅者是否存在。
        
        Args:
            subscriber_id: 订阅者唯一标识
            
        Returns:
            是否存在
        """
        return subscriber_id in self._subscribers
    
    def get_subscribers(self) -> list:
        """获取所有订阅者列表。
        
        Returns:
            订阅者 ID 列表
        """
        return list(self._subscribers.keys())
    
    def get_subscriber_count(self) -> int:
        """获取订阅者数量。
        
        Returns:
            订阅者数量
        """
        return len(self._subscribers)
    
    async def broadcast(
        self,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """广播消息到所有订阅者。
        
        Args:
            message: 要广播的消息
            metadata: 消息元数据（可选）
            
        Returns:
            成功发送的订阅者数量
        """
        if not self._subscribers:
            logger.debug("[MessageDispatcher] 没有订阅者，跳过广播")
            return 0
        
        success_count = 0
        metadata = metadata or {}
        
        logger.info(
            f"[MessageDispatcher] 开始广播消息，消息长度: {len(message)}，"
            f"订阅者数量: {len(self._subscribers)}"
        )
        
        # 并发发送到所有订阅者
        tasks = []
        for subscriber_id, callback in self._subscribers.items():
            tasks.append(self._send_to_subscriber(subscriber_id, callback, message, metadata))
        
        # 等待所有发送完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计成功数量
        for i, result in enumerate(results):
            subscriber_id = list(self._subscribers.keys())[i]
            if isinstance(result, Exception):
                logger.error(
                    f"[MessageDispatcher] 发送消息到订阅者 {subscriber_id} 失败: {result}"
                )
            else:
                success_count += 1
        
        logger.info(
            f"[MessageDispatcher] 广播完成，成功: {success_count}/{len(self._subscribers)}"
        )
        
        return success_count
    
    async def _send_to_subscriber(
        self,
        subscriber_id: str,
        callback: Callable,
        message: str,
        metadata: Dict[str, Any]
    ):
        """发送消息到单个订阅者。
        
        Args:
            subscriber_id: 订阅者 ID
            callback: 回调函数
            message: 消息内容
            metadata: 元数据
            
        Raises:
            Exception: 发送失败时抛出异常
        """
        try:
            logger.debug(f"[MessageDispatcher] 发送消息到订阅者 {subscriber_id}")
            
            # 调用订阅者回调
            result = callback(message, metadata)
            
            # 如果返回的是协程对象，需要 await
            if asyncio.iscoroutine(result):
                await result
            
            logger.debug(f"[MessageDispatcher] 订阅者 {subscriber_id} 处理成功")
            
        except Exception as e:
            logger.error(f"[MessageDispatcher] 订阅者 {subscriber_id} 处理失败: {e}")
            raise
    
    def clear_all(self) -> int:
        """清除所有订阅者。
        
        Returns:
            清除的订阅者数量
        """
        count = len(self._subscribers)
        self._subscribers.clear()
        self._metadata.clear()
        logger.info(f"[MessageDispatcher] 已清除所有订阅者，数量: {count}")
        return count
    
    def __repr__(self) -> str:
        return f"MessageDispatcher(subscribers={len(self._subscribers)})"