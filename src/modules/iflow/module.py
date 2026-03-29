"""
IFlow Module

完整的 iflow 管理模块，集成 Controller、Monitor、MessageStore 和 Logger。
模块实例与 tmux/iflow 生命周期同步。
支持状态管理、消息归属、订阅通知。
"""

import asyncio
import logging
import uuid
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass

from ...core.base import BaseModule
from ...core.message import Message, MessageContent, MessageType as CoreMessageType
from .controller import IFlowController
from .monitor import IFlowMonitor, IFlowState, OutboundMessage, MessageType
from .session_manager import SessionManager
from .logger import InteractionLogger
from .message_store import MessageStore, MessageStatus


logger = logging.getLogger(__name__)


@dataclass
class Response:
    """响应消息"""
    success: bool
    error: Optional[str] = None
    message: str = ""
    duration: int = 0
    message_id: Optional[str] = None


class IFlowModule(BaseModule):
    """iflow 模块

    完整的 iflow 管理，包括启动、停止、消息注入、输出监控、状态管理、
    消息归属、订阅通知和交互记录。

    模块实例与 tmux/iflow 生命周期同步：
    - 启动模块 → 自动创建 tmux 会话并启动 iflow
    - 停止模块 → 自动停止 iflow 并销毁 tmux 会话
    """

    def __init__(
        self,
        module_id: Optional[str] = None,
        tmux_session: Optional[str] = None,
        model: str = "kimi-k2.5",
        workspace: str = "~/.iflow",
        auto_restart: bool = True,
        log_interactions: bool = True,
        log_dir: str = "logs/interactions"
    ):
        """初始化 iflow 模块

        Args:
            module_id: 模块唯一标识符，如果为 None 则自动生成
            tmux_session: tmux 会话名称，如果为 None 则自动分配
            model: iflow 模型
            workspace: iflow 工作目录
            auto_restart: iflow 异常时是否自动重启
            log_interactions: 是否记录交互
            log_dir: 交互日志目录
        """
        self._temp_module_id = module_id
        super().__init__(module_id or "iflow_placeholder")

        self._tmux_session_param = tmux_session
        self.model = model
        self.workspace = workspace
        self.auto_restart = auto_restart
        self.log_interactions_enabled = log_interactions
        self.log_dir = log_dir

        # 创建控制器（会话名称延迟分配）
        self.controller = IFlowController(self._tmux_session_param)
        self.monitor = IFlowMonitor(self.controller)
        
        # 设置 controller 对 module 的引用，让 monitor 可以访问 message_store
        self.controller.module = self

        # 创建会话管理器
        self.session_manager = SessionManager(self.workspace)
        
        # 消息库
        self.message_store = MessageStore()
        
        # 交互记录器（延迟初始化）
        self.logger: Optional[InteractionLogger] = None
        
        # 订阅者列表
        self._subscribers: list = []
        
        # 消息发送钩子（用于测试）
        self._message_sent_hook: Optional[Callable] = None
        
        # iflow 就绪状态
        self._is_ready: bool = False
        
        # 回复模式：reply_only（仅回复✦标记的消息）或 all_messages（全部消息）
        self.reply_mode: str = "reply_only"
        
        # 模块管理器引用（用于状态上报）
        self.manager: Optional[Any] = None
        
        # 设置监控器回调
        self.monitor.subscribe(self._on_monitor_message)
        self.monitor.set_state_change_callback(self._on_state_change)
    
    @property
    def tmux_session(self) -> str:
        """获取 tmux 会话名称"""
        return self.controller.tmux_session
    
    @property
    def state(self) -> IFlowState:
        """获取当前 iflow 状态"""
        return self.monitor.state
    
    @property
    def generating_duration(self) -> int:
        """获取生成持续时间（秒）"""
        return self.monitor.generating_duration
    
    async def _on_start(self) -> None:
        """启动时的钩子方法"""
        # 分配会话名称
        session_name = await self.controller.assign_session_name()
        
        # 更新 module_id
        if self._temp_module_id is None:
            self.module_id = f"iflow_{session_name}"
        
        # 初始化交互记录器
        self.logger = InteractionLogger(
            module_id=self.module_id,
            log_dir=self.log_dir,
            enabled=self.log_interactions_enabled
        )
        
        logger.info(f"[{self.module_id}] 启动 iflow 模块 (tmux: {session_name})")
        
        # 开始交互记录会话
        if self.logger:
            self.logger.start_session()
        
        # 创建 tmux 会话并启动 iflow
        success = await self.controller.start_iflow(self.model)
        if not success:
            raise RuntimeError(f"[{self.module_id}] 启动 iflow 失败")
        
        # 启动监控器
        await self.monitor.start()
        
        logger.info(f"[{self.module_id}] iflow 模块启动完成")
    
    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        logger.info(f"[{self.module_id}] 停止 iflow 模块")
        
        # 停止监控器
        await self.monitor.stop()
        
        # 销毁 tmux 会话
        await self.controller.destroy_session()
        
        # 保存交互记录
        if self.logger:
            self.logger.save_session()
        
        logger.info(f"[{self.module_id}] iflow 模块已停止")
    
    async def _on_receive(self, message) -> None:
        """接收消息时的钩子方法
        
        Args:
            message: 接收到的消息
        """
        logger.info(f"[{self.module_id}] 收到来自消息总线的消息")
        # 从消息中提取信息
        content = getattr(message, 'content', None)
        if hasattr(content, 'text'):
            content = content.text
        elif content is None:
            content = str(message) if message else ""
        
        # 提取来源、范围和聊天ID
        chat_id = getattr(message, "chat_id", "") or ""
        user_id = getattr(message, "user_id", "") or ""
        is_group = getattr(message, "is_group", False)
        
        # 提取来源和范围
        source = getattr(message, 'from_module', '') or ""
        scope = "reply_only"
        
        # 从 metadata 中获取 scope
        if hasattr(message, 'metadata') and message.metadata:
            scope = message.metadata.get('scope', 'reply_only')
        
        # 发送消息
        response = await self.send(content, source, scope, chat_id, user_id, is_group)
        
        if not response.success:
            logger.warning(f"[{self.module_id}] 消息发送失败: {response.message}")
            # 发送错误消息回来源模块
            if source and self.message_bus:
                error_message = Message(
                    id=Message.generate_id(),
                    type=CoreMessageType.TEXT,
                    content=MessageContent(type=CoreMessageType.TEXT, text=f"❌ {response.message}"),
                    from_module=self.module_id,
                    metadata={
                        "msg_type": "error",
                        "chat_id": chat_id,
                        "is_group": is_group,
                        "receiver": source
                    }
                )
                await self.send_to_bus(error_message)
                logger.info(f"[{self.module_id}] 已发送错误消息到 {source}: {response.message}")
    
    # ==================== 公共接口 ====================
    
    @property
    def is_ready(self) -> bool:
        """检查 iflow 是否就绪（同步版本，用于快速检查）"""
        return self._is_ready
    
    async def wait_for_ready(self, timeout: float = 60.0) -> bool:
        """等待 iflow 完全就绪
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            是否就绪
        """
        logger.info(f"[{self.module_id}] 等待 iflow 就绪...")
        
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.controller.check_iflow_ready():
                self._is_ready = True
                logger.info(f"[{self.module_id}] iflow 已就绪")
                return True
            await asyncio.sleep(1)
        
        logger.warning(f"[{self.module_id}] 等待 iflow 就绪超时 ({timeout}秒)")
        return False
    
    async def send(
        self,
        content: str,
        source: str = "",
        scope: str = "reply_only",
        chat_id: str = "",
        user_id: str = "",
        is_group: bool = False
    ) -> Response:
        """发送消息到 iflow
        
        Args:
            content: 消息内容
            source: 来源模块 ID（可选）
            scope: 返回范围（reply_only / all）
            chat_id: 聊天 ID（可选）
            user_id: 用户 ID（可选）
            is_group: 是否为群聊（可选）
            
        Returns:
            Response: 成功或拒绝响应
        """
        # 检查 iflow 状态
        if self.state == IFlowState.GENERATING:
            duration = self.generating_duration
            logger.warning(f"[{self.module_id}] iflow 生成中，拒绝消息 (duration={duration}s)")
            return Response(
                success=False,
                error="iflow_generating",
                message=f"iflow 生成中，请稍后再试",
                duration=duration
            )
        
        # 生成消息 ID
        message_id = str(uuid.uuid4())[:8]
        
        # 记录到消息库
        self.message_store.add(
            metadata={"chat_id": chat_id, "user_id": user_id, "is_group": is_group},
            message_id=message_id,
            source=source,
            content=content,
            scope=scope
        )
        
        # 更新状态为处理中
        self.message_store.update_status(message_id, MessageStatus.PROCESSING)
        
        # 注入到 iflow
        success = await self.controller.send_message(content)
        
        # 从 tmux 捕获实际发送的消息（用于交互记录）
        # 这样可以确保日志准确反映 tmux 中实际发生的内容
        if success and self.logger:
            sent_content = await self.controller.capture_sent_message()
            if sent_content:
                self.logger.log_sent(sent_content)
            else:
                # 降级：使用原始内容（不应该发生）
                logger.warning(f"[{self.module_id}] 无法从 tmux 捕获发送的消息，使用原始内容")
                self.logger.log_sent(content)
        
        if success:
            logger.info(f"[{self.module_id}] 消息已注入 (id={message_id}, source={source})")
            return Response(
                success=True,
                message="消息已发送",
                message_id=message_id
            )
        else:
            logger.error(f"[{self.module_id}] 消息注入失败")
            self.message_store.update_status(message_id, MessageStatus.COMPLETED)
            return Response(
                success=False,
                error="send_failed",
                message="消息发送失败"
            )
    
    def subscribe(self, callback: Callable) -> None:
        """订阅 iflow 输出消息
        
        Args:
            callback: 回调函数，接收 OutboundMessage
        """
        self._subscribers.append(callback)
        logger.debug(f"[{self.module_id}] Added subscriber, total: {len(self._subscribers)}")
    
    def unsubscribe(self, callback: Callable) -> None:
        """取消订阅
        
        Args:
            callback: 回调函数
        """
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.debug(f"[{self.module_id}] Removed subscriber, total: {len(self._subscribers)}")
    
    def set_message_sent_hook(self, hook: Callable) -> None:
        """设置消息发送钩子（用于测试）
        
        Args:
            hook: 钩子函数，接收 Message 对象
        """
        self._message_sent_hook = hook
        logger.debug(f"[{self.module_id}] 消息发送钩子已设置")
    
    async def get_status(self) -> dict:
        """获取状态
        
        Returns:
            状态信息字典
        """
        session_info = await self.controller.get_session_info()
        monitor_stats = self.monitor.get_stats()
        session_manager_info = self.session_manager.get_current_session_info()
        logger_stats = self.logger.get_stats() if self.logger else {}
        store_stats = self.message_store.get_stats()
        
        return {
            "module_id": self.module_id,
            "running": self._running,
            "tmux_session": self.tmux_session,
            "model": self.model,
            "workspace": self.workspace,
            "auto_restart": self.auto_restart,
            "iflow_state": self.state.value,
            "generating_duration": self.generating_duration,
            "reply_mode": self.reply_mode,
            "session_info": session_info,
            "monitor_stats": monitor_stats,
            "session_manager_info": session_manager_info,
            "logger_stats": logger_stats,
            "message_store": store_stats
        }
    
    def should_send_message(self, message: OutboundMessage) -> bool:
        """判断是否应该发送消息
        
        根据当前回复模式决定是否发送消息
        
        Args:
            message: 出站消息
            
        Returns:
            True表示应该发送，False表示不应该发送
        """
        if self.reply_mode == "all_messages":
            # 全部消息模式，发送所有消息
            return True
        else:
            # reply_only 模式，只发送 ✦ 标记的消息（reply类型）
            return message.type == MessageType.REPLY
    
    def set_reply_mode(self, mode: str) -> bool:
        """设置回复模式
        
        Args:
            mode: 回复模式，"reply_only" 或 "all_messages"
            
        Returns:
            True表示设置成功，False表示设置失败
        """
        if mode in ["reply_only", "all_messages"]:
            self.reply_mode = mode
            logger.info(f"[{self.module_id}] 回复模式已切换为: {mode}")
            return True
        return False
    
    def get_reply_mode(self) -> str:
        """获取当前回复模式
        
        Returns:
            当前回复模式
        """
        return self.reply_mode
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查
        
        Returns:
            健康检查结果
        """
        try:
            # 检查模块是否运行
            if not self._running:
                return {
                    'healthy': False,
                    'reason': 'module_not_running',
                    'details': {'running': False}
                }
            
            # 检查 tmux 会话是否存在
            tmux_exists = await self.controller.check_tmux_session()
            if not tmux_exists:
                return {
                    'healthy': False,
                    'reason': 'tmux_session_not_found',
                    'details': {'tmux_session': self.tmux_session}
                }
            
            # 检查 iflow 是否运行
            iflow_running = await self.controller.check_iflow_running()
            if not iflow_running:
                return {
                    'healthy': False,
                    'reason': 'iflow_not_running',
                    'details': {
                        'tmux_session': self.tmux_session,
                        'iflow_state': self.state.value
                    }
                }
            
            # 检查 iflow 是否就绪（可选，更严格的检查）
            iflow_ready = await self.controller.check_iflow_ready()
            if not iflow_ready:
                return {
                    'healthy': False,
                    'reason': 'iflow_not_ready',
                    'details': {
                        'tmux_session': self.tmux_session,
                        'iflow_state': self.state.value
                    }
                }
            
            # 一切正常
            return {
                'healthy': True,
                'reason': 'ok',
                'details': {
                    'tmux_session': self.tmux_session,
                    'iflow_state': self.state.value,
                    'iflow_running': True
                }
            }
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 健康检查异常: {e}", exc_info=True)
            return {
                'healthy': False,
                'reason': 'check_exception',
                'details': {'error': str(e)}
            }
    
    # ==================== 内部回调 ====================
    
    async def _on_monitor_message(self, message: OutboundMessage) -> None:
        """处理监控器输出的消息
        
        Args:
            message: 出站消息
        """
        logger.info(f"[{self.module_id}] [_on_monitor_message] 收到消息: type={message.type.value}, content={message.content[:80]}...")
        
        # 获取当前消息的来源和范围
        source = self.message_store.get_current_source()
        scope = self.message_store.get_current_scope()
        current_id = self.message_store._current_message_id
        
        logger.debug(f"[{self.module_id}] [_on_monitor_message] current_id={current_id}, source={source}, scope={scope}")
        
        # 如果当前没有处理中的消息（状态变化太快被清空），尝试从最近记录获取
        if not current_id:
            # 获取最近的消息记录（用于恢复消息归属）
            recent = self.message_store.get_recent_processing()
            if recent:
                source = recent.source
                current_id = recent.message_id
                # 恢复当前消息 ID（临时）
                self.message_store._current_message_id = current_id
                logger.debug(f"[{self.module_id}] 恢复消息归属: {current_id}, source={source}")
        
        # 关键修复：使用 reply_mode 而不是 scope 来过滤消息
        # scope 只用于记录消息的来源范围，reply_mode 用于控制发送行为
        if not self.should_send_message(message):
            logger.debug(f"[{self.module_id}] [_on_monitor_message] 过滤消息 (reply_mode={self.reply_mode}, type={message.type.value})")
            return
        
        # 使用 reply_mode 进行过滤（不再使用 scope）
        # reply_mode 是全局设置，通过 /scope 命令控制
        # scope 是消息级别属性，用于记录消息的来源范围
        effective_scope = "reply_only" if self.reply_mode == "reply_only" else "all"
        if effective_scope == "reply_only" and message.type != MessageType.REPLY:
            logger.debug(f"[{self.module_id}] [_on_monitor_message] 过滤非回复消息 (reply_mode={self.reply_mode}, effective_scope={effective_scope})")
            return
        
        # 设置接收方和范围
        # 注意：message.receiver 已经在 monitor 中正确设置为 chat_id
        # 不要用 source（模块 ID）覆盖它
        # 如果 receiver 为空（无来源消息），保持为空用于广播
        message.scope = scope
        
        # 增加回复计数
        count_before = self.message_store.get_reply_count(current_id) if current_id else 0
        self.message_store.increment_reply_count(current_id)
        count_after = self.message_store.get_reply_count(current_id) if current_id else 0
        logger.debug(f"[{self.module_id}] [_on_monitor_message] 回复计数: {count_before} -> {count_after}")
        
        # 记录接收
        if self.logger:
            self.logger.log_received(message.content)
        
        # 发送到消息总线
        # 获取当前消息的 chat_id
        current_record = self.message_store.get_current_message()
        chat_id = current_record.metadata.get("chat_id", "") if current_record else ""
        is_group = current_record.metadata.get("is_group", False) if current_record else False
        
        logger.info(f"[{self.module_id}] [_on_monitor_message] 准备发送: chat_id={chat_id}, is_group={is_group}")
        
        # 创建消息
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=message.content),
            from_module=self.module_id,
            metadata={
                "msg_type": "iflow_reply",
                "reply_type": message.type.value,
                "chat_id": chat_id,
                "is_group": is_group,
                "receiver": message.receiver,
                "scope": message.scope
            }
        )
        
        # 调用钩子（用于测试）- 只在钩子存在且没有消息总线时调用
        # 如果有消息总线，由消息总线负责分发（避免重复）
        if self._message_sent_hook and not self.message_bus:
            try:
                await self._message_sent_hook(msg)
            except Exception as e:
                logger.error(f"[{self.module_id}] 消息发送钩子错误: {e}", exc_info=True)
        
        # 发送到消息总线
        if self.message_bus:
            if message.receiver == "":
                # 无来源消息：广播给所有绑定者
                logger.info(f"[{self.module_id}] 无来源消息，使用广播模式")
                count = await self.message_bus.broadcast_to_bindings(msg, self.module_id)
                logger.debug(f"[{self.module_id}] 已广播 iflow 回复到 {count} 个模块")
            else:
                # 有来源消息：按绑定关系路由
                await self.send_to_bus(msg)
                logger.debug(f"[{self.module_id}] 已发送 iflow 回复到消息总线")

        # 通知订阅者
        await self._notify_subscribers(message)
    
    async def _on_state_change(self, old_state: IFlowState, new_state: IFlowState, duration: int = 0) -> None:
        """处理状态变更

        Args:
            old_state: 旧状态
            new_state: 新状态
            duration: 生成持续时间（秒）
        """
        logger.info(f"[{self.module_id}] State changed: {old_state.value} -> {new_state.value}, duration={duration}s")
        
        # 通知 ModuleManager 更新状态
        if self.manager:
            try:
                self.manager.update_iflow_state(self.module_id, new_state.value, duration)
                logger.debug(f"[{self.module_id}] 已通知 ModuleManager 更新状态")
            except Exception as e:
                logger.error(f"[{self.module_id}] 通知 ModuleManager 更新状态失败: {e}", exc_info=True)

        if new_state == IFlowState.IDLE and old_state == IFlowState.GENERATING:
            # 生成完成
            logger.info(f"[{self.module_id}] [COMPLETION] 检测到生成完成，准备调用 complete_current()")
            logger.debug(f"[{self.module_id}] 当前消息 ID: {self.message_store._current_message_id}")
            completed = self.message_store.complete_current()
            logger.info(f"[{self.module_id}] [COMPLETION] complete_current() 返回: reply_count={completed.reply_count if completed else None}, source={completed.source if completed else None}")

            if completed and completed.source:
                # 只有有来源的消息才发送完成通知
                # 无来源消息由 _flush_buffered_messages 发送，不需要此通知
                # 使用 metadata 中的 chat_id 作为接收方，而不是 source（模块 ID）
                receiver = completed.metadata.get("chat_id", "")
                complete_message = OutboundMessage(
                    type=MessageType.COMPLETE,
                    content=f"【回复结束】本次交互共 {completed.reply_count} 条消息，处理耗时 {duration} 秒",
                    receiver=receiver,
                    scope=completed.scope,
                    metadata={
                        "reply_type": "complete",  # 统一使用 reply_type 字段
                        "reply_count": completed.reply_count,
                        "duration": duration
                    }
                )

                # 通知订阅者
                await self._notify_subscribers(complete_message)

                # 发送到消息总线（与 REPLY/OTHER 消息保持一致）
                msg = Message(
                    id=Message.generate_id(),
                    type=CoreMessageType.TEXT,
                    content=MessageContent(type=CoreMessageType.TEXT, text=complete_message.content),
                    from_module=self.module_id,
                    metadata={
                        "msg_type": "iflow_complete",
                        "reply_type": "complete",  # 统一使用 reply_type 字段
                        "complete_type": complete_message.type.value,
                        "receiver": complete_message.receiver,
                        "scope": complete_message.scope,
                        "reply_count": completed.reply_count,
                        "duration": duration
                    }
                )

                # 调用钩子（用于测试）- 只在钩子存在且没有消息总线时调用
                # 如果有消息总线，由消息总线负责分发（避免重复）
                if self._message_sent_hook and not self.message_bus:
                    try:
                        await self._message_sent_hook(msg)
                    except Exception as e:
                        logger.error(f"[{self.module_id}] 消息发送钩子错误: {e}", exc_info=True)

                # 发送到消息总线
                if self.message_bus:
                    await self.send_to_bus(msg)
                    logger.debug(f"[{self.module_id}] 已发送 iflow 完成通知到消息总线")

                logger.info(f"[{self.module_id}] 消息处理完成: {completed.message_id}, replies={completed.reply_count}")
    
    async def _notify_subscribers(self, message: OutboundMessage) -> None:
        """通知所有订阅者
        
        Args:
            message: 出站消息
        """
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"[{self.module_id}] Subscriber callback error: {e}", exc_info=True)
    
    # ==================== 兼容接口 ====================
    
    def get_monitor_stats(self) -> dict:
        """获取监控统计信息"""
        return self.monitor.get_stats()
    
    def reset_monitor_stats(self) -> None:
        """重置监控统计信息"""
        self.monitor.reset_stats()
    
    def get_status_message(self) -> str:
        """获取状态信息的 Markdown 格式"""
        return self.session_manager.get_status_message()
    
    def get_sessions_message(self, limit: int = 10) -> str:
        """获取会话列表信息的 Markdown 格式"""
        return self.session_manager.get_sessions_message(limit)
    
    def create_new_session(self) -> dict:
        """创建新会话"""
        return self.session_manager.create_new_session()
    
    def get_all_sessions(self, limit: int = 20) -> list:
        """获取所有会话列表"""
        return self.session_manager.get_all_sessions(limit)
    
    def get_interaction_log(self) -> list:
        """获取交互记录"""
        if self.logger:
            return self.logger.get_session_log()
        return []