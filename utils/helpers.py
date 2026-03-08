"""工具函数模块。"""

import time
from datetime import datetime


def format_timestamp(timestamp: float) -> str:
    """格式化时间戳。
    
    Args:
        timestamp: Unix 时间戳
        
    Returns:
        格式化的时间字符串
    """
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    return ""


def truncate_string(s: str, max_length: int = 100) -> str:
    """截断字符串。
    
    Args:
        s: 原始字符串
        max_length: 最大长度
        
    Returns:
        截断后的字符串
    """
    if len(s) <= max_length:
        return s
    return s[:max_length] + "..."