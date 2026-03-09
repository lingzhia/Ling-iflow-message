"""配置 Schema for Ling-iflow。"""

from pathlib import Path
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WechatWorkConfig(BaseModel):
    """企业微信配置。
    
    支持两种模式：
    1. 应用机器人：通过企业微信 API 接收和发送消息
    2. 群机器人：通过 Webhook 发送消息（仅发送）
    """
    model_config = {"extra": "ignore"}
    
    enabled: bool = False
    
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


class InteractiveConfig(BaseSettings):
    """交互模式配置。"""

    model_config = {
        "env_prefix": "LING_IFLOW_",
        "env_nested_delimiter": "__",
        "extra": "ignore",
    }

    # iflow 配置
    workspace: str = "~/.iflow"
    """iflow 工作目录。"""
    
    model: str = "kimi-k2.5"
    """iflow 模型名称。"""
    
    tmux_session: str = "iflow"
    """tmux 会话名称。"""
    
    # 企业微信配置
    wechat_work: WechatWorkConfig = Field(default_factory=WechatWorkConfig)
    
    # 日志配置
    log_level: str = "INFO"
    log_file: str = ""
    
    # 消息过滤配置
    filter_thinking: bool = True
    """是否过滤 iflow 思考消息（以 * 开头的行）。"""
    
    def get_workspace_path(self) -> Path:
        """获取工作目录路径。"""
        return Path(self.workspace).expanduser()
    
    def get_enabled_channels(self) -> list[str]:
        """获取已启用的渠道列表。"""
        enabled = []
        if self.wechat_work and self.wechat_work.enabled:
            enabled.append("wechat_work")
        return enabled