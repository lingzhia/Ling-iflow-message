"""
核心基础类

包含消息格式、模块基类和消息总线等核心组件。
"""

from .message import Message, MessageType, MessageContent
from .base import BaseModule
from .bus import MessageBus

__all__ = ["Message", "MessageType", "MessageContent", "BaseModule", "MessageBus"]