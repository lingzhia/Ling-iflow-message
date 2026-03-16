"""
统一返回类型定义

定义统一的返回类型，用于方法返回值的规范化。
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from .exceptions import ModuleManagerError


@dataclass
class Result:
    """统一返回类型

    所有 ModuleManager 的方法都应该返回此类型。
    """
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None) -> 'Result':
        """创建成功结果

        Args:
            data: 返回的数据

        Returns:
            Result 对象
        """
        return cls(success=True, data=data)

    @classmethod
    def fail(
        cls,
        error: str,
        error_code: str = None,
        details: Dict = None
    ) -> 'Result':
        """创建失败结果

        Args:
            error: 错误信息
            error_code: 错误代码
            details: 详细信息

        Returns:
            Result 对象
        """
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            details=details or {}
        )

    @classmethod
    def from_exception(cls, exception: ModuleManagerError) -> 'Result':
        """从异常创建结果

        Args:
            exception: 模块管理器异常

        Returns:
            Result 对象
        """
        return cls(
            success=False,
            error=str(exception),
            error_code=exception.error_code,
            details=exception.details
        )

    def __bool__(self) -> bool:
        """布尔值判断"""
        return self.success

    def __repr__(self) -> str:
        if self.success:
            return f"Result(ok, data={self.data})"
        else:
            return f"Result(fail, error={self.error}, code={self.error_code})"


# 常用错误码
class ErrorCode:
    """错误码常量"""

    # 模块相关
    MODULE_NOT_FOUND = "MODULE_NOT_FOUND"
    MODULE_NOT_RUNNING = "MODULE_NOT_RUNNING"
    MODULE_UNHEALTHY = "MODULE_UNHEALTHY"
    MODULE_START_FAILED = "MODULE_START_FAILED"
    MODULE_STOP_FAILED = "MODULE_STOP_FAILED"

    # 依赖相关
    DEPENDENCY_NOT_SATISFIED = "DEPENDENCY_NOT_SATISFIED"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"

    # 消息相关
    RECEIVER_NOT_AVAILABLE = "RECEIVER_NOT_AVAILABLE"
    SENDER_NOT_FOUND = "SENDER_NOT_FOUND"
    MESSAGE_BUS_NOT_SET = "MESSAGE_BUS_NOT_SET"

    # IFlow 相关
    IFLOW_NOT_AVAILABLE = "IFLOW_NOT_AVAILABLE"

    # 健康检查相关
    HEALTH_CHECK_TIMEOUT = "HEALTH_CHECK_TIMEOUT"
    AUTO_RECOVERY_FAILED = "AUTO_RECOVERY_FAILED"

    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"