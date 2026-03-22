"""
消息总线

实现模块间消息路由和分发的核心组件。
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Set
from collections import defaultdict
from datetime import datetime

from .message import Message
from .base import BaseModule


logger = logging.getLogger(__name__)


def _format_content(content: str, max_len: int = 50) -> str:
    """格式化消息内容用于日志显示
    
    Args:
        content: 消息内容
        max_len: 最大显示长度
        
    Returns:
        格式化后的内容
    """
    if not content:
        return "(空)"
    if len(content) <= max_len:
        return content
    return content[:max_len] + "..."


class MessageBus:
    """消息总线
    
    负责模块注册、消息路由、绑定关系管理和发布-订阅机制。
    """
    
    def __init__(self, module_manager=None):
        """初始化消息总线
        
        Args:
            module_manager: 模块管理器实例（用于状态检查）
        """
        # 注册的模块
        self.modules: Dict[str, BaseModule] = {}
        
        # 绑定关系：发送模块 -> 接收模块
        self.bindings: Dict[str, str] = {}
        
        # 订阅者：主题 -> [回调函数]
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        
        # 模块管理器
        self.module_manager = module_manager
        
        # 消息统计
        self.stats = {
            "messages_sent": 0,
            "messages_routed": 0,
            "messages_published": 0,
            "errors": 0,
            "rejected": 0
        }
        
        logger.info("[MessageBus] 消息总线初始化完成")
    
    def register_module(self, module: BaseModule) -> bool:
        """注册模块
        
        Args:
            module: 模块实例
            
        Returns:
            是否注册成功
        """
        module_id = module.module_id
        
        if module_id in self.modules:
            logger.warning(f"[MessageBus] 模块 {module_id} 已存在，将被覆盖")
        
        try:
            self.modules[module_id] = module
            module.set_message_bus(self)
            logger.info(f"[MessageBus] ✅ 模块注册成功: {module_id} (总计: {len(self.modules)} 个)")
            return True
        except Exception as e:
            logger.error(f"[MessageBus] ❌ 模块注册失败: {module_id}, 错误: {e}", exc_info=True)
            return False
    
    def unregister_module(self, module_id: str) -> bool:
        """注销模块
        
        Args:
            module_id: 模块标识符
            
        Returns:
            是否注销成功
        """
        if module_id not in self.modules:
            logger.warning(f"[MessageBus] 模块 {module_id} 不存在，无法注销")
            return False
        
        try:
            # 移除模块
            del self.modules[module_id]
            
            # 移除相关绑定关系
            removed_bindings = []
            self.bindings = {
                k: v for k, v in self.bindings.items()
                if k != module_id and v != module_id
            }
            if removed_bindings:
                logger.debug(f"[MessageBus] 移除相关绑定: {removed_bindings}")
            
            logger.info(f"[MessageBus] ✅ 模块注销成功: {module_id} (剩余: {len(self.modules)} 个)")
            return True
        except Exception as e:
            logger.error(f"[MessageBus] ❌ 模块注销失败: {module_id}, 错误: {e}", exc_info=True)
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
            logger.error(f"[MessageBus] ❌ 绑定失败: 发送模块 {from_module} 不存在")
            return False
        
        if to_module not in self.modules:
            logger.error(f"[MessageBus] ❌ 绑定失败: 接收模块 {to_module} 不存在")
            return False
        
        # 检查是否已存在绑定
        old_binding = self.bindings.get(from_module)
        if old_binding:
            logger.debug(f"[MessageBus] 更新绑定: {from_module} -> {old_binding} 改为 -> {to_module}")
        
        self.bindings[from_module] = to_module
        logger.info(f"[MessageBus] ✅ 绑定成功: {from_module} -> {to_module} (总计: {len(self.bindings)} 个绑定)")
        return True
    
    def unbind(self, from_module: str) -> bool:
        """解绑模块
        
        Args:
            from_module: 发送模块
            
        Returns:
            是否解绑成功
        """
        if from_module not in self.bindings:
            logger.debug(f"[MessageBus] 模块 {from_module} 未绑定，无需解绑")
            return False
        
        to_module = self.bindings[from_module]
        del self.bindings[from_module]
        logger.info(f"[MessageBus] ✅ 解绑成功: {from_module} -> {to_module} (剩余: {len(self.bindings)} 个绑定)")
        return True
    
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
            logger.error(f"[MessageBus] ❌ 发送失败: 消息 {message.id} 未指定接收模块")
            self.stats["errors"] += 1
            return False
        
        if message.to_module not in self.modules:
            logger.error(f"[MessageBus] ❌ 发送失败: 接收模块 {message.to_module} 不存在 (消息: {message.id})")
            self.stats["errors"] += 1
            return False
        
        try:
            target_module = self.modules[message.to_module]
            content_preview = _format_content(message.content.text if message.content else "")
            
            logger.debug(f"[MessageBus] 📤 发送消息: {message.id}")
            logger.debug(f"   从: {message.from_module or '(未知)'}")
            logger.debug(f"   到: {message.to_module}")
            logger.debug(f"   内容: {content_preview}")
            
            await target_module.receive(message)
            self.stats["messages_sent"] += 1
            
            logger.info(f"[MessageBus] ✅ 消息发送成功: {message.id} -> {message.to_module}")
            return True
        except Exception as e:
            logger.error(f"[MessageBus] ❌ 消息发送异常: {message.id}, 错误: {e}", exc_info=True)
            self.stats["errors"] += 1
            return False
    
    async def broadcast_to_bindings(self, message: Message, sender_id: str) -> int:
        """广播消息给所有绑定了发送者的模块
        
        用于无来源消息的场景：当 receiver 为空时，向所有绑定了发送者的模块广播。
        
        Args:
            message: 消息对象
            sender_id: 发送模块 ID（通常是 iflow 模块）
            
        Returns:
            成功发送的模块数量
        """
        success_count = 0
        
        # 找出所有绑定了发送者的模块
        for from_module, to_module in self.bindings.items():
            if from_module == sender_id:
                # 发送者是绑定的发起方，跳过（避免循环）
                continue
            if to_module == sender_id:
                # 绑定的接收方是发送者，向发起方广播
                target_module_id = from_module
            else:
                continue
            
            # 发送到目标模块
            if target_module_id in self.modules:
                try:
                    target_message = Message(
                        id=Message.generate_id(),
                        type=message.type,
                        content=message.content,
                        from_module=sender_id,
                        to_module=target_module_id,
                        metadata=message.metadata
                    )
                    await self.modules[target_module_id].receive(target_message)
                    success_count += 1
                    logger.debug(f"[MessageBus] 广播消息到: {target_module_id}")
                except Exception as e:
                    logger.error(f"[MessageBus] 广播到 {target_module_id} 失败: {e}")
        
        logger.info(f"[MessageBus] 📢 广播消息: {message.id} 到 {success_count} 个模块")
        return success_count
    
    async def route(self, message: Message) -> bool:
        """路由消息（根据绑定关系）
        
        Args:
            message: 消息对象
            
        Returns:
            是否路由成功
        """
        from_module = message.from_module
        
        if from_module not in self.bindings:
            logger.warning(f"[MessageBus] ⚠️ 路由失败: 模块 {from_module} 未绑定 (消息: {message.id})")
            return False
        
        to_module = self.bindings[from_module]
        message.to_module = to_module
        
        # 检查接收方状态
        if self.module_manager:
            check_result = await self.module_manager.check_receiver_availability(to_module)
            
            if not check_result["available"]:
                # 接收方不可用，构造错误消息并返回给发送方
                logger.warning(
                    f"[MessageBus] ⚠️ 接收方不可用: {to_module}, "
                    f"错误: {check_result['error']}, "
                    f"消息: {check_result['error_message']}"
                )
                
                # 生成错误消息
                error_message = self.module_manager.generate_error_message(
                    check_result["error"],
                    check_result.get("details", {})
                )
                
                # 创建错误消息对象
                from .message import Message, MessageContent, MessageType
                
                error_msg = Message(
                    id=Message.generate_id(),
                    type=MessageType.TEXT,
                    content=MessageContent(type=MessageType.TEXT, text=error_message),
                    from_module="message_bus",
                    to_module=from_module,
                    metadata={
                        "msg_type": "error_response",
                        "error_type": check_result["error"],
                        "error_message": check_result["error_message"],
                        "original_message_id": message.id,
                        "failed_receiver": to_module,
                        "details": check_result.get("details", {})
                    }
                )
                
                # 路由错误消息回发送方
                await self.send_to_module(error_msg)
                
                # 更新统计
                self.stats["rejected"] += 1
                self.stats["errors"] += 1
                
                return False  # 路由失败（被拒绝）
        
        # 接收方可用，正常路由
        content_preview = _format_content(message.content.text if message.content else "")
        logger.info(f"[MessageBus] 🔀 路由消息: {message.id}")
        logger.debug(f"   {from_module} -> {to_module}")
        logger.debug(f"   内容: {content_preview}")
        
        result = await self.send_to_module(message)
        if result:
            self.stats["messages_routed"] += 1
        return result
    
    async def publish(self, topic: str, message: Message) -> bool:
        """发布消息到主题（广播）
        
        Args:
            topic: 主题名称
            message: 消息对象
            
        Returns:
            是否发布成功
        """
        if topic not in self.subscribers:
            logger.warning(f"[MessageBus] ⚠️ 发布失败: 主题 {topic} 没有订阅者 (消息: {message.id})")
            return False
        
        try:
            callbacks = self.subscribers[topic]
            subscriber_count = len(callbacks)
            
            content_preview = _format_content(message.content.text if message.content else "")
            logger.info(f"[MessageBus] 📢 发布消息: {message.id} 到主题 {topic}")
            logger.debug(f"   订阅者数量: {subscriber_count}")
            logger.debug(f"   内容: {content_preview}")
            
            # 并发调用所有订阅者
            tasks = [callback(message) for callback in callbacks]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 检查结果
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            
            if success_count < len(results):
                errors = [r for r in results if isinstance(r, Exception)]
                logger.error(f"[MessageBus] ❌ 发布部分失败: {len(errors)}/{subscriber_count} 个订阅者处理失败")
                for i, err in enumerate(errors):
                    logger.error(f"   错误 {i+1}: {err}")
                self.stats["errors"] += len(errors)
            
            self.stats["messages_published"] += 1
            logger.info(f"[MessageBus] ✅ 发布完成: {success_count}/{subscriber_count} 成功")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"[MessageBus] ❌ 发布异常: 主题 {topic}, 错误: {e}", exc_info=True)
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
            logger.error(f"[MessageBus] ❌ 订阅失败: 回调必须是协程函数 (主题: {topic})")
            return False
        
        self.subscribers[topic].append(callback)
        logger.info(f"[MessageBus] ✅ 订阅成功: 主题 {topic} (订阅者: {len(self.subscribers[topic])})")
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
            logger.debug(f"[MessageBus] 主题 {topic} 不存在，无法取消订阅")
            return False
        
        if callback in self.subscribers[topic]:
            self.subscribers[topic].remove(callback)
            logger.info(f"[MessageBus] ✅ 取消订阅: 主题 {topic} (剩余订阅者: {len(self.subscribers[topic])})")
            return True
        
        logger.debug(f"[MessageBus] 回调不在主题 {topic} 的订阅者列表中")
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
        stats = self.stats.copy()
        stats["modules_count"] = len(self.modules)
        stats["bindings_count"] = len(self.bindings)
        stats["topics_count"] = len(self.subscribers)
        return stats
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        old_stats = self.stats.copy()
        self.stats = {
            "messages_sent": 0,
            "messages_routed": 0,
            "messages_published": 0,
            "errors": 0
        }
        logger.info(f"[MessageBus] 📊 统计信息已重置 (之前: sent={old_stats['messages_sent']}, "
                   f"routed={old_stats['messages_routed']}, published={old_stats['messages_published']}, "
                   f"errors={old_stats['errors']})")
    

    
    def __repr__(self) -> str:
        return f"MessageBus(modules={len(self.modules)}, bindings={len(self.bindings)}, topics={len(self.subscribers)})"