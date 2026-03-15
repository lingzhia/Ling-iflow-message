"""
模块管理器

负责模块生命周期管理、状态监控、健康检查和消息应答检查。
与 MessageBus 配合，实现控制逻辑和业务逻辑的分离。
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from .bus import MessageBus
from .message import Message


logger = logging.getLogger(__name__)


@dataclass
class ModuleStatus:
    """模块状态"""
    module_id: str
    running: bool = False
    healthy: bool = False
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_check: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class IFlowStatus:
    """IFlow 模块专用状态"""
    module_id: str
    state: str = "idle"  # idle | generating
    generating_start: Optional[datetime] = None
    generating_duration: int = 0
    total_generated: int = 0
    total_rejected: int = 0


class ModuleManager:
    """模块管理器
    
    负责模块生命周期管理、状态监控、健康检查和消息应答检查。
    与 MessageBus 配合，实现控制逻辑和业务逻辑的分离。
    """
    
    def __init__(self, message_bus: MessageBus):
        """初始化模块管理器
        
        Args:
            message_bus: 消息总线实例
        """
        self.message_bus = message_bus
        
        # 模块实例
        self.modules: Dict[str, Any] = {}
        
        # 模块状态
        self.module_states: Dict[str, ModuleStatus] = {}
        
        # IFlow 专用状态
        self.iflow_status: Dict[str, IFlowStatus] = {}
        
        # 组定义
        self.module_groups: Dict[str, List[str]] = {}
        
        # 依赖关系
        self.dependencies: Dict[str, List[str]] = {}
        
        # 健康监控
        self.health_check_interval = 30  # 秒
        self.health_check_task: Optional[asyncio.Task] = None
        
        # 状态变更回调
        self.state_callbacks: List[Callable] = []
    
    # ==================== 模块生命周期管理 ====================
    
    async def create_module(
        self,
        module_type: str,
        module_id: str,
        config: Dict[str, Any]
    ) -> Any:
        """创建模块实例
        
        Args:
            module_type: 模块类型（iflow, wechat, command）
            module_id: 模块 ID
            config: 模块配置
            
        Returns:
            模块实例
        """
        logger.info(f"[ModuleManager] 创建模块: {module_id} (type: {module_type})")
        
        # 根据类型创建模块
        if module_type == "iflow":
            from ..modules.iflow import IFlowModule
            module = IFlowModule(module_id=module_id, **config)
        elif module_type == "wechat":
            from ..modules.wechat import WeChatModule
            module = WeChatModule(module_id=module_id, config=config)
        elif module_type == "command":
            from ..modules.command import CommandHandler
            module = CommandHandler(message_bus=self.message_bus)
        else:
            raise ValueError(f"未知的模块类型: {module_type}")
        
        # 存储模块实例
        self.modules[module_id] = module
        
        # 初始化状态
        self.module_states[module_id] = ModuleStatus(module_id=module_id)
        
        # 如果是 IFlow 模块，初始化专用状态
        if module_type == "iflow":
            self.iflow_status[module_id] = IFlowStatus(module_id=module_id)
        
        return module
    
    async def destroy_module(self, module_id: str) -> bool:
        """销毁模块实例
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否成功
        """
        logger.info(f"[ModuleManager] 销毁模块: {module_id}")
        
        # 检查模块是否存在
        if module_id not in self.modules:
            logger.warning(f"[ModuleManager] 模块不存在: {module_id}")
            return False
        
        # 停止模块
        await self.stop_module(module_id)
        
        # 从消息总线注销
        if self.message_bus:
            self.message_bus.unregister_module(module_id)
        
        # 移除模块
        del self.modules[module_id]
        del self.module_states[module_id]
        
        # 移除 IFlow 状态
        if module_id in self.iflow_status:
            del self.iflow_status[module_id]
        
        logger.info(f"[ModuleManager] 模块已销毁: {module_id}")
        return True
    
    async def start_module(self, module_id: str) -> bool:
        """启动模块
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否成功
        """
        logger.info(f"[ModuleManager] 启动模块: {module_id}")
        
        # 检查模块是否存在
        if module_id not in self.modules:
            logger.error(f"[ModuleManager] 模块不存在: {module_id}")
            return False
        
        module = self.modules[module_id]
        
        try:
            # 启动模块
            await module.start()
            
            # 更新状态
            self.module_states[module_id].running = True
            self.module_states[module_id].started_at = datetime.now()
            self.module_states[module_id].healthy = True
            
            logger.info(f"[ModuleManager] 模块已启动: {module_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ModuleManager] 启动模块失败: {module_id}, {e}", exc_info=True)
            self.module_states[module_id].error = str(e)
            return False
    
    async def stop_module(self, module_id: str) -> bool:
        """停止模块
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否成功
        """
        logger.info(f"[ModuleManager] 停止模块: {module_id}")
        
        # 检查模块是否存在
        if module_id not in self.modules:
            logger.warning(f"[ModuleManager] 模块不存在: {module_id}")
            return False
        
        module = self.modules[module_id]
        
        try:
            # 停止模块
            await module.stop()
            
            # 更新状态
            self.module_states[module_id].running = False
            self.module_states[module_id].stopped_at = datetime.now()
            
            logger.info(f"[ModuleManager] 模块已停止: {module_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ModuleManager] 停止模块失败: {module_id}, {e}", exc_info=True)
            return False
    
    async def restart_module(self, module_id: str) -> bool:
        """重启模块
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否成功
        """
        logger.info(f"[ModuleManager] 重启模块: {module_id}")
        
        # 先停止
        await self.stop_module(module_id)
        
        # 等待一下
        await asyncio.sleep(1)
        
        # 再启动
        return await self.start_module(module_id)
    
    # ==================== 模块注册协调 ====================
    
    async def register_module(self, module_id: str) -> bool:
        """注册模块到消息总线
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否成功
        """
        logger.info(f"[ModuleManager] 注册模块到消息总线: {module_id}")
        
        # 检查模块是否存在
        if module_id not in self.modules:
            logger.error(f"[ModuleManager] 模块不存在: {module_id}")
            return False
        
        module = self.modules[module_id]
        
        # 注册到消息总线
        if self.message_bus:
            self.message_bus.register_module(module)
            logger.info(f"[ModuleManager] 模块已注册: {module_id}")
            return True
        
        logger.warning(f"[ModuleManager] 消息总线未设置，跳过注册: {module_id}")
        return False
    
    async def unregister_module(self, module_id: str) -> bool:
        """从消息总线注销模块
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否成功
        """
        logger.info(f"[ModuleManager] 从消息总线注销模块: {module_id}")
        
        # 从消息总线注销
        if self.message_bus:
            self.message_bus.unregister_module(module_id)
            logger.info(f"[ModuleManager] 模块已注销: {module_id}")
            return True
        
        logger.warning(f"[ModuleManager] 消息总线未设置，跳过注销: {module_id}")
        return False
    
    def set_message_bus_for_module(self, module_id: str) -> None:
        """设置模块的消息总线引用
        
        Args:
            module_id: 模块 ID
        """
        if module_id not in self.modules:
            logger.warning(f"[ModuleManager] 模块不存在: {module_id}")
            return
        
        module = self.modules[module_id]
        if hasattr(module, 'set_message_bus'):
            module.set_message_bus(self.message_bus)
            logger.info(f"[ModuleManager] 已设置消息总线引用: {module_id}")
    
    # ==================== 状态管理 ====================
    
    def get_module_status(self, module_id: str) -> Optional[Dict[str, Any]]:
        """获取模块状态
        
        Args:
            module_id: 模块 ID
            
        Returns:
            状态信息字典
        """
        if module_id not in self.module_states:
            return None
        
        status = self.module_states[module_id]
        return {
            "module_id": status.module_id,
            "running": status.running,
            "healthy": status.healthy,
            "started_at": status.started_at.isoformat() if status.started_at else None,
            "stopped_at": status.stopped_at.isoformat() if status.stopped_at else None,
            "last_check": status.last_check.isoformat() if status.last_check else None,
            "error": status.error
        }
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有模块状态
        
        Returns:
            所有模块的状态信息
        """
        return {
            module_id: self.get_module_status(module_id)
            for module_id in self.module_states.keys()
        }
    
    def is_module_running(self, module_id: str) -> bool:
        """检查模块是否运行
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否运行
        """
        if module_id not in self.module_states:
            return False
        
        return self.module_states[module_id].running
    
    def is_module_healthy(self, module_id: str) -> bool:
        """检查模块是否健康
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否健康
        """
        if module_id not in self.module_states:
            return False
        
        return self.module_states[module_id].healthy
    
    # ==================== 组管理 ====================
    
    def define_group(self, group_name: str, module_ids: List[str]) -> None:
        """定义模块组
        
        Args:
            group_name: 组名
            module_ids: 模块 ID 列表
        """
        logger.info(f"[ModuleManager] 定义组: {group_name}, 模块: {module_ids}")
        self.module_groups[group_name] = module_ids
    
    def get_group_modules(self, group_name: str) -> List[str]:
        """获取组的模块列表
        
        Args:
            group_name: 组名
            
        Returns:
            模块 ID 列表
        """
        return self.module_groups.get(group_name, [])
    
    async def start_group(self, group_name: str) -> Dict[str, bool]:
        """启动组的所有模块
        
        Args:
            group_name: 组名
            
        Returns:
            每个模块的启动结果
        """
        logger.info(f"[ModuleManager] 启动组: {group_name}")
        
        module_ids = self.get_group_modules(group_name)
        if not module_ids:
            logger.warning(f"[ModuleManager] 组不存在或为空: {group_name}")
            return {}
        
        results = {}
        for module_id in module_ids:
            results[module_id] = await self.start_module(module_id)
        
        return results
    
    async def stop_group(self, group_name: str) -> Dict[str, bool]:
        """停止组的所有模块
        
        Args:
            group_name: 组名
            
        Returns:
            每个模块的停止结果
        """
        logger.info(f"[ModuleManager] 停止组: {group_name}")
        
        module_ids = self.get_group_modules(group_name)
        if not module_ids:
            logger.warning(f"[ModuleManager] 组不存在或为空: {group_name}")
            return {}
        
        results = {}
        for module_id in module_ids:
            results[module_id] = await self.stop_module(module_id)
        
        return results
    
    # ==================== 依赖管理 ====================
    
    def add_dependency(self, module_id: str, dependency_id: str) -> None:
        """添加依赖关系
        
        Args:
            module_id: 模块 ID
            dependency_id: 依赖的模块 ID
        """
        if module_id not in self.dependencies:
            self.dependencies[module_id] = []
        
        if dependency_id not in self.dependencies[module_id]:
            self.dependencies[module_id].append(dependency_id)
            logger.info(f"[ModuleManager] 添加依赖: {module_id} -> {dependency_id}")
    
    def get_dependencies(self, module_id: str) -> List[str]:
        """获取模块的依赖列表
        
        Args:
            module_id: 模块 ID
            
        Returns:
            依赖的模块 ID 列表
        """
        return self.dependencies.get(module_id, [])
    
    def check_dependencies(self, module_id: str) -> bool:
        """检查依赖是否满足
        
        Args:
            module_id: 模块 ID
            
        Returns:
            依赖是否满足
        """
        dependencies = self.get_dependencies(module_id)
        
        for dep_id in dependencies:
            if not self.is_module_running(dep_id):
                logger.warning(f"[ModuleManager] 依赖未满足: {module_id} 需要 {dep_id}")
                return False
        
        return True
    
    # ==================== IFlow 状态管理 ====================
    
    def get_iflow_status(self, module_id: str) -> Optional[Dict[str, Any]]:
        """获取 IFlow 模块状态
        
        Args:
            module_id: 模块 ID
            
        Returns:
            IFlow 状态信息
        """
        if module_id not in self.iflow_status:
            return None
        
        status = self.iflow_status[module_id]
        return {
            "module_id": status.module_id,
            "state": status.state,
            "generating_start": status.generating_start.isoformat() if status.generating_start else None,
            "generating_duration": status.generating_duration,
            "total_generated": status.total_generated,
            "total_rejected": status.total_rejected
        }
    
    def is_iflow_available(self, module_id: str) -> bool:
        """检查 IFlow 是否可用（不在生成中）
        
        Args:
            module_id: 模块 ID
            
        Returns:
            是否可用
        """
        if module_id not in self.iflow_status:
            return False
        
        return self.iflow_status[module_id].state == "idle"
    
    def update_iflow_state(self, module_id: str, state: str, duration: int = 0) -> None:
        """更新 IFlow 状态
        
        Args:
            module_id: 模块 ID
            state: 状态（idle | generating）
            duration: 生成持续时间（秒）
        """
        if module_id not in self.iflow_status:
            logger.warning(f"[ModuleManager] IFlow 模块不存在: {module_id}")
            return
        
        iflow_status = self.iflow_status[module_id]
        iflow_status.state = state
        
        if state == "generating":
            iflow_status.generating_start = datetime.now()
        elif state == "idle":
            iflow_status.generating_duration = duration
            iflow_status.total_generated += 1
        
        logger.debug(f"[ModuleManager] IFlow 状态更新: {module_id} -> {state}")
    
    # ==================== 健康监控 ====================
    
    async def start_health_monitor(self) -> None:
        """启动健康监控"""
        if self.health_check_task and not self.health_check_task.done():
            logger.warning("[ModuleManager] 健康监控已在运行")
            return
        
        logger.info("[ModuleManager] 启动健康监控")
        self.health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def stop_health_monitor(self) -> None:
        """停止健康监控"""
        if self.health_check_task:
            logger.info("[ModuleManager] 停止健康监控")
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
            self.health_check_task = None
    
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        logger.info("[ModuleManager] 健康监控循环启动")
        
        try:
            while True:
                for module_id in self.modules.keys():
                    await self._check_module_health(module_id)
                
                await asyncio.sleep(self.health_check_interval)
                
        except asyncio.CancelledError:
            logger.info("[ModuleManager] 健康监控循环已取消")
        except Exception as e:
            logger.error(f"[ModuleManager] 健康监控循环错误: {e}", exc_info=True)
    
    async def _check_module_health(self, module_id: str) -> None:
        """检查单个模块健康
        
        Args:
            module_id: 模块 ID
        """
        module = self.modules.get(module_id)
        if not module:
            return
        
        try:
            # 调用模块的健康检查方法
            if hasattr(module, 'health_check'):
                health_result = await module.health_check()
                healthy = health_result.get('healthy', False)
                
                # 更新状态
                self.module_states[module_id].healthy = healthy
                self.module_states[module_id].last_check = datetime.now()
                
                # 检查状态变更
                old_healthy = self.module_states[module_id].healthy
                if old_healthy != healthy:
                    await self._notify_state_change(module_id, "healthy" if healthy else "unhealthy")
                
            else:
                # 如果没有健康检查方法，默认认为健康
                self.module_states[module_id].healthy = True
                self.module_states[module_id].last_check = datetime.now()
                
        except Exception as e:
            logger.error(f"[ModuleManager] 健康检查失败: {module_id}, {e}")
            self.module_states[module_id].healthy = False
            self.module_states[module_id].error = str(e)
    
    async def _notify_state_change(self, module_id: str, new_state: str) -> None:
        """通知状态变更
        
        Args:
            module_id: 模块 ID
            new_state: 新状态
        """
        for callback in self.state_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(module_id, new_state)
                else:
                    callback(module_id, new_state)
            except Exception as e:
                logger.error(f"[ModuleManager] 状态变更回调失败: {e}")
    
    def on_state_change(self, callback: Callable) -> None:
        """注册状态变更回调
        
        Args:
            callback: 回调函数
        """
        self.state_callbacks.append(callback)
        logger.info(f"[ModuleManager] 状态变更回调已注册，总数: {len(self.state_callbacks)}")