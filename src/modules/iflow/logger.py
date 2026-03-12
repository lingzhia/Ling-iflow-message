"""
Interaction Logger

记录与 iflow 的交互信息。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


logger = logging.getLogger(__name__)


class InteractionLogger:
    """交互记录器
    
    记录与 iflow 的所有交互信息，包括发送的消息和收到的回复。
    """
    
    def __init__(
        self,
        module_id: str,
        log_dir: str = "logs/interactions",
        enabled: bool = True
    ):
        """初始化交互记录器
        
        Args:
            module_id: 模块 ID，用于标识日志来源
            log_dir: 日志存储目录
            enabled: 是否启用记录
        """
        self.module_id = module_id
        self.log_dir = Path(log_dir)
        self.enabled = enabled
        
        # 当前会话的交互记录
        self._session_log: List[Dict[str, Any]] = []
        
        # 会话开始时间
        self._session_start: Optional[datetime] = None
        
        # 确保日志目录存在
        if self.enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def start_session(self) -> None:
        """开始新会话"""
        self._session_log = []
        self._session_start = datetime.now()
        logger.debug(f"[{self.module_id}] 交互记录会话已开始")
    
    def log_sent(self, content: str) -> None:
        """记录发送的消息
        
        Args:
            content: 发送的消息内容
        """
        if not self.enabled:
            return
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": "sent",
            "content": content,
            "module_id": self.module_id
        }
        self._session_log.append(entry)
        logger.debug(f"[{self.module_id}] 记录发送消息: {content[:50]}...")
    
    def log_received(self, content: str) -> None:
        """记录收到的回复
        
        Args:
            content: 收到的回复内容
        """
        if not self.enabled:
            return
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": "received",
            "content": content,
            "module_id": self.module_id
        }
        self._session_log.append(entry)
        logger.debug(f"[{self.module_id}] 记录接收消息: {content[:50]}...")
    
    def get_session_log(self) -> List[Dict[str, Any]]:
        """获取当前会话的交互记录
        
        Returns:
            交互记录列表
        """
        return self._session_log.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        sent_count = sum(1 for e in self._session_log if e["direction"] == "sent")
        received_count = sum(1 for e in self._session_log if e["direction"] == "received")
        
        return {
            "module_id": self.module_id,
            "session_start": self._session_start.isoformat() if self._session_start else None,
            "total_interactions": len(self._session_log),
            "sent_count": sent_count,
            "received_count": received_count,
            "enabled": self.enabled
        }
    
    def save_session(self) -> Optional[Path]:
        """保存会话到文件
        
        Returns:
            保存的文件路径，如果未启用则返回 None
        """
        if not self.enabled or not self._session_log:
            return None
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.module_id}_{timestamp}.json"
        filepath = self.log_dir / filename
        
        # 构建保存数据
        data = {
            "module_id": self.module_id,
            "session_start": self._session_start.isoformat() if self._session_start else None,
            "session_end": datetime.now().isoformat(),
            "total_interactions": len(self._session_log),
            "interactions": self._session_log
        }
        
        # 保存到文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[{self.module_id}] 交互记录已保存: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"[{self.module_id}] 保存交互记录失败: {e}")
            return None
    
    def clear_session(self) -> None:
        """清空当前会话日志"""
        self._session_log = []
        self._session_start = None
        logger.debug(f"[{self.module_id}] 交互记录会话已清空")
    
    def set_enabled(self, enabled: bool) -> None:
        """设置是否启用
        
        Args:
            enabled: 是否启用
        """
        self.enabled = enabled
        if enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
