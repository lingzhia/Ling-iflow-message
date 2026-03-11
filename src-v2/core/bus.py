"""
消息总线

实现模块间消息路由和分发的核心组件。
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Set
from collections import defaultdict

from .message import Message
from .base import BaseModule


logger = logging.getLogger(__name__)


class MessageBus:
    """消息总线
    
    负责模块注册、消息路由、绑定关系管理和发布-订阅机制。
    """
    
    def __init__(self):
        """初始化消息总线"""
        # 注册的模块
        self.modules: Dict[str, BaseModule] = {}
        
        # 绑定关系：发送模块 -> 接收模块
        self.bindings: Dict[str, str] = {}
        
        # 订阅者：主题 -> [回调函数]
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        
        # 消息统计
        self.stats = {
            "messages_sent": 0,
            "messages_routed": 0,
            "messages_published": 0,
            "errors": 0
        }
        
        self._running = False
    
    def register_module(self, module: BaseModule) -> bool:
        """注册模块
        
        Args:
            module: 模块实例
            
        Returns:
            是否注册成功
        """
        module_id = module.module_id
        
        if module_id in self.modules:
            logger.warning(f"模块 {module_id} 已存在，将被覆盖")
        
        try:
            self.modules[module_id] = module
            module.set_message_bus(self)
            logger.info(f"[MessageBus] 模块 {module_id} 注册成功")
            return True
        except Exception as e:
            logger.error(f"[MessageBus] 注册模块 {module_id} 失败: {e}", exc_info=True)
            return False
    
    def unregister_module(self, module_id: str) -> bool:
        """注销模块
        
        Args:
            module_id: 模块标识符
            
        Returns:
            是否注销成功
        """
        if module_id not in self.modules:
            logger.warning(f"模块 {module_id} 不存在")
            return False
        
        try:
            # 移除模块
            del self.modules[module_id]
            
            # 移除绑定关系
            self.bindings = {
                k: v for k, v in self.bindings.items()
                if k != module_id and v != module_id
            }
            
            logger.info(f"[MessageBus] 模块 {module_id} 注销成功")
            return True
        except Exception as e:
            logger.error(f"[MessageBus] 注销模块 {module_id} 失败: {e}", exc_info=True)
            return False
    
    def bind(self, from_module: str, to_module: str) -> bool:
        """绑定两个模块
        
        Args:
            from_module: 发送模块
            to_module: 接收模块
            
        Returns:
            是否绑定成功
        """
        if from_module not in self.modules:
            logger.error(f"发送模块 {from_module} 不存在")
            return False
        
        if to_module not in self.modules:
            logger.error(f"接收模块 {to_module} 不存在")
            return False
        
        self.bindings[from_module] = to_module
        logger.info(f"[MessageBus] 绑定 {from_module} -> {to_module}")
        return True
    
    def unbind(self, from_module: str) -> bool:
        """解绑模块
        
        Args:
            from_module: 发送模块
            
        Returns:
            是否解绑成功
        """
        if from_module in self.bindings:
            del self.bindings[from_module]
            logger.info(f"[MessageBus] 解绑 {from_module}")
            return True
        return False
    
    def get_binding(self, from_module: str) -> Optional[str]:
        """获取绑定关系
        
        Args:
            from_module: 发送模块
            
        Returns:
            接收模块，如果不存在则返回 None
        """
        return self.bindings.get(from_module)
    
    async def send_to_module(self, message: Message) -> bool:
        """发送消息到指定模块
        
        Args:
            message: 消息对象
            
        Returns:
            是否发送成功
        """
        if not message.to_module:
            logger.error("[MessageBus] 消息未指定接收模块")
            self.stats["errors"] += 1
            return False
        
        if message.to_module not in self.modules:
            logger.error(f"[MessageBus] 接收模块 {message.to_module} 不存在")
            self.stats["errors"] += 1
            return False
        
        try:
            target_module = self.modules[message.to_module]
            await target_module.receive(message)
            self.stats["messages_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"[MessageBus] 发送消息失败: {e}", exc_info=True)
            self.stats["errors"] += 1
            return False
    
    async def route(self, message: Message) -> bool:
        """路由消息（根据绑定关系）
        
        Args:
            message: 消息对象
            
        Returns:
            是否路由成功
        """
        from_module = message.from_module
        
        if from_module not in self.bindings:
            logger.warning(f"[MessageBus] 模块 {from_module} 未绑定")
            return False
        
        to_module = self.bindings[from_module]
        message.to_module = to_module
        
        return await self.send_to_module(message)
    
    async def publish(self, topic: str, message: Message) -> bool:
        """发布消息到主题（广播）
        
        Args:
            topic: 主题名称
            message: 消息对象
            
        Returns:
            是否发布成功
        """
        if topic not in self.subscribers:
            logger.warning(f"[MessageBus] 主题 {topic} 没有订阅者")
            return False
        
        try:
            callbacks = self.subscribers[topic]
            
            # 并发调用所有订阅者
            tasks = [callback(message) for callback in callbacks]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 检查结果
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            
            if success_count < len(results):
                errors = [r for r in results if isinstance(r, Exception)]
                logger.error(f"[MessageBus] {len(errors)} 个订阅者处理失败: {errors}")
                self.stats["errors"] += len(errors)
            
            self.stats["messages_published"] += 1
            logger.debug(f"[MessageBus] 发布消息到主题 {topic}，{success_count}/{len(results)} 成功")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"[MessageBus] 发布消息失败: {e}", exc_info=True)
            self.stats["errors"] += 1
            return False
    
    def subscribe(self, topic: str, callback: Callable) -> bool:
        """订阅主题
        
        Args:
            topic: 主题名称
            callback: 回调函数
            
        Returns:
            是否订阅成功
        """
        if not asyncio.iscoroutinefunction(callback):
            logger.error("[MessageBus] 订阅回调必须是协程函数")
            return False
        
        self.subscribers[topic].append(callback)
        logger.debug(f"[MessageBus] 订阅主题 {topic}，订阅者数量: {len(self.subscribers[topic])}")
        return True
    
    def unsubscribe(self, topic: str, callback: Callable) -> bool:
        """取消订阅主题
        
        Args:
            topic: 主题名称
            callback: 回调函数
            
        Returns:
            是否取消成功
        """
        if topic not in self.subscribers:
            return False
        
        if callback in self.subscribers[topic]:
            self.subscribers[topic].remove(callback)
            logger.debug(f"[MessageBus] 取消订阅主题 {topic}")
            return True
        
        return False
    
    def list_modules(self) -> List[str]:
        """列出所有注册的模块
        
        Returns:
            模块ID列表
        """
        return list(self.modules.keys())
    
    def list_bindings(self) -> Dict[str, str]:
        """列出所有绑定关系
        
        Returns:
            绑定关系字典
        """
        return self.bindings.copy()
    
    def list_topics(self) -> Set[str]:
        """列出所有主题
        
        Returns:
            主题集合
        """
        return set(self.subscribers.keys())
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            "messages_sent": 0,
            "messages_routed": 0,
            "messages_published": 0,
            "errors": 0
        }
        logger.info("[MessageBus] 统计信息已重置")
    
    async def start_all(self) -> bool:
        """启动所有模块
        
        Returns:
            是否全部启动成功
        """
        success_count = 0
        for module_id, module in self.modules.items():
            try:
                if await module.start():
                    success_count += 1
            except Exception as e:
                logger.error(f"[MessageBus] 启动模块 {module_id} 失败: {e}", exc_info=True)
        
        self._running = True
        logger.info(f"[MessageBus] 启动 {success_count}/{len(self.modules)} 个模块")
        return success_count == len(self.modules)
    
    async def stop_all(self) -> None:
        """停止所有模块"""
        if not self._running:
            return
        
        for module_id, module in self.modules.items():
            try:
                await module.stop()
            except Exception as e:
                logger.error(f"[MessageBus] 停止模块 {module_id} 失败: {e}", exc_info=True)
        
        self._running = False
        logger.info("[MessageBus] 所有模块已停止")
    
    def __repr__(self) -> str:
        return f"MessageBus(modules={len(self.modules)}, bindings={len(self.bindings)}, topics={len(self.subscribers)})"