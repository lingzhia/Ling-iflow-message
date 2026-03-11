"""配置管理模块。"""

from .schema import InteractiveConfig, WechatWorkConfig
from .loader import load_config, save_config

__all__ = ["InteractiveConfig", "WechatWorkConfig", "load_config", "save_config"]