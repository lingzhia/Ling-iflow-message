"""
核心基础类

包含消息格式、模块基类、消息总线和模块管理器等核心组件。
"""

from .message import Message, MessageType, MessageContent
from .base import BaseModule
from .bus import MessageBus
from .manager import ModuleManager, ModuleStatus, IFlowStatus

__all__ = ["Message", "MessageType", "MessageContent", "BaseModule", "MessageBus", "ModuleManager", "ModuleStatus", "IFlowStatus"]