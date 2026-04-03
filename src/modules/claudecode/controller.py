"""
Claude Code Controller

通过 tmux 管理 Claude Code CLI 的控制器。
Claude Code 需要以非 root 用户运行，因此需要使用 su 命令切换用户。
"""

import subprocess
import time
import asyncio
import os
import pwd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ClaudeCodeController:
    """Claude Code CLI 控制器

    通过 tmux 命令管理 Claude Code CLI 会话。
    需要以非 root 用户运行以支持 --dangerously-skip-permissions 参数。
    """

    # 默认会话名称前缀
    SESSION_PREFIX = "claude"

    # 默认运行用户
    DEFAULT_RUN_USER = "vboxuser"

    def __init__(
        self,
        tmux_session: Optional[str] = None,
        run_user: Optional[str] = None,
        workspace: Optional[str] = None
    ):
        """初始化 Claude Code 控制器

        Args:
            tmux_session: tmux 会话名称，如果为 None 则自动分配
            run_user: 运行 Claude Code 的用户（需要非 root）
            workspace: 工作目录
        """
        self._tmux_session = tmux_session
        self._session_assigned = tmux_session is not None
        self._run_user = run_user or self.DEFAULT_RUN_USER
        self._workspace = workspace or os.getcwd()
        self._last_sent_message: Optional[str] = None
        self._last_sent_time: Optional[float] = None
        self._safety_confirmed = False  # 安全确认是否已完成

    @property
    def tmux_session(self) -> str:
        """获取 tmux 会话名称（延迟分配）"""
        return self._tmux_session or ""

    @tmux_session.setter
    def tmux_session(self, value: str):
        """设置 tmux 会话名称"""
        self._tmux_session = value
        self._session_assigned = True

    @property
    def run_user(self) -> str:
        """获取运行用户"""
        return self._run_user

    async def get_existing_sessions(self) -> list:
        """获取已存在的 Claude Code 会话列表

        会话命名规则：
        - 自动分配：claude1, claude2, ... (以 claude 开头)
        - 渠道专用：{channel}+claude (以 +claude 结尾)

        Returns:
            已存在的 Claude Code 会话名称列表
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
            # 匹配两种会话命名：
            # 1. 以 SESSION_PREFIX 开头 (claude1, claude2, ...)
            # 2. 以 +claude 结尾 (simulator1+claude, wechat_bot1+claude, ...)
            claude_sessions = [
                s for s in sessions
                if s.startswith(self.SESSION_PREFIX) or s.endswith("+claude")
            ]
            return claude_sessions

        except Exception as e:
            logger.warning(f"[ClaudeCodeController] Error listing sessions: {e}")
            return []

    async def get_next_session_name(self) -> str:
        """获取下一个可用的会话名称

        Returns:
            可用的会话名称（如 claude1, claude2...）
        """
        existing = await self.get_existing_sessions()

        # 提取已使用的序号
        used_numbers = set()
        for session in existing:
            if session.startswith(self.SESSION_PREFIX):
                num_str = session[len(self.SESSION_PREFIX):]
                if num_str.isdigit():
                    used_numbers.add(int(num_str))

        # 找到最小的未使用序号
        for i in range(1, 1000):
            if i not in used_numbers:
                return f"{self.SESSION_PREFIX}{i}"

        return f"{self.SESSION_PREFIX}_{int(time.time())}"

    async def assign_session_name(self) -> str:
        """分配会话名称（如果未指定）"""
        if self._session_assigned and self._tmux_session:
            return self._tmux_session

        self._tmux_session = await self.get_next_session_name()
        self._session_assigned = True
        logger.info(f"[ClaudeCodeController] 自动分配会话名称: {self._tmux_session}")
        return self._tmux_session

    async def check_tmux_session(self) -> bool:
        """检查 tmux 会话是否存在"""
        if not self.tmux_session:
            logger.warning(f"[ClaudeCodeController] tmux_session is empty")
            return False

        try:
            result = await asyncio.create_subprocess_exec(
                "tmux", "has-session", "-t", self.tmux_session,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"[ClaudeCodeController] Error checking tmux session: {e}")
            return False

    async def check_safety_confirmation(self) -> bool:
        """检查是否需要处理安全确认对话框

        Returns:
            是否显示安全确认对话框
        """
        try:
            output = await self.capture_output(lines=50)
            # 只检测真正的交互式确认提示，不包括 "bypass permissions on" 这类状态提示
            # 真正的确认对话框会有类似 "Press Enter" 或 "continue?" 的交互式提示
            prompts = ["Quick safety check", "trust this folder", "trust and open",
                       "Do you want to continue", "type 'yes' to"]
            return any(p.lower() in output.lower() for p in prompts)
        except Exception:
            return False

    async def handle_safety_confirmation(self) -> bool:
        """处理安全确认对话框

        Claude Code 启动时会显示安全确认对话框，
        需要发送 Enter 来确认（默认选择第一项）。

        Returns:
            是否处理成功
        """
        if self._safety_confirmed:
            return True

        try:
            # 检测到安全确认对话框后立即发送 Enter
            if await self.check_safety_confirmation():
                logger.info("[ClaudeCodeController] 检测到安全确认对话框，发送 Enter")
                await asyncio.create_subprocess_exec(
                    "tmux", "send-keys", "-t", self.tmux_session, "Enter",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.sleep(2)

            # 等待对话框消失（最多 10 秒）
            for _ in range(10):
                if not await self.check_safety_confirmation():
                    self._safety_confirmed = True
                    logger.info("[ClaudeCodeController] Safety confirmation completed")
                    return True
                # 如果还在显示，再次发送 Enter
                await asyncio.create_subprocess_exec(
                    "tmux", "send-keys", "-t", self.tmux_session, "Enter",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.sleep(1)

            return False

        except Exception as e:
            logger.error(f"[ClaudeCodeController] Error handling safety confirmation: {e}")
            return False

    async def check_claude_ready(self) -> bool:
        """检查 Claude Code 是否就绪

        就绪条件：
        1. tmux 会话存在
        2. Claude Code 已完全启动
        3. 安全确认已完成（没有安全确认对话框）
        4. 显示 ❯ 提示符

        Returns:
            Claude Code 是否就绪
        """
        # 1. 检查 tmux 会话
        if not await self.check_tmux_session():
            logger.debug("[check_claude_ready] tmux session not found")
            return False

        # 2. 捕获输出
        output = await self.capture_output(lines=100)
        if not output:
            logger.debug("[check_claude_ready] no output captured")
            return False

        # 3. 检查安全确认对话框是否消失
        if await self.check_safety_confirmation():
            logger.debug("[check_claude_ready] safety confirmation still showing")
            return False

        # 4. 检查是否有 ❯ 提示符（Claude Code 就绪）
        if "❯" in output:
            logger.debug("[check_claude_ready] Claude Code is ready")
            return True

        return False

    async def is_generating(self) -> bool:
        """检查是否正在生成回复

        Claude Code 处理中时会显示 "Choreographing..."

        Returns:
            是否正在生成
        """
        try:
            output = await self.capture_output(lines=100)
            return "Choreographing" in output
        except Exception:
            return False

    async def send_message(self, message: str) -> bool:
        """发送消息到 Claude Code CLI

        Args:
            message: 要发送的消息

        Returns:
            是否发送成功
        """
        if not self.tmux_session:
            logger.error(f"[ClaudeCodeController] tmux_session is empty, cannot send message")
            return False

        if not await self.check_tmux_session():
            logger.error(f"[ClaudeCodeController] tmux session '{self.tmux_session}' not found")
            return False

        try:
            # 0. 检查 Claude Code 是否准备好
            if not await self.check_claude_ready():
                logger.warning(f"[ClaudeCodeController] Claude Code not ready, cannot send message")
                return False

            # 1. 清除输入框（使用 C-c）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["tmux", "send-keys", "-t", self.tmux_session, "C-c"],
                    check=True,
                    capture_output=True,
                    text=True
                )
            )
            await asyncio.sleep(0.3)

            # 2. 直接发送消息内容
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["tmux", "send-keys", "-t", self.tmux_session, message],
                    check=True,
                    capture_output=True,
                    text=True
                )
            )
            await asyncio.sleep(0.5)

            # 3. 发送回车键
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    ["tmux", "send-keys", "-t", self.tmux_session, "C-m"],
                    check=True,
                    capture_output=True,
                    text=True
                )
            )

            logger.info(f"[ClaudeCodeController] 发送消息到 Claude Code: {message[:50]}...")

            # 记录最后发送的消息
            self._last_sent_message = message
            self._last_sent_time = time.time()

            return True

        except Exception as e:
            logger.error(f"[ClaudeCodeController] Error sending message: {e}")
            return False

    async def start_claude_code(
        self,
        model: str = "sonnet",
        continue_last: bool = True
    ) -> bool:
        """在 tmux 会话中启动 Claude Code CLI

        Args:
            model: Claude Code 模型
            continue_last: 是否继续上一次对话（添加 -c 参数）

        Returns:
            是否启动成功
        """
        # 确保会话名称已分配
        await self.assign_session_name()

        # 检查 tmux 会话是否已存在
        tmux_exists = await self.check_tmux_session()

        if tmux_exists:
            # 检查 Claude Code 是否已在运行
            if await self.check_claude_ready():
                logger.info("[ClaudeCodeController] Claude Code already running")
                return True
            else:
                # 会话存在但 Claude 未运行，销毁后重建
                logger.info(f"[ClaudeCodeController] destroying existing session '{self.tmux_session}'...")
                await self.destroy_session()
                await asyncio.sleep(0.5)

        try:
            # 构建启动命令
            # Claude Code 需要以非 root 用户运行，且需要先 cd 到工作目录
            claude_cmd = f"cd {self._workspace} && claude -c --dangerously-skip-permissions"
            if not continue_last:
                claude_cmd = f"cd {self._workspace} && claude --dangerously-skip-permissions"

            # 使用 su 切换到指定用户启动 Claude Code
            cmd = f"tmux new-session -d -s {self.tmux_session} 'su - {self._run_user} -c \"{claude_cmd}\"'"

            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=30)

            if result.returncode != 0:
                logger.error(f"[ClaudeCodeController] Failed to create tmux session with Claude Code")
                return False

            logger.info(f"[ClaudeCodeController] Claude Code starting in tmux session '{self.tmux_session}'")

            # 等待 Claude Code 完全启动（最多 120 秒，因为安全确认可能需要较长时间）
            for i in range(120):
                await asyncio.sleep(1)

                # 先处理安全确认
                if await self.check_safety_confirmation():
                    await self.handle_safety_confirmation()

                if await self.check_claude_ready():
                    logger.info(f"[ClaudeCodeController] Claude Code ready after {i+1}s")
                    self._safety_confirmed = True
                    return True

            logger.warning("[ClaudeCodeController] Claude Code may not have started properly (timeout)")
            return False

        except Exception as e:
            logger.error(f"[ClaudeCodeController] Error starting Claude Code: {e}")
            return False

    async def stop_claude_code(self) -> bool:
        """停止 Claude Code CLI（但保留 tmux 会话）

        Returns:
            是否停止成功
        """
        if not await self.check_tmux_session():
            logger.info(f"[ClaudeCodeController] tmux session '{self.tmux_session}' not found")
            return True

        try:
            # 发送 Ctrl+C 停止 Claude Code
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

            logger.info(f"[ClaudeCodeController] Claude Code stopped in session '{self.tmux_session}'")
            return True

        except Exception as e:
            logger.error(f"[ClaudeCodeController] Error stopping Claude Code: {e}")
            return False

    async def destroy_session(self) -> bool:
        """销毁 tmux 会话（停止 Claude Code 并删除会话）

        Returns:
            是否销毁成功
        """
        if not await self.check_tmux_session():
            logger.info(f"[ClaudeCodeController] tmux session '{self.tmux_session}' not found")
            return True

        try:
            # 先停止 Claude Code
            await self.stop_claude_code()

            await asyncio.sleep(0.5)

            # 强制关闭 tmux 会话
            result = await asyncio.create_subprocess_exec(
                "tmux", "kill-session", "-t", self.tmux_session,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(result.communicate(), timeout=10)

            if result.returncode != 0:
                logger.warning(f"[ClaudeCodeController] Failed to kill session")
                return False

            logger.info(f"[ClaudeCodeController] tmux session '{self.tmux_session}' destroyed")
            self._safety_confirmed = False
            return True

        except Exception as e:
            logger.error(f"[ClaudeCodeController] Error destroying session: {e}")
            return False

    async def capture_output(self, lines: int = 500) -> str:
        """捕获 tmux 输出（包括滚动历史）

        Args:
            lines: 捕获的行数（从历史的最后开始）

        Returns:
            捕获的输出
        """
        try:
            # 使用 -S 参数从最后 N 行开始捕获
            result = await asyncio.create_subprocess_exec(
                "tmux", "capture-pane", "-t", self.tmux_session,
                "-S", f"-{lines}", "-p",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=10)

            if result.returncode == 0:
                output = stdout.decode()
                return output

            return ""

        except Exception as e:
            logger.error(f"[ClaudeCodeController] Error capturing output: {e}")
            return ""

    async def get_session_info(self) -> Optional[dict]:
        """获取会话信息

        Returns:
            会话信息字典，如果获取失败则返回 None
        """
        try:
            info = {
                "tmux_session": self.tmux_session,
                "run_user": self._run_user,
                "workspace": self._workspace,
                "tmux_exists": await self.check_tmux_session(),
                "claude_ready": False,
                "generating": False,
            }

            if info["tmux_exists"]:
                info["claude_ready"] = await self.check_claude_ready()
                info["generating"] = await self.is_generating()

            return info
        except Exception as e:
            logger.error(f"[ClaudeCodeController] Error getting session info: {e}")
            return None
