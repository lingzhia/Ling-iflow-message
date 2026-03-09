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
            logger.info(f"[BotIntegration] 处理命令: type={parsed['type']}, command={parsed.get('command', '')[:50]}")
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
        logger.info(f"[BotIntegration] 执行命令: chat_id={chat_id}, is_group={is_group}, command={command[:100]}")
        
        if not command:
            logger.warning("[BotIntegration] 命令为空")
            await self.wechat_channel.send("❌ 命令不能为空", chat_id, is_group=is_group)
            return
        
        # 检查 iflow 是否运行
        if not self.iflow_controller.check_tmux_session():
            logger.error(f"[BotIntegration] iflow 未运行，tmux_session={self.tmux_session}")
            await self.wechat_channel.send(
                "❌ iflow 未运行，请先启动 iflow: tmux new-session -d -s iflow \"iflow --model kimi-k2.5\"",
                chat_id,
                is_group=is_group
            )
            return
        
        try:
            # 在发送命令之前，先提取初始回复（作为基准）
            logger.debug(f"[BotIntegration] 获取发送前的初始回复")
            initial_messages, initial_generating, _ = self._extract_reply_from_tmux()
            initial_count = len(initial_messages)
            logger.debug(f"[BotIntegration] 初始回复数量: {initial_count}, 生成中: {initial_generating}")
            
            # 发送命令到 iflow
            logger.info(f"[BotIntegration] 发送命令到 iflow")
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
            
            # 记录已发送的消息内容（使用内容作为键）
            sent_message_contents = {}
            # 将初始消息标记为已发送，避免发送旧消息
            for message in initial_messages:
                msg_content_hash = hash(message.strip())
                sent_message_contents[msg_content_hash] = True
            
            last_message_count = initial_count  # 初始化为初始消息数
            last_generating = False
            self._stable_count = 0  # 初始化稳定计数器
            
            # 实时监控并发送新消息
            timeout = 60  # 60 秒超时
            
            logger.info(f"[BotIntegration] 开始实时监控 iflow 回复，超时时间: {timeout}秒")
            
            for i in range(timeout):
                await asyncio.sleep(1)
                
                # 获取当前回复和生成状态
                current_messages, is_generating, generation_time = self._extract_reply_from_tmux()
                current_count = len(current_messages)
                
                # 每次循环都检查所有消息，只发送未发送的新消息
                new_message_count = 0
                for j, message in enumerate(current_messages, start=1):
                    # 使用消息内容的 hash 作为唯一标识
                    msg_content_hash = hash(message.strip())
                    
                    # 检查是否已发送
                    if msg_content_hash in sent_message_contents:
                        logger.debug(f"[BotIntegration] 消息已发送，跳过: {j}")
                        continue
                    
                    sent_message_contents[msg_content_hash] = True
                    new_message_count += 1
                    logger.debug(f"[BotIntegration] 发送新消息 {j}: {message[:50]}")
                    
                    # 根据配置过滤思考消息
                    if self.filter_thinking:
                        filtered_message = self._filter_thinking_messages(message)
                        logger.info(f"[BotIntegration] 消息 {j} 过滤后长度: {len(filtered_message)}")
                    else:
                        filtered_message = message
                    
                    if filtered_message.strip():
                        # 分段发送（避免超过长度限制）
                        chunks = self._split_message(filtered_message)
                        logger.info(f"[BotIntegration] 消息 {j} 分段发送，共 {len(chunks)} 段")
                        
                        for k, chunk in enumerate(chunks):
                            if k > 0:
                                await asyncio.sleep(0.3)
                            
                            await self.wechat_channel.send(chunk, chat_id, is_group=is_group)
                
                if new_message_count > 0:
                    logger.info(f"[BotIntegration] 发送 {new_message_count} 条新消息")
                
                # 更新最后的消息计数
                last_message_count = current_count
                
                # 检查是否在生成中
                if is_generating:
                    logger.debug(f"[BotIntegration] iflow 正在生成中... (时间: {generation_time})")
                    last_generating = True
                    self._stable_count = 0  # 重置稳定计数器
                    continue
                
                # "生成中"消失了，检查是否之前在生成中
                if last_generating and not is_generating:
                    logger.info(f"[BotIntegration] 检测到生成中消失，回复可能完成")
                    
                    # 等待一下，确保不会有新消息
                    await asyncio.sleep(1)
                    
                    # 再次检查，确保"生成中"仍然消失
                    final_messages, final_generating, _ = self._extract_reply_from_tmux()
                    final_count = len(final_messages)
                    
                    if not final_generating:
                        logger.info(f"[BotIntegration] 确认回复完成（生成中消失），消息数量: {final_count}")
                        
                        # 检查是否有新消息出现（防止tmux缓冲区更新导致的消息丢失）
                        new_message_count = 0
                        for j, message in enumerate(final_messages, start=1):
                            msg_content_hash = hash(message.strip())
                            
                            if msg_content_hash not in sent_message_contents:
                                sent_message_contents[msg_content_hash] = True
                                logger.debug(f"[BotIntegration] 补充发送新消息 {j}: {message[:50]}")
                                
                                # 过滤思考消息
                                if self.filter_thinking:
                                    filtered_message = self._filter_thinking_messages(message)
                                else:
                                    filtered_message = message
                                
                                if filtered_message.strip():
                                    # 分段发送
                                    chunks = self._split_message(filtered_message)
                                    for k, chunk in enumerate(chunks):
                                        if k > 0:
                                            await asyncio.sleep(0.3)
                                        await self.wechat_channel.send(chunk, chat_id, is_group=is_group)
                                    new_message_count += 1
                        
                        if new_message_count > 0:
                            logger.info(f"[BotIntegration] 补充发送了 {new_message_count} 条新消息")
                        
                        # 在最后一条消息结尾添加"回答完毕"提示
                        if sent_message_contents:
                            completion_message = "\n\n✅ 当前问题回答完毕"
                            await self.wechat_channel.send(completion_message, chat_id, is_group=is_group)
                            logger.info(f"[BotIntegration] 已发送回答完毕提示")
                        break
                    else:
                        # "生成中"又出现了，继续监控
                        logger.debug(f"[BotIntegration] 生成中又出现，继续监控")
                        last_generating = True
                        continue
                
                # 如果从来没有检测到"生成中"，使用稳定检测作为 fallback
                if not last_generating and current_count == last_message_count:
                    # 消息数量稳定（fallback 机制）
                    logger.debug(f"[BotIntegration] 消息数量稳定（未检测到生成中）")
                    
                    # 增加稳定计数
                    self._stable_count += 1
                    
                    # 如果连续 3 秒稳定，认为完成
                    if self._stable_count >= 3:
                        logger.info(f"[BotIntegration] 回复完成（消息数量稳定且无生成中）")
                        
                        # 在最后一条消息结尾添加"回答完毕"提示
                        if sent_message_contents:
                            completion_message = "\n\n✅ 当前问题回答完毕"
                            await self.wechat_channel.send(completion_message, chat_id, is_group=is_group)
                            logger.info(f"[BotIntegration] 已发送回答完毕提示")
                        
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
    
    def _extract_reply_from_tmux(self) -> tuple:
        """从 tmux 输出中提取回复和生成状态。
        
        Returns:
            (messages: list, is_generating: bool, generation_time: str)
            - messages: 提取到的回复列表
            - is_generating: 是否正在生成中
            - generation_time: 生成时间记录（如果有）
        """
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", self.tmux_session, "-p"],
                capture_output=True,
                text=True
            )
            
            output = result.stdout
            lines = output.split('\n')
            
            messages = []
            in_thinking = False
            is_generating = False
            generation_time = None
            
            # 当前正在处理的消息（用于多行消息）
            current_message = []
            
            for i, line in enumerate(lines):
                curr_line_stripped = line.strip()
                
                # 检测"生成中"标识
                if '生成中' in line:
                    is_generating = True
                    # 尝试提取时间记录（格式类似：生成中 12:34:56）
                    import re
                    time_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', line)
                    if time_match:
                        generation_time = time_match.group(1)
                    logger.debug(f"[BotIntegration] 检测到生成中: {generation_time}")
                    continue
                
                # 根据配置决定提取逻辑
                if self.extract_all_messages:
                    # 提取所有消息（包括思考过程、工具调用、AI回复）
                    
                    # 排除状态栏信息（包含多个 | 或特定关键词）
                    if curr_line_stripped.count('|') >= 2 and (
                        '上下文' in curr_line_stripped or 
                        '思考' in curr_line_stripped or 
                        'cwd:' in curr_line_stripped or 
                        '%' in curr_line_stripped
                    ):
                        continue
                    
                    # 排除用户输入（以 > 开头）
                    if curr_line_stripped.startswith('>'):
                        continue
                    
                    # 排除分割线等装饰性内容（完全匹配）
                    if line.strip() and all(c in '─=-' for c in line.strip()):
                        continue
                    
                    # 排除输入提示行
                    if '输入消息或@文件路径' in line:
                        continue
                    
                    # 检测是否是新消息的开始（包含特殊标记）
                    has_special_marker = (
                        ('✻' in curr_line_stripped or 
                         '✦' in curr_line_stripped or 
                         '✔' in curr_line_stripped) and
                        '✹' not in curr_line_stripped
                    )
                    
                    # 如果遇到新消息的开始，保存之前的消息并开始新消息
                    if has_special_marker and current_message:
                        # 移除包含状态栏信息的行
                        filtered_lines = []
                        for msg_line in current_message:
                            # 跳过状态栏信息
                            if 'cwd:' in msg_line and '|' in msg_line:
                                continue
                            # 跳过其他状态栏信息
                            if msg_line.count('|') >= 2 and ('%' in msg_line or '上下文' in msg_line or '思考' in msg_line):
                                continue
                            filtered_lines.append(msg_line)
                        
                        message_text = '\n'.join(filtered_lines).strip()
                        if message_text:
                            messages.append(message_text)
                            logger.debug(f"[BotIntegration] 提取消息 {len(messages)}: {message_text[:50]}")
                        current_message = []
                    
                    # 只有当前有消息或遇到特殊标记时，才添加行
                    if current_message or has_special_marker:
                        current_message.append(curr_line_stripped)
                    
                else:
                    # 只提取带有"✦"标记的消息（默认模式）
                    
                    # 检测思考区域的开始
                    if '✻ 思考中' in line:
                        in_thinking = True
                        continue
                    
                    # 检测思考区域的结束（遇到"✦"标记，表示开始实际回复）
                    if in_thinking and '✦' in line and '✻' not in line and '✹' not in line:
                        in_thinking = False
                        # 继续处理这条消息
                    
                    # 如果在思考区域中，跳过
                    if in_thinking:
                        continue
                    
                    # 检测是否是新消息的开始（包含✦标记）
                    if '✦' in line and '✻' not in line and '✹' not in line:
                        # 保存之前的消息（如果有）
                        if current_message:
                            message_text = '\n'.join(current_message).strip()
                            if message_text:
                                messages.append(message_text)
                                logger.debug(f"[BotIntegration] 提取消息 {len(messages)}: {message_text[:50]}")
                            current_message = []
                        
                        # 去掉所有"✦"符号
                        clean_line = curr_line_stripped.replace('✦', '').strip()
                        
                        # 排除用户输入（以 > 开头）
                        if clean_line.startswith('>'):
                            current_message = []  # 重置，跳过用户输入
                            continue
                        
                        # 排除空行
                        if not clean_line:
                            current_message = []  # 重置，跳过空行
                            continue
                        
                        # 添加到当前消息
                        current_message.append(clean_line)
                    elif current_message:
                        # 如果已经在消息中，检查是否应该继续收集
                        # 只收集属于同一条消息的行（缩进的行或空行）
                        # 遇到非空行且非缩进行时，停止收集
                        if not curr_line_stripped or line.startswith(' ') or line.startswith('\t'):
                            # 这是消息的后续行（缩进行或空行），添加到消息中
                            current_message.append(curr_line_stripped)
                        else:
                            # 遇到非空行且非缩进行，停止收集，保存当前消息
                            message_text = '\n'.join(current_message).strip()
                            if message_text:
                                messages.append(message_text)
                                logger.debug(f"[BotIntegration] 提取消息 {len(messages)}: {message_text[:50]}")
                            current_message = []
            
            # 保存最后一条消息（如果有）
            if current_message:
                # 如果是 extract_all_messages 模式，应用过滤逻辑
                if self.extract_all_messages:
                    # 移除包含状态栏信息的行
                    filtered_lines = []
                    for msg_line in current_message:
                        # 跳过状态栏信息
                        if 'cwd:' in msg_line and '|' in msg_line:
                            continue
                        # 跳过其他状态栏信息
                        if msg_line.count('|') >= 2 and ('%' in msg_line or '上下文' in msg_line or '思考' in msg_line):
                            continue
                        filtered_lines.append(msg_line)
                    message_text = '\n'.join(filtered_lines).strip()
                else:
                    message_text = '\n'.join(current_message).strip()
                
                if message_text:
                    messages.append(message_text)
                    logger.debug(f"[BotIntegration] 提取消息 {len(messages)}: {message_text[:50]}")
            
            logger.debug(f"[BotIntegration] 提取完成，共 {len(messages)} 条消息，生成中: {is_generating}")
            
            return messages, is_generating, generation_time
        except Exception as e:
            logger.error(f"[BotIntegration] 提取 tmux 回复失败: {e}")
            return [], False, None
    
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