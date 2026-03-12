"""
IFlow Module

完整的 iflow 管理模块，集成 Controller、Monitor、MessageStore 和 Logger。
模块实例与 tmux/iflow 生命周期同步。
支持状态管理、消息归属、订阅通知。
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any

from ...core.base import BaseModule
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
        self.controller = IFlowController(tmux_session)
        self.monitor = IFlowMonitor(self.controller)
        
        # 创建会话管理器
        self.session_manager = SessionManager(workspace)
        
        # 消息库
        self.message_store = MessageStore()
        
        # 交互记录器（延迟初始化）
        self.logger: Optional[InteractionLogger] = None
        
        # 订阅者列表
        self._subscribers: list = []
        
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
        
        # 创建监控任务
        self.create_background_task(self._monitor_task())
        
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
        # 从消息中提取信息
        content = getattr(message, 'content', None)
        if hasattr(content, 'text'):
            content = content.text
        elif content is None:
            content = str(message) if message else ""
        
        # 提取来源和范围
        source = getattr(message, 'from_module', '') or ""
        scope = "reply_only"
        
        # 从 metadata 中获取 scope
        if hasattr(message, 'metadata') and message.metadata:
            scope = message.metadata.get('scope', 'reply_only')
        
        # 发送消息
        response = await self.send(content, source, scope)
        
        if not response.success:
            logger.warning(f"[{self.module_id}] 消息发送失败: {response.message}")
    
    # ==================== 公共接口 ====================
    
    async def send(
        self,
        content: str,
        source: str = "",
        scope: str = "reply_only"
    ) -> Response:
        """发送消息到 iflow
        
        Args:
            content: 消息内容
            source: 来源模块 ID（可选）
            scope: 返回范围（reply_only / all）
            
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
            message_id=message_id,
            source=source,
            content=content,
            scope=scope
        )
        
        # 更新状态为处理中
        self.message_store.update_status(message_id, MessageStatus.PROCESSING)
        
        # 记录发送
        if self.logger:
            self.logger.log_sent(content)
        
        # 注入到 iflow
        success = await self.controller.send_message(content)
        
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
            "session_info": session_info,
            "monitor_stats": monitor_stats,
            "session_manager_info": session_manager_info,
            "logger_stats": logger_stats,
            "message_store": store_stats
        }
    
    # ==================== 内部回调 ====================
    
    async def _on_monitor_message(self, message: OutboundMessage) -> None:
        """处理监控器输出的消息
        
        Args:
            message: 出站消息
        """
        # 获取当前消息的来源和范围
        source = self.message_store.get_current_source()
        scope = self.message_store.get_current_scope()
        
        # 检查 scope 过滤
        if scope == "reply_only" and message.type != MessageType.REPLY:
            logger.debug(f"[{self.module_id}] 过滤非回复消息 (scope={scope})")
            return
        
        # 设置接收方和范围
        message.receiver = source
        message.scope = scope
        
        # 增加回复计数
        self.message_store.increment_reply_count()
        
        # 记录接收
        if self.logger:
            self.logger.log_received(message.content)
        
        # 通知订阅者
        await self._notify_subscribers(message)
    
    async def _on_state_change(self, old_state: IFlowState, new_state: IFlowState) -> None:
        """处理状态变更
        
        Args:
            old_state: 旧状态
            new_state: 新状态
        """
        logger.info(f"[{self.module_id}] State changed: {old_state.value} -> {new_state.value}")
        
        if new_state == IFlowState.IDLE and old_state == IFlowState.GENERATING:
            # 生成完成
            completed = self.message_store.complete_current()
            
            if completed:
                # 发送完成通知
                complete_message = OutboundMessage(
                    type=MessageType.COMPLETE,
                    content=f"【回复结束】本次交互共 {completed.reply_count} 条消息，处理耗时 {self.generating_duration} 秒",
                    receiver=completed.source,
                    scope=completed.scope,
                    metadata={
                        "reply_count": completed.reply_count,
                        "duration": self.generating_duration
                    }
                )
                
                await self._notify_subscribers(complete_message)
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
    
    async def _monitor_task(self) -> None:
        """监控任务（后台运行）"""
        try:
            while self._running:
                # 检查 iflow 状态
                iflow_running = await self.controller.check_iflow_running()
                
                if not iflow_running and self.auto_restart:
                    logger.warning(f"[{self.module_id}] iflow 未运行，尝试重启...")
                    await self.controller.start_iflow(self.model)
                
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{self.module_id}] 监控任务错误: {e}", exc_info=True)
    
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