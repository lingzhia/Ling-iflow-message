"""机器人配置加载器。

注意：已废弃，机器人配置现在直接在 config.json 中管理。
此模块保留用于向后兼容，内部已重定向到 config.json。
"""

import json
from pathlib import Path
from typing import Optional

from loguru import logger

from .schema import BotsConfig


def load_bots_config(config_path: Optional[Path] = None) -> BotsConfig:
    """加载机器人配置（从 config.json）。
    
    Args:
        config_path: 配置文件路径，默认为 config.json
        
    Returns:
        机器人配置对象
        
    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置文件格式错误
    """
    if config_path is None:
        # 使用项目根目录下的 config.json
        from config.loader import PROJECT_ROOT
        config_path = PROJECT_ROOT / "config.json"
    
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 从 config.json 中提取 bots 配置
        bots_data = config_data.get('bots', [])
        
        config = BotsConfig(bots=bots_data)
        logger.info(f"已加载机器人配置: {len(config.bots)} 个机器人")
        
        # 记录启用的机器人
        enabled_bots = config.get_enabled_bots()
        if enabled_bots:
            logger.info(f"启用的机器人: {', '.join([bot.name for bot in enabled_bots])}")
        
        return config
        
    except json.JSONDecodeError as e:
        logger.error(f"配置文件格式错误: {e}")
        raise ValueError(f"配置文件格式错误: {e}")
    except Exception as e:
        logger.error(f"加载机器人配置失败: {e}")
        raise


def save_bots_config(config: BotsConfig, config_path: Optional[Path] = None) -> None:
    """保存机器人配置（到 config.json）。
    
    Args:
        config: 机器人配置对象
        config_path: 配置文件路径，默认为 config.json
        
    Raises:
        IOError: 保存失败
    """
    if config_path is None:
        # 使用项目根目录下的 config.json
        from config.loader import PROJECT_ROOT
        config_path = PROJECT_ROOT / "config.json"
    
    try:
        # 读取现有配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 更新 bots 配置
        config_data['bots'] = config.model_dump(mode='json')['bots']
        
        # 原子写入：先写入临时文件，再重命名
        temp_path = config_path.with_suffix('.tmp')
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        
        # 重命名临时文件
        temp_path.replace(config_path)
        
        logger.info(f"已保存机器人配置: {config_path}")
        
    except Exception as e:
        logger.error(f"保存机器人配置失败: {e}")
        raise IOError(f"保存机器人配置失败: {e}")