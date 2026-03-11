# 模块设计 - Config 层

## 概述

Config 层负责配置管理，定义配置的数据模型、验证规则和加载机制。支持多种配置方式，包括命令行参数、环境变量和配置文件。

## 目录结构

```
config/
├── __init__.py
├── schema.py          # 配置 Schema（主配置）
├── loader.py          # 配置加载器
├── bots_schema.py     # 机器人配置 Schema
└── bots_loader.py     # 机器人配置加载器
```

## Schema（配置模型）

### 职责
定义配置的数据模型和验证规则。

### 核心配置模型

#### 1. WechatWorkConfig（企业微信配置）

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class WechatWorkConfig(BaseModel):
    """企业微信配置。"""
    
    # 基础配置
    enabled: bool = Field(
        default=False,
        description="是否启用企业微信"
    )
    corp_id: str = Field(
        default="",
        description="企业 ID"
    )
    agent_id: int = Field(
        default=0,
        description="应用 AgentId"
    )
    secret: str = Field(
        default="",
        description="应用 Secret"
    )
    
    # 回调配置
    token: str = Field(
        default="",
        description="回调 Token"
    )
    encoding_aes_key: str = Field(
        default="",
        description="回调 EncodingAESKey"
    )
    callback_port: int = Field(
        default=8788,
        ge=1024,
        le=65535,
        description="回调服务端口"
    )
    callback_host: str = Field(
        default="0.0.0.0",
        description="回调服务监听地址"
    )
    
    # 轮询配置
    stream_mode: bool = Field(
        default=False,
        description="是否启用 Stream Mode（长轮询）"
    )
    poll_interval: int = Field(
        default=5,
        ge=1,
        le=60,
        description="轮询间隔（秒）"
    )
    
    # 权限配置
    allow_from: List[str] = Field(
        default_factory=list,
        description="用户 ID 白名单"
    )
    group_policy: str = Field(
        default="mention",
        description="群聊消息响应策略（mention/all/none）"
    )
    group_allow_from: List[str] = Field(
        default_factory=list,
        description="群聊白名单"
    )
    
    # 用户配置
    user_id: str = Field(
        default="",
        description="用于发送消息的用户 ID"
    )
```

#### 2. TmuxSessionConfig（tmux 会话配置）

```python
class TmuxSessionConfig(BaseModel):
    """tmux 会话配置。"""
    
    name: str = Field(
        default="iflow",
        description="tmux 会话名称"
    )
    workspace: str = Field(
        default="~/.iflow",
        description="iflow 工作目录"
    )
    model: str = Field(
        default="kimi-k2.5",
        description="iflow 模型名称"
    )
```

#### 3. InteractiveConfig（交互模式配置）

```python
class InteractiveConfig(BaseSettings):
    """交互模式配置。"""
    
    # 基础配置
    workspace: str = Field(
        default="~/.iflow",
        description="iflow 工作目录"
    )
    model: str = Field(
        default="kimi-k2.5",
        description="iflow 模型名称"
    )
    tmux_sessions: List[TmuxSessionConfig] = Field(
        default_factory=lambda: [TmuxSessionConfig()],
        description="tmux 会话配置列表"
    )
    
    # 企业微信配置
    wechat_work: WechatWorkConfig = Field(
        default_factory=WechatWorkConfig,
        description="企业微信配置"
    )
    
    # 日志配置
    log_level: str = Field(
        default="INFO",
        description="日志级别"
    )
    log_file: str = Field(
        default="",
        description="日志文件路径"
    )
    
    # 功能配置
    filter_thinking: bool = Field(
        default=True,
        description="是否过滤思考消息"
    )
    
    class Config:
        env_prefix = "LING_IFLOW__"
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### 配置验证

```python
from pydantic import validator

class WechatWorkConfig(BaseModel):
    # ... 其他字段 ...
    
    @validator('group_policy')
    def validate_group_policy(cls, v):
        """验证群聊策略。"""
        if v not in ['mention', 'all', 'none']:
            raise ValueError(f'group_policy must be one of mention, all, none, got {v}')
        return v
    
    @validator('callback_port')
    def validate_callback_port(cls, v):
        """验证回调端口。"""
        if v < 1024 or v > 65535:
            raise ValueError(f'callback_port must be between 1024 and 65535, got {v}')
        return v
```

## Loader（配置加载器）

### 职责
加载和管理配置文件。

### 核心方法

```python
from pathlib import Path
from typing import Optional
import json
import os

class ConfigLoader:
    """配置加载器。"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置加载器。
        
        Args:
            config_path: 配置文件路径（可选）
        """
        self.config_path = self._get_config_path(config_path)
    
    def get_config_path(self, config_path: Optional[str] = None) -> Path:
        """获取配置文件路径。
        
        优先级：
        1. 指定的 config_path
        2. 环境变量 LING_IFLOW_CONFIG
        3. ~/.ling-iflow/config.json
        
        Returns:
            配置文件路径
        """
        # 1. 指定的 config_path
        if config_path:
            return Path(config_path).expanduser()
        
        # 2. 环境变量
        env_config = os.getenv("LING_IFLOW_CONFIG")
        if env_config:
            return Path(env_config).expanduser()
        
        # 3. 默认路径
        return Path.home() / ".ling-iflow" / "config.json"
    
    def load_config(self) -> InteractiveConfig:
        """加载配置。
        
        Returns:
            配置对象
        """
        # 1. 如果配置文件不存在，创建默认配置
        if not self.config_path.exists():
            return self._create_default_config()
        
        # 2. 读取配置文件
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 3. 创建配置对象
            config = InteractiveConfig(**config_data)
            
            logger.info(f"[ConfigLoader] Loaded config from {self.config_path}")
            return config
            
        except Exception as e:
            logger.error(f"[ConfigLoader] Failed to load config: {e}", exc_info=True)
            return self._create_default_config()
    
    def _create_default_config(self) -> InteractiveConfig:
        """创建默认配置。
        
        Returns:
            默认配置对象
        """
        # 创建默认配置
        config = InteractiveConfig()
        
        # 保存到文件
        self._save_config(config)
        
        logger.info(f"[ConfigLoader] Created default config at {self.config_path}")
        return config
    
    def _save_config(self, config: InteractiveConfig) -> None:
        """保存配置到文件。"""
        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 转换为字典
        config_dict = config.dict()
        
        # 写入文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[ConfigLoader] Saved config to {self.config_path}")
    
    def update_config(self, updates: dict) -> InteractiveConfig:
        """更新配置。
        
        Args:
            updates: 更新的配置字典
            
        Returns:
            更新后的配置对象
        """
        # 加载当前配置
        config = self.load_config()
        
        # 更新配置
        config_dict = config.dict()
        config_dict.update(updates)
        
        # 创建新配置对象
        updated_config = InteractiveConfig(**config_dict)
        
        # 保存配置
        self._save_config(updated_config)
        
        return updated_config
```

## BotsSchema（机器人配置 Schema）

### 职责
定义多机器人配置的数据模型。

### 核心配置模型

```python
class BotConfig(BaseModel):
    """单个机器人配置。"""
    
    # 基础配置
    name: str = Field(
        ...,
        description="机器人名称（唯一标识）"
    )
    enabled: bool = Field(
        default=True,
        description="是否启用"
    )
    
    # 企业微信配置
    corp_id: str = Field(
        ...,
        description="企业 ID"
    )
    agent_id: int = Field(
        ...,
        description="应用 AgentId"
    )
    secret: str = Field(
        ...,
        description="应用 Secret"
    )
    
    # 用户配置
    user_id: str = Field(
        ...,
        description="用于发送消息的用户 ID"
    )
    
    # 回调配置
    token: str = Field(
        ...,
        description="回调 Token"
    )
    encoding_aes_key: str = Field(
        ...,
        description="回调 EncodingAESKey"
    )
    callback_port: int = Field(
        ...,
        description="回调服务端口"
    )
    
    # tmux 配置
    tmux_session: str = Field(
        ...,
        description="关联的 tmux 会话名称"
    )

class BotsConfig(BaseModel):
    """多机器人配置。"""
    
    bots: List[BotConfig] = Field(
        default_factory=list,
        description="机器人配置列表"
    )
    
    @validator('bots')
    def validate_bots(cls, v):
        """验证机器人配置。"""
        # 检查名称唯一性
        names = [bot.name for bot in v]
        if len(names) != len(set(names)):
            raise ValueError("Bot names must be unique")
        
        # 检查端口唯一性
        ports = [bot.callback_port for bot in v]
        if len(ports) != len(set(ports)):
            raise ValueError("Callback ports must be unique")
        
        return v
```

## BotsLoader（机器人配置加载器）

### 职责
加载和管理机器人配置文件。

### 核心方法

```python
class BotsLoader:
    """机器人配置加载器。"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化机器人配置加载器。
        
        Args:
            config_path: 配置文件路径（可选）
        """
        self.config_path = self._get_config_path(config_path)
    
    def _get_config_path(self, config_path: Optional[str] = None) -> Path:
        """获取配置文件路径。"""
        if config_path:
            return Path(config_path).expanduser()
        
        # 默认路径：项目根目录 / bots.json
        project_root = Path(__file__).parent.parent
        return project_root / "bots.json"
    
    def load_config(self) -> BotsConfig:
        """加载机器人配置。
        
        Returns:
            机器人配置对象
        """
        # 如果配置文件不存在，创建默认配置
        if not self.config_path.exists():
            return self._create_default_config()
        
        # 读取配置文件
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 创建配置对象
            config = BotsConfig(**config_data)
            
            logger.info(f"[BotsLoader] Loaded config from {self.config_path}")
            return config
            
        except Exception as e:
            logger.error(f"[BotsLoader] Failed to load config: {e}", exc_info=True)
            return self._create_default_config()
    
    def _create_default_config(self) -> BotsConfig:
        """创建默认配置。"""
        config = BotsConfig()
        
        # 保存到文件
        self._save_config(config)
        
        logger.info(f"[BotsLoader] Created default config at {self.config_path}")
        return config
    
    def _save_config(self, config: BotsConfig) -> None:
        """保存配置到文件。"""
        # 确保目录存在
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 转换为字典
        config_dict = config.dict()
        
        # 写入文件
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[BotsLoader] Saved config to {self.config_path}")
    
    def get_bot_config(self, bot_name: str) -> Optional[BotConfig]:
        """获取指定机器人的配置。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            机器人配置对象，如果不存在则返回 None
        """
        config = self.load_config()
        
        for bot in config.bots:
            if bot.name == bot_name:
                return bot
        
        return None
    
    def update_bot_config(self, bot_name: str, updates: dict) -> bool:
        """更新机器人配置。
        
        Args:
            bot_name: 机器人名称
            updates: 更新的配置字典
            
        Returns:
            是否更新成功
        """
        config = self.load_config()
        
        # 查找机器人
        for i, bot in enumerate(config.bots):
            if bot.name == bot_name:
                # 更新配置
                bot_dict = bot.dict()
                bot_dict.update(updates)
                config.bots[i] = BotConfig(**bot_dict)
                
                # 保存配置
                self._save_config(config)
                return True
        
        return False
    
    def add_bot_config(self, bot_config: BotConfig) -> bool:
        """添加机器人配置。
        
        Args:
            bot_config: 机器人配置对象
            
        Returns:
            是否添加成功
        """
        config = self.load_config()
        
        # 检查名称是否已存在
        for bot in config.bots:
            if bot.name == bot_config.name:
                logger.error(f"[BotsLoader] Bot {bot_config.name} already exists")
                return False
        
        # 添加机器人
        config.bots.append(bot_config)
        
        # 保存配置
        self._save_config(config)
        return True
    
    def remove_bot_config(self, bot_name: str) -> bool:
        """删除机器人配置。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            是否删除成功
        """
        config = self.load_config()
        
        # 查找并删除机器人
        for i, bot in enumerate(config.bots):
            if bot.name == bot_name:
                config.bots.pop(i)
                
                # 保存配置
                self._save_config(config)
                return True
        
        return False
```

## 配置文件示例

### config.json（主配置）

```json
{
  "workspace": "~/.iflow",
  "model": "kimi-k2.5",
  "tmux_sessions": [
    {
      "name": "iflow1",
      "workspace": "~/.iflow1",
      "model": "kimi-k2.5"
    },
    {
      "name": "iflow2",
      "workspace": "~/.iflow2",
      "model": "kimi-k2.5"
    }
  ],
  "wechat_work": {
    "enabled": true,
    "corp_id": "ww1234567890abcdef",
    "agent_id": 1000001,
    "secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "token": "xxxxxxxxxxxxxxxxxxxx",
    "encoding_aes_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "callback_port": 8788,
    "callback_host": "0.0.0.0",
    "stream_mode": false,
    "poll_interval": 5,
    "allow_from": ["user1", "user2"],
    "group_policy": "mention",
    "group_allow_from": ["group1"],
    "user_id": "user1"
  },
  "log_level": "INFO",
  "log_file": "/var/log/ling-iflow/app.log",
  "filter_thinking": true
}
```

### bots.json（机器人配置）

```json
{
  "bots": [
    {
      "name": "bot1",
      "enabled": true,
      "corp_id": "ww1234567890abcdef",
      "agent_id": 1000001,
      "secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "user_id": "user1",
      "token": "xxxxxxxxxxxxxxxxxxxx",
      "encoding_aes_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "callback_port": 8788,
      "tmux_session": "iflow1"
    },
    {
      "name": "bot2",
      "enabled": true,
      "corp_id": "ww0987654321fedcba",
      "agent_id": 1000002,
      "secret": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
      "user_id": "user2",
      "token": "yyyyyyyyyyyyyyyy",
      "encoding_aes_key": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
      "callback_port": 8789,
      "tmux_session": "iflow2"
    }
  ]
}
```

## 配置加载优先级

配置加载遵循以下优先级（从高到低）：

1. **命令行参数**：最高优先级
   ```bash
   ling-iflow start --workspace /custom/workspace --model custom-model
   ```

2. **环境变量**：中等优先级
   ```bash
   export LING_IFLOW__WORKSPACE=/custom/workspace
   export LING_IFLOW__MODEL=custom-model
   ```

3. **配置文件**：低优先级
   ```json
   {
     "workspace": "~/.iflow",
     "model": "kimi-k2.5"
   }
   ```

4. **默认值**：最低优先级
   ```python
   workspace: str = "~/.iflow"
   model: str = "kimi-k2.5"
   ```

## 配置验证

### 字段验证

```python
from pydantic import validator, Field

class WechatWorkConfig(BaseModel):
    callback_port: int = Field(
        ...,
        ge=1024,
        le=65535,
        description="回调服务端口"
    )
    
    @validator('group_policy')
    def validate_group_policy(cls, v):
        """验证群聊策略。"""
        valid_values = ['mention', 'all', 'none']
        if v not in valid_values:
            raise ValueError(f'group_policy must be one of {valid_values}, got {v}')
        return v
```

### 跨字段验证

```python
class WechatWorkConfig(BaseModel):
    enabled: bool = False
    corp_id: str = ""
    agent_id: int = 0
    secret: str = ""
    
    @validator('agent_id')
    def validate_agent_id(cls, v, values):
        """验证 AgentId（如果启用）。"""
        if values.get('enabled') and v <= 0:
            raise ValueError('agent_id must be positive when enabled')
        return v
    
    @validator('corp_id', 'secret')
    def validate_required_fields(cls, v, values, field):
        """验证必填字段（如果启用）。"""
        if values.get('enabled') and not v:
            raise ValueError(f'{field.name} is required when enabled')
        return v
```

## 配置热更新

```python
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变更处理器。"""
    
    def __init__(self, config_path: Path, callback):
        self.config_path = config_path
        self.callback = callback
    
    def on_modified(self, event):
        """文件修改事件。"""
        if event.src_path == str(self.config_path):
            logger.info(f"[ConfigWatcher] Config file modified: {self.config_path}")
            self.callback()

class ConfigWatcher:
    """配置文件监控器。"""
    
    def __init__(self, config_path: Path, callback):
        self.config_path = config_path
        self.callback = callback
        self.observer = None
    
    def start(self):
        """启动监控。"""
        self.observer = Observer()
        handler = ConfigFileHandler(self.config_path, self.callback)
        self.observer.schedule(handler, str(self.config_path.parent), recursive=False)
        self.observer.start()
        logger.info(f"[ConfigWatcher] Started watching: {self.config_path}")
    
    def stop(self):
        """停止监控。"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("[ConfigWatcher] Stopped watching")
```

## 相关文档

- [设计总览](./01-设计总览.md) - 项目概述、整体架构、核心目标
- [架构设计](./02-架构设计.md) - 详细的架构设计
- [模块设计-Channels层](./03-模块设计-Channels层.md) - 渠道层的详细设计
- [模块设计-Interactive层](./04-模块设计-Interactive层.md) - 交互层的详细设计
- [模块设计-CLI层](./06-模块设计-CLI层.md) - CLI层的详细设计