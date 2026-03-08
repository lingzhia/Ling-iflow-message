"""机器人集成模块。

连接企业微信渠道和 iflow CLI，实现消息双向流转。
"""

import asyncio
import logging
import subprocess
from typing import Optional, Dict, Any
from loguru import logger

from .session_manager import SessionManager
from .iflow_controller import IFlowController


class BotIntegration:
    """机器人集成。
    
    功能：
    - 接收企业微信消息
    - 解析命令
    - 调用 iflow CLI
    - 发送回复到企业微信
    """
    
    def __init__(
        self,
        wechat_channel: Any,
        tmux_session: str = "iflow",
        workspace: str = "~/.iflow"
    ):
        """初始化机器人集成。
        
        Args:
            wechat_channel: 企业微信渠道实例
            tmux_session: tmux 会话名称
            workspace: iflow 工作目录
        """
        self.wechat_channel = wechat_channel
        self.tmux_session = tmux_session
        self.workspace = workspace
        
        # 初始化组件
        self.session_manager = SessionManager(workspace)
        self.iflow_controller = IFlowController(tmux_session)
        
        # 命令前缀
        self.COMMAND_PREFIX = "/"
        
        logger.info("[BotIntegration] 初始化完成")
    
    async def handle_message(
        self,
        content: str,
        sender_id: str,
        chat_id: str,
        is_group: bool,
        metadata: Optional[dict] = None
    ) -> None:
        """处理入站消息。
        
        Args:
            content: 消息内容
            sender_id: 发送者 ID
            chat_id: 聊天 ID
            is_group: 是否为群聊
            metadata: 元数据
        """
        try:
            # 解析命令
            parsed = self._parse_command(content)
            
            if not parsed["valid"]:
                await self._send_help(chat_id, is_group)
                return
            
            # 根据命令类型处理
            await self._handle_command(
                chat_id,
                is_group,
                parsed["type"],
                parsed.get("command"),
                parsed.get("args")
            )
            
        except Exception as e:
            logger.error(f"[BotIntegration] 处理消息错误: {e}", exc_info=True)
            await self._send_error(chat_id, is_group, f"处理消息时出错: {e}")
    
    def _parse_command(self, content: str) -> Dict:
        """解析用户消息，提取命令。
        
        Args:
            content: 用户发送的消息
            
        Returns:
            解析结果字典，格式：
            {
                "valid": bool,
                "type": str,
                "command": Optional[str],
                "args": Optional[str]
            }
        """
        trimmed = content.strip()
        
        # 支持的命令格式：
        # /run <命令>  - 执行 iFlow 命令
        # /new - 开始新会话
        # /sessions - 查看历史会话
        # /help - 显示帮助
        # /status - 查看状态
        
        if trimmed.startswith("/run "):
            cmd = trimmed[5:].strip()
            return {"valid": True, "type": "run", "command": cmd}
        
        if trimmed == "/new":
            return {"valid": True, "type": "new"}
        
        if trimmed == "/sessions":
            return {"valid": True, "type": "sessions"}
        
        if trimmed == "/help":
            return {"valid": True, "type": "help"}
        
        if trimmed == "/status":
            return {"valid": True, "type": "status"}
        
        # 直接发送命令（不带前缀）
        if trimmed and not trimmed.startswith("/"):
            return {"valid": True, "type": "run", "command": trimmed}
        
        return {"valid": False, "type": "unknown"}
    
    async def _handle_command(
        self,
        chat_id: str,
        is_group: bool,
        cmd_type: str,
        command: Optional[str] = None,
        args: Optional[str] = None
    ) -> None:
        """处理命令。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
            cmd_type: 命令类型
            command: 命令内容（仅 run 类型）
            args: 命令参数
        """
        if cmd_type == "help":
            await self._send_help(chat_id, is_group)
        
        elif cmd_type == "status":
            await self._send_status(chat_id, is_group)
        
        elif cmd_type == "new":
            await self._create_new_session(chat_id, is_group)
        
        elif cmd_type == "sessions":
            await self._send_sessions(chat_id, is_group)
        
        elif cmd_type == "run":
            await self._run_command(chat_id, is_group, command)
        
        else:
            await self._send_help(chat_id, is_group)
    
    async def _send_help(self, chat_id: str, is_group: bool) -> None:
        """发送帮助信息。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        help_message = """**iFlow 企业微信助手** 🤖

*支持连续对话，自动保持上下文*

可用命令：
- 直接发送消息：执行 iFlow 命令（自动恢复上次会话）
- `/run <命令>`：执行 iFlow 命令
- `/new`：开始新会话（清除上下文）
- `/sessions`：查看历史会话
- `/status`：查看服务状态
- `/help`：显示此帮助

💡 提示：默认会自动恢复最近的会话，保持对话连续性。如需重新开始，请使用 `/new` 命令。

示例：
```
帮我写一个 Python 脚本
再帮我添加一个函数
继续完善这个脚本
```
"""
        await self.wechat_channel.send(help_message, chat_id, is_group=is_group)
    
    async def _send_status(self, chat_id: str, is_group: bool) -> None:
        """发送状态信息。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        # 检查 iflow 状态
        session_info = self.iflow_controller.get_session_info()
        
        status_message = f"""**iFlow 服务状态** 📊

- iflow 运行: {'是' if session_info['iflow_running'] else '否'}
- tmux 会话: {session_info['tmux_session']}
- tmux 存在: {'是' if session_info['tmux_exists'] else '否'}

"""
        
        # 添加会话信息
        status_message += self.session_manager.get_status_message()
        
        await self.wechat_channel.send(status_message, chat_id, is_group=is_group)
    
    async def _create_new_session(self, chat_id: str, is_group: bool) -> None:
        """创建新会话。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        result = self.session_manager.create_new_session()
        
        message = f"✅ {result['message']}"
        await self.wechat_channel.send(message, chat_id, is_group=is_group)
    
    async def _send_sessions(self, chat_id: str, is_group: bool) -> None:
        """发送会话列表。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        message = self.session_manager.get_sessions_message()
        await self.wechat_channel.send(message, chat_id, is_group=is_group)
    
    async def _run_command(self, chat_id: str, is_group: bool, command: str) -> None:
        """运行 iFlow 命令。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
            command: 要执行的命令
        """
        if not command:
            await self.wechat_channel.send("❌ 命令不能为空", chat_id, is_group=is_group)
            return
        
        # 检查 iflow 是否运行
        if not self.iflow_controller.check_tmux_session():
            await self.wechat_channel.send(
                "❌ iflow 未运行，请先启动 iflow: tmux new-session -d -s iflow \"iflow --model kimi-k2.5\"",
                chat_id,
                is_group=is_group
            )
            return
        
        # 发送正在处理消息
        await self.wechat_channel.send(
            f"⏳ 正在执行: {command}",
            chat_id,
            is_group=is_group
        )
        
        try:
            # 发送命令到 iflow
            success = self.iflow_controller.send_message(command)
            
            if not success:
                await self.wechat_channel.send(
                    "❌ 命令发送失败",
                    chat_id,
                    is_group=is_group
                )
                return
            
            # 等待 iflow 处理
            await asyncio.sleep(3)
            
            # 提取回复
            # 获取发送前的回复（作为基准）
            initial_reply = self._extract_reply_from_tmux()
            
            # 等待回复稳定
            last_reply = ""
            stable_count = 0
            max_stable_checks = 3
            timeout = 60  # 60 秒超时
            
            for i in range(timeout):
                await asyncio.sleep(1)
                
                tmux_reply = self._extract_reply_from_tmux()
                
                # 如果有回复，并且与初始回复不同
                if tmux_reply and tmux_reply != initial_reply:
                    if tmux_reply != last_reply:
                        # 新回复
                        last_reply = tmux_reply
                        stable_count = 0
                    else:
                        # 回复稳定
                        stable_count += 1
                        
                        # 如果回复稳定了多次，认为完成
                        if stable_count >= max_stable_checks:
                            break
            
            # 发送回复
            if last_reply and last_reply != initial_reply:
                # 分段发送（避免超过长度限制）
                chunks = self._split_message(last_reply)
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        await asyncio.sleep(0.5)
                    await self.wechat_channel.send(chunk, chat_id, is_group=is_group)
            else:
                await self.wechat_channel.send(
                    "⚠️ 未收到 iflow 的回复",
                    chat_id,
                    is_group=is_group
                )
            
        except Exception as e:
            logger.error(f"[BotIntegration] 运行命令错误: {e}", exc_info=True)
            await self.wechat_channel.send(
                f"❌ 执行命令时出错: {e}",
                chat_id,
                is_group=is_group
            )
    
    def _extract_reply_from_tmux(self) -> str:
        """从 tmux 输出中提取最终回复。
        
        Returns:
            提取到的回复内容
        """
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", self.tmux_session, "-p"],
                capture_output=True,
                text=True
            )
            
            output = result.stdout
            lines = output.split('\n')
            
            reply_lines = []
            
            # 查找最后一个"✦"行（最新的回复）
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                
                if '✦' in line and '✻' not in line and '✹' not in line:
                    # 从"✦"行开始提取，直到遇到分隔线或命令提示
                    for j in range(i, len(lines)):
                        curr_line = lines[j]
                        
                        # 如果遇到分隔线，停止
                        if '─' * 10 in curr_line:
                            break
                        
                        # 如果遇到新的命令提示，停止
                        if '>' in curr_line and '输入消息' in curr_line:
                            break
                        
                        # 处理内容行
                        curr_line_stripped = curr_line.strip()
                        if curr_line_stripped:
                            # 去掉"✦"符号
                            clean_line = curr_line_stripped.replace('✦', '').strip()
                            if clean_line:
                                reply_lines.append(clean_line)
                    
                    break
            
            # 去掉末尾的空行和分隔线
            while reply_lines and (not reply_lines[-1].strip() or '─' * 5 in reply_lines[-1]):
                reply_lines.pop()
            
            return '\n'.join(reply_lines)
        except Exception as e:
            logger.error(f"[BotIntegration] 提取 tmux 回复失败: {e}")
            return ""
    
    def _split_message(self, message: str, max_length: int = 4096) -> list:
        """分段消息（避免超过长度限制）。
        
        Args:
            message: 要分段的消息
            max_length: 每段最大长度
            
        Returns:
            分段后的消息列表
        """
        if len(message) <= max_length:
            return [message]
        
        chunks = []
        current = ""
        
        for line in message.split('\n'):
            if len(current) + len(line) + 1 <= max_length:
                current += line + '\n'
            else:
                if current:
                    chunks.append(current.rstrip())
                current = line + '\n'
        
        if current:
            chunks.append(current.rstrip())
        
        return chunks
    
    async def _send_error(self, chat_id: str, is_group: bool, error_message: str) -> None:
        """发送错误消息。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
            error_message: 错误消息
        """
        message = f"❌ {error_message}"
        await self.wechat_channel.send(message, chat_id, is_group=is_group)