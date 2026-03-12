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
    
    # 默认会话名称前缀
    SESSION_PREFIX = "iflow"
    
    def __init__(self, tmux_session: Optional[str] = None):
        """初始化 iflow 控制器
        
        Args:
            tmux_session: tmux 会话名称，如果为 None 则自动分配
        """
        self._tmux_session = tmux_session
        self._session_assigned = tmux_session is not None
    
    @property
    def tmux_session(self) -> str:
        """获取 tmux 会话名称（延迟分配）"""
        return self._tmux_session or ""
    
    @tmux_session.setter
    def tmux_session(self, value: str):
        """设置 tmux 会话名称"""
        self._tmux_session = value
        self._session_assigned = True
    
    async def get_existing_sessions(self) -> list:
        """获取已存在的 iflow 会话列表
        
        Returns:
            已存在的 iflow 会话名称列表
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "tmux", "list-sessions", "-F", "#{session_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            
            if result.returncode != 0:
                return []
            
            sessions = stdout.decode().strip().split('\n')
            # 筛选出以 iflow 开头的会话
            iflow_sessions = [s for s in sessions if s.startswith(self.SESSION_PREFIX)]
            return iflow_sessions
            
        except Exception as e:
            logger.warning(f"[IFlowController] Error listing sessions: {e}")
            return []
    
    async def get_next_session_name(self) -> str:
        """获取下一个可用的会话名称
        
        Returns:
            可用的会话名称（如 iflow1, iflow2...）
        """
        existing = await self.get_existing_sessions()
        
        # 提取已使用的序号
        used_numbers = set()
        for session in existing:
            # 从 "iflow1", "iflow2" 等提取数字
            if session.startswith(self.SESSION_PREFIX):
                num_str = session[len(self.SESSION_PREFIX):]
                if num_str.isdigit():
                    used_numbers.add(int(num_str))
        
        # 找到最小的未使用序号
        for i in range(1, 1000):
            if i not in used_numbers:
                return f"{self.SESSION_PREFIX}{i}"
        
        # 备用方案：使用时间戳
        return f"{self.SESSION_PREFIX}_{int(time.time())}"
    
    async def assign_session_name(self) -> str:
        """分配会话名称（如果未指定）
        
        Returns:
            分配的会话名称
        """
        if self._session_assigned and self._tmux_session:
            return self._tmux_session
        
        # 自动分配名称
        self._tmux_session = await self.get_next_session_name()
        self._session_assigned = True
        logger.info(f"[IFlowController] 自动分配会话名称: {self._tmux_session}")
        return self._tmux_session
    
    async def check_tmux_session(self) -> bool:
        """检查 tmux 会话是否存在
        
        Returns:
            会话是否存在
        """
        if not self.tmux_session:
            logger.warning(f"[IFlowController] tmux_session is empty")
            return False
            
        try:
            result = await asyncio.create_subprocess_exec(
                "tmux", "has-session", "-t", self.tmux_session,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            if result.returncode != 0:
                logger.debug(f"[IFlowController] tmux session '{self.tmux_session}' not found (returncode={result.returncode})")
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
            # 捕获输出，检查是否有 iflow 的特征（增加行数确保捕获完整界面）
            output = await self.capture_output(200)
            
            # 检查输出中是否有 iflow 的特征：
            # 1. 输入框 ">   输入消息或@文件路径"
            # 2. 状态栏 "思考: 开启" 或 "智能模式"
            # 3. 版本号 "版本号:"
            iflow_indicators = [
                "输入消息或@文件路径",
                "Hi～今天想做点什么",
                "版本号:",
            ]
            
            for indicator in iflow_indicators:
                if indicator in output:
                    return True
            
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
        if not self.tmux_session:
            logger.error(f"[IFlowController] tmux_session is empty, cannot send message")
            return False
            
        if not await self.check_tmux_session():
            logger.error(f"[IFlowController] tmux session '{self.tmux_session}' not found")
            return False
        
        try:
            # 1. 先发送 C-c 清除当前输入框（参考旧版本实现）
            proc0 = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "C-c",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc0.communicate()
            await asyncio.sleep(0.1)
            
            # 2. 发送消息内容（使用 -l 选项逐字发送）
            proc1 = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "-l", message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc1.communicate()
            await asyncio.sleep(0.1)
            
            # 3. 发送回车键
            proc2 = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "C-m",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc2.communicate(), timeout=5)
            
            if proc2.returncode != 0:
                logger.error(f"[IFlowController] Failed to send message (returncode={proc2.returncode})")
                return False
            
            logger.info(f"[IFlowController] 发送消息到 iflow: {message[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"[IFlowController] Error sending message: {e}")
            return False
    
    async def start_iflow(self, model: str = "kimi-k2.5") -> bool:
        """在 tmux 会话中启动 iflow CLI
        
        如果会话名称未指定，自动分配。
        
        Args:
            model: iflow 模型
            
        Returns:
            是否启动成功
        """
        # 确保会话名称已分配
        await self.assign_session_name()
        
        # 检查 tmux 会话是否已存在
        tmux_exists = await self.check_tmux_session()
        
        if tmux_exists:
            # 检查 iflow 是否已在运行
            if await self.check_iflow_running():
                logger.info("[IFlowController] iflow already running")
                return True
            else:
                # tmux 会话存在但 iflow 未运行，重新启动 iflow
                logger.info("[IFlowController] tmux session exists, starting iflow...")
                result = await asyncio.create_subprocess_exec(
                    "tmux", "send-keys", "-t", self.tmux_session,
                    f"iflow --model {model}", "C-m",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(result.communicate(), timeout=10)
                
                # 等待 iflow 完全启动（最多 25 秒）
                for i in range(25):
                    await asyncio.sleep(1)
                    if await self.check_iflow_running():
                        logger.info(f"[IFlowController] iflow started in existing tmux session '{self.tmux_session}' after {i+1}s")
                        return True
                
                logger.warning("[IFlowController] iflow may not have started properly")
                return False
        
        try:
            # 参考旧版本：直接在创建 tmux 会话时启动 iflow
            # 使用 shell=True 来解析命令
            result = await asyncio.create_subprocess_shell(
                f"tmux new-session -d -s {self.tmux_session} 'iflow --model {model}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=30)
            
            if result.returncode != 0:
                logger.error(f"[IFlowController] Failed to create tmux session with iflow")
                return False
            
            logger.info(f"[IFlowController] iflow starting in tmux session '{self.tmux_session}'")
            
            # 等待 iflow 完全启动（最多 25 秒）
            for i in range(25):
                await asyncio.sleep(1)
                if await self.check_iflow_running():
                    logger.info(f"[IFlowController] iflow fully started after {i+1}s")
                    return True
            
            logger.warning("[IFlowController] iflow may not have started properly (timeout)")
            return False
            
        except Exception as e:
            logger.error(f"[IFlowController] Error starting iflow: {e}")
            return False
    
    async def stop_iflow(self) -> bool:
        """停止 iflow CLI（但保留 tmux 会话）
        
        Returns:
            是否停止成功
        """
        if not await self.check_tmux_session():
            logger.info(f"[IFlowController] tmux session '{self.tmux_session}' not found")
            return True
        
        try:
            # 发送 Ctrl+C 停止 iflow
            await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "C-c",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await asyncio.sleep(0.5)
            
            # 发送 exit 命令
            result = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", self.tmux_session, "exit", "C-m",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=5)
            
            logger.info(f"[IFlowController] iflow stopped in session '{self.tmux_session}'")
            return True
            
        except Exception as e:
            logger.error(f"[IFlowController] Error stopping iflow: {e}")
            return False
    
    async def destroy_session(self) -> bool:
        """销毁 tmux 会话（停止 iflow 并删除会话）
        
        Returns:
            是否销毁成功
        """
        if not await self.check_tmux_session():
            logger.info(f"[IFlowController] tmux session '{self.tmux_session}' not found")
            return True
        
        try:
            # 先停止 iflow
            await self.stop_iflow()
            
            # 等待一下
            await asyncio.sleep(0.5)
            
            # 强制关闭 tmux 会话
            result = await asyncio.create_subprocess_exec(
                "tmux", "kill-session", "-t", self.tmux_session,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=10)
            
            if result.returncode != 0:
                logger.warning(f"[IFlowController] Failed to kill session")
                return False
            
            logger.info(f"[IFlowController] tmux session '{self.tmux_session}' destroyed")
            return True
            
        except Exception as e:
            logger.error(f"[IFlowController] Error destroying session: {e}")
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