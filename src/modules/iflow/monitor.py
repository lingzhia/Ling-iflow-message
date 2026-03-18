"""
IFlow Monitor

持续监听 iflow 的 tmux 输出，提取新消息，检测状态变化。
"""

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class IFlowState(Enum):
    """iflow 状态"""
    IDLE = "idle"           # 空闲，等待输入
    GENERATING = "generating"  # 生成中


class MessageType(Enum):
    """消息类型"""
    REPLY = "reply"     # 回复（✦ 标记）
    OTHER = "other"     # 其他（✻ 思考 + 无标记）
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


class IFlowMonitor:
    """iflow 监控器
    
    持续监听 iflow 的 tmux 输出，提取新消息，检测状态变化。
    """
    
    # 扫描行数配置
    LINES_LIGHTWEIGHT = 20  # 轻量级模式（IDLE 状态）
    LINES_FULL = 1000       # 完整模式（GENERATING 状态）
    
    def __init__(self, controller, check_interval: float = 0.5):
        """初始化监控器

        Args:
            controller: IFlowController 实例
            check_interval: 检查间隔（秒）
        """
        self.controller = controller
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 状态管理
        self._state = IFlowState.IDLE
        self._generating_start_time: Optional[datetime] = None

        # 初始化状态标志（防止在模块初始化期间触发错误的状态变更）
        self._is_initialized = False
        self._initialization_time: Optional[datetime] = None
        
        # 消息记录（用于延迟记录原则）
        self._current_messages: List[Dict] = []  # 当前提取的消息列表（按顺序）
        self._sent_count: int = 0  # 已发送的消息数量
        
        # 稳定检测（用于确认生成中真正消失）
        self._stable_start_time: Optional[datetime] = None  # 稳定开始时间
        self._stable_duration: float = 2.0  # 稳定持续时间（秒）
        self._generating_state_started: bool = False  # 生成状态是否已开始
        
        # 消息定位（用于过滤发送消息前的内容）
        self._last_received_line: Optional[int] = None  # 记录接收消息的行号
        
        # 订阅者列表
        self._subscribers: List[Callable] = []
        
        # 状态变更回调
        self._on_state_change: Optional[Callable] = None
        
        # 消息去重（确保相同内容的消息只发送一次）
        self._sent_message_hashes: set = set()  # 已发送消息的内容哈希集合
        
        # 统计信息
        self.stats = {
            "messages_extracted": 0,
            "messages_filtered": 0,
            "check_count": 0,
            "state_changes": 0
        }
    
    @property
    def state(self) -> IFlowState:
        """当前 iflow 状态"""
        return self._state
    
    @property
    def generating_duration(self) -> int:
        """生成持续时间（秒）"""
        if self._state == IFlowState.GENERATING and self._generating_start_time:
            return int((datetime.now() - self._generating_start_time).total_seconds())
        return 0
    
    async def start(self) -> None:
        """启动监控器"""
        if self._running:
            logger.warning("[IFlowMonitor] Monitor already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("[IFlowMonitor] Monitor started")
    
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
        
        logger.info("[IFlowMonitor] Monitor stopped")
    
    def subscribe(self, callback: Callable) -> None:
        """订阅 iflow 输出消息
        
        Args:
            callback: 回调函数，接收 OutboundMessage
        """
        self._subscribers.append(callback)
        logger.debug(f"[IFlowMonitor] Added subscriber, total: {len(self._subscribers)}")
    
    def unsubscribe(self, callback: Callable) -> None:
        """取消订阅
        
        Args:
            callback: 回调函数
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.debug(f"[IFlowMonitor] Removed subscriber, total: {len(self._subscribers)}")
    
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
                logger.error(f"[IFlowMonitor] Monitor loop error: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _check(self) -> None:
        """检查新消息和状态（优化后的策略）
        
        根据当前状态选择不同的检查模式：
        - IDLE 状态：轻量级检查，只扫描 20 行，只检查"生成中"
        - GENERATING 状态：完整检查，扫描 1000 行，提取所有消息
        """
        # 如果是 IDLE 状态，使用轻量级检查
        if self._state == IFlowState.IDLE:
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
                    logger.debug(f"[IFlowMonitor] 开始初始化计时")

                initialization_duration = (datetime.now() - self._initialization_time).total_seconds()
                if initialization_duration < 3.0:
                    # 仍在初始化期间，跳过状态检测和消息提取
                    logger.debug(f"[IFlowMonitor] 初始化期间，跳过检查 ({initialization_duration:.1f}s / 3.0s)")
                    return
                else:
                    # 初始化完成
                    self._is_initialized = True
                    logger.info(f"[IFlowMonitor] 初始化完成 ({initialization_duration:.1f}s)")

            # 先检测状态变化（在所有逻辑之前）
            await self._check_state(output)
            
            # 检测生成状态
            is_generating = self._detect_generating(output)
            
            # 超时保护：如果 generating 状态持续超过 5 分钟，强制变回 idle
            if self._state == IFlowState.GENERATING:
                duration = self.generating_duration
                if duration > 300:  # 5 分钟
                    logger.warning(f"[IFlowMonitor] Generating 状态持续超过 5 分钟（{duration}s），强制变回 idle")
                    self._state = IFlowState.IDLE
                    self._generating_start_time = None
                    self._stable_start_time = None
                    self._generating_state_started = False
                    self._interaction_complete = False
                    self._current_messages = []
                    self._sent_count = 0
                    logger.info(f"[IFlowMonitor] State changed: {IFlowState.GENERATING.value} -> {IFlowState.IDLE.value} (timeout)")
            
            # 提取所有消息（只在GENERATING状态下提取）
            current_messages = []
            if self._state == IFlowState.GENERATING:
                current_messages = self._extract_messages(output)
                logger.debug(f"[IFlowMonitor] GENERATING state: extracted {len(current_messages)} messages")
            elif self._state == IFlowState.IDLE:
                logger.debug(f"[IFlowMonitor] IDLE state: not extracting messages")
            
            # 调试日志：输出关键状态
            if self.stats["check_count"] % 5 == 0:  # 每5次检查输出一次
                logger.debug(f"[IFlowMonitor] Check #{self.stats['check_count']}: state={self._state.value}, is_generating={is_generating}, "
                           f"sent_count={self._sent_count}, "
                           f"current_count={len(current_messages)}")
                
                # 输出前几行用于调试
                lines = output.split('\n')
                logger.debug(f"[IFlowMonitor] Output preview (first 10 lines):")
                for i, line in enumerate(lines[:10]):
                    logger.debug(f"  Line {i}: {line[:80]}")
            
            # 延迟记录原则：找出新增的消息并记录发送
            if self._state == IFlowState.GENERATING:
                # 找出新增的消息（从已发送数量开始）
                new_messages = current_messages[self._sent_count:]
                
                if len(new_messages) > 0:
                    logger.debug(f"[IFlowMonitor] 检测到 {len(new_messages)} 个新消息，已发送={self._sent_count}，当前总数={len(current_messages)}")
                    
                    # 按顺序记录并发送新增的消息
                    for i, message in enumerate(new_messages):
                        # 记录消息
                        self._sent_count += 1
                        marker_symbol = message['marker_type']
                        logger.debug(f"[IFlowMonitor] 记录消息 #{self._sent_count}: {marker_symbol} - {message['content'][:50]}...")
                        
                        # 立即发送
                        await self._send_message(message)
                        logger.info(f"[IFlowMonitor] 发送消息 #{self._sent_count}: {marker_symbol} - {message['content'][:50]}...")
                
                # 更新当前消息列表
                self._current_messages = current_messages
                
                # 检测生成中是否消失
                if not is_generating:
                    # 生成中消失，开始稳定检测
                    if self._stable_start_time is None:
                        self._stable_start_time = datetime.now()
                        logger.debug(f"[IFlowMonitor] 检测到生成中消失，开始稳定计时...")
                    else:
                        stable_time = (datetime.now() - self._stable_start_time).total_seconds()
                        logger.debug(f"[IFlowMonitor] 等待稳定... ({stable_time:.1f}秒 / {self._stable_duration}秒)")
                        
                        if stable_time >= self._stable_duration:
                            # 稳定2秒，确认结束
                            logger.info(f"[IFlowMonitor] 生成中稳定消失（{stable_time:.1f}s），交互结束")
                            
                            # 记录剩余的所有消息
                            remaining_messages = current_messages[self._sent_count:]
                            
                            if len(remaining_messages) > 0:
                                logger.debug(f"[IFlowMonitor] 记录剩余的 {len(remaining_messages)} 个消息")
                                
                                # 按顺序记录并发送剩余的消息
                                for message in remaining_messages:
                                    # 记录消息
                                    self._sent_count += 1
                                    marker_symbol = message['marker_type']
                                    logger.debug(f"[IFlowMonitor] 记录消息 #{self._sent_count}: {marker_symbol} - {message['content'][:50]}...")
                                    
                                    # 立即发送
                                    await self._send_message(message)
                                    logger.info(f"[IFlowMonitor] 发送消息 #{self._sent_count}: {marker_symbol} - {message['content'][:50]}...")
                            
                            # 清空缓存
                            self._current_messages = []
                            self._sent_count = 0
                            self._stable_start_time = None
                            
                            # 清理去重集合（为下一次对话准备）
                            self._sent_message_hashes.clear()
                            
                            # 切换到IDLE状态（将在_check_state中触发）
            elif self._state == IFlowState.IDLE:
                # IDLE状态：只检查，不记录
                pass
            
            # 生成中存在，处理新增的消息
            elif is_generating:
                if self._stable_start_time is not None:
                    logger.debug(f"[IFlowMonitor] 生成中重新出现，重置稳定计时器")
                    self._stable_start_time = None
                
                # 生成中重新出现，重置交互完成标志
                if self._interaction_complete:
                    logger.debug(f"[IFlowMonitor] 生成中重新出现，重置交互完成标志")
                    self._interaction_complete = False
            
        except Exception as e:
            logger.error(f"[IFlowMonitor] Error checking messages: {e}", exc_info=True)
    
    async def _check_lightweight(self) -> None:
        """轻量级检查（IDLE 状态）
        
        只检查是否出现"生成中"关键词，不进行消息提取。
        用于 IDLE 状态下的高效监控。
        """
        self.stats["check_count"] += 1

        try:
            # 只扫描最近的 20 行（轻量级模式）
            output = await self.controller.capture_output(lines=self.LINES_LIGHTWEIGHT)

            if not output:
                return

            # 检查是否出现"生成中"
            is_generating = self._detect_generating(output)

            if is_generating:
                # 检测到"生成中"，需要执行一次完整的检查来初始化状态
                # 先更新状态
                self._state = IFlowState.GENERATING
                self._generating_start_time = datetime.now()
                self.stats["state_changes"] += 1
                logger.info(f"[IFlowMonitor] State changed: IDLE -> GENERATING (lightweight detected)")
                
                # 获取完整输出进行消息提取
                full_output = await self.controller.capture_output(lines=self.LINES_FULL)
                
                # 状态变更和消息处理（直接调用，避免递归）
                await self._check_state(full_output)
                
                logger.debug(f"[IFlowMonitor] Check #{self.stats['check_count']}: lightweight -> full")
            else:
                # 仍然在 IDLE 状态，只检查，不记录
                logger.debug(f"[IFlowMonitor] IDLE mode: no generating detected")
                
                if self.stats["check_count"] % 60 == 0:  # 每30秒输出一次（0.5s间隔）
                    logger.debug(f"[IFlowMonitor] Check #{self.stats['check_count']}: lightweight mode (idle)")

        except Exception as e:
            logger.error(f"[IFlowMonitor] Error in lightweight check: {e}", exc_info=True)
    
    async def _check_state(self, output: str) -> None:
        """检测 iflow 状态
        
        检查界面中是否显示"生成中"。
        
        Args:
            output: tmux 输出
        """
        # 检测 "生成中" 关键字
        is_generating = self._detect_generating(output)
        
        old_state = self._state
        
        if is_generating and self._state == IFlowState.IDLE:
            # 状态变更：空闲 -> 生成中
            self._state = IFlowState.GENERATING
            self._generating_start_time = datetime.now()
            self.stats["state_changes"] += 1
            logger.info(f"[IFlowMonitor] State changed: {old_state.value} -> {self._state.value}")
            
            # 生成状态首次开始，清空缓存
            logger.debug(f"[IFlowMonitor] 生成状态首次开始，清空缓存")
            self._current_messages = []
            self._sent_count = 0
            self._generating_state_started = True
            
            # 触发状态变更回调
            if self._on_state_change:
                await self._call_callback(self._on_state_change, old_state, self._state)
        
        elif not is_generating and self._state == IFlowState.GENERATING:
            # 状态变更：生成中 -> 空闲
            logger.debug(f"[IFlowMonitor] 检测到状态可能变更: is_generating={is_generating}, state={self._state.value}")

            # 如果生成中已经消失，等待稳定检测（在_check方法中处理）
            # 不要在这里直接变回 idle，让 _check() 中的稳定检测逻辑处理
            logger.debug(f"[IFlowMonitor] 等待稳定检测...")
    
    def _detect_generating(self, output: str) -> bool:
        """检测是否处于生成中状态

        状态检测原则：
        - 只检测"生成中"关键词是否存在
        - 必须是 iflow 的状态指示器，不是用户消息
        - 状态指示器特征：包含"生成中"和"按esc取消"或时间（如"6m 37s"）
        
        状态指示器示例：
        - "⠦ 生成中 6m 37s ... (按esc取消)" - 正在生成回复
        - "生成中 6m 37s ... (按esc取消)" - 正在生成回复（无符号）

        检测方式：
        - 查找包含"生成中"的行
        - 必须包含状态指示器特征（"按esc取消"或时间）
        - 排除"上下文剩余"等无关行

        Args:
            output: tmux 输出

        Returns:
            是否处于生成中
        """
        lines = output.split('\n')

        # 检查每一行是否包含"生成中"
        for line in lines:
            line_stripped = line.strip()

            # 检测"生成中"关键词
            if '生成中' in line_stripped:
                # 排除"上下文剩余"等无关行
                if '上下文剩余' in line_stripped:
                    continue
                
                # 必须是状态指示器，包含以下特征之一：
                # 1. "按esc取消"
                # 2. 时间（如 "6m 37s"）
                # 3. 生成进度（如 "6m 37s"）
                if ('按esc取消' in line_stripped or 
                    re.search(r'\d+[ms]\s*\d+s', line_stripped) or  # 时间模式
                    re.search(r'生成中\s+\d+[ms]', line_stripped)):  # 生成中 + 时间
                    return True

        return False
    
    def _extract_received_message(self, lines: List[str]) -> tuple[Optional[str], Optional[int]]:
        """从 tmux 输出中提取发给 iflow 的消息
        
        发送给 iflow 的消息特征：
        - 以 `>` 开头的行
        - 例如：`> 用户的消息内容`
        
        排除的行（iflow 提示符）：
        - `输入消息或@文件路径`
        - 其他 iflow 系统提示
        
        Args:
            lines: tmux 输出行列表
        
        Returns:
            (消息内容, 消息行号) 或 (None, None)
        """
        # iflow 提示符关键词（用于过滤）
        iflow_prompt_keywords = ['输入消息', '@文件路径']
        
        # 从下往上扫描，找到最后一个用户发送的消息
        for i in range(len(lines) - 1, -1, -1):
            line_stripped = lines[i].strip()
            
            if line_stripped.startswith('>'):
                # 提取消息内容（去掉 `>` 前缀）
                message_content = line_stripped[1:].strip()
                
                # 检查是否是 iflow 提示符
                is_prompt = False
                for keyword in iflow_prompt_keywords:
                    if keyword in message_content:
                        is_prompt = True
                        break
                
                if is_prompt:
                    # 这是 iflow 提示符，继续往上查找
                    logger.debug(f"[IFlowMonitor] 跳过 iflow 提示符: {line_stripped}")
                    continue
                
                # 找到了用户消息
                return message_content, i
        
        return None, None
    
    def _is_tui_line(self, line: str) -> bool:
        """判断一行是否为 TUI 界面内容
        
        TUI 界面特征：
        - 包含 "生成中"
        - 包含 "思考:"
        - 包含 "上下文剩余"
        - 是分隔符（---, ══, ────）
        
        Args:
            line: 要检查的行
        
        Returns:
            是否为 TUI 界面行
        """
        # 如果行包含消息标记，不是TUI界面行
        if '✦' in line or '✻' in line:
            return False
        
        tui_markers = ['生成中', '思考:', '上下文剩余', '---', '══', '────']
        
        line_stripped = line.strip()
        
        # 检查是否包含 TUI 标记
        for marker in tui_markers:
            if marker in line_stripped:
                return True
        
        return False
    
    def _extract_messages(self, output: str) -> List[Dict]:
        """从 tmux 输出中提取消息
        
        提取策略：
        - 提取发给 iflow 的消息并记录行号
        - 过滤掉发送消息前的内容
        - 检测标记行（✦ 或 ✻）
        - 收集标记行及所有后续缩进的内容
        - 跳过 TUI 界面行（生成中、思考、分隔符等）
        
        Args:
            output: tmux 输出
        
        Returns:
            消息列表
        """
        messages = []
        lines = output.split('\n')
        
        logger.debug(f"[IFlowMonitor] _extract_messages: processing {len(lines)} lines")
        
        # 提取发给 iflow 的消息
        received_message, received_line = self._extract_received_message(lines)
        
        # 如果找到了接收消息，记录行号
        if received_line is not None:
            # 只更新_last_received_line，不过滤内容
            # 这样可以确保新消息被正确提取
            self._last_received_line = received_line
            logger.debug(f"[IFlowMonitor] 找到接收消息: {received_message[:50]}..., 行号: {received_line}")
        
        # 不过滤内容，扫描整个输出提取消息
        # 这样可以确保所有消息都被正确提取
        
        logger.debug(f"[IFlowMonitor] _extract_messages: scanning {len(lines)} lines for markers (✦, ✻)")
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # 跳过 TUI 界面行
            if self._is_tui_line(line):
                logger.debug(f"[IFlowMonitor] 跳过 TUI 界面行: {line[:50]}")
                continue
            
            # 检查标记行
            has_diamond = '✦' in line
            has_thought = '✻' in line
            
            if has_diamond or has_thought:
                # 提取标记内容（去掉标记符号）
                marker_type = '✦' if has_diamond else '✻'
                marker_content = line.replace('✦', '').replace('✻', '').strip()
                
                logger.debug(f"[IFlowMonitor] Line {i}: 检测到标记行")
                logger.debug(f"  Raw line: {line}")
                logger.debug(f"  Marker type: {marker_type}")
                logger.debug(f"  Marker content: {marker_content}")
                
                if not marker_content:
                    logger.debug(f"[IFlowMonitor] 跳过空标记内容")
                    continue
                
                # 收集后续行（消息延续）
                content_lines = [marker_content]
                
                # 遍历后续行，收集缩进的内容
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    next_line_stripped = next_line.strip()
                    
                    # 跳过 TUI 界面行
                    if self._is_tui_line(next_line):
                        logger.debug(f"[IFlowMonitor] 跳过 TUI 界面行: {next_line[:50]}")
                        continue
                    
                    # 如果遇到新的标记行，停止
                    if '✦' in next_line or '✻' in next_line:
                        logger.debug(f"[IFlowMonitor] 遇到新标记，停止收集: {next_line[:50]}")
                        break
                    
                    # 跳过空行
                    if not next_line_stripped:
                        logger.debug(f"[IFlowMonitor] 跳过空行")
                        continue
                    
                    # 关键修复：检查行是否以空格开头（表示是前一条消息的延续）
                    if next_line.startswith('  ') or next_line.startswith('\t'):
                        # 这是前一条消息的延续
                        logger.debug(f"[IFlowMonitor] 收集缩进行: {next_line[:80]}")
                        content_lines.append(next_line_stripped)
                    else:
                        # 非缩进行，停止收集
                        logger.debug(f"[IFlowMonitor] 遇到非缩进行，停止收集: {next_line[:50]}")
                        break
                
                # 合并内容
                full_content = '\n'.join(content_lines)
                
                logger.debug(f"[IFlowMonitor] 提取的消息内容: {full_content[:100]}...")
                
                messages.append({
                    'content': full_content,
                    'marker_type': marker_type,
                    'marker_only': marker_content
                })
        
        logger.debug(f"[IFlowMonitor] _extract_messages: extracted {len(messages)} messages total")
        return messages
    
    async def _send_message(self, message_data: Dict) -> None:
        """发送消息
        
        Args:
            message_data: 消息数据字典
        """
        marker_symbol = message_data.get('marker_type', '')  # 标记符号（支持任意符号）
        full_content = message_data.get('content', '')
        
        # 计算内容哈希（用于去重）
        content_hash = hashlib.md5(full_content.encode()).hexdigest()
        
        # 检查消息是否已发送（去重）
        if content_hash in self._sent_message_hashes:
            logger.debug(f"[IFlowMonitor] 消息已发送，跳过（内容哈希相同）")
            return
        
        # 添加到已发送集合
        self._sent_message_hashes.add(content_hash)
        
        # 限制集合大小（防止内存泄漏）
        if len(self._sent_message_hashes) > 1000:
            # 保留最近的 500 个哈希值
            self._sent_message_hashes = set(list(self._sent_message_hashes)[-500:])
        
        # 创建出站消息
        msg_type = MessageType.REPLY if marker_symbol == '✦' else MessageType.OTHER
        
        message = OutboundMessage(
            type=msg_type,
            content=full_content,
            receiver="",
            scope="all",  # 由IFlowModule根据reply_mode过滤
            timestamp=datetime.now(),
            metadata={'marker_symbol': marker_symbol}
        )
        
        # 通知订阅者
        await self._notify_subscribers(message)
        self.stats["messages_extracted"] += 1
        
        logger.info(f"[IFlowMonitor] 发送消息: {full_content[:50]}")
    
    def _clean_message_content(self, content: str) -> str:
        """清理消息内容，移除 iflow UI 元素
        
        Args:
            content: 原始消息内容
            
        Returns:
            清理后的消息内容
        """
        if not content:
            return content
        
        # 分隔符列表（iflow UI 元素）
        separators = [
            '---',
            '══',
            '────────',
            '────────────────',
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
            return cleaned_content
        
        return content.strip()
    
    async def _notify_subscribers(self, message: OutboundMessage) -> None:
        """通知所有订阅者
        
        Args:
            message: 出站消息
        """
        for callback in self._subscribers:
            try:
                await self._call_callback(callback, message)
            except Exception as e:
                logger.error(f"[IFlowMonitor] Subscriber callback error: {e}", exc_info=True)
    
    async def _call_callback(self, callback: Callable, *args) -> None:
        """调用回调函数
    
        Args:
            callback: 回调函数
            args: 参数
        """
        try:
            logger.debug(f"[IFlowMonitor] Calling callback: {callback.__name__ if hasattr(callback, '__name__') else 'unknown'}")
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
            logger.debug(f"[IFlowMonitor] Callback completed successfully")
        except Exception as e:
            logger.error(f"[IFlowMonitor] Callback error: {e}", exc_info=True)    
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
        logger.info("[IFlowMonitor] Stats reset")
    
    @property
    def running(self) -> bool:
        """监控器是否运行中"""
        return self._running