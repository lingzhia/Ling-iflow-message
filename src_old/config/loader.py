"""配置加载器。"""

import json
from pathlib import Path
from typing import Optional

from pydantic import ValidationError
from loguru import logger

from .schema import InteractiveConfig

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def get_config_dir() -> Path:
    """获取配置目录。"""
    return Path.home() / ".ling-iflow"


def get_config_path() -> Path:
    """获取配置文件路径。"""
    return get_config_dir() / "config.json"


def load_config(config_path: Optional[Path] = None, auto_create: bool = True) -> InteractiveConfig:
    """
    加载配置文件。
    
    Args:
        config_path: 可选的配置文件路径，如果不提供则使用默认路径。
        auto_create: 如果为 True，当配置文件不存在时创建默认配置。
    
    Returns:
        配置对象。
    """
    if config_path is None:
        config_path = get_config_path()
    
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = InteractiveConfig(**data)
            logger.info(f"从 {config_path} 加载配置")
            return config
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"配置文件无效: {e}。使用默认配置。")
    else:
        logger.info("未找到配置文件。创建默认配置。")
        config = InteractiveConfig()
        if auto_create:
            _create_default_config(config_path)
        return config
    
    return InteractiveConfig()


def _create_default_config(config_path: Path) -> None:
    """创建默认配置文件（使用原子写入）。"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    default_config = {
        "workspace": "~/.iflow",
        "model": "kimi-k2.5",
        "tmux_session": "iflow",
        "wechat_work": {
            "enabled": False,
            "corp_id": "",
            "agent_id": "",
            "secret": "",
            "token": "",
            "encoding_aes_key": "",
            "callback_port": 8788,
            "callback_host": "0.0.0.0",
            "stream_mode": False,
            "poll_interval": 5,
            "allow_from": [],
            "group_policy": "mention",
            "group_allow_from": []
        },
        "log_level": "INFO",
        "log_file": ""
    }
    
    # 使用临时文件进行原子写入
    temp_path = config_path.with_suffix('.tmp')
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        # 原子性重命名
        temp_path.replace(config_path)
        logger.info(f"在 {config_path} 创建默认配置")
    except Exception as e:
        # 如果写入失败，清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        raise e


def save_config(config: InteractiveConfig, config_path: Optional[Path] = None) -> None:
    """
    保存配置到文件（使用原子写入）。
    
    Args:
        config: 要保存的配置对象。
        config_path: 可选的配置文件路径，如果不提供则使用默认路径。
    """
    if config_path is None:
        config_path = get_config_path()
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 使用临时文件进行原子写入
    temp_path = config_path.with_suffix('.tmp')
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
        # 原子性重命名
        temp_path.replace(config_path)
        logger.info(f"配置已保存到 {config_path}")
    except Exception as e:
        # 如果写入失败，清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        logger.error(f"保存配置失败: {e}")
        raise