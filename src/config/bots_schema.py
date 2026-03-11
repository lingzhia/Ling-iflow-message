"""机器人配置 Schema for Ling-iflow。"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class BotConfig(BaseModel):
    """单个机器人配置。"""
    model_config = {"extra": "ignore"}
    
    # 机器人名称（唯一标识）
    name: str
    
    # 是否启用
    enabled: bool = True
    
    # 企业 ID
    corp_id: str = ""
    
    # 应用配置
    agent_id: str = ""  # 应用 AgentId
    secret: str = ""    # 应用 Secret
    user_id: str = ""   # 默认用户 ID
    
    # 回调配置（可选，用于消息验证和加解密）
    token: str = ""
    encoding_aes_key: str = ""
    
    # 内嵌 HTTP 服务配置
    callback_port: int = 8788
    """内嵌 HTTP 回调服务端口。"""
    
    callback_host: str = "0.0.0.0"
    """内嵌 HTTP 回调服务监听地址。"""
    
    # 消息接收模式
    stream_mode: bool = False
    """是否启用 Stream Mode（长轮询）。"""
    
    poll_interval: int = 5
    """轮询间隔（秒），仅 stream_mode=True 时有效。"""
    
    # 权限控制
    allow_from: list[str] = Field(default_factory=list)
    """允许的用户 ID 白名单。"""
    
    # 群聊配置
    group_policy: str = "mention"
    """群聊消息响应策略。"""
    
    group_allow_from: list[str] = Field(default_factory=list)
    """群聊白名单。"""
    
    # 关联的 tmux 会话
    tmux_session: str = "iflow"
    """关联的 tmux 会话名称。"""


class BotsConfig(BaseModel):
    """机器人配置列表。"""
    model_config = {"extra": "ignore"}
    
    bots: list[BotConfig] = Field(default_factory=list)
    """机器人配置列表。"""
    
    def get_bot_by_name(self, name: str) -> Optional[BotConfig]:
        """根据名称获取机器人配置。"""
        for bot in self.bots:
            if bot.name == name:
                return bot
        return None
    
    def get_enabled_bots(self) -> list[BotConfig]:
        """获取所有启用的机器人。"""
        return [bot for bot in self.bots if bot.enabled]
    
    def get_bot_names(self) -> list[str]:
        """获取所有机器人名称。"""
        return [bot.name for bot in self.bots]