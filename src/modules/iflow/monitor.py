"""
IFlow Monitor

持续监听 iflow 的 tmux 输出，提取新消息。
"""

import asyncio
import hashlib
import logging
from typing import List, Dict, Optional, Callable
from datetime import datetime

from ...core.message import Message, MessageType


logger = logging.getLogger(__name__)


class IFlowMonitor:
    """iflow 监控器
    
    持续监听 iflow 的 tmux 输出，提取新消息。
    """
    
    def __init__(self, controller, check_interval: float = 0.5):
        """初始化监控器
        
        Args:
            controller: IFlowController 实例
            check_interval: 检查间隔（秒）
        """
        self.controller = controller
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # 消息缓存（用于去重）
        self._processed_hashes: set = set()
        self._last_hashes: set = set()
        
        # 监听器列表
        self._listeners: List[Callable] = []
        
        # 统计信息
        self.stats = {
            "messages_extracted": 0,
            "messages_filtered": 0,
            "check_count": 0
        }
    
    async def start(self) -> None:
        """启动监控器"""
        if self._running:
            logger.warning("[IFlowMonitor] Monitor already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("[IFlowMonitor] Monitor started")
    
    async def stop(self) -> None:
        """停止监控器"""
        if not self._running:
            return
        
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("[IFlowMonitor] Monitor stopped")
    
    def add_listener(self, listener: Callable) -> None:
        """添加消息监听器
        
        Args:
            listener: 监听器函数，接收 Message 对象
        """
        self._listeners.append(listener)
        logger.debug(f"[IFlowMonitor] Added listener, total: {len(self._listeners)}")
    
    def remove_listener(self, listener: Callable) -> None:
        """移除消息监听器
        
        Args:
            listener: 监听器函数
        """
        if listener in self._listeners:
            self._listeners.remove(listener)
            logger.debug(f"[IFlowMonitor] Removed listener, total: {len(self._listeners)}")
    
    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._check()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[IFlowMonitor] Monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _check(self) -> None:
        """检查新消息"""
        self.stats["check_count"] += 1
        
        try:
            # 捕获 tmux 输出
            output = await self.controller.capture_output(lines=1000)
            
            if not output:
                return
            
            # 提取消息
            messages = self._extract_messages(output)
            
            # 过滤新消息
            new_messages = self._filter_new_messages(messages)
            
            # 通知监听器
            for message in new_messages:
                await self._notify_listeners(message)
                self.stats["messages_extracted"] += 1
            
        except Exception as e:
            logger.error(f"[IFlowMonitor] Error checking messages: {e}", exc_info=True)
    
    def _extract_messages(self, output: str) -> List[Message]:
        """从 tmux 输出中提取消息
        
        Args:
            output: tmux 输出
            
        Returns:
            消息列表
        """
        messages = []
        lines = output.split('\n')
        
        current_message = []
        current_marker = None
        marker_type = None  # '✦' or '✻'
        
        for line in lines:
            # 检查标记行
            if '✦' in line or '✻' in line:
                # 保存上一条消息
                if current_marker and current_message:
                    content = '\n'.join(current_message).strip()
                    if content:
                        messages.append({
                            'marker_id': current_marker,
                            'content': content,
                            'marker_type': marker_type,
                            'full_marker': f'{marker_type} {current_marker}'
                        })
                
                # 开始新消息
                current_marker = line.replace('✦', '').replace('✻', '').strip()
                marker_type = '✦' if '✦' in line else '✻'
                current_message = []
            else:
                current_message.append(line)
        
        # 保存最后一条消息
        if current_marker and current_message:
            content = '\n'.join(current_message).strip()
            if content:
                messages.append({
                    'marker_id': current_marker,
                    'content': content,
                    'marker_type': marker_type,
                    'full_marker': f'{marker_type} {current_marker}'
                })
        
        return messages
    
    def _filter_new_messages(self, messages: List[dict]) -> List[Message]:
        """过滤新消息
        
        Args:
            messages: 消息列表
            
        Returns:
            新消息列表
        """
        new_messages = []
        
        for msg_data in messages:
            # 只处理 ✦ 标记的消息（实际回复）
            if msg_data['marker_type'] != '✦':
                continue
            
            # 清理消息内容
            content = self._clean_message_content(msg_data['content'])
            
            # 如果内容为空，使用 marker_id 作为内容（iflow 回复格式：✦ 内容）
            if not content:
                content = self._clean_message_content(msg_data['marker_id'])
            
            if not content:
                continue
            
            # 计算消息哈希
            msg_hash = hashlib.md5(content.encode()).hexdigest()
            
            # 检查是否已处理
            if msg_hash in self._processed_hashes:
                self.stats["messages_filtered"] += 1
                continue
            
            # 添加到已处理集合
            self._processed_hashes.add(msg_hash)
            
            # 限制缓存大小
            if len(self._processed_hashes) > 1000:
                self._processed_hashes = set(list(self._processed_hashes)[-500:])
            
            # 创建消息对象
            message = Message(
                id=Message.generate_id(),
                type=MessageType.TEXT,
                content=content,
                from_module=self.controller.tmux_session,
                metadata={
                    'marker_id': msg_data['marker_id'],
                    'marker_type': msg_data['marker_type']
                }
            )
            
            new_messages.append(message)
        
        return new_messages
    
    def _clean_message_content(self, content: str) -> str:
        """清理消息内容，移除 iflow UI 元素
        
        Args:
            content: 原始消息内容
            
        Returns:
            清理后的消息内容
        """
        if not content:
            return content
        
        # 分隔符列表（iflow UI 元素）
        separators = [
            '---',
            '══',
            '────────',
            '────────────────',
            '════════════════',
            '══════════════════════════',
            '══════════════════════════════════════',
            '══════════════════════════════════════════════════',
        ]
        
        # 找到第一个分隔符的位置
        first_separator_pos = -1
        for sep in separators:
            pos = content.find(sep)
            if pos != -1 and (first_separator_pos == -1 or pos < first_separator_pos):
                first_separator_pos = pos
        
        # 如果找到分隔符，只保留之前的内容
        if first_separator_pos != -1:
            cleaned_content = content[:first_separator_pos].strip()
            return cleaned_content
        
        return content.strip()
    
    async def _notify_listeners(self, message: Message) -> None:
        """通知所有监听器
        
        Args:
            message: 消息对象
        """
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(message)
                else:
                    listener(message)
            except Exception as e:
                logger.error(f"[IFlowMonitor] Listener error: {e}", exc_info=True)
    
    def get_stats(self) -> Dict:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            "messages_extracted": 0,
            "messages_filtered": 0,
            "check_count": 0
        }
        logger.info("[IFlowMonitor] Stats reset")
    
    @property
    def running(self) -> bool:
        """监控器是否运行中"""
        return self._running