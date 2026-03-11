"""
Ling-iflow v2 - Refactored Architecture

New architecture based on message bus pattern.
"""

from src_v2.core import MessageBus, Message, MessageType, BaseModule
from src_v2.modules import IFlowModule, WeChatModule

__all__ = [
    "MessageBus",
    "Message",
    "MessageType",
    "BaseModule",
    "IFlowModule",
    "WeChatModule",
]
