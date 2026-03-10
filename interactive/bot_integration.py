"""机器人集成模块。

连接企业微信渠道和 iflow CLI，实现消息双向流转。
"""

import asyncio
import logging
import subprocess
from typing import Optional, Dict, Any
from loguru import logger
from .message_dispatcher import MessageDispatcher

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
        workspace: str = "~/.iflow",
        filter_thinking: bool = True,
        extract_all_messages: bool = False
    ):
        """初始化机器人集成。

        Args:
            wechat_channel: 企业微信渠道实例
            tmux_session: tmux 会话名称
            workspace: iflow 工作目录
            filter_thinking: 是否过滤思考消息
            extract_all_messages: 是否提取全部消息（包括非✦标记的消息）
        """
        self.wechat_channel = wechat_channel
        self.tmux_session = tmux_session
        self.workspace = workspace
        self.filter_thinking = filter_thinking
        self.extract_all_messages = extract_all_messages

        # 初始化组件
        self.session_manager = SessionManager(workspace)

        # 消息缓冲区（用于延迟发送）
        self._message_buffer: Dict[str, str] = {}  # {marker: content}
        self._sent_marker_ids: set = set()  # 已发送的消息标识（前10字符）
        self._wechat_message_markers: set = set()  # 由企业微信请求触发的消息标记（避免后台监控重复添加前缀）
        self._last_sent_marker_id: str = ""  # 最后发送的消息标识
        self._current_marker: Optional[str] = None  # 当前正在处理的标记
        self._sent_message_hashes: set = set()  # 已发送的消息哈希（用于去重）
        self._sent_markers: set = set()  # 已发送的标记哈希（用于 fallback 机制）
        self._current_source: str = ""  # 当前正在处理的请求来源（wechat/tool/""）
        self._pending_messages: list = []  # 待处理的未知来源消息
        self._processing_wechat_request: bool = False  # 是否正在处理企业微信请求（标志，避免后台监控重复发送）
        self.iflow_controller = IFlowController(tmux_session)
        
        # 命令前缀
        self.COMMAND_PREFIX = "/"
        
        logger.info(
            f"[BotIntegration] 初始化完成 "
            f"(tmux_session={self.tmux_session}, workspace={self.workspace})"
        )
    
    async def handle_message(
        self,
        content: str,
        sender_id: str,
        chat_id: str,
        is_group: bool,
        metadata: Optional[dict] = None,
        source: str = "wechat"  # 新增参数：消息来源
    ) -> None:
        """处理入站消息。

        Args:
            content: 消息内容
            sender_id: 发送者 ID
            chat_id: 聊天 ID
            is_group: 是否为群聊
            metadata: 元数据
            source: 消息来源（wechat/tool）
        """
        try:
            # 解析命令
            parsed = self._parse_command(content)
            
            if not parsed["valid"]:
                await self._send_help(chat_id, is_group)
                return
            
            # 根据命令类型处理
            logger.info(f"[BotIntegration] 处理命令: type={parsed['type']}, command={parsed.get('command', '')[:50]}")
            await self._handle_command(
                chat_id,
                is_group,
                parsed["type"],
                parsed.get("command"),
                parsed.get("args"),
                source
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
        # /lscmd - 列出所有可用命令
        # /start-iflow - 启动 iflow CLI
        # /stop-iflow - 停止 iflow CLI
        # /restart-iflow - 重启 iflow CLI
        
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
        
        if trimmed == "/start-iflow":
            return {"valid": True, "type": "start-iflow"}
        
        if trimmed == "/stop-iflow":
            return {"valid": True, "type": "stop-iflow"}
        
        if trimmed == "/restart-iflow":
            return {"valid": True, "type": "restart-iflow"}
        
        if trimmed == "/lscmd":
            return {"valid": True, "type": "lscmd"}
        
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
        args: Optional[str] = None,
        source: str = "wechat"  # 新增参数：消息来源
    ) -> None:
        """处理命令。

        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
            cmd_type: 命令类型
            command: 命令内容（仅 run 类型）
            args: 命令参数
            source: 消息来源（wechat/tool）
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
            await self._run_command(chat_id, is_group, command, source)
        
        elif cmd_type == "start-iflow":
            await self._start_iflow(chat_id, is_group)
        
        elif cmd_type == "stop-iflow":
            await self._stop_iflow(chat_id, is_group)
        
        elif cmd_type == "restart-iflow":
            await self._restart_iflow(chat_id, is_group)
        
        elif cmd_type == "lscmd":
            await self._list_commands(chat_id, is_group)
        
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

**iflow 管理命令：**
- `/start-iflow`：启动 iflow CLI
- `/stop-iflow`：停止 iflow CLI
- `/restart-iflow`：重启 iflow CLI

**帮助命令：**
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
    
    async def _list_commands(self, chat_id: str, is_group: bool) -> None:
        """列出所有可用命令。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        # 检查 iflow 状态
        session_info = self.iflow_controller.get_session_info()
        iflow_running = session_info.get('iflow_running', False) if session_info else False
        
        commands_message = """**📋 iFlow 企业微信机器人 - 可用命令**

**基础命令：**
• 直接发送消息：执行 iFlow 命令（自动恢复上次会话）
• `/run <命令>`：执行 iFlow 命令
• `/new`：开始新会话（清除上下文）

**查询命令：**
• `/status`：查看服务状态（tmux、iflow 运行状态）
• `/sessions`：查看历史会话列表
• `/lscmd`：列出所有可用命令（本命令）

**iflow 管理命令：**
• `/start-iflow`：启动 iflow CLI""" + ("" if iflow_running else "（推荐）") + """
• `/stop-iflow`：停止 iflow CLI
• `/restart-iflow`：重启 iflow CLI

**帮助命令：**
• `/help`：显示详细帮助信息

---
💡 提示：
• """ + ("iflow 已运行，可以直接发送命令使用" if iflow_running else "iflow 未运行，请先使用 `/start-iflow` 启动") + """
• 默认会自动恢复最近的会话，保持对话连续性
• 如需重新开始，请使用 `/new` 命令

示例：
```
""" + ("帮我写一个 Python 脚本" if iflow_running else "/start-iflow") + """
继续完善这个脚本
```
"""
        await self.wechat_channel.send(commands_message, chat_id, is_group=is_group)
    
    async def _start_iflow(self, chat_id: str, is_group: bool) -> None:
        """启动 iflow CLI。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        logger.info(f"[BotIntegration] 收到启动 iflow 请求")
        
        # 检查 iflow 是否已经在运行
        session_info = self.iflow_controller.get_session_info()
        if session_info and session_info.get('iflow_running', False):
            message = "✅ iflow 已经在运行中"
            await self.wechat_channel.send(message, chat_id, is_group=is_group)
            return
        
        # 尝试启动 iflow
        logger.info(f"[BotIntegration] 正在启动 iflow...")
        await self.wechat_channel.send("⏳ 正在启动 iflow，请稍候...", chat_id, is_group=is_group)
        
        success = self.iflow_controller.start_iflow(model="kimi-k2.5")
        
        if success:
            # 等待 iflow 完全启动
            await asyncio.sleep(3)
            
            # 验证 iflow 是否真的启动了
            session_info = self.iflow_controller.get_session_info()
            if session_info and session_info.get('iflow_running', False):
                message = "✅ iflow 启动成功！现在可以开始使用了"
                await self.wechat_channel.send(message, chat_id, is_group=is_group)
                logger.info(f"[BotIntegration] iflow 启动成功")
            else:
                message = "⚠️ iflow 启动失败，请检查日志"
                await self.wechat_channel.send(message, chat_id, is_group=is_group)
                logger.error(f"[BotIntegration] iflow 启动验证失败")
        else:
            message = "❌ iflow 启动失败，请检查服务器日志"
            await self.wechat_channel.send(message, chat_id, is_group=is_group)
            logger.error(f"[BotIntegration] iflow 启动失败")
    
    async def _stop_iflow(self, chat_id: str, is_group: bool) -> None:
        """停止 iflow CLI。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        logger.info(f"[BotIntegration] 收到停止 iflow 请求")
        
        # 检查 iflow 是否在运行
        session_info = self.iflow_controller.get_session_info()
        if not session_info or not session_info.get('tmux_exists', False):
            message = "✅ iflow 未运行，无需停止"
            await self.wechat_channel.send(message, chat_id, is_group=is_group)
            return
        
        # 尝试停止 iflow
        logger.info(f"[BotIntegration] 正在停止 iflow...")
        await self.wechat_channel.send("⏳ 正在停止 iflow，请稍候...", chat_id, is_group=is_group)
        
        success = self.iflow_controller.stop_iflow()
        
        if success:
            # 等待 iflow 完全停止
            await asyncio.sleep(2)
            
            # 验证 iflow 是否真的停止了
            session_info = self.iflow_controller.get_session_info()
            if not session_info or not session_info.get('tmux_exists', False):
                message = "✅ iflow 已停止"
                await self.wechat_channel.send(message, chat_id, is_group=is_group)
                logger.info(f"[BotIntegration] iflow 停止成功")
            else:
                message = "⚠️ iflow 停止失败，请检查日志"
                await self.wechat_channel.send(message, chat_id, is_group=is_group)
                logger.error(f"[BotIntegration] iflow 停止验证失败")
        else:
            message = "❌ iflow 停止失败，请检查服务器日志"
            await self.wechat_channel.send(message, chat_id, is_group=is_group)
            logger.error(f"[BotIntegration] iflow 停止失败")
    
    async def _restart_iflow(self, chat_id: str, is_group: bool) -> None:
        """重启 iflow CLI。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        logger.info(f"[BotIntegration] 收到重启 iflow 请求")
        
        # 先停止 iflow（如果正在运行）
        session_info = self.iflow_controller.get_session_info()
        if session_info and session_info.get('tmux_exists', False):
            logger.info(f"[BotIntegration] 正在停止 iflow...")
            await self.wechat_channel.send("⏳ 正在停止 iflow，请稍候...", chat_id, is_group=is_group)
            
            success = self.iflow_controller.stop_iflow()
            if not success:
                message = "❌ iflow 停止失败，无法重启"
                await self.wechat_channel.send(message, chat_id, is_group=is_group)
                logger.error(f"[BotIntegration] iflow 停止失败，无法重启")
                return
            
            # 等待 iflow 完全停止
            await asyncio.sleep(2)
        
        # 启动 iflow
        logger.info(f"[BotIntegration] 正在启动 iflow...")
        await self.wechat_channel.send("⏳ 正在启动 iflow，请稍候...", chat_id, is_group=is_group)
        
        success = self.iflow_controller.start_iflow(model="kimi-k2.5")
        
        if success:
            # 等待 iflow 完全启动
            await asyncio.sleep(3)
            
            # 验证 iflow 是否真的启动了
            session_info = self.iflow_controller.get_session_info()
            if session_info and session_info.get('iflow_running', False):
                message = "✅ iflow 重启成功！现在可以开始使用了"
                await self.wechat_channel.send(message, chat_id, is_group=is_group)
                logger.info(f"[BotIntegration] iflow 重启成功")
            else:
                message = "⚠️ iflow 重启失败，请检查日志"
                await self.wechat_channel.send(message, chat_id, is_group=is_group)
                logger.error(f"[BotIntegration] iflow 重启验证失败")
        else:
            message = "❌ iflow 重启失败，请检查服务器日志"
            await self.wechat_channel.send(message, chat_id, is_group=is_group)
            logger.error(f"[BotIntegration] iflow 重启失败")
    
    async def _send_sessions(self, chat_id: str, is_group: bool) -> None:
        """发送会话列表。
        
        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        message = self.session_manager.get_sessions_message()
        await self.wechat_channel.send(message, chat_id, is_group=is_group)
    
    async def _run_command(self, chat_id: str, is_group: bool, command: str, source: str = "wechat") -> None:
        """运行 iFlow 命令（基于标记的延迟发送版本）。

        Args:
            chat_id: 聊天 ID
            is_group: 是否为群聊
            command: 要执行的命令
            source: 消息来源（wechat/tool）
        """
        logger.info(f"[BotIntegration] 执行命令: chat_id={chat_id}, is_group={is_group}, command={command[:100]}, source={source}")

        # 设置当前来源
        self._current_source = source

        # 设置企业微信请求处理标志（避免后台监控重复发送）
        if source == "wechat":
            self._processing_wechat_request = True
            logger.info(f"[BotIntegration] 设置企业微信请求处理标志为 True")

        if not command:
            logger.warning("[BotIntegration] 命令为空")
            await self.wechat_channel.send("❌ 命令不能为空", chat_id, is_group=is_group)
            return

        # 检查 iflow 是否运行
        if not self.iflow_controller.check_tmux_session():
            logger.error(f"[BotIntegration] iflow 未运行，tmux_session={self.tmux_session}")
            await self.wechat_channel.send(
                "❌ iflow 未运行\n\n请使用以下命令启动服务：\n"
                "python manage.py start\n\n"
                "或者只启动 iflow：\n"
                "python manage.py start --no-wechat",
                chat_id,
                is_group=is_group
            )
            return

        try:
            # 在发送命令之前，先提取初始回复（作为基准）
            logger.debug(f"[BotIntegration] 获取发送前的初始回复")
            initial_messages, initial_generating, generation_time, _ = self._extract_reply_from_tmux()
            initial_count = len(initial_messages)
            logger.debug(f"[BotIntegration] 初始回复数量: {initial_count}, 生成中: {initial_generating}")

            # 如果 iflow 正在生成，等待完成
            if initial_generating:
                logger.info(f"[BotIntegration] iflow 正在生成中，等待完成...")
                await asyncio.sleep(2)
                initial_messages, initial_generating, generation_time, _ = self._extract_reply_from_tmux()
                initial_count = len(initial_messages)
                logger.debug(f"[BotIntegration] 等待后初始回复数量: {initial_count}, 生成中: {initial_generating}")

            # 检查 iflow 是否正在生成中
            if initial_generating:
                logger.warning(f"[BotIntegration] iflow 正在生成中，无法发送新消息")
                generation_time_msg = f" ({generation_time})" if generation_time else ""
                await self.wechat_channel.send(
                    f"⚠️ 当前正在生成中{generation_time_msg}，请稍后再试",
                    chat_id,
                    is_group=is_group
                )
                return

            # 发送命令到 iflow
            logger.info(f"[BotIntegration] 发送命令到 iflow: {command}")
            success = self.iflow_controller.send_message(command)

            if not success:
                logger.error(f"[BotIntegration] 命令发送失败")
                await self.wechat_channel.send(
                    "❌ 命令发送失败",
                    chat_id,
                    is_group=is_group
                )
                return

            logger.info(f"[BotIntegration] 命令发送成功，等待 iflow 处理")
            # 等待 iflow 处理
            await asyncio.sleep(3)

            # 重置缓冲区
            self._message_buffer.clear()
            self._sent_marker_ids.clear()
            self._last_sent_marker_id = ""
            self._current_marker = None
            self._sent_message_hashes.clear()
            self._sent_markers.clear()

            # 记录初始消息的标识，避免发送旧消息
            for message in initial_messages:
                marker_id = message.get('marker_id', '')
                if marker_id:
                    self._sent_marker_ids.add(marker_id)
                    # 同时添加到企业微信消息标记集合，避免后台监控误判为 iflow 交互界面消息
                    self._wechat_message_markers.add(marker_id)
                    logger.debug(f"[BotIntegration] 标记初始消息为已发送: {marker_id}")
            
            # 设置最后发送的标记（用于后续发送逻辑）
            if initial_messages:
                self._last_sent_marker_id = initial_messages[-1].get('marker_id', '')
                logger.info(f"[BotIntegration] 设置最后发送的标记: {self._last_sent_marker_id}")

            last_message_count = initial_count
            last_generating = False
            self._stable_count = 0

            # 实时监控并发送新消息
            max_timeout = 600  # 最大超时时间 10 分钟（绝对超时保险）
            loop_count = 0

            logger.info(f"[BotIntegration] 开始实时监控 iflow 回复，最大超时: {max_timeout}秒")

            while True:
                # 检查绝对超时
                if loop_count * 0.5 >= max_timeout:
                    logger.warning(f"[BotIntegration] 超时 ({max_timeout}秒)，停止监控")
                    break

                await asyncio.sleep(0.5)
                loop_count += 1

                # 获取当前回复和生成状态
                current_messages, is_generating, generation_time, _ = self._extract_reply_from_tmux()
                current_count = len(current_messages)

                # 检查是否在生成中
                if is_generating:
                    logger.debug(f"[BotIntegration] iflow 正在生成中... (时间: {generation_time})")
                    last_generating = True
                    self._stable_count = 0
                    continue

                # 检测生成完成
                if last_generating and not is_generating:
                    logger.info(f"[BotIntegration] 检测到生成完成")

                    # 等待一下，确保不会有新消息
                    await asyncio.sleep(1)

                    # 再次检查，确保生成完成
                    final_messages, final_generating, _, _ = self._extract_reply_from_tmux()
                    final_count = len(final_messages)

                    if not final_generating:
                        logger.info(f"[BotIntegration] 确认生成完成，消息数量: {final_count}")
                        
                        # 打印所有消息的标记ID
                        for i, msg in enumerate(final_messages):
                            logger.debug(f"[BotIntegration] 最终消息 {i+1}: marker_id={msg.get('marker_id', '')}, content={msg.get('content', '')[:50]}")
                        
                        # 应用新的发送规则
                        if len(self._sent_marker_ids) == 0:
                            # 场景1：没有发送记录
                            # 生成完成后，发送所有消息（包括最后一条）
                            for i in range(final_count):
                                msg = final_messages[i]
                                marker_id = msg.get('marker_id', '')
                                
                                # 检查消息内容是否为空（清理后）
                                cleaned_content = self._clean_message_content(msg['content'])
                                if not cleaned_content.strip():
                                    logger.debug(f"[BotIntegration] 跳过空消息 {i+1}/{final_count}: 标识={marker_id}")
                                    continue
                                
                                logger.info(f"[BotIntegration] 发送消息 {i+1}/{final_count}: 标识={marker_id}")
                                await self._send_message_content(msg['content'], chat_id, is_group)
                                self._sent_marker_ids.add(marker_id)
                                # 添加到标记集合，避免后台监控误判
                                self._wechat_message_markers.add(marker_id)
                            
                            # 记录最后一个标记
                            if final_count > 0:
                                last_marker_id = final_messages[final_count - 1].get('marker_id', '')
                                self._last_sent_marker_id = last_marker_id
                                logger.info(f"[BotIntegration] 记录最后发送的标记: {last_marker_id}")
                        else:
                            # 场景2：有发送记录
                            if final_count >= 1 and hasattr(self, '_last_sent_marker_id'):
                                # 从 tmux 消息中定位到已发送的消息标识
                                sent_index = -1
                                for i, msg in enumerate(final_messages):
                                    if msg.get('marker_id', '') == self._last_sent_marker_id:
                                        sent_index = i
                                        break
                                
                                # 如果找到已发送的消息，发送其后所有未发送的消息（包括最后一条）
                                if sent_index >= 0:
                                    remaining_count = final_count - sent_index - 1
                                    if remaining_count >= 1:
                                        # 发送所有未发送的消息（sent_index+1 到 final_count-1）
                                        for i in range(sent_index + 1, final_count):
                                            msg = final_messages[i]
                                            marker_id = msg.get('marker_id', '')
                                            
                                            # 检查消息内容是否为空（清理后）
                                            cleaned_content = self._clean_message_content(msg['content'])
                                            if not cleaned_content.strip():
                                                logger.debug(f"[BotIntegration] 跳过空消息 {i+1}/{final_count}: 标识={marker_id}")
                                                continue
                                            
                                            logger.info(f"[BotIntegration] 发送消息 {i+1}/{final_count}: 标识={marker_id}")
                                            await self._send_message_content(msg['content'], chat_id, is_group)
                                            self._sent_marker_ids.add(marker_id)
                                            # 添加到标记集合，避免后台监控检测
                                            self._wechat_message_markers.add(marker_id)
                                        
                                        # 更新最后发送的标记
                                        new_last_marker_id = final_messages[final_count - 1].get('marker_id', '')
                                        self._last_sent_marker_id = new_last_marker_id
                                        logger.info(f"[BotIntegration] 更新最后发送的标记: {new_last_marker_id}")
                                else:
                                    # 未找到已发送的消息（可能是新对话），发送所有消息
                                    logger.warning(f"[BotIntegration] 未找到已发送的消息标识: {self._last_sent_marker_id}，发送所有消息")
                                    for i in range(final_count):
                                        msg = final_messages[i]
                                        marker_id = msg.get('marker_id', '')
                                        
                                        # 检查消息内容是否为空（清理后）
                                        cleaned_content = self._clean_message_content(msg['content'])
                                        if not cleaned_content.strip():
                                            logger.debug(f"[BotIntegration] 跳过空消息 {i+1}/{final_count}: 标识={marker_id}")
                                            continue
                                        
                                        logger.info(f"[BotIntegration] 发送消息 {i+1}/{final_count}: 标识={marker_id}")
                                        await self._send_message_content(msg['content'], chat_id, is_group)
                                        self._sent_marker_ids.add(marker_id)
                                        # 添加到标记集合，避免后台监控检测
                                        self._wechat_message_markers.add(marker_id)
                                    
                                    # 更新最后发送的标记
                                    if final_count > 0:
                                        new_last_marker_id = final_messages[final_count - 1].get('marker_id', '')
                                        self._last_sent_marker_id = new_last_marker_id
                                        logger.info(f"[BotIntegration] 更新最后发送的标记: {new_last_marker_id}")
                        
                        # 发送完成提示
                        completion_message = "✅ 当前问题回答完毕"
                        await self.wechat_channel.send(completion_message, chat_id, is_group=is_group)
                        logger.info(f"[BotIntegration] 已发送回答完毕提示")
                        break
                    else:
                        # 生成中又出现了，继续监控
                        logger.debug(f"[BotIntegration] 生成中又出现，继续监控")
                        last_generating = True

                # 处理新消息（延迟发送逻辑）
                if current_count > last_message_count:
                    logger.info(f"[BotIntegration] 检测到新消息: {last_message_count} -> {current_count}")

                    # 发送新增的消息（从 last_message_count 到 current_count-1）
                    for i in range(last_message_count, current_count):
                        if i < len(current_messages):
                            message_dict = current_messages[i]
                            message = message_dict['content']
                            marker_id = message_dict['marker_id']
                            msg_hash = hash(message.strip())

                            # 根据来源决定是否发送
                            if self._current_source == "tool":
                                # 工具来源：只返回给工具，不发企业微信
                                logger.debug(f"[BotIntegration] 工具来源消息，不发送到企业微信")
                                # 添加到标记集合，避免后台监控检测
                                self._wechat_message_markers.add(marker_id)
                            elif self._current_source == "wechat":
                                # 企业微信来源：逐条发送
                                if msg_hash not in self._sent_message_hashes:
                                    logger.info(f"[BotIntegration] 发送消息 {i+1}: {message[:50]}")
                                    await self._send_message_content(message, chat_id, is_group)
                                    self._sent_message_hashes.add(msg_hash)
                                    # 添加到标记集合，避免后台监控检测
                                    self._wechat_message_markers.add(marker_id)

                # 更新最后的消息计数
                last_message_count = current_count

                # 检测未知来源的消息（iflow 交互界面）
                unknown_messages = []
                for msg in current_messages:
                    marker_id = msg.get('marker_id', '')
                    if marker_id and marker_id not in self._sent_marker_ids:
                        unknown_messages.append(msg)

                if unknown_messages and self._current_source == "":
                    # 没有当前请求来源，判断为 iflow 交互界面的消息
                    logger.info(f"[BotIntegration] 检测到 iflow 交互界面消息，共 {len(unknown_messages)} 条")

                    # 合并所有 ✦ 标记的消息
                    merged_content = self._merge_messages(unknown_messages)

                    # 提取用户提问
                    _, _, _, user_question = self._extract_reply_from_tmux()

                    # 构造开头标记
                    header = f"🔔 iflow交互模式请求：原消息=[{user_question}]，当前回复完成，回复结果如下：\n\n"
                    # 合并开头标记和内容
                    full_message = header + merged_content

                    # 使用消息分发器广播消息到所有订阅者
                    dispatcher = MessageDispatcher()
                    await dispatcher.broadcast(
                        full_message,
                        {
                            "source": "iflow_interactive",
                            "tmux_session": self.tmux_session,
                            "workspace": self.workspace,
                            "user_question": user_question,
                            "message_count": len(unknown_messages)
                        }
                    )
                    logger.info(
                        f"[BotIntegration] 已通过分发器发送 iflow 交互界面消息 "
                        f"(tmux: {self.tmux_session}, workspace: {self.workspace})"
                    )

                    # 标记为已发送
                    for msg in unknown_messages:
                        marker_id = msg.get('marker_id', '')
                        if marker_id:
                            self._sent_marker_ids.add(marker_id)

                # 如果从来没有检测到"生成中"，使用稳定检测作为 fallback
                if not last_generating and current_count == last_message_count:
                    # 消息数量稳定（fallback 机制）
                    logger.debug(f"[BotIntegration] 消息数量稳定（未检测到生成中）")

                    # 增加稳定计数
                    self._stable_count += 1

                    # 如果连续 3 秒稳定，认为完成
                    if self._stable_count >= 3:
                        logger.info(f"[BotIntegration] 回复完成（消息数量稳定且无生成中）")

                        # 发送最后一个消息
                        if current_messages:
                            last_message_dict = current_messages[-1]
                            last_message = last_message_dict['content']
                            last_marker_hash = hash(last_message.strip())

                            if last_marker_hash not in self._sent_markers:
                                logger.info(f"[BotIntegration] 发送最后一个消息: {last_message[:50]}")
                                await self._send_message_content(last_message, chat_id, is_group)
                                self._sent_markers.add(last_marker_hash)

                        # 回复完成，退出循环（不发送"回答完毕"提示）
                        logger.info(f"[BotIntegration] 回复完成，退出等待")
                        # 重置计数器
                        self._stable_count = 0
                        break

        except Exception as e:
            logger.error(f"[BotIntegration] 运行命令错误: {e}", exc_info=True)
            await self.wechat_channel.send(
                f"❌ 执行命令时出错: {e}",
                chat_id,
                is_group=is_group
            )
        finally:
            # 清理当前来源
            self._current_source = ""
            
            # 清理企业微信请求处理标志（延迟清理，确保实时监控的消息已经发送）
            if self._processing_wechat_request:
                logger.info(f"[BotIntegration] 延迟清理企业微信请求处理标志，等待 5 秒...")
                await asyncio.sleep(5)
                
                # 检查后台监控是否已经检测到了消息
                # 如果检测到了，就清理标志；如果没有检测到，就不清理标志
                current_messages, _, _, _ = self._extract_reply_from_tmux()
                if len(current_messages) > 0:
                    logger.info(f"[BotIntegration] 后台监控已检测到 {len(current_messages)} 条消息，清理标志")
                    self._processing_wechat_request = False
                    logger.info(f"[BotIntegration] 已清理企业微信请求处理标志，设置为 False")
                else:
                    logger.warning(f"[BotIntegration] 后台监控未检测到消息，不清理标志，继续等待后台监控处理")

    def _clean_message_content(self, content: str) -> str:
        """清理消息内容，去除 iflow 的 UI 元素。

        Args:
            content: 原始消息内容

        Returns:
            清理后的消息内容
        """
        if not content:
            return content

        # 类型检查：确保 content 是字符串
        if not isinstance(content, str):
            logger.error(f"[BotIntegration] _clean_message_content 收到非字符串类型: {type(content)}, 值: {content}")
            # 尝试转换为字符串
            try:
                content = str(content)
            except Exception as e:
                logger.error(f"[BotIntegration] 无法转换为字符串: {e}")
                return ''

        # 查找分隔符（虚线、横线等）
        separators = [
            '---',
            '══',
            '────────',
            '────────────────',
            '════════════════',
            '══════════════════════════',
            '══════════════════════════════════════',
            '══════════════════════════════════════════════════',
            '══════════════════════════════════════════════════════════════',
            '══════════════════════════════════════════════════════════════════════════',
        ]

        # 找到第一个分隔符的位置
        first_separator_pos = -1
        for sep in separators:
            pos = content.find(sep)
            if pos != -1 and (first_separator_pos == -1 or pos < first_separator_pos):
                first_separator_pos = pos

        # 如果找到分隔符，只保留之前的内容
        if first_separator_pos != -1:
            cleaned_content = content[:first_separator_pos].strip()
            logger.debug(f"[BotIntegration] 清理消息：移除 {len(content) - len(cleaned_content)} 个字符")
            return cleaned_content

        return content.strip()

    async def _send_message_content(self, content: str, chat_id: str, is_group: bool) -> None:
        """发送消息内容（包含过滤和分段）。

        Args:
            content: 消息内容
            chat_id: 聊天 ID
            is_group: 是否为群聊
        """
        # 清理消息内容，去除 iflow 的 UI 元素
        cleaned_content = self._clean_message_content(content)
        
        # 根据配置过滤思考消息
        if self.filter_thinking:
            filtered_message = self._filter_thinking_messages(cleaned_content)
            logger.info(f"[BotIntegration] 消息过滤后长度: {len(filtered_message)}")
        else:
            filtered_message = cleaned_content

        if filtered_message.strip():
            # 分段发送（避免超过长度限制）
            chunks = self._split_message(filtered_message)
            logger.info(f"[BotIntegration] 消息分段发送，共 {len(chunks)} 段")

            for k, chunk in enumerate(chunks):
                if k > 0:
                    await asyncio.sleep(0.3)
                # 打印发送到企业微信的消息内容
                logger.info(
                    f"[BotIntegration] 发送消息到企业微信 (第{k+1}/{len(chunks)}段)\n"
                    f"  接收者: {chat_id}\n"
                    f"  类型: {'群聊' if is_group else '私聊'}\n"
                    f"  消息内容: {chunk}"
                )
                await self.wechat_channel.send(chunk, chat_id, is_group=is_group)
    
    def _extract_reply_from_tmux(self) -> tuple:
        """从 tmux 输出中提取回复和生成状态（基于标记的改进版）。
        
        改进版逻辑：
        1. 捕获最后300行 tmux 输出
        2. 扫描用户提问，定位当前对话范围
        3. 提取标记消息，前10字符作为唯一标识
        4. 绑定标记之间的内容作为消息扩展
        
        Returns:
            (messages: list, is_generating: bool, generation_time: str)
            - messages: 提取到的回复列表，每个元素为字典 {'marker_id': str, 'content': str, 'full_marker': str}
            - is_generating: 是否正在生成中
            - generation_time: 生成时间记录（如果有）
        """
        
        try:
            # 捕获最后1000行 tmux 输出
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", self.tmux_session, "-S", "-1000", "-p"],
                capture_output=True,
                text=True
            )
            
            output = result.stdout
            lines = output.split('\n')
            
            messages = []
            is_generating = False
            generation_time = None
            
            # 步骤1：扫描用户提问，定位当前对话范围（找到最后一个用户提问）
            current_conversation_start = 0
            user_question = ""  # 用户问题
            for i in range(len(lines) - 1, -1, -1):
                line_stripped = lines[i].strip()
                # 检查是否是用户提问（以 > 开头，并且不是输入提示符）
                if line_stripped.startswith('>') and len(line_stripped) > 1:
                    # 跳过输入提示符
                    if line_stripped == '>   输入消息或@文件路径':
                        continue
                    current_conversation_start = i
                    # 提取用户问题（移除 > 前缀和空白字符）
                    user_question = lines[i].strip()[1:].strip()
                    logger.debug(f"[BotIntegration] 找到最后一个用户提问，从第{i+1}行开始: {user_question}")
                    break
            
            # 只处理当前对话范围
            conversation_lines = lines[current_conversation_start:]
            
            # 步骤2：提取标记消息并绑定扩展内容
            current_message = []
            current_marker = None
            current_marker_id = None
            
            # 先检测生成中状态（只检查最后 10 行）
            for line in lines[-10:]:
                line_stripped = line.strip()
                # 检测"生成中"标记
                if '生成中' in line_stripped:
                    import re
                    time_match = re.search(r'(\d+)s', line_stripped)
                    if time_match:
                        is_generating = True
                        generation_time = time_match.group(1) + 's'
                        logger.debug(f"[BotIntegration] 检测到生成中: {generation_time}")
                        break
                # 检测"思考中"标记（✻）
                if '✻' in line_stripped:
                    is_generating = True
                    generation_time = 'thinking'
                    logger.debug(f"[BotIntegration] 检测到思考中标记")
                    break
            
            # 提取标记消息
            for line in conversation_lines:
                # 检测标记
                marker = self._detect_marker(line)
                
                if marker:
                    # 保存前一条消息（如果有）
                    if current_marker and current_message:
                        messages.append({
                            'marker_id': current_marker_id,
                            'content': '\n'.join(current_message),
                            'full_marker': current_marker
                        })
                    
                    # 开始新消息
                    current_marker = line.strip()
                    # 使用完整内容作为唯一标识（避免前10字符重复的问题）
                    clean_marker = line.replace('✦', '').replace('✻', '').strip()
                    current_marker_id = clean_marker if clean_marker else ''
                    current_message = [line.strip()]
                    
                    logger.debug(f"[BotIntegration] 检测到标记: {marker}, 标识: {current_marker_id}")
                elif current_marker:
                    # 收集当前消息的扩展内容
                    current_message.append(line.strip())
            
            # 保存最后一条消息（如果有）
            if current_marker and current_message:
                messages.append({
                    'marker_id': current_marker_id,
                    'content': '\n'.join(current_message),
                    'full_marker': current_marker
                })
                logger.debug(f"[BotIntegration] 提取最后一条消息: 标识={current_marker_id}")
            
            # 根据配置过滤消息
            filtered_messages = []
            for msg in messages:
                if self.extract_all_messages:
                    # 返回所有标记的消息
                    filtered_messages.append(msg)
                else:
                    # 只返回 ✦ 标记的消息
                    if '✦' in msg['full_marker'] and '✻' not in msg['full_marker']:
                        # 清理 ✦ 符号和 UI 元素
                        clean_content = self._clean_message_content(msg['content'].replace('✦', '').strip())
                        if clean_content:
                            filtered_messages.append({
                                'marker_id': msg['marker_id'],
                                'content': clean_content,
                                'full_marker': msg['full_marker']
                            })
            
            logger.debug(f"[BotIntegration] 提取完成，共 {len(messages)} 条消息，过滤后 {len(filtered_messages)} 条，生成中: {is_generating}")

            # 验证所有消息的 content 都是字符串
            for i, msg in enumerate(filtered_messages):
                if not isinstance(msg.get('content'), str):
                    logger.error(f"[BotIntegration] 消息 {i+1} 的 content 不是字符串: type={type(msg.get('content'))}, value={msg.get('content')}")
                    # 尝试转换为字符串
                    try:
                        msg['content'] = str(msg['content'])
                    except Exception as e:
                        logger.error(f"[BotIntegration] 无法转换消息 {i+1} 的 content 为字符串: {e}")

            return filtered_messages, is_generating, generation_time, user_question
            
        except Exception as e:
            logger.error(f"[BotIntegration] 提取 tmux 回复失败: {e}")
            return [], False, None
    def _detect_marker(self, line: str) -> str:
        """检测行中的标记类型。

        Args:
            line: 要检测的行

        Returns:
            标记类型（'✦' 或 '✻'），如果没有标记返回 None
        """
        curr_line_stripped = line.strip()

        # 排除用户输入和状态栏
        if curr_line_stripped.startswith('>') or curr_line_stripped.count('|') >= 2:
            return None

        # 检测 ✻ 标记（思考、工具调用等）
        if '✻' in curr_line_stripped and '✹' not in curr_line_stripped:
            return '✻'

        # 检测 ✦ 标记（实际回复）
        if '✦' in curr_line_stripped and '✻' not in curr_line_stripped and '✹' not in curr_line_stripped:
            return '✦'

        return None
    
    def _filter_thinking_messages(self, message: str) -> str:
        """过滤思考消息（以 * 开头的行）。
        
        Args:
            message: 原始消息
            
        Returns:
            过滤后的消息
        """
        lines = message.split('\n')
        filtered_lines = []
        
        for line in lines:
            # 过滤掉以 * 开头的行（思考消息）
            stripped = line.strip()
            if stripped.startswith('*'):
                continue
            filtered_lines.append(line)
        
        # 去掉多余的空行
        result = '\n'.join(filtered_lines)
        result = '\n'.join(line for line in result.split('\n') if line.strip())
        
        return result
    
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

    def _merge_messages(self, messages: list) -> str:
        """合并多条消息为一条。

        只合并 ✦ 标记的消息，消息之间直接换行连接。

        Args:
            messages: 消息列表

        Returns:
            合并后的消息
        """
        merged_lines = []

        for msg in messages:
            # 只处理 ✦ 标记的消息
            if '✦' in msg.get('full_marker', '') and '✻' not in msg.get('full_marker', ''):
                content = msg.get('content', '').strip()
                if content:
                    logger.debug(f"[BotIntegration] 使用 content 作为回复内容: {content[:50]}")
                    merged_lines.append(content)
                    continue

        # 直接换行连接，无分隔符
        return '\n'.join(merged_lines)

    async def start_background_monitor(self) -> None:
        """启动后台监控，检测 iflow 交互界面的消息。

        这个方法会在后台持续运行，检测用户在 tmux iflow 中直接输入的消息，
        并将这些消息合并后发送到企业微信。
        """
        logger.info(
            f"[BotIntegration] 启动后台监控 "
            f"(tmux_session={self.tmux_session}, workspace={self.workspace})"
        )
        
        last_known_messages = set()
        
        while True:
            try:
                # 等待一段时间再检查（避免频繁检查）
                await asyncio.sleep(5)
                
                # 提取当前所有消息
                current_messages, is_generating, generation_time, user_question = self._extract_reply_from_tmux()
                
                # 获取当前所有消息的 marker_id
                current_marker_ids = set()
                for msg in current_messages:
                    marker_id = msg.get('marker_id', '')
                    if marker_id:
                        current_marker_ids.add(marker_id)
                
                # 检测新的消息（不在 last_known_messages 中）
                new_messages = []
                for msg in current_messages:
                    marker_id = msg.get('marker_id', '')
                    if marker_id and marker_id not in last_known_messages:
                        # 检查消息是否已经被企业微信请求触发过（避免重复添加前缀）
                        if marker_id in self._wechat_message_markers:
                            logger.debug(f"[BotIntegration] 跳过企业微信消息: {marker_id}（已在企业微信标记中）")
                        else:
                            logger.debug(f"[BotIntegration] 检测到新消息: {marker_id}, 企业微信消息数: {len(self._wechat_message_markers)}")
                            logger.debug(f"[BotIntegration] 企业微信标记集合: {list(self._wechat_message_markers)}")
                            new_messages.append(msg)
                
                # 如果有新消息且不在处理中
                if new_messages and not is_generating and self._current_source == "":
                    logger.info(f"[BotIntegration] 后台监控检测到新消息: {len(new_messages)} 条")
                    logger.info(f"[BotIntegration] 当前来源状态: _current_source='{self._current_source}', _processing_wechat_request={self._processing_wechat_request}")
                    
                    # 合并所有 ✦ 标记的消息
                    merged_content = self._merge_messages(new_messages)
                    
                    if merged_content.strip():
                        # 再次检查所有消息标记，确保不是企业微信消息（双重检查）
                        all_in_wechat_markers = all(
                            msg.get('marker_id', '') in self._wechat_message_markers
                            for msg in new_messages
                        )
                        
                        # 检查是否正在处理企业微信请求
                        is_wechat_request_processing = self._processing_wechat_request
                        
                        if all_in_wechat_markers:
                            logger.info(f"[BotIntegration] 所有消息都在企业微信标记中，跳过后台监控发送")
                            last_known_messages.update(current_marker_ids)
                            continue
                        
                        # 如果正在处理企业微信请求，也不添加前缀
                        if is_wechat_request_processing:
                            logger.info(f"[BotIntegration] 正在处理企业微信请求，分别发送每条消息到企业微信（不添加前缀）")
                            # 分别发送每条消息到企业微信
                            dispatcher = MessageDispatcher()
                            sent_count = 0
                            for msg in new_messages:
                                # 只发送 ✦ 标记的消息
                                if '✦' in msg.get('full_marker', '') and '✻' not in msg.get('full_marker', ''):
                                    content = msg.get('content', '').strip()
                                    if content:
                                        await dispatcher.broadcast(
                                            content,
                                            {
                                                "source": "wechat",
                                                "tmux_session": self.tmux_session,
                                                "workspace": self.workspace,
                                                "user_question": user_question,
                                                "message_count": 1,
                                                "message_index": sent_count + 1
                                            }
                                        )
                                        sent_count += 1
                                        logger.info(f"[BotIntegration] 已发送第 {sent_count} 条消息到企业微信")
                            logger.info(
                                f"[BotIntegration] 已通过分发器发送 {sent_count} 条企业微信请求消息 (tmux: {self.tmux_session}, workspace: {self.workspace})"
                            )
                            last_known_messages.update(current_marker_ids)
                            continue
                        
                        # 打印每条消息的标记状态（调试）
                        for msg in new_messages:
                            marker_id = msg.get('marker_id', '')
                            in_markers = marker_id in self._wechat_message_markers
                            logger.debug(f"[BotIntegration] 消息标记检查: {marker_id} -> in_wechat_markers={in_markers}")
                        
                        # 构造开头标记
                        header = f"🔔 iflow交互模式请求：原消息=[{user_question}]，当前回复完成，回复结果如下：\n\n"
                        # 合并开头标记和内容
                        full_message = header + merged_content
                        
                        # 打印完整的 iflow 回复消息
                        logger.info(
                            f"[BotIntegration] 检测到 iflow 交互界面回复 (后台监控)\n"
                            f"  用户问题: {user_question}\n"
                            f"  消息数量: {len(new_messages)}\n"
                            f"  完整回复: {full_message}"
                        )
                        
                        # 使用消息分发器广播消息
                        dispatcher = MessageDispatcher()
                        await dispatcher.broadcast(
                            full_message,
                            {
                                "source": "iflow_interactive",
                                "tmux_session": self.tmux_session,
                                "workspace": self.workspace,
                                "user_question": user_question,
                                "message_count": len(new_messages)
                            }
                        )
                        logger.info(
                            f"[BotIntegration] 已通过分发器发送 iflow 交互界面消息 "
                            f"(tmux: {self.tmux_session}, workspace: {self.workspace})"
                        )
                    
                    # 更新已知消息
                    last_known_messages.update(current_marker_ids)
                else:
                    # 定期更新已知消息（避免内存泄漏）
                    if len(last_known_messages) > 1000:
                        last_known_messages = current_marker_ids
                    else:
                        last_known_messages.update(current_marker_ids)
                
            except Exception as e:
                logger.error(f"[BotIntegration] 后台监控错误: {e}", exc_info=True)
                await asyncio.sleep(10)  # 出错后等待一段时间再继续