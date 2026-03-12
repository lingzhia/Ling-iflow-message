"""
Message Store

消息库，记录消息来源、状态等信息。
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


logger = logging.getLogger(__name__)


class MessageStatus(Enum):
    """消息状态"""
    PENDING = "pending"      # 等待处理
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 已完成


@dataclass
class MessageRecord:
    """消息记录"""
    message_id: str                    # 消息唯一标识
    source: str                        # 来源模块 ID（空表示无来源）
    content: str                       # 消息内容
    scope: str                         # 返回范围（reply_only / all）
    status: MessageStatus              # 消息状态
    created_at: datetime               # 创建时间
    processing_at: Optional[datetime] = None   # 开始处理时间
    completed_at: Optional[datetime] = None    # 完成时间
    reply_count: int = 0               # 回复数量
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他元数据


class MessageStore:
    """消息库
    
    记录消息来源、状态等信息，支持来源查询。
    """
    
    def __init__(self, max_records: int = 100):
        """初始化消息库
        
        Args:
            max_records: 最大记录数
        """
        self._records: Dict[str, MessageRecord] = {}  # message_id -> record
        self._max_records = max_records
        self._current_message_id: Optional[str] = None  # 当前处理的消息 ID
    
    def add(self, message_id: str, source: str, content: str, 
            scope: str = "reply_only", metadata: Dict[str, Any] = None) -> MessageRecord:
        """添加消息记录
        
        Args:
            message_id: 消息唯一标识
            source: 来源模块 ID
            content: 消息内容
            scope: 返回范围
            metadata: 其他元数据
            
        Returns:
            消息记录
        """
        record = MessageRecord(
            message_id=message_id,
            source=source,
            content=content,
            scope=scope,
            status=MessageStatus.PENDING,
            created_at=datetime.now(),
            metadata=metadata or {}
        )
        
        self._records[message_id] = record
        
        # 清理过期记录
        self._cleanup()
        
        logger.debug(f"[MessageStore] 添加消息记录: {message_id}, source={source}")
        return record
    
    def get(self, message_id: str) -> Optional[MessageRecord]:
        """获取消息记录
        
        Args:
            message_id: 消息唯一标识
            
        Returns:
            消息记录，不存在则返回 None
        """
        return self._records.get(message_id)
    
    def update_status(self, message_id: str, status: MessageStatus) -> bool:
        """更新消息状态
        
        Args:
            message_id: 消息唯一标识
            status: 新状态
            
        Returns:
            是否更新成功
        """
        record = self._records.get(message_id)
        if not record:
            return False
        
        record.status = status
        
        if status == MessageStatus.PROCESSING:
            record.processing_at = datetime.now()
            self._current_message_id = message_id
        elif status == MessageStatus.COMPLETED:
            record.completed_at = datetime.now()
            if self._current_message_id == message_id:
                self._current_message_id = None
        
        logger.debug(f"[MessageStore] 更新消息状态: {message_id} -> {status.value}")
        return True
    
    def get_current_message(self) -> Optional[MessageRecord]:
        """获取当前正在处理的消息
        
        Returns:
            当前处理的消息记录，无则返回 None
        """
        if not self._current_message_id:
            return None
        return self._records.get(self._current_message_id)
    
    def get_current_source(self) -> str:
        """获取当前处理消息的来源
        
        Returns:
            来源模块 ID，无则返回空字符串
        """
        current = self.get_current_message()
        return current.source if current else ""
    
    def get_current_scope(self) -> str:
        """获取当前处理消息的返回范围
        
        Returns:
            返回范围，无则返回默认值 reply_only
        """
        current = self.get_current_message()
        return current.scope if current else "reply_only"
    
    def increment_reply_count(self, message_id: str = None) -> None:
        """增加回复计数
        
        Args:
            message_id: 消息 ID，默认使用当前消息
        """
        if message_id is None:
            message_id = self._current_message_id
        
        if message_id:
            record = self._records.get(message_id)
            if record:
                record.reply_count += 1
    
    def complete_current(self) -> Optional[MessageRecord]:
        """完成当前处理的消息
        
        Returns:
            完成的消息记录
        """
        if not self._current_message_id:
            return None
        
        record = self._records.get(self._current_message_id)
        if record:
            record.status = MessageStatus.COMPLETED
            record.completed_at = datetime.now()
            logger.info(f"[MessageStore] 消息处理完成: {self._current_message_id}, "
                       f"replies={record.reply_count}")
        
        self._current_message_id = None
        return record
    
    def clear(self) -> None:
        """清空所有记录"""
        self._records.clear()
        self._current_message_id = None
        logger.debug("[MessageStore] 已清空所有记录")
    
    def _cleanup(self) -> None:
        """清理过期记录"""
        if len(self._records) <= self._max_records:
            return
        
        # 按创建时间排序，删除最旧的记录
        sorted_ids = sorted(
            self._records.keys(),
            key=lambda x: self._records[x].created_at
        )
        
        # 保留最新的记录
        to_remove = sorted_ids[:len(self._records) - self._max_records]
        for msg_id in to_remove:
            del self._records[msg_id]
        
        logger.debug(f"[MessageStore] 清理了 {len(to_remove)} 条过期记录")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        pending = sum(1 for r in self._records.values() if r.status == MessageStatus.PENDING)
        processing = sum(1 for r in self._records.values() if r.status == MessageStatus.PROCESSING)
        completed = sum(1 for r in self._records.values() if r.status == MessageStatus.COMPLETED)
        
        return {
            "total": len(self._records),
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "current_message_id": self._current_message_id
        }
