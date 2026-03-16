"""
模块管理器异常定义

定义统一的异常类，用于错误处理和返回。
"""

from typing import List, Optional, Dict, Any


class ModuleManagerError(Exception):
    """模块管理器基础异常"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            error_code: 错误代码
            details: 详细信息
        """
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class ModuleNotFoundError(ModuleManagerError):
    """模块不存在异常"""

    def __init__(self, module_id: str):
        """
        初始化异常

        Args:
            module_id: 模块 ID
        """
        super().__init__(
            message=f"模块不存在: {module_id}",
            error_code="MODULE_NOT_FOUND",
            details={"module_id": module_id}
        )
        self.module_id = module_id


class ModuleNotRunningError(ModuleManagerError):
    """模块未运行异常"""

    def __init__(self, module_id: str):
        """
        初始化异常

        Args:
            module_id: 模块 ID
        """
        super().__init__(
            message=f"模块未运行: {module_id}",
            error_code="MODULE_NOT_RUNNING",
            details={"module_id": module_id}
        )
        self.module_id = module_id


class ModuleUnhealthyError(ModuleManagerError):
    """模块状态异常"""

    def __init__(self, module_id: str, health_details: Optional[Dict[str, Any]] = None):
        """
        初始化异常

        Args:
            module_id: 模块 ID
            health_details: 健康检查详情
        """
        super().__init__(
            message=f"模块状态异常: {module_id}",
            error_code="MODULE_UNHEALTHY",
            details={"module_id": module_id, **(health_details or {})}
        )
        self.module_id = module_id


class DependencyNotSatisfiedError(ModuleManagerError):
    """依赖不满足异常"""

    def __init__(self, module_id: str, missing_deps: List[str]):
        """
        初始化异常

        Args:
            module_id: 模块 ID
            missing_deps: 缺失的依赖列表
        """
        super().__init__(
            message=f"依赖不满足: {module_id}, 缺少: {missing_deps}",
            error_code="DEPENDENCY_NOT_SATISFIED",
            details={"module_id": module_id, "missing_deps": missing_deps}
        )
        self.module_id = module_id
        self.missing_deps = missing_deps


class CircularDependencyError(ModuleManagerError):
    """循环依赖异常"""

    def __init__(self, cycle: List[str]):
        """
        初始化异常

        Args:
            cycle: 循环依赖的模块列表
        """
        cycle_str = " -> ".join(cycle)
        super().__init__(
            message=f"检测到循环依赖: {cycle_str}",
            error_code="CIRCULAR_DEPENDENCY",
            details={"cycle": cycle}
        )
        self.cycle = cycle


class IFlowNotAvailableError(ModuleManagerError):
    """IFlow 不可用异常"""

    def __init__(self, module_id: str, duration: int, state: str = "generating"):
        """
        初始化异常

        Args:
            module_id: 模块 ID
            duration: 生成持续时间（秒）
            state: 当前状态
        """
        super().__init__(
            message=f"IFlow 正在{state}中，已持续 {duration} 秒",
            error_code="IFLOW_NOT_AVAILABLE",
            details={"module_id": module_id, "duration": duration, "state": state}
        )
        self.module_id = module_id
        self.duration = duration
        self.state = state


class ModuleStartFailedError(ModuleManagerError):
    """模块启动失败异常"""

    def __init__(self, module_id: str, reason: str):
        """
        初始化异常

        Args:
            module_id: 模块 ID
            reason: 失败原因
        """
        super().__init__(
            message=f"模块启动失败: {module_id}, 原因: {reason}",
            error_code="MODULE_START_FAILED",
            details={"module_id": module_id, "reason": reason}
        )
        self.module_id = module_id
        self.reason = reason


class ModuleStopFailedError(ModuleManagerError):
    """模块停止失败异常"""

    def __init__(self, module_id: str, reason: str):
        """
        初始化异常

        Args:
            module_id: 模块 ID
            reason: 失败原因
        """
        super().__init__(
            message=f"模块停止失败: {module_id}, 原因: {reason}",
            error_code="MODULE_STOP_FAILED",
            details={"module_id": module_id, "reason": reason}
        )
        self.module_id = module_id
        self.reason = reason


class ReceiverNotAvailableError(ModuleManagerError):
    """接收方不可用异常"""

    def __init__(
        self,
        receiver_id: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            receiver_id: 接收方模块 ID
            reason: 不可用的原因
            details: 详细信息
        """
        super().__init__(
            message=f"接收方不可用: {receiver_id}, 原因: {reason}",
            error_code="RECEIVER_NOT_AVAILABLE",
            details={"receiver_id": receiver_id, "reason": reason, **(details or {})}
        )
        self.receiver_id = receiver_id
        self.reason = reason


class MessageBusNotSetError(ModuleManagerError):
    """消息总线未设置异常"""

    def __init__(self):
        """初始化异常"""
        super().__init__(
            message="消息总线未设置",
            error_code="MESSAGE_BUS_NOT_SET",
            details={}
        )


class HealthCheckTimeoutError(ModuleManagerError):
    """健康检查超时异常"""

    def __init__(self, module_id: str, timeout: int):
        """
        初始化异常

        Args:
            module_id: 模块 ID
            timeout: 超时时间（秒）
        """
        super().__init__(
            message=f"健康检查超时: {module_id}, 超时时间: {timeout} 秒",
            error_code="HEALTH_CHECK_TIMEOUT",
            details={"module_id": module_id, "timeout": timeout}
        )
        self.module_id = module_id
        self.timeout = timeout


class AutoRecoveryFailedError(ModuleManagerError):
    """自动恢复失败异常"""

    def __init__(self, module_id: str, reason: str):
        """
        初始化异常

        Args:
            module_id: 模块 ID
            reason: 失败原因
        """
        super().__init__(
            message=f"自动恢复失败: {module_id}, 原因: {reason}",
            error_code="AUTO_RECOVERY_FAILED",
            details={"module_id": module_id, "reason": reason}
        )
        self.module_id = module_id
        self.reason = reason