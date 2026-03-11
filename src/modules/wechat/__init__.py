"""
WeChat Module

企业微信消息模块，包含通道和主模块。
"""

from .channel import WeChatChannel
from .module import WeChatModule

__all__ = ["WeChatChannel", "WeChatModule"]