"""
Claude Code Monitor

持续监听 Claude Code 的 tmux 输出，提取新消息，检测状态变化。
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ClaudeCodeState(Enum):
    """Claude Code 状态"""
    IDLE = "idle"           # 空闲，等待输入
    GENERATING = "generating"  # 生成中


class MessageType(Enum):
    """消息类型"""
    REPLY = "reply"     # 回复（● 标记）
    THINKING = "thinking"  # 思考（✻ 标记）
    COMPLETE = "complete"  # 完成通知


@dataclass
class OutboundMessage:
    """出站消息"""
    type: MessageType                 # 消息类型
    content: str                      # 消息内容
    receiver: str                     # 接收方（来源模块 ID，空表示无特定接收方）
    scope: str                        # 返回范围（reply_only / all）
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "type": self.type.value,
            "content": self.content,
            "receiver": self.receiver,
            "scope": self.scope,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class ClaudeCodeMonitor:
    """Claude Code 监控器

    持续监听 Claude Code 的 tmux 输出，提取新消息，检测状态变化。
    """

    # 扫描行数配置
    LINES_LIGHTWEIGHT = 20  # 轻量级模式（IDLE 状态）
    LINES_FULL = 1000       # 完整模式（GENERATING 状态）

    def __init__(self, controller, check_interval: float = 0.5):
        """初始化监控器

        Args:
            controller: ClaudeCodeController 实例
            check_interval: 检查间隔（秒）
        """
        self.controller = controller
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 状态管理
        self._state = ClaudeCodeState.IDLE
        self._generating_start_time: Optional[datetime] = None
        self._last_generating_duration: int = 0

        # 初始化状态标志（防止在模块初始化期间触发错误的状态变更）
        self._is_initialized = False
        self._initialization_time: Optional[datetime] = None
        
        # 初始化后稳定期（启动后一段时间内不进行状态检测）
        self._stabilization_period = 10.0  # 稳定期 10 秒
        self._stabilization_end_time: Optional[datetime] = None

        # 消息记录（用于延迟记录原则）

        # 稳定检测（用于确认生成中真正消失）
        # 使用连续3次扫描判断，不需要时间变量

        # 消息定位（用于过滤发送消息前的内容）
        self._last_received_line: Optional[int] = None

        # 订阅者列表
        self._subscribers: List[Callable] = []

        # 状态变更回调
        self._on_state_change: Optional[Callable] = None

        # 消息去重（确保相同内容的消息只发送一次）
        self._sent_message_hashes: set = set()
        self._sent_marker_strings: set = set()
        
        # 初始化时记录已存在的消息（避免发送历史消息）
        self._initial_messages_loaded: bool = False

        # 发送模式控制（消息来源差异化处理）
        self._send_mode: str = "STREAM_MODE"
        self._current_request_record: Optional[Any] = None
        self._request_matched: bool = False

        # 无来源消息缓冲区
        self._no_source_buffer: List[str] = []
        self._no_source_request_content: str = ""

        # 结束判断（连续3次扫描）
        self._missing_generating_count: int = 0

        # 统计信息
        self.stats = {
            "messages_extracted": 0,
            "messages_filtered": 0,
            "check_count": 0,
            "state_changes": 0
        }

    @property
    def state(self) -> ClaudeCodeState:
        """当前 Claude Code 状态"""
        return self._state

    @property
    def generating_duration(self) -> int:
        """生成持续时间（秒）"""
        if self._state == ClaudeCodeState.GENERATING and self._generating_start_time:
            return int((datetime.now() - self._generating_start_time).total_seconds())
        return self._last_generating_duration

    async def start(self) -> None:
        """启动监控器"""
        if self._running:
            logger.warning("[ClaudeCodeMonitor] Monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("[ClaudeCodeMonitor] Monitor started")

    async def stop(self) -> None:
        """停止监控器"""
        if not self._running:
            return

        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("[ClaudeCodeMonitor] Monitor stopped")

    def subscribe(self, callback: Callable) -> None:
        """订阅 Claude Code 输出消息

        Args:
            callback: 回调函数，接收 OutboundMessage
        """
        self._subscribers.append(callback)
        logger.debug(f"[ClaudeCodeMonitor] Added subscriber, total: {len(self._subscribers)}")

    def unsubscribe(self, callback: Callable) -> None:
        """取消订阅

        Args:
            callback: 回调函数
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.debug(f"[ClaudeCodeMonitor] Removed subscriber, total: {len(self._subscribers)}")

    def set_state_change_callback(self, callback: Callable) -> None:
        """设置状态变更回调

        Args:
            callback: 回调函数，参数为 (old_state, new_state)
        """
        self._on_state_change = callback

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._check()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[ClaudeCodeMonitor] Monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _check(self) -> None:
        """检查新消息和状态

        根据当前状态选择不同的检查模式：
        - IDLE 状态：轻量级检查，只扫描 20 行，只检查"生成中"
        - GENERATING 状态：完整检查，扫描 1000 行，提取所有消息
        """
        # 如果是 IDLE 状态，使用轻量级检查
        if self._state == ClaudeCodeState.IDLE:
            await self._check_lightweight()
            return

        # GENERATING 状态：执行完整检查
        self.stats["check_count"] += 1

        try:
            # 捕获 tmux 输出（完整模式：1000 行）
            output = await self.controller.capture_output(lines=self.LINES_FULL)

            if not output:
                return

            # 检查是否处于初始化期间（启动后 3 秒内）
            if not self._is_initialized:
                if self._initialization_time is None:
                    self._initialization_time = datetime.now()
                    logger.debug(f"[ClaudeCodeMonitor] 开始初始化计时")

                initialization_duration = (datetime.now() - self._initialization_time).total_seconds()
                if initialization_duration < 3.0:
                    logger.debug(f"[ClaudeCodeMonitor] 初始化期间，跳过检查 ({initialization_duration:.1f}s / 3.0s)")
                    return
                else:
                    self._is_initialized = True
                    logger.info(f"[ClaudeCodeMonitor] 初始化完成 ({initialization_duration:.1f}s)")
                    
                    # 记录初始化时已存在的消息，避免后续重复发送
                    if not self._initial_messages_loaded:
                        full_output = await self.controller.capture_output(lines=self.LINES_FULL)
                        if full_output:
                            initial_messages = self._extract_messages(full_output)
                            if initial_messages:
                                # 将所有已存在的消息添加到去重集合
                                for msg in initial_messages:
                                    marker_only = msg.get('marker_only', '')
                                    full_content = msg.get('content', '')
                                    if marker_only:
                                        self._sent_marker_strings.add(marker_only)
                                    if full_content:
                                        content_hash = hashlib.md5(full_content.encode()).hexdigest()
                                        self._sent_message_hashes.add(content_hash)
                                logger.info(f"[ClaudeCodeMonitor] 已记录 {len(initial_messages)} 条历史消息，避免重复发送")
                        self._initial_messages_loaded = True

            # 先检测状态变化
            await self._check_state(output)

            # 检测生成状态
            is_generating = self._detect_generating(output)

            # 提取所有消息（只在GENERATING状态下提取）
            current_messages = []
            if self._state == ClaudeCodeState.GENERATING:
                current_messages = self._extract_messages(output)
                logger.debug(f"[ClaudeCodeMonitor] GENERATING state: extracted {len(current_messages)} messages")
            elif self._state == ClaudeCodeState.IDLE:
                logger.debug(f"[ClaudeCodeMonitor] IDLE state: not extracting messages")

            # 调试日志
            if self.stats["check_count"] % 5 == 0:
                logger.debug(f"[ClaudeCodeMonitor] Check #{self.stats['check_count']}: state={self._state.value}, is_generating={is_generating}, "
                           f"current_count={len(current_messages)}")

            # 延迟记录原则
            if self._state == ClaudeCodeState.GENERATING:
                if len(current_messages) < 2:
                    logger.debug(f"[ClaudeCodeMonitor] 只有 {len(current_messages)} 条消息，不记录（延迟记录原则）")
                    return

                # 定位已记录的最新消息
                last_sent_index = self._locate_last_sent_message(current_messages)

                # 计算需要记录的消息
                if last_sent_index is None:
                    messages_to_send = current_messages[:-1]
                    logger.debug(f"[ClaudeCodeMonitor] 未找到已记录消息，记录第1条到倒数第2条：{len(messages_to_send)} 条")
                else:
                    messages_to_send = current_messages[last_sent_index + 1:-1]
                    logger.debug(f"[ClaudeCodeMonitor] 找到已记录消息（索引={last_sent_index}），记录其后到倒数第2条：{len(messages_to_send)} 条")

                # 记录并发送消息
                if len(messages_to_send) > 0:
                    logger.debug(f"[ClaudeCodeMonitor] 记录并发送 {len(messages_to_send)} 条消息")

                    for i, message in enumerate(messages_to_send):
                        marker_symbol = message['marker_type']
                        logger.debug(f"[ClaudeCodeMonitor] 记录消息: {marker_symbol} - {message['content'][:50]}...")

                        await self._send_message(message)
                        logger.info(f"[ClaudeCodeMonitor] 发送消息: {marker_symbol} - {message['content'][:50]}...")

                # 检测生成中是否消失
                if not is_generating:
                    self._missing_generating_count += 1
                    logger.debug(f"[ClaudeCodeMonitor] 生成中消失，计数：{self._missing_generating_count}/3")

                    # 连续3次扫描"生成中"消失，确认结束
                    if self._missing_generating_count >= 3:
                        logger.info(f"[ClaudeCodeMonitor] 连续3次扫描\"生成中\"消失，交互结束")

                        # 延迟记录原则：记录最后一条消息
                        if len(current_messages) > 0:
                            last_message = current_messages[-1]
                            logger.debug(f"[ClaudeCodeMonitor] 记录最后一条消息: {last_message['marker_type']} - {last_message['content'][:50]}...")

                            await self._send_message(last_message)
                            logger.info(f"[ClaudeCodeMonitor] 发送最后一条消息: {last_message['marker_type']} - {last_message['content'][:50]}...")

                        self._missing_generating_count = 0

                        # 切换到IDLE状态
                        old_state = self._state
                        self._state = ClaudeCodeState.IDLE
                        self.stats["state_changes"] += 1

                        # 重置请求匹配标志
                        self._request_matched = False

                        # 计算生成持续时间
                        if self._generating_start_time:
                            duration = int((datetime.now() - self._generating_start_time).total_seconds())
                        else:
                            duration = 0
                            logger.warning(f"[ClaudeCodeMonitor] _generating_start_time is None, duration set to 0")

                        self._last_generating_duration = duration

                        logger.info(f"[ClaudeCodeMonitor] State changed: {old_state.value} -> {self._state.value} (completed after {duration}s)")

                        # 消息来源差异化处理
                        if self._send_mode == "BUFFER_MODE":
                            await self._flush_buffered_messages()
                        self._send_mode = "STREAM_MODE"
                        self._current_request_record = None

                        # 触发状态变更回调
                        if self._on_state_change:
                            await self._call_callback(self._on_state_change, old_state, self._state, duration)

                        # 重置生成开始时间
                        self._generating_start_time = None

        except Exception as e:
            logger.error(f"[ClaudeCodeMonitor] Error checking messages: {e}", exc_info=True)

    async def _check_lightweight(self) -> None:
        """轻量级检查（IDLE 状态）

        只检查是否出现"生成中"关键词，不进行消息提取。
        """
        self.stats["check_count"] += 1

        try:
            output = await self.controller.capture_output(lines=self.LINES_LIGHTWEIGHT)

            if not output:
                return

            # 检查是否处于初始化期间（启动后 5 秒内）
            # 在初始化期间，跳过历史消息的发送
            if not self._is_initialized:
                if self._initialization_time is None:
                    self._initialization_time = datetime.now()
                    logger.debug(f"[ClaudeCodeMonitor] 开始初始化计时")

                initialization_duration = (datetime.now() - self._initialization_time).total_seconds()
                if initialization_duration < 5.0:
                    logger.debug(f"[ClaudeCodeMonitor] 初始化期间，跳过 lightweight 检查 ({initialization_duration:.1f}s / 5.0s)")
                    # 初始化期间不触发状态变更，只等待初始化完成
                    return
                else:
                    self._is_initialized = True
                    logger.info(f"[ClaudeCodeMonitor] 初始化完成 ({initialization_duration:.1f}s)")
                    
                    # 记录初始化时已存在的消息，避免后续重复发送
                    if not self._initial_messages_loaded:
                        full_output = await self.controller.capture_output(lines=self.LINES_FULL)
                        if full_output:
                            initial_messages = self._extract_messages(full_output)
                            if initial_messages:
                                # 将所有已存在的消息添加到去重集合
                                for msg in initial_messages:
                                    marker_only = msg.get('marker_only', '')
                                    full_content = msg.get('content', '')
                                    if marker_only:
                                        self._sent_marker_strings.add(marker_only)
                                    if full_content:
                                        content_hash = hashlib.md5(full_content.encode()).hexdigest()
                                        self._sent_message_hashes.add(content_hash)
                                logger.info(f"[ClaudeCodeMonitor] 已记录 {len(initial_messages)} 条历史消息，避免重复发送")
                        self._initial_messages_loaded = True
                    # 初始化完成后，继续执行后续检查
                    # 不要 return，让代码继续执行下面的逻辑
                    # 但是要确保状态是 IDLE，避免历史消息触发错误的状态变更
                    self._state = ClaudeCodeState.IDLE
                    # 设置稳定期结束时间
                    self._stabilization_end_time = datetime.now() + timedelta(seconds=self._stabilization_period)
                    logger.info(f"[ClaudeCodeMonitor] 初始化完成后重置状态为 IDLE，进入稳定期 {self._stabilization_period}s")

            # 检查是否在稳定期内
            if self._stabilization_end_time:
                if datetime.now() < self._stabilization_end_time:
                    remaining_time = (self._stabilization_end_time - datetime.now()).total_seconds()
                    logger.debug(f"[ClaudeCodeMonitor] 在稳定期内，跳过状态检测 ({remaining_time:.1f}s 剩余)")
                    # 稳定期内只检查是否正在生成，不触发状态变更
                    is_generating = self._detect_generating(output)
                    return
                else:
                    # 稳定期结束
                    self._stabilization_end_time = None
                    logger.info(f"[ClaudeCodeMonitor] 稳定期结束，开始正常状态检测")

            is_generating = self._detect_generating(output)

            if is_generating:
                self._state = ClaudeCodeState.GENERATING
                self._generating_start_time = datetime.now()
                self.stats["state_changes"] += 1
                logger.info(f"[ClaudeCodeMonitor] State changed: IDLE -> GENERATING (lightweight detected)")

                full_output = await self.controller.capture_output(lines=self.LINES_FULL)
                await self._check_state(full_output)

                logger.debug(f"[ClaudeCodeMonitor] Check #{self.stats['check_count']}: lightweight -> full")
            else:
                # 检查是否有 ● 标记（简单响应可能不显示 "Choreographing"）
                # 直接提取最后一条消息并发送
                has_response_marker = '●' in output
                if has_response_marker:
                    full_output = await self.controller.capture_output(lines=self.LINES_FULL)
                    if full_output:
                        current_messages = self._extract_messages(full_output)
                        if current_messages:
                            # 只发送最后一条消息（最新的回复）
                            last_message = current_messages[-1]
                            # 注意：_send_message_simple 内部会进行去重检查
                            # 如果消息已发送，会直接返回，不会重复发送
                            logger.debug(f"[ClaudeCodeMonitor] lightweight 检测到 ● 标记，尝试发送最后一条消息")
                            await self._send_message_simple(last_message)
                elif self.stats["check_count"] % 60 == 0:
                    logger.debug(f"[ClaudeCodeMonitor] Check #{self.stats['check_count']}: lightweight mode (idle)")

        except Exception as e:
            logger.error(f"[ClaudeCodeMonitor] Error in lightweight check: {e}", exc_info=True)

    async def _check_state(self, output: str) -> None:
        """检测 Claude Code 状态

        检查界面中是否显示"Choreographing..."。

        Args:
            output: tmux 输出
        """
        is_generating = self._detect_generating(output)

        old_state = self._state

        if is_generating and self._state == ClaudeCodeState.IDLE:
            self._state = ClaudeCodeState.GENERATING
            self._generating_start_time = datetime.now()
            self.stats["state_changes"] += 1
            logger.info(f"[ClaudeCodeMonitor] State changed: {old_state.value} -> {self._state.value}")

            # 触发状态变更回调
            if self._on_state_change:
                await self._call_callback(self._on_state_change, old_state, self._state)

        elif not is_generating and self._state == ClaudeCodeState.GENERATING:
            logger.debug(f"[ClaudeCodeMonitor] 检测到状态可能变更: is_generating={is_generating}, state={self._state.value}")

    def _detect_generating(self, output: str) -> bool:
        """检测是否处于生成中状态

        检测方法：
        1. 检查是否有状态指示器关键词（Choreographing, Baking, Honking, Thinking, Orbiting）
        2. 检查最后几行是否有用户输入提示符 `❯` 但没有对应的回复标记 `●`

        注意：这个方法主要用于检测正在生成的状态，不应用于历史消息。

        Args:
            output: tmux 输出

        Returns:
            是否处于生成中
        """
        # 方法1：检测状态指示器关键词
        indicators = ["Choreographing", "Baking…", "Honking…", "Thinking…", "Orbiting…", 
                     "Baking...", "Honking...", "Thinking...", "Orbiting..."]
        if any(indicator in output for indicator in indicators):
            return True
        
        # 方法2：检测最后几行是否有用户输入但没有回复
        # 只检查最后10行，避免检测历史消息
        lines = output.split('\n')
        recent_lines = lines[-10:] if len(lines) >= 10 else lines
        
        # 查找最后一个用户输入提示符
        last_user_input_index = -1
        for i in range(len(recent_lines) - 1, -1, -1):
            line_stripped = recent_lines[i].strip()
            # 找到用户输入（排除命令和空输入）
            if line_stripped.startswith('❯') and not line_stripped.startswith('❯ /'):
                # 提取输入内容（去掉 ❯ 前缀）
                input_content = line_stripped[1:].strip()
                # 如果输入内容不为空，才认为是有效的用户输入
                if input_content:
                    last_user_input_index = i
                    break
        
        # 如果有用户输入，检查后面是否有回复标记
        if last_user_input_index >= 0:
            has_reply_after_input = False
            for i in range(last_user_input_index + 1, len(recent_lines)):
                if '●' in recent_lines[i]:
                    has_reply_after_input = True
                    break
            
            if not has_reply_after_input:
                # 用户输入后没有回复，正在生成
                return True
        
        return False

    def _extract_received_message(self, lines: List[str]) -> tuple[Optional[str], Optional[int]]:
        """从 tmux 输出中提取发给 Claude Code 的消息

        发给 Claude Code 的消息特征：
        - 以 `❯` 开头的行（用户输入提示符）

        Args:
            lines: tmux 输出行列表

        Returns:
            (消息内容, 消息行号) 或 (None, None)
        """
        # 从下往上扫描，找到最后一个用户发送的消息
        for i in range(len(lines) - 1, -1, -1):
            line_stripped = lines[i].strip()

            if line_stripped.startswith('❯'):
                # 提取消息内容（去掉 `❯` 前缀）
                message_content = line_stripped[1:].strip()
                return message_content, i

        return None, None

    def _is_tui_line(self, line: str) -> bool:
        """判断一行是否为 TUI 界面内容

        TUI 界面特征：
        - 包含 "Choreographing"
        - 包含 "╭─" / "╰─" 等分隔符
        - 是进度条或状态显示

        Args:
            line: 要检查的行

        Returns:
            是否为 TUI 界面行
        """
        # 如果行包含消息标记，不是TUI界面行
        if '●' in line or '✻' in line:
            return False

        tui_markers = ['Choreographing', '╭─', '╰─', '│', '├', '┬', '┴']

        line_stripped = line.strip()

        for marker in tui_markers:
            if marker in line_stripped:
                return True

        return False

    def _extract_messages(self, output: str) -> List[Dict]:
        """从 tmux 输出中提取消息

        Claude Code 消息标记：
        - `●` - 助手回复
        - `✻` - 思考内容

        Args:
            output: tmux 输出

        Returns:
            消息列表
        """
        messages = []
        lines = output.split('\n')

        logger.debug(f"[ClaudeCodeMonitor] _extract_messages: processing {len(lines)} lines")

        # 提取发给 Claude Code 的消息
        received_message, received_line = self._extract_received_message(lines)

        if received_line is not None:
            self._last_received_line = received_line
            logger.debug(f"[ClaudeCodeMonitor] 找到接收消息: {received_message[:50]}..., 行号: {received_line}")

            # 消息来源差异化处理
            if not self._request_matched and received_message and hasattr(self.controller, 'module') and self.controller.module:
                message_store = self.controller.module.message_store
                matched_record = message_store.find_by_content(received_message)

                if matched_record:
                    self._current_request_record = matched_record
                    self._request_matched = True

                    if matched_record.source:
                        self._send_mode = "STREAM_MODE"
                        logger.info(f"[ClaudeCodeMonitor] 请求消息有明确来源 ({matched_record.source})，使用流式发送")
                    else:
                        self._send_mode = "BUFFER_MODE"
                        matched_record.requires_buffering = True
                        self._no_source_request_content = matched_record.content
                        logger.info(f"[ClaudeCodeMonitor] 请求消息无明确来源，使用缓冲发送，原始请求: {matched_record.content[:50]}")
                else:
                    self._send_mode = "BUFFER_MODE"
                    self._current_request_record = None
                    self._no_source_request_content = received_message
                    self._request_matched = True
                    logger.info(f"[ClaudeCodeMonitor] 请求消息未匹配到记录，使用缓冲发送，原始请求: {received_message[:50]}")

        logger.debug(f"[ClaudeCodeMonitor] _extract_messages: scanning {len(lines)} lines for markers (●, ✻)")

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 跳过 TUI 界面行
            if self._is_tui_line(line):
                logger.debug(f"[ClaudeCodeMonitor] 跳过 TUI 界面行: {line[:50]}")
                continue

            # 检查标记行
            has_bullet = '●' in line
            has_thought = '✻' in line

            if has_bullet or has_thought:
                marker_type = '●' if has_bullet else '✻'
                marker_content = line.replace('●', '').replace('✻', '').strip()

                logger.debug(f"[ClaudeCodeMonitor] Line {i}: 检测到标记行")
                logger.debug(f"  Raw line: {line}")
                logger.debug(f"  Marker type: {marker_type}")
                logger.debug(f"  Marker content: {marker_content}")

                if not marker_content:
                    logger.debug(f"[ClaudeCodeMonitor] 跳过空标记内容")
                    continue

                # 收集后续行（消息延续）
                content_lines = [marker_content]

                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    next_line_stripped = next_line.strip()

                    # 跳过 TUI 界面行
                    if self._is_tui_line(next_line):
                        logger.debug(f"[ClaudeCodeMonitor] 跳过 TUI 界面行: {next_line[:50]}")
                        continue

                    # 如果遇到新的标记行，停止
                    if '●' in next_line or '✻' in next_line:
                        logger.debug(f"[ClaudeCodeMonitor] 遇到新标记，停止收集: {next_line[:50]}")
                        break

                    # 跳过空行
                    if not next_line_stripped:
                        logger.debug(f"[ClaudeCodeMonitor] 跳过空行")
                        continue

                    # 检查行是否以空格开头（表示是前一条消息的延续）
                    if next_line.startswith('  ') or next_line.startswith('\t'):
                        logger.debug(f"[ClaudeCodeMonitor] 收集缩进行: {next_line[:80]}")
                        content_lines.append(next_line_stripped)
                    else:
                        logger.debug(f"[ClaudeCodeMonitor] 遇到非缩进行，停止收集: {next_line[:50]}")
                        break

                # 合并内容
                full_content = '\n'.join(content_lines)

                logger.debug(f"[ClaudeCodeMonitor] 提取的消息内容: {full_content[:100]}...")

                messages.append({
                    'content': full_content,
                    'marker_type': marker_type,
                    'marker_only': marker_content
                })

        logger.debug(f"[ClaudeCodeMonitor] _extract_messages: extracted {len(messages)} messages total")
        return messages

    def _cleanup_cache(self) -> None:
        """清理旧缓存，保留最近的 N 条消息

        清理策略：
        - 最大缓存大小：100 条
        - 保留数量：50 条
        """
        max_cache_size = 100
        keep_count = 50

        if len(self._sent_marker_strings) > max_cache_size:
            self._sent_marker_strings = set(list(self._sent_marker_strings)[-keep_count:])
            logger.debug(f"[ClaudeCodeMonitor] 清理缓存：保留最近 {keep_count} 条标记行字符串")

        if len(self._sent_message_hashes) > max_cache_size:
            self._sent_message_hashes = set(list(self._sent_message_hashes)[-keep_count:])
            logger.debug(f"[ClaudeCodeMonitor] 清理缓存：保留最近 {keep_count} 条内容哈希")

    async def _send_message(self, message_data: Dict) -> None:
        """发送消息

        Args:
            message_data: 消息数据字典
        """
        marker_symbol = message_data.get('marker_type', '')
        marker_only = message_data.get('marker_only', '')
        full_content = message_data.get('content', '')

        # 字符串定位（优先）
        if marker_only in self._sent_marker_strings:
            logger.debug(f"[ClaudeCodeMonitor] 消息已发送，跳过（标记行字符串相同）：{marker_only[:50]}")
            return

        # 计算内容哈希（备用定位）
        content_hash = hashlib.md5(full_content.encode()).hexdigest()

        # 检查消息是否已发送（去重）
        if content_hash in self._sent_message_hashes:
            logger.debug(f"[ClaudeCodeMonitor] 消息已发送，跳过（内容哈希相同）")
            return

        # 添加到已发送集合
        self._sent_marker_strings.add(marker_only)
        self._sent_message_hashes.add(content_hash)

        # 清理旧缓存
        self._cleanup_cache()

        # 根据 send_mode 决定发送方式
        if self._send_mode == "STREAM_MODE":
            await self._send_immediately(message_data)
        elif self._send_mode == "BUFFER_MODE":
            await self._buffer_message(message_data)
        else:
            await self._send_immediately(message_data)

    async def _send_immediately(self, message_data: Dict) -> None:
        """立即发送消息（流式模式）

        Args:
            message_data: 消息数据字典
        """
        marker_symbol = message_data.get('marker_type', '')
        full_content = message_data.get('content', '')

        # 创建出站消息
        msg_type = MessageType.REPLY if marker_symbol == '●' else MessageType.THINKING

        # 设置接收方
        receiver = ""
        if self._current_request_record:
            receiver = self._current_request_record.metadata.get("chat_id", "")

        message = OutboundMessage(
            type=msg_type,
            content=full_content,
            receiver=receiver,
            scope="all",
            timestamp=datetime.now(),
            metadata={'marker_symbol': marker_symbol, 'send_mode': 'stream'}
        )

        # 通知订阅者
        logger.debug(f"[ClaudeCodeMonitor] [_send_immediately] 调用 _notify_subscribers, subscriber_count={len(self._subscribers)}")
        await self._notify_subscribers(message)
        self.stats["messages_extracted"] += 1

        logger.info(f"[ClaudeCodeMonitor] [_send_immediately] 流式发送完成: {full_content[:50]}, receiver={receiver}")

    async def _send_message_simple(self, message_data: Dict) -> None:
        """直接发送消息（带去重）

        用于 lightweight 模式下简单响应的快速发送。
        使用标记行字符串和内容哈希进行去重。

        Args:
            message_data: 消息数据字典
        """
        marker_symbol = message_data.get('marker_type', '')
        marker_only = message_data.get('marker_only', '')
        full_content = message_data.get('content', '')

        # 字符串定位去重（优先）
        if marker_only in self._sent_marker_strings:
            logger.debug(f"[ClaudeCodeMonitor] [_send_message_simple] 消息已发送，跳过（标记行字符串相同）：{marker_only[:50]}")
            return

        # 计算内容哈希（备用定位）
        content_hash = hashlib.md5(full_content.encode()).hexdigest()

        # 检查消息是否已发送（去重）
        if content_hash in self._sent_message_hashes:
            logger.debug(f"[ClaudeCodeMonitor] [_send_message_simple] 消息已发送，跳过（内容哈希相同）")
            return

        # 添加到已发送集合
        self._sent_marker_strings.add(marker_only)
        self._sent_message_hashes.add(content_hash)

        # 清理旧缓存
        self._cleanup_cache()

        msg_type = MessageType.REPLY if marker_symbol == '●' else MessageType.THINKING

        # 获取接收方信息
        receiver = ""
        if self._current_request_record:
            receiver = self._current_request_record.metadata.get("chat_id", "")

        message = OutboundMessage(
            type=msg_type,
            content=full_content,
            receiver=receiver,
            scope="all",
            timestamp=datetime.now(),
            metadata={'marker_symbol': marker_symbol, 'send_mode': 'simple'}
        )

        await self._notify_subscribers(message)
        self.stats["messages_extracted"] += 1

        logger.info(f"[ClaudeCodeMonitor] [_send_message_simple] 直接发送: {full_content[:50]}, receiver={receiver}")

    async def _buffer_message(self, message_data: Dict) -> None:
        """缓冲消息（缓冲模式）

        Args:
            message_data: 消息数据字典
        """
        marker_symbol = message_data.get('marker_type', '')
        full_content = message_data.get('content', '')

        # 只缓冲 ● 标记的消息
        if marker_symbol == '●':
            if self._current_request_record:
                if hasattr(self.controller, 'module') and self.controller.module:
                    message_store = self.controller.module.message_store
                    message_store.add_buffered_reply(self._current_request_record.message_id, full_content)
                    logger.debug(f"[ClaudeCodeMonitor] 缓冲回复消息（有来源）: {full_content[:50]}")
            else:
                self._no_source_buffer.append(full_content)
                logger.debug(f"[ClaudeCodeMonitor] 缓冲回复消息（无来源）: {full_content[:50]}")
        else:
            logger.debug(f"[ClaudeCodeMonitor] 跳过缓冲: marker={marker_symbol}")

    async def _flush_buffered_messages(self) -> None:
        """发送缓冲的消息（生成结束时调用）

        整合所有缓冲的 ● 消息为一条，发送到消息总线。
        """
        if not self._current_request_record or not self._current_request_record.requires_buffering:
            if not self._no_source_buffer:
                logger.debug("[ClaudeCodeMonitor] 不需要刷新缓冲区")
                return

            reply_blocks = []
            for i, reply_content in enumerate(self._no_source_buffer, 1):
                reply_blocks.append(f"回复 {i}/{len(self._no_source_buffer)}：\n\n```\n{reply_content}\n```")

            merged_reply = '\n'.join(reply_blocks)

            formatted_content = f"""未知来源消息回复结束！
原请求消息内容是：{self._no_source_request_content}
回复内容如下：

{merged_reply}"""

            message = OutboundMessage(
                type=MessageType.REPLY,
                content=formatted_content,
                receiver="",
                scope="all",
                timestamp=datetime.now(),
                metadata={'merged': True, 'reply_count': len(self._no_source_buffer), 'send_mode': 'buffer', 'has_source': False, 'original_request': self._no_source_request_content}
            )

            await self._notify_subscribers(message)
            logger.info(f"[ClaudeCodeMonitor] 已发送无来源消息（广播模式，整合 {len(self._no_source_buffer)} 条回复）")

            self._no_source_request_content = ""
            return

        if not hasattr(self.controller, 'module') or not self.controller.module:
            logger.warning("[ClaudeCodeMonitor] 无法访问消息库")
            return

        message_store = self.controller.module.message_store
        buffered_replies = message_store.get_buffered_replies(self._current_request_record.message_id)

        if not buffered_replies:
            logger.debug("[ClaudeCodeMonitor] 没有缓冲的消息")
            return

        if self._current_request_record.source:
            merged_content = '\n'.join(buffered_replies)
            receiver = self._current_request_record.metadata.get("chat_id", "")
            message = OutboundMessage(
                type=MessageType.REPLY,
                content=merged_content,
                receiver=receiver,
                scope="all",
                timestamp=datetime.now(),
                metadata={'merged': True, 'reply_count': len(buffered_replies), 'send_mode': 'buffer', 'has_source': True}
            )
            await self._notify_subscribers(message)
            logger.info(f"[ClaudeCodeMonitor] 已发送整合后的消息（{len(buffered_replies)} 条回复，有来源）")
        else:
            original_request = self._current_request_record.content
            for i, reply_content in enumerate(buffered_replies):
                formatted_content = f"回复 {i+1}/{len(buffered_replies)}：\n\n```\n{reply_content}\n```"

                message = OutboundMessage(
                    type=MessageType.REPLY,
                    content=formatted_content,
                    receiver="",
                    scope="all",
                    timestamp=datetime.now(),
                    metadata={'merged': False, 'reply_index': i+1, 'reply_count': len(buffered_replies), 'send_mode': 'buffer', 'has_source': False, 'original_request': original_request}
                )

                await self._notify_subscribers(message)
                logger.info(f"[ClaudeCodeMonitor] 已发送无来源消息 {i+1}/{len(buffered_replies)}")

            logger.info(f"[ClaudeCodeMonitor] 已发送 {len(buffered_replies)} 条无来源消息（广播模式，每条独立代码块）")

        if self._current_request_record:
            self._current_request_record.buffered_replies.clear()
        return

    def _locate_last_sent_message(self, messages: List[Dict]) -> Optional[int]:
        """定位已记录的最新消息

        使用字符串定位（优先）+ 哈希定位（备用）

        Args:
            messages: 消息列表

        Returns:
            已记录的最新消息的索引，如果未找到返回 None
        """
        for i in range(len(messages) - 1, -1, -1):
            message = messages[i]
            marker_only = message.get('marker_only', '')

            if marker_only in self._sent_marker_strings:
                matches = [j for j, msg in enumerate(messages) if msg.get('marker_only', '') == marker_only]
                if len(matches) == 1:
                    logger.debug(f"[ClaudeCodeMonitor] 定位成功（字符串）：索引={i}, 标记行字符串={marker_only}")
                    return i
                elif len(matches) > 1:
                    full_content = message.get('content', '')
                    content_hash = hashlib.md5(full_content.encode()).hexdigest()
                    if content_hash in self._sent_message_hashes:
                        logger.debug(f"[ClaudeCodeMonitor] 定位成功（哈希）：索引={i}, 标记行字符串={marker_only}")
                        return i

        logger.debug(f"[ClaudeCodeMonitor] 未找到已记录的消息")
        return None

    async def _notify_subscribers(self, message: OutboundMessage) -> None:
        """通知所有订阅者

        Args:
            message: 出站消息
        """
        for callback in self._subscribers:
            try:
                await self._call_callback(callback, message)
            except Exception as e:
                logger.error(f"[ClaudeCodeMonitor] Subscriber callback error: {e}", exc_info=True)

    async def _call_callback(self, callback: Callable, *args) -> None:
        """调用回调函数

        Args:
            callback: 回调函数
            args: 参数
        """
        try:
            logger.debug(f"[ClaudeCodeMonitor] Calling callback: {callback.__name__ if hasattr(callback, '__name__') else 'unknown'}")
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
            logger.debug(f"[ClaudeCodeMonitor] Callback completed successfully")
        except Exception as e:
            logger.error(f"[ClaudeCodeMonitor] Callback error: {e}", exc_info=True)

    def get_stats(self) -> Dict:
        """获取统计信息

        Returns:
            统计信息字典
        """
        return {
            **self.stats,
            "state": self._state.value,
            "generating_duration": self.generating_duration
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            "messages_extracted": 0,
            "messages_filtered": 0,
            "check_count": 0,
            "state_changes": 0
        }
        logger.info("[ClaudeCodeMonitor] Stats reset")

    @property
    def running(self) -> bool:
        """监控器是否运行中"""
        return self._running