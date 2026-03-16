"""
核心基础类

包含消息格式、模块基类、消息总线和模块管理器等核心组件。
"""

from .message import Message, MessageType, MessageContent
from .base import BaseModule
from .bus import MessageBus
from .manager import ModuleManager, ModuleStatus, IFlowStatus
from .exceptions import (
    ModuleManagerError,
    ModuleNotFoundError,
    ModuleNotRunningError,
    ModuleUnhealthyError,
    DependencyNotSatisfiedError,
    CircularDependencyError,
    IFlowNotAvailableError,
    ModuleStartFailedError,
    ModuleStopFailedError,
    ReceiverNotAvailableError,
    MessageBusNotSetError,
    HealthCheckTimeoutError,
    AutoRecoveryFailedError
)
from .result import Result, ErrorCode

__all__ = [
    "Message", "MessageType", "MessageContent",
    "BaseModule", "MessageBus", "ModuleManager", "ModuleStatus", "IFlowStatus",
    "ModuleManagerError",
    "ModuleNotFoundError",
    "ModuleNotRunningError",
    "ModuleUnhealthyError",
    "DependencyNotSatisfiedError",
    "CircularDependencyError",
    "IFlowNotAvailableError",
    "ModuleStartFailedError",
    "ModuleStopFailedError",
    "ReceiverNotAvailableError",
    "MessageBusNotSetError",
    "HealthCheckTimeoutError",
    "AutoRecoveryFailedError",
    "Result", "ErrorCode"
]