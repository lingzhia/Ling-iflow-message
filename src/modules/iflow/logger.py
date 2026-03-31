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
        log_dir: Optional[str] = None,
        enabled: bool = True,
        project_root: Optional[Path] = None
    ):
        """初始化交互记录器

        Args:
            module_id: 模块 ID，用于标识日志来源
            log_dir: 日志存储目录（相对路径，相对于项目根目录）
            enabled: 是否启用记录
            project_root: 项目根目录，如果为 None 则自动推导
        """
        self.module_id = module_id
        self.enabled = enabled
        
        # 自动推导项目根目录：当前文件 (src/modules/iflow/logger.py) 的上级上级上级目录
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent.parent
        
        # 日志目录：项目根目录下的 logs/interactions
        if log_dir is None:
            self.log_dir = project_root / "logs" / "interactions"
        else:
            self.log_dir = project_root / log_dir

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
    
    def log_sent(self, content: str, message_type: Optional[str] = None) -> None:
        """记录发送的消息
        
        Args:
            content: 发送的消息内容
        """
        if not self.enabled:
            return
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": "sent",
            "message_type": message_type,  # None 表示用户发送的问题
            "content": content,
            "module_id": self.module_id
        }
        self._session_log.append(entry)
        logger.debug(f"[{self.module_id}] 记录发送消息: {content[:50]}...")
    
    def log_received(self, content: str, message_type: str = "reply", extra_info: Optional[Dict] = None) -> None:
        """记录收到的回复
        
        Args:
            content: 收到的回复内容
        """
        if not self.enabled:
            return
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": "received",
            "message_type": message_type,  # "reply" | "thought" | "other"
            "content": content,
            "module_id": self.module_id
        }

        # 添加额外信息（如果有）
        if extra_info:
            for key, value in extra_info.items():
                entry[key] = value
        
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
    
    def save_session(self, append: bool = True) -> Optional[Path]:
        """保存会话到文件

        Args:
            append: 是否追加到文件（True）还是覆盖写入（False）
                   True - 追加到模块固定文件（JSONL 格式）
                   False - 写入带时间戳的文件（完整 JSON 格式，用于模块停止时）

        Returns:
            保存的文件路径，如果未启用则返回 None
        """
        if not self.enabled or not self._session_log:
            return None

        # 生成文件名
        if append:
            # 使用固定文件名（每次交互都追加到同一个文件，JSONL 格式）
            filename = f"iflow_{self.module_id}.jsonl"
        else:
            # 模块停止时使用带时间戳的文件名（完整 JSON 格式）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"iflow_{self.module_id}_{timestamp}.json"
        
        filepath = self.log_dir / filename
        
        if append:
            # 追加模式：每行一个 JSON（JSONL 格式）
            try:
                with open(filepath, 'a', encoding='utf-8') as f:
                    # 每行保存一条交互记录
                    for entry in self._session_log:
                        json_line = json.dumps(entry, ensure_ascii=False)
                        f.write(json_line + '\n')
                logger.info(f"[{self.module_id}] 交互记录已追加：{filepath} ({len(self._session_log)} 条)")
                return filepath
            except Exception as e:
                logger.error(f"[{self.module_id}] 追加交互记录失败：{e}")
                return None
        else:
            # 覆盖模式：完整 JSON 格式（用于模块停止时）
            data = {
                "module_id": self.module_id,
                "session_start": self._session_start.isoformat() if self._session_start else None,
                "session_end": datetime.now().isoformat(),
                "total_interactions": len(self._session_log),
                "interactions": self._session_log
            }
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"[{self.module_id}] 交互记录已保存：{filepath}")
                return filepath
            except Exception as e:
                logger.error(f"[{self.module_id}] 保存交互记录失败：{e}")
                return None

    def clear_session(self) -> None:
        """清空当前会话日志"""
        self._session_log = []
        self._session_start = None
        logger.debug(f"[{self.module_id}] 交互记录会话已清空")

    def _cleanup_old_files(self, keep_count: int = 10) -> None:
        """清理旧的交互记录文件，只保留最近 N 个"""
        try:
            pattern = f"{self.module_id}_*.json"
            files = sorted(
                [f for f in self.log_dir.glob(pattern) if f.is_file()],
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )

            if len(files) > keep_count:
                for f in files[keep_count:]:
                    f.unlink()
                    logger.debug(f"[{self.module_id}] 删除旧交互记录: {f.name}")
        except Exception as e:
            logger.warning(f"[{self.module_id}] 清理旧交互记录失败: {e}")
    
    def set_enabled(self, enabled: bool) -> None:
        """设置是否启用
        
        Args:
            enabled: 是否启用
        """
        self.enabled = enabled
        if enabled:
            self.log_dir.mkdir(parents=True, exist_ok=True)
