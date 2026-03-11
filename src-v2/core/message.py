"""
统一消息格式

定义所有模块间通信的统一消息结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import hashlib
import json


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    SYSTEM = "system"
    ERROR = "error"


@dataclass
class MessageContent:
    """消息内容"""
    type: MessageType
    text: str = ""
    url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "text": self.text,
            "url": self.url,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageContent':
        """从字典创建"""
        return cls(
            type=MessageType(data.get("type", "text")),
            text=data.get("text", ""),
            url=data.get("url", ""),
            metadata=data.get("metadata", {})
        )


@dataclass
class Message:
    """统一消息格式
    
    用于所有模块间通信的标准消息结构。
    """
    
    # 消息标识
    id: str
    type: MessageType
    
    # 消息内容
    content: MessageContent
    
    # 来源信息
    from_module: str
    to_module: Optional[str] = None
    
    # 会话信息
    chat_id: str = ""
    user_id: str = ""
    is_group: bool = False
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 生成唯一ID
    @classmethod
    def generate_id(cls) -> str:
        """生成唯一消息ID"""
        return hashlib.md5(
            f"{datetime.now().isoformat()}_{id(obj):x}".encode()
        ).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于序列化）"""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content.to_dict(),
            "from_module": self.from_module,
            "to_module": self.to_module,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "is_group": self.is_group,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建（用于反序列化）"""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        return cls(
            id=data["id"],
            type=MessageType(data["type"]),
            content=MessageContent.from_dict(data["content"]),
            from_module=data["from_module"],
            to_module=data.get("to_module"),
            chat_id=data.get("chat_id", ""),
            user_id=data.get("user_id", ""),
            is_group=data.get("is_group", False),
            metadata=data.get("metadata", {}),
            timestamp=timestamp or datetime.now()
        )
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """从 JSON 字符串创建"""
        return cls.from_dict(json.loads(json_str))
    
    def copy(self) -> 'Message':
        """创建消息副本"""
        return Message(
            id=self.id,
            type=self.type,
            content=self.content,
            from_module=self.from_module,
            to_module=self.to_module,
            chat_id=self.chat_id,
            user_id=self.user_id,
            is_group=self.is_group,
            metadata=self.metadata.copy(),
            timestamp=self.timestamp
        )
    
    def __repr__(self) -> str:
        return f"Message(id={self.id[:8]}..., type={self.type.value}, from={self.from_module}, to={self.to_module})"