"""
模块基类

定义所有模块的标准接口。
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable
import asyncio
import logging

from .message import Message


logger = logging.getLogger(__name__)


class BaseModule(ABC):
    """模块基类
    
    所有模块必须继承此类并实现标准接口。
    """
    
    def __init__(self, module_id: str):
        """初始化模块
        
        Args:
            module_id: 模块唯一标识符
        """
        self.module_id = module_id
        self.message_bus: Optional['MessageBus'] = None
        self._running = False
        self._tasks: list = []
    
    @property
    def running(self) -> bool:
        """模块是否运行中"""
        return self._running
    
    def set_message_bus(self, bus: 'MessageBus') -> None:
        """设置消息总线
        
        Args:
            bus: 消息总线实例
        """
        self.message_bus = bus
        logger.info(f"[{self.module_id}] 消息总线已设置")
    
    async def start(self) -> bool:
        """启动模块
        
        Returns:
            是否启动成功
        """
        if self._running:
            logger.warning(f"[{self.module_id}] 模块已在运行中")
            return True
        
        try:
            await self._on_start()
            self._running = True
            logger.info(f"[{self.module_id}] 模块启动成功")
            return True
        except Exception as e:
            logger.error(f"[{self.module_id}] 模块启动失败: {e}", exc_info=True)
            return False
    
    async def stop(self) -> None:
        """停止模块"""
        if not self._running:
            logger.warning(f"[{self.module_id}] 模块未运行")
            return
        
        try:
            # 取消所有后台任务
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            
            # 等待任务完成
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            
            await self._on_stop()
            self._running = False
            self._tasks.clear()
            logger.info(f"[{self.module_id}] 模块已停止")
        except Exception as e:
            logger.error(f"[{self.module_id}] 模块停止失败: {e}", exc_info=True)
    
    async def receive(self, message: Message) -> None:
        """接收消息（由消息总线调用）
        
        Args:
            message: 接收到的消息
        """
        try:
            await self._on_receive(message)
            logger.debug(f"[{self.module_id}] 收到消息: {message.id[:8]}...")
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理消息失败: {e}", exc_info=True)
    
    async def send_to_bus(self, message: Message) -> bool:
        """发送消息到消息总线
        
        Args:
            message: 要发送的消息
            
        Returns:
            是否发送成功
        """
        if not self.message_bus:
            logger.error(f"[{self.module_id}] 消息总线未设置")
            return False
        
        try:
            # 设置发送者
            message.from_module = self.module_id
            await self.message_bus.send_to_module(message)
            return True
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送消息失败: {e}", exc_info=True)
            return False
    
    async def publish_to_bus(self, topic: str, message: Message) -> bool:
        """发布消息到消息总线（广播）
        
        Args:
            topic: 主题名称
            message: 要发布的消息
            
        Returns:
            是否发布成功
        """
        if not self.message_bus:
            logger.error(f"[{self.module_id}] 消息总线未设置")
            return False
        
        try:
            # 设置发送者
            message.from_module = self.module_id
            await self.message_bus.publish(topic, message)
            return True
        except Exception as e:
            logger.error(f"[{self.module_id}] 发布消息失败: {e}", exc_info=True)
            return False
    
    def create_background_task(self, coro: Awaitable) -> None:
        """创建后台任务
        
        Args:
            coro: 协程对象
        """
        task = asyncio.create_task(coro)
        self._tasks.append(task)
        logger.debug(f"[{self.module_id}] 创建后台任务: {task.get_name()}")
    
    # 子类需要实现的抽象方法
    
    @abstractmethod
    async def _on_start(self) -> None:
        """启动时的钩子方法（子类实现）"""
        pass
    
    @abstractmethod
    async def _on_stop(self) -> None:
        """停止时的钩子方法（子类实现）"""
        pass
    
    @abstractmethod
    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法（子类实现）
        
        Args:
            message: 接收到的消息
        """
        pass
    
    def __repr__(self) -> str:
        return f"BaseModule(id={self.module_id}, running={self._running})"