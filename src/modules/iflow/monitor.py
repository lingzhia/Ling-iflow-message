"""
IFlow Monitor

持续监听 iflow 的 tmux 输出，提取新消息，检测状态变化。
"""

import asyncio
import hashlib
import logging
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
        
        # 消息缓存（用于去重）
        self._processed_hashes: set = set()
        
        # 订阅者列表
        self._subscribers: List[Callable] = []
        
        # 状态变更回调
        self._on_state_change: Optional[Callable] = None
        
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
        """检查新消息和状态"""
        self.stats["check_count"] += 1
        
        try:
            # 捕获 tmux 输出
            output = await self.controller.capture_output(lines=1000)
            
            if not output:
                return
            
            # 提取消息（先于状态检测，确保 reply 在 complete 之前）
            messages = self._extract_messages(output)
            
            # 过滤新消息
            new_messages = self._filter_new_messages(messages)
            
            # 通知订阅者
            for message in new_messages:
                await self._notify_subscribers(message)
                self.stats["messages_extracted"] += 1
            
            # 检测状态变化（在消息通知之后）
            await self._check_state(output)
            
        except Exception as e:
            logger.error(f"[IFlowMonitor] Error checking messages: {e}", exc_info=True)
    
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
            
            # 触发状态变更回调
            if self._on_state_change:
                await self._call_callback(self._on_state_change, old_state, self._state)
        
        elif not is_generating and self._state == IFlowState.GENERATING:
            # 状态变更：生成中 -> 空闲
            # 先计算持续时间（在状态改变之前）
            duration = self.generating_duration
            self._state = IFlowState.IDLE
            self._generating_start_time = None
            self.stats["state_changes"] += 1
            logger.info(f"[IFlowMonitor] State changed: {old_state.value} -> {self._state.value}, duration={duration}s")
            
            # 触发状态变更回调（传递 duration）
            if self._on_state_change:
                await self._call_callback(self._on_state_change, old_state, self._state, duration)
    
    def _detect_generating(self, output: str) -> bool:
        """检测是否处于生成中状态
        
        iflow 状态指示器（位于界面输入框上方）：
        - "⠦ 生成中 XXm XXs ... (按esc取消)" - 正在生成回复（唯一判断标准）
        - "思考: 开启" - 思考模式开启（与是否生成无关）
        
        检测方式：查找包含"生成中"的行，排除其他 UI 元素的干扰。
        
        Args:
            output: tmux 输出
            
        Returns:
            是否处于生成中
        """
        lines = output.split('\n')
        
        # 检查每一行是否包含"生成中"
        for line in lines:
            line_stripped = line.strip()
            # 检测"生成中"标记（排除误判）
            # 格式：⠦ 生成中 6m 37s ... (按esc取消)
            if '生成中' in line_stripped:
                # 排除"上下文剩余"等无关行
                if '上下文剩余' not in line_stripped:
                    return True
        
        return False
    
    def _extract_messages(self, output: str) -> List[Dict]:
        """从 tmux 输出中提取消息
        
        iflow 输出格式：
        - ✦ 回复内容...  (回复消息，标记行)
        - ✻ 思考中...    (思考状态，标记行)
        - 后续缩进行：消息延续内容
        - UI 行（不包含）：生成中、分隔符等
        
        Args:
            output: tmux 输出
            
        Returns:
            消息列表
        """
        messages = []
        lines = output.split('\n')
        
        for i, line in enumerate(lines):
            # 检查标记行
            if '✦' in line or '✻' in line:
                # 提取标记内容（去掉标记符号）
                marker_type = '✦' if '✦' in line else '✻'
                marker_content = line.replace('✦', '').replace('✻', '').strip()
                
                if not marker_content:
                    continue
                
                # 收集后续行（消息延续）
                content_lines = [marker_content]
                
                # 遍历后续行，收集缩进的内容
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    
                    # 如果遇到新的标记行或分隔符，停止
                    if '✦' in next_line or '✻' in next_line or next_line.startswith('---') or next_line.startswith('═') or next_line.startswith('─'):
                        break
                    
                    # 跳过"生成中"等 UI 行
                    if '生成中' in next_line and '按' in next_line:
                        continue
                    
                    # 如果行以缩进开头，认为是消息延续
                    if next_line.startswith('  ') or next_line.startswith('\t'):
                        content_lines.append(next_line.strip())
                    else:
                        # 非缩进行，停止
                        break
                
                # 合并内容
                full_content = '\n'.join(content_lines)
                
                messages.append({
                    'content': full_content,
                    'marker_type': marker_type,
                    'marker_only': marker_content  # 用于哈希计算
                })
        
        return messages
    
    def _filter_new_messages(self, messages: List[dict]) -> List[OutboundMessage]:
        """过滤新消息
        
        Args:
            messages: 消息列表
            
        Returns:
            新消息列表
        """
        new_messages = []
        
        for msg_data in messages:
            # 使用标记行内容进行哈希计算（忽略后续行，避免动态 UI 影响）
            marker_content = msg_data.get('marker_only', msg_data.get('content', ''))
            marker_type = msg_data.get('marker_type', '')
            
            # 计算哈希（只基于标记行，避免动态内容影响）
            msg_hash = hashlib.md5(f"{marker_type}:{marker_content}".encode()).hexdigest()
            
            # 检查是否已处理
            if msg_hash in self._processed_hashes:
                self.stats["messages_filtered"] += 1
                continue
            
            # 添加到已处理集合
            self._processed_hashes.add(msg_hash)
            
            # 限制缓存大小
            if len(self._processed_hashes) > 1000:
                self._processed_hashes = set(list(self._processed_hashes)[-500:])
            
            # 确定消息类型
            msg_type = MessageType.REPLY if marker_type == '✦' else MessageType.OTHER
            
            # 创建出站消息（使用完整内容）
            full_content = msg_data['content']
            
            message = OutboundMessage(
                type=msg_type,
                content=full_content,
                receiver="",  # 由 IFlowModule 设置
                scope="reply_only",  # 由 IFlowModule 设置
                timestamp=datetime.now(),
                metadata={
                    'marker_type': marker_type
                }
            )
            
            new_messages.append(message)
        
        return new_messages
    
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
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
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