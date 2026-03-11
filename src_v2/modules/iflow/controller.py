"""
IFlow Controller

通过 tmux 管理 iflow CLI 的控制器。
"""

import subprocess
import time
import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class IFlowController:
    """iflow CLI 控制器
    
    通过 tmux 命令管理 iflow CLI 会话。
    """
    
    def __init__(self, tmux_session: str = "iflow"):
        """初始化 iflow 控制器
        
        Args:
            tmux_session: tmux 会话名称
        """
        self.tmux_session = tmux_session
    
    async def check_tmux_session(self) -> bool:
        """检查 tmux 会话是否存在
        
        Returns:
            会话是否存在
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "tmux", "has-session", "-t", self.tmux_session,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"[IFlowController] Error checking tmux session: {e}")
            return False
    
    async def check_iflow_running(self) -> bool:
        """检查 iflow CLI 是否在运行
        
        Returns:
            iflow 是否运行
        """
        if not await self.check_tmux_session():
            return False
        
        try:
            # 检查会话中是否有 iflow 进程
            result = await asyncio.create_subprocess_exec(
                "tmux", "list-panes", "-t", self.tmux_session, "-F", "#{pane_pid}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            
            if result.returncode == 0 and stdout.strip():
                pane_pid = stdout.decode().strip()
                
                # 检查进程命令是否包含 iflow
                try:
                    with open(f"/proc/{pane_pid}/cmdline", "r") as f:
                        cmdline = f.read()
                        if "iflow" in cmdline.lower():
                            return True
                except:
                    pass
            
            return False
        except Exception as e:
            logger.warning(f"[IFlowController] Error checking iflow status: {e}")
            return False
    
    async def send_message(self, message: str) -> bool:
        """发送消息到 iflow CLI
        
        Args:
            message: 要发送的消息
            
        Returns:
            是否发送成功
        """
        if not await self.check_tmux_session():
            logger.error(f"[IFlowController] tmux session '{self.tmux_session}' not found")
            return False
        
        try:
            # 清除当前输入框（如果有）
            await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "C-c",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 稍微等待一下
            await asyncio.sleep(0.1)
            
            # 发送消息内容（使用 -l 选项逐字发送）
            await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "-l", message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 稍微等待一下
            await asyncio.sleep(0.1)
            
            # 发送回车键
            result = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "C-m",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=5)
            
            if result.returncode != 0:
                logger.error(f"[IFlowController] Failed to send message")
                return False
            
            logger.info(f"[IFlowController] 发送消息到 iflow: {message}")
            return True
            
        except Exception as e:
            logger.error(f"[IFlowController] Error sending message: {e}")
            return False
    
    async def start_iflow(self, model: str = "kimi-k2.5") -> bool:
        """在 tmux 会话中启动 iflow CLI
        
        Args:
            model: iflow 模型
            
        Returns:
            是否启动成功
        """
        if await self.check_tmux_session():
            logger.warning(f"[IFlowController] tmux session '{self.tmux_session}' already exists")
            if await self.check_iflow_running():
                logger.info("[IFlowController] iflow already running")
                return True
        
        try:
            # 创建新的 tmux 会话并启动 iflow
            result = await asyncio.create_subprocess_exec(
                "tmux", "new-session", "-d", "-s", self.tmux_session,
                f"iflow --model {model}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=30)
            
            if result.returncode != 0:
                logger.error(f"[IFlowController] Failed to start iflow")
                return False
            
            logger.info(f"[IFlowController] iflow started in tmux session '{self.tmux_session}'")
            
            # 等待 iflow 启动
            await asyncio.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"[IFlowController] Error starting iflow: {e}")
            return False
    
    async def stop_iflow(self) -> bool:
        """停止 iflow CLI
        
        Returns:
            是否停止成功
        """
        if not await self.check_tmux_session():
            logger.info(f"[IFlowController] tmux session '{self.tmux_session}' not found")
            return True
        
        try:
            # 关闭 tmux 会话
            result = await asyncio.create_subprocess_exec(
                "tmux", "kill-session", "-t", self.tmux_session,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=10)
            
            if result.returncode != 0:
                logger.warning(f"[IFlowController] Failed to kill session")
                return False
            
            logger.info(f"[IFlowController] tmux session '{self.tmux_session}' killed")
            return True
            
        except Exception as e:
            logger.error(f"[IFlowController] Error stopping iflow: {e}")
            return False
    
    async def get_session_info(self) -> Optional[dict]:
        """获取会话信息
        
        Returns:
            会话信息字典，如果获取失败则返回 None
        """
        try:
            info = {
                "tmux_session": self.tmux_session,
                "tmux_exists": await self.check_tmux_session(),
                "iflow_running": False,
            }
            
            # 只有当 tmux 会话存在时才检查 iflow
            if info["tmux_exists"]:
                info["iflow_running"] = await self.check_iflow_running()
            
            return info
        except Exception as e:
            logger.error(f"[IFlowController] Error getting session info: {e}")
            return None
    
    async def capture_output(self, lines: int = 1000) -> str:
        """捕获 tmux 输出
        
        Args:
            lines: 捕获的行数
            
        Returns:
            捕获的输出
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "tmux", "capture-pane", "-t", self.tmux_session,
                "-S", f"-{lines}", "-p",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=10)
            
            if result.returncode == 0:
                return stdout.decode()
            else:
                logger.error(f"[IFlowController] Failed to capture output")
                return ""
                
        except Exception as e:
            logger.error(f"[IFlowController] Error capturing output: {e}")
            return ""