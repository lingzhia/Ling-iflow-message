"""
IFlow Module

完整的 iflow 管理模块，集成 Controller 和 Monitor。
"""

import asyncio
import logging
from typing import Optional

from ...core.base import BaseModule
from ...core.message import Message, MessageType
from .controller import IFlowController
from .monitor import IFlowMonitor


logger = logging.getLogger(__name__)


class IFlowModule(BaseModule):
    """iflow 模块
    
    完整的 iflow 管理，包括启动、停止、消息注入和输出监控。
    """
    
    def __init__(
        self,
        module_id: str,
        tmux_session: str = "iflow",
        model: str = "kimi-k2.5",
        workspace: str = "~/.iflow",
        auto_start: bool = True
    ):
        """初始化 iflow 模块
        
        Args:
            module_id: 模块唯一标识符
            tmux_session: tmux 会话名称
            model: iflow 模型
            workspace: iflow 工作目录
            auto_start: 是否自动启动 iflow
        """
        super().__init__(module_id)
        
        self.tmux_session = tmux_session
        self.model = model
        self.workspace = workspace
        self.auto_start = auto_start
        
        # 创建控制器和监控器
        self.controller = IFlowController(tmux_session)
        self.monitor = IFlowMonitor(self.controller)
        
        # 添加监听器
        self.monitor.add_listener(self._on_new_message)
    
    async def _on_start(self) -> None:
        """启动时的钩子方法"""
        logger.info(f"[{self.module_id}] 启动 iflow 模块")
        
        # 自动启动 iflow
        if self.auto_start:
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
        
        # 停止 iflow（可选）
        # await self.controller.stop_iflow()
        
        logger.info(f"[{self.module_id}] iflow 模块已停止")
    
    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法
        
        Args:
            message: 接收到的消息
        """
        try:
            # 提取消息内容
            content = message.content.text if message.content else ""
            
            if not content:
                logger.warning(f"[{self.module_id}] 收到空消息")
                return
            
            # 注入到 iflow
            success = await self.controller.send_message(content)
            
            if success:
                logger.info(f"[{self.module_id}] 消息已注入到 iflow")
            else:
                logger.error(f"[{self.module_id}] 消息注入失败")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理消息失败: {e}", exc_info=True)
    
    async def _on_new_message(self, message: Message) -> None:
        """新消息回调
        
        Args:
            message: 新消息
        """
        try:
            # 设置消息来源
            message.from_module = self.module_id
            
            # 广播到消息总线
            if self.message_bus:
                # 发布到主题
                topic = f"iflow.{self.module_id}"
                await self.publish_to_bus(topic, message)
                
                logger.debug(f"[{self.module_id}] 广播消息到主题: {topic}")
            else:
                logger.warning(f"[{self.module_id}] 消息总线未设置，无法广播")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 广播消息失败: {e}", exc_info=True)
    
    async def _monitor_task(self) -> None:
        """监控任务（后台运行）"""
        try:
            while self._running:
                # 检查 iflow 状态
                iflow_running = await self.controller.check_iflow_running()
                
                if not iflow_running:
                    logger.warning(f"[{self.module_id}] iflow 未运行，尝试重启...")
                    await self.controller.start_iflow(self.model)
                
                # 等待一段时间再检查
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{self.module_id}] 监控任务错误: {e}", exc_info=True)
    
    async def start_iflow(self, model: Optional[str] = None) -> bool:
        """启动 iflow
        
        Args:
            model: iflow 模型（可选）
            
        Returns:
            是否启动成功
        """
        if model is None:
            model = self.model
        
        return await self.controller.start_iflow(model)
    
    async def stop_iflow(self) -> bool:
        """停止 iflow
        
        Returns:
            是否停止成功
        """
        return await self.controller.stop_iflow()
    
    async def get_status(self) -> dict:
        """获取状态
        
        Returns:
            状态信息字典
        """
        session_info = await self.controller.get_session_info()
        monitor_stats = self.monitor.get_stats()
        
        return {
            "module_id": self.module_id,
            "running": self._running,
            "tmux_session": self.tmux_session,
            "model": self.model,
            "workspace": self.workspace,
            "session_info": session_info,
            "monitor_stats": monitor_stats
        }
    
    def get_monitor_stats(self) -> dict:
        """获取监控统计信息
        
        Returns:
            统计信息字典
        """
        return self.monitor.get_stats()
    
    def reset_monitor_stats(self) -> None:
        """重置监控统计信息"""
        self.monitor.reset_stats()