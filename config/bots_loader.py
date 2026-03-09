"""机器人配置加载器。"""

import json
from pathlib import Path
from typing import Optional

from loguru import logger

from .bots_schema import BotsConfig


def load_bots_config(config_path: Optional[Path] = None) -> BotsConfig:
    """加载机器人配置。
    
    Args:
        config_path: 配置文件路径，默认为 bots.json
        
    Returns:
        机器人配置对象
        
    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置文件格式错误
    """
    if config_path is None:
        # 使用项目根目录下的 bots.json
        from config.loader import PROJECT_ROOT
        config_path = PROJECT_ROOT / "bots.json"
    
    if not config_path.exists():
        logger.error(f"机器人配置文件不存在: {config_path}")
        raise FileNotFoundError(f"机器人配置文件不存在: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        config = BotsConfig(**config_data)
        logger.info(f"已加载机器人配置: {len(config.bots)} 个机器人")
        
        # 记录启用的机器人
        enabled_bots = config.get_enabled_bots()
        if enabled_bots:
            logger.info(f"启用的机器人: {', '.join([bot.name for bot in enabled_bots])}")
        
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"机器人配置文件格式错误: {e}")
        raise ValueError(f"机器人配置文件格式错误: {e}")
    except Exception as e:
        logger.error(f"加载机器人配置失败: {e}")
        raise


def save_bots_config(config: BotsConfig, config_path: Optional[Path] = None) -> None:
    """保存机器人配置。
    
    Args:
        config: 机器人配置对象
        config_path: 配置文件路径，默认为 bots.json
        
    Raises:
        IOError: 保存失败
    """
    if config_path is None:
        # 使用项目根目录下的 bots.json
        from config.loader import PROJECT_ROOT
        config_path = PROJECT_ROOT / "bots.json"
    
    try:
        # 原子写入：先写入临时文件，再重命名
        temp_path = config_path.with_suffix('.tmp')
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config.model_dump(mode='json'), f, indent=2, ensure_ascii=False)
        
        # 重命名临时文件
        temp_path.replace(config_path)
        
        logger.info(f"已保存机器人配置: {config_path}")
        
    except Exception as e:
        logger.error(f"保存机器人配置失败: {e}")
        raise IOError(f"保存机器人配置失败: {e}")