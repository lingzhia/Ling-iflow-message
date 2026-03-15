"""
Ling-iflow v2 - Refactored Architecture

New architecture based on message bus pattern.
"""

from src.core import MessageBus, Message, MessageType, BaseModule
from src.modules import IFlowModule, WeChatChannel

__all__ = [
    "MessageBus",
    "Message",
    "MessageType",
    "BaseModule",
    "IFlowModule",
    "WeChatChannel",
]
