"""
日志适配器

提供模块标识和消息类型标识的日志记录功能。
"""

import logging
from contextvars import ContextVar
from typing import Optional


# 上下文变量，用于存储当前模块ID和消息类型
current_module_id: ContextVar[Optional[str]] = ContextVar('current_module_id', default=None)
current_message_type: ContextVar[Optional[str]] = ContextVar('current_message_type', default=None)


class ModuleAwareFormatter(logging.Formatter):
    """带模块标识的日志格式化器"""
    
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
    
    def format(self, record):
        # 从上下文变量中获取模块ID和消息类型
        module_id = current_module_id.get()
        message_type = current_message_type.get()
        
        # 添加到record中
        record.module_id = module_id or record.name
        record.message_type = message_type or 'general'
        
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    """获取带模块标识的logger
    
    Args:
        name: logger名称
        
    Returns:
        logger实例
    """
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: int,
    msg: str,
    module_id: Optional[str] = None,
    message_type: Optional[str] = None,
    *args,
    **kwargs
):
    """带上下文信息的日志记录
    
    Args:
        logger: logger实例
        level: 日志级别
        msg: 日志消息
        module_id: 模块ID
        message_type: 消息类型（如：feishu_message, tmux_output, system_event）
        *args: 其他参数
        **kwargs: 其他关键字参数
    """
    # 设置上下文变量
    if module_id:
        token = current_module_id.set(module_id)
    else:
        token = None
    
    if message_type:
        token_type = current_message_type.set(message_type)
    else:
        token_type = None
    
    try:
        logger.log(level, msg, *args, **kwargs)
    finally:
        # 清理上下文变量
        if token:
            current_module_id.reset(token)
        if token_type:
            current_message_type.reset(token_type)


# 消息类型常量
class MessageType:
    """消息类型常量"""
    FEISHU_MESSAGE = "feishu_message"        # 飞书消息
    FEISHU_EVENT = "feishu_event"            # 飞书事件
    TMUX_OUTPUT = "tmux_output"              # tmux输出
    TMUX_INPUT = "tmux_input"                # tmux输入
    SYSTEM_EVENT = "system_event"            # 系统事件
    MESSAGE_BUS = "message_bus"              # 消息总线
    ERROR = "error"                          # 错误
    DEBUG = "debug"                          # 调试


def log_feishu_message(logger: logging.Logger, module_id: str, msg: str, level: int = logging.INFO):
    """记录飞书消息
    
    Args:
        logger: logger实例
        module_id: 模块ID
        msg: 消息内容
        level: 日志级别
    """
    log_with_context(logger, level, msg, module_id, MessageType.FEISHU_MESSAGE)


def log_tmux_output(logger: logging.Logger, module_id: str, msg: str, level: int = logging.INFO):
    """记录tmux输出
    
    Args:
        logger: logger实例
        module_id: 模块ID
        msg: 消息内容
        level: 日志级别
    """
    log_with_context(logger, level, msg, module_id, MessageType.TMUX_OUTPUT)


def log_system_event(logger: logging.Logger, module_id: str, msg: str, level: int = logging.INFO):
    """记录系统事件
    
    Args:
        logger: logger实例
        module_id: 模块ID
        msg: 消息内容
        level: 日志级别
    """
    log_with_context(logger, level, msg, module_id, MessageType.SYSTEM_EVENT)