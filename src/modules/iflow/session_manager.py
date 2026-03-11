"""会话管理器

管理 iflow 的会话（session）文件，提供会话查询、创建等功能。
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器。
    
    功能：
    - 获取最新的 session 文件
    - 获取所有 session 列表
    - 创建新会话
    - 获取当前会话信息
    - 删除指定 session
    """
    
    def __init__(self, workspace: str = "~/.iflow"):
        """初始化会话管理器。
        
        Args:
            workspace: iflow 工作目录
        """
        self.workspace = Path(workspace).expanduser()
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
    
    @property
    def session_dir(self) -> Path:
        """获取 session 目录路径。"""
        return self.workspace / "projects" / os.getcwd().replace("/", "-")
    
    def ensure_session_dir(self) -> Path:
        """确保 session 目录存在。"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        return self.session_dir
    
    def get_latest_session(self) -> Optional[Dict]:
        """获取最新的 session 文件。
        
        Returns:
            session 信息字典，格式：
            {
                "id": "session-id",
                "path": "/path/to/session-file.jsonl",
                "mtime": datetime,
                "size": int
            }
            或 None（如果没有 session）
        """
        if not self.session_dir.exists():
            return None
        
        try:
            files = list(self.session_dir.glob("session-*.jsonl"))
            
            if not files:
                return None
            
            sessions = []
            for file_path in files:
                stats = file_path.stat()
                # 从文件名提取 session ID: session-xxx.jsonl
                session_id = file_path.name.replace("session-", "").replace(".jsonl", "")
                sessions.append({
                    "id": session_id,
                    "path": str(file_path),
                    "mtime": datetime.fromtimestamp(stats.st_mtime),
                    "size": stats.st_size
                })
            
            # 按修改时间排序，最新的在前
            sessions.sort(key=lambda x: x["mtime"], reverse=True)
            return sessions[0] if sessions else None
            
        except Exception as e:
            logger.error(f"[SessionManager] 获取最新 session 失败: {e}")
            return None
    
    def get_all_sessions(self, limit: int = 20) -> List[Dict]:
        """获取所有 session 列表。
        
        Args:
            limit: 最多返回的数量
            
        Returns:
            session 信息列表，每个 session 包含 id, mtime, size, path
        """
        if not self.session_dir.exists():
            return []
        
        try:
            files = list(self.session_dir.glob("session-*.jsonl"))
            
            sessions = []
            for file_path in files:
                stats = file_path.stat()
                session_id = file_path.name.replace("session-", "").replace(".jsonl", "")
                sessions.append({
                    "id": session_id,
                    "path": str(file_path),
                    "mtime": datetime.fromtimestamp(stats.st_mtime),
                    "size": stats.st_size
                })
            
            # 按修改时间排序，最新的在前
            sessions.sort(key=lambda x: x["mtime"], reverse=True)
            
            return sessions[:limit]
            
        except Exception as e:
            logger.error(f"[SessionManager] 获取 session 列表失败: {e}")
            return []
    
    def create_new_session(self) -> Dict:
        """创建新会话（重置当前 session 状态）。
        
        Returns:
            操作结果字典，格式：
            {
                "success": bool,
                "message": str,
                "session_id": Optional[str]
            }
        """
        self.current_session_id = None
        self.session_start_time = None
        logger.info("[SessionManager] 开始新会话")
        
        return {
            "success": True,
            "message": "已开始新会话，下次命令将从空白上下文开始",
            "session_id": None
        }
    
    def delete_session(self, session_id: str) -> bool:
        """删除指定 session。
        
        Args:
            session_id: session ID
            
        Returns:
            是否成功
        """
        try:
            session_path = self.session_dir / f"session-{session_id}.jsonl"
            if session_path.exists():
                session_path.unlink()
                logger.info(f"[SessionManager] 已删除 session: {session_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"[SessionManager] 删除 session 失败: {e}")
            return False
    
    def get_current_session_info(self) -> Dict:
        """获取当前会话信息。
        
        Returns:
            会话信息字典，格式：
            {
                "has_session": bool,
                "session_id": Optional[str],
                "start_time": Optional[datetime],
                "is_restored": bool
            }
        """
        if self.current_session_id:
            return {
                "has_session": True,
                "session_id": self.current_session_id,
                "start_time": self.session_start_time,
                "is_restored": False
            }
        
        latest = self.get_latest_session()
        if latest:
            return {
                "has_session": True,
                "session_id": latest["id"],
                "start_time": latest["mtime"],
                "is_restored": True
            }
        
        return {
            "has_session": False,
            "session_id": None,
            "start_time": None,
            "is_restored": False
        }
    
    def get_status_message(self) -> str:
        """获取状态信息的 Markdown 格式字符串。
        
        Returns:
            状态信息 Markdown 文本
        """
        session_info = self.get_current_session_info()
        
        if session_info["has_session"]:
            session_id = session_info["session_id"]
            session_time = session_info["start_time"].strftime("%Y-%m-%d %H:%M:%S") if session_info["start_time"] else "未知"
            restored_text = " [已恢复]" if session_info.get("is_restored") else ""
            session_status = f"`{session_id[:8]}...` ({session_time}){restored_text}"
        else:
            session_status = "无活跃会话"
        
        return f"""**iFlow 服务状态** 📊

- Session 目录: `{self.session_dir}`
- 当前会话: {session_status}
- Session 文件数: {len(self.get_all_sessions())}
"""
    
    def get_sessions_message(self, limit: int = 10) -> str:
        """获取会话列表信息的 Markdown 格式字符串。
        
        Args:
            limit: 最多显示的数量
            
        Returns:
            会话列表 Markdown 文本
        """
        sessions = self.get_all_sessions(limit)
        
        if not sessions:
            return f"""**历史会话** 📋

暂无历史会话记录
"""
        
        message = f"""**历史会话** 📋

共 {len(sessions)} 个会话：

"""
        
        for index, session in enumerate(sessions):
            session_id = session["id"]
            mtime = session["mtime"].strftime("%Y-%m-%d %H:%M:%S")
            size_kb = round(session["size"] / 1024)
            current = " ✓ 当前" if session_id == self.current_session_id else ""
            message += f"{index + 1}. `{session_id[:8]}...` - {mtime} ({size_kb}KB){current}\n"
        
        return message
    
    def set_current_session(self, session_id: str) -> None:
        """设置当前会话 ID。
        
        Args:
            session_id: session ID
        """
        self.current_session_id = session_id
        self.session_start_time = datetime.now()
        logger.info(f"[SessionManager] 设置当前会话: {session_id}")
    
    def clear_current_session(self) -> None:
        """清除当前会话状态。"""
        self.current_session_id = None
        self.session_start_time = None
        logger.info("[SessionManager] 清除当前会话状态")
