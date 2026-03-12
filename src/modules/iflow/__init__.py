"""
IFlow Module

iflow CLI 管理模块。
"""

from .module import IFlowModule, Response
from .controller import IFlowController
from .monitor import IFlowMonitor, IFlowState, MessageType, OutboundMessage
from .session_manager import SessionManager
from .logger import InteractionLogger
from .message_store import MessageStore, MessageRecord, MessageStatus

__all__ = [
    # 主模块
    "IFlowModule",
    "Response",
    # 控制器
    "IFlowController",
    # 监控器
    "IFlowMonitor",
    "IFlowState",
    "MessageType",
    "OutboundMessage",
    # 会话管理
    "SessionManager",
    # 交互记录
    "InteractionLogger",
    # 消息库
    "MessageStore",
    "MessageRecord",
    "MessageStatus",
]
