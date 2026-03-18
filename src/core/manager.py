"""
模块管理器

负责模块生命周期管理、状态监控、健康检查和消息应答检查。
与 MessageBus 配合，实现控制逻辑和业务逻辑的分离。
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from .bus import MessageBus
from .message import Message
from .result import Result
from .exceptions import (
    ModuleNotFoundError,
    ModuleNotRunningError,
    DependencyNotSatisfiedError,
    CircularDependencyError,
    IFlowNotAvailableError,
    ModuleStartFailedError,
    ModuleStopFailedError,
    ReceiverNotAvailableError,
    MessageBusNotSetError
)


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


@dataclass
class StateTransition:
    """状态转换记录"""
    module_id: str
    from_state: str
    to_state: str
    timestamp: datetime
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ModuleMetadata:
    """模块元数据"""
    module_id: str
    name: str
    description: str
    author: str
    version: str
    created_at: datetime
    updated_at: datetime
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ModuleVersion:
    """模块版本信息"""
    version: str  # 语义化版本，如 "1.2.3"
    compatible_versions: List[str] = field(default_factory=list)  # 兼容的版本列表
    changelog: str = ""  # 变更日志
    released_at: Optional[datetime] = None  # 发布时间


@dataclass
class ModuleMetrics:
    """模块性能指标"""
    module_id: str
    start_time: Optional[datetime] = None  # 启动时间
    startup_duration: float = 0  # 启动耗时(秒)
    message_count: int = 0  # 处理消息数量
    avg_processing_time: float = 0  # 平均处理时间(秒)
    max_processing_time: float = 0  # 最大处理时间(秒)
    error_count: int = 0  # 错误数量
    last_message_time: Optional[datetime] = None  # 最后消息时间

    def update_processing_time(self, duration: float) -> None:
        """更新处理时间

        Args:
            duration: 处理耗时(秒)
        """
        self.message_count += 1
        self.max_processing_time = max(self.max_processing_time, duration)
        self.avg_processing_time = (
            (self.avg_processing_time * (self.message_count - 1) + duration) / self.message_count
        )


@dataclass
class HealthCheckConfig:
    """健康检查配置"""
    interval: int = 30  # 检查间隔(秒)
    max_failures: int = 3  # 最大失败次数
    recovery_delay: int = 5  # 恢复延迟(秒)
    retry_interval: int = 10  # 重试间隔(秒)
    timeout: int = 5  # 健康检查超时(秒)


class ModuleManager:
    """模块管理器
    
    负责模块生命周期管理、状态监控、健康检查和消息应答检查。
    与 MessageBus 配合，实现控制逻辑和业务逻辑的分离。
    """
    
    def __init__(
        self,
        message_bus: MessageBus,
        health_check_config: HealthCheckConfig = None
    ):
        """初始化模块管理器
        
        Args:
            message_bus: 消息总线实例
            health_check_config: 健康检查配置
        """
        self.message_bus = message_bus
        
        # 模块实例
        self.modules: Dict[str, Any] = {}
        
        # 模块状态
        self.module_states: Dict[str, ModuleStatus] = {}
        
        # IFlow 专用状态
        self.iflow_status: Dict[str, IFlowStatus] = {}
        
        # 依赖关系
        self.dependencies: Dict[str, List[str]] = {}
        
        # 健康监控配置
        self.health_check_config = health_check_config or HealthCheckConfig()
        
        # 健康监控
        self.health_check_task: Optional[asyncio.Task] = None
        
        # 健康检查失败计数
        self.health_check_failures: Dict[str, int] = {}
        
        # 状态变更回调
        self.state_callbacks: List[Callable] = []
        
        # 状态历史
        self.state_history: Dict[str, List[StateTransition]] = {}
        self.max_history_size = 100  # 每个模块最多保留 100 条记录
        
        # 模块元数据
        self.module_metadata: Dict[str, ModuleMetadata] = {}
        
        # 模块版本
        self.module_versions: Dict[str, ModuleVersion] = {}
        
        # 性能指标
        self.module_metrics: Dict[str, ModuleMetrics] = {}
    
    # ==================== 模块生命周期管理 ====================
    
    async def create_module(
        self,
        module_type: str,
        module_id: str,
        config: Dict[str, Any]
    ) -> Any:
        """创建模块实例

        Args:
            module_type: 模块类型(iflow, wechat, simulator, command)
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
            from ..modules.channel import WeChatChannel
            module = WeChatChannel(module_id=module_id, config=config)
        elif module_type == "simulator":
            from ..modules.channel import SimulatorChannel
            module = SimulatorChannel(module_id=module_id, config=config)
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
    
    async def start_module(self, module_id: str) -> Result:
        """启动模块
        
        Args:
            module_id: 模块 ID
            
        Returns:
            启动结果
        """
        logger.info(f"[ModuleManager] 启动模块: {module_id}")

        # 检查模块是否存在
        if module_id not in self.modules:
            error = f"模块不存在: {module_id}"
            logger.error(f"[ModuleManager] {error}")
            return Result.fail(error, "MODULE_NOT_FOUND", {"module_id": module_id})

        module = self.modules[module_id]

        try:
            # 记录启动开始时间
            start_time = time.time()

            # 启动模块
            await module.start()

            # 计算启动耗时
            startup_duration = time.time() - start_time

            # 初始化性能指标
            self.module_metrics[module_id] = ModuleMetrics(
                module_id=module_id,
                start_time=datetime.now(),
                startup_duration=startup_duration
            )

            # 更新状态
            old_running = self.module_states[module_id].running
            self.module_states[module_id].running = True
            self.module_states[module_id].started_at = datetime.now()
            self.module_states[module_id].healthy = True

            # 记录状态转换
            self._record_state_transition(
                module_id, "stopped" if not old_running else "running", "running",
                reason="module_started",
                details={"startup_duration": startup_duration}
            )

            logger.info(f"[ModuleManager] 模块已启动: {module_id} (耗时: {startup_duration:.2f}s)")
            return Result.ok({"startup_duration": startup_duration})

        except Exception as e:
            logger.error(f"[ModuleManager] 启动模块失败: {module_id}, {e}", exc_info=True)
            self.module_states[module_id].error = str(e)
            return Result.fail(str(e), "START_FAILED", {"module_id": module_id})
    
    async def stop_module(self, module_id: str) -> Result:
        """停止模块
        
        Args:
            module_id: 模块 ID
            
        Returns:
            停止结果
        """
        logger.info(f"[ModuleManager] 停止模块: {module_id}")

        # 检查模块是否存在
        if module_id not in self.modules:
            logger.warning(f"[ModuleManager] 模块不存在: {module_id}")
            return Result.fail(f"模块不存在: {module_id}", "MODULE_NOT_FOUND", {"module_id": module_id})

        module = self.modules[module_id]

        try:
            # 停止模块
            await module.stop()

            # 更新状态
            old_running = self.module_states[module_id].running
            self.module_states[module_id].running = False
            self.module_states[module_id].healthy = False  # 停止的模块不是健康的
            self.module_states[module_id].stopped_at = datetime.now()

            # 记录状态转换
            self._record_state_transition(
                module_id, "running", "stopped",
                reason="module_stopped"
            )

            logger.info(f"[ModuleManager] 模块已停止: {module_id}")
            return Result.ok()

        except Exception as e:
            logger.error(f"[ModuleManager] 停止模块失败: {module_id}, {e}", exc_info=True)
            return Result.fail(str(e), "STOP_FAILED", {"module_id": module_id})
    
    async def restart_module(self, module_id: str) -> Result:
        """重启模块
        
        Args:
            module_id: 模块 ID
            
        Returns:
            重启结果
        """
        logger.info(f"[ModuleManager] 重启模块: {module_id}")

        # 先停止
        stop_result = await self.stop_module(module_id)
        if not stop_result.success:
            return stop_result

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
    
    def get_status(self, module_id: str) -> Optional[ModuleStatus]:
        """获取模块状态（get_module_status 的别名）
        
        Args:
            module_id: 模块 ID
            
        Returns:
            模块状态对象
        """
        if module_id not in self.module_states:
            return None
        
        return self.module_states[module_id]
    
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
    
    # ==================== 状态历史管理 ====================
    
    def _record_state_transition(
        self,
        module_id: str,
        from_state: str,
        to_state: str,
        reason: str = None,
        details: Dict = None
    ) -> None:
        """记录状态转换"""
        if module_id not in self.state_history:
            self.state_history[module_id] = []

        transition = StateTransition(
            module_id=module_id,
            from_state=from_state,
            to_state=to_state,
            timestamp=datetime.now(),
            reason=reason,
            details=details
        )

        self.state_history[module_id].append(transition)

        # 限制历史记录数量
        if len(self.state_history[module_id]) > self.max_history_size:
            self.state_history[module_id] = self.state_history[module_id][-self.max_history_size:]

        logger.debug(f"[ModuleManager] 记录状态转换: {module_id} {from_state} -> {to_state}")

    def get_state_history(self, module_id: str, limit: int = 10) -> List[StateTransition]:
        """获取状态历史
        
        Args:
            module_id: 模块 ID
            limit: 返回的记录数量
            
        Returns:
            状态转换记录列表
        """
        if module_id not in self.state_history:
            return []
        return self.state_history[module_id][-limit:]

    def get_state_transitions(
        self,
        module_id: str,
        from_state: str = None,
        to_state: str = None,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[StateTransition]:
        """查询状态转换
        
        Args:
            module_id: 模块 ID
            from_state: 源状态
            to_state: 目标状态
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            状态转换记录列表
        """
        if module_id not in self.state_history:
            return []

        transitions = self.state_history[module_id]

        if from_state:
            transitions = [t for t in transitions if t.from_state == from_state]
        if to_state:
            transitions = [t for t in transitions if t.to_state == to_state]
        if start_time:
            transitions = [t for t in transitions if t.timestamp >= start_time]
        if end_time:
            transitions = [t for t in transitions if t.timestamp <= end_time]

        return transitions

    # ==================== 模块元数据管理 ====================
    
    def register_metadata(self, metadata: ModuleMetadata) -> None:
        """注册模块元数据
        
        Args:
            metadata: 模块元数据
        """
        self.module_metadata[metadata.module_id] = metadata
        logger.info(f"[ModuleManager] 注册元数据: {metadata.module_id}")

    def get_metadata(self, module_id: str) -> Optional[ModuleMetadata]:
        """获取模块元数据
        
        Args:
            module_id: 模块 ID
            
        Returns:
            模块元数据
        """
        return self.module_metadata.get(module_id)

    def get_metadata_by_tag(self, tag: str) -> List[ModuleMetadata]:
        """按标签获取模块元数据
        
        Args:
            tag: 标签
            
        Returns:
            模块元数据列表
        """
        return [
            m for m in self.module_metadata.values()
            if tag in m.tags
        ]

    def get_metadata_by_category(self, category: str) -> List[ModuleMetadata]:
        """按分类获取模块元数据
        
        Args:
            category: 分类
            
        Returns:
            模块元数据列表
        """
        return [
            m for m in self.module_metadata.values()
            if m.category == category
        ]

    def list_all_metadata(self) -> List[ModuleMetadata]:
        """列出所有模块元数据
        
        Returns:
            模块元数据列表
        """
        return list(self.module_metadata.values())

    # ==================== 模块版本管理 ====================
    
    def register_version(self, module_id: str, version: ModuleVersion) -> None:
        """注册模块版本
        
        Args:
            module_id: 模块 ID
            version: 版本信息
        """
        self.module_versions[module_id] = version
        logger.info(f"[ModuleManager] 注册版本: {module_id} v{version.version}")

    def get_version(self, module_id: str) -> Optional[ModuleVersion]:
        """获取模块版本
        
        Args:
            module_id: 模块 ID
            
        Returns:
            版本信息
        """
        return self.module_versions.get(module_id)

    def check_compatibility(self, module_id: str, required_version: str) -> bool:
        """检查版本兼容性
        
        Args:
            module_id: 模块 ID
            required_version: 需要的版本
            
        Returns:
            是否兼容
        """
        version_info = self.get_version(module_id)
        if not version_info:
            return False

        current_version = version_info.version
        return required_version in version_info.compatible_versions

    def can_hot_reload(self, module_id: str, new_version: str) -> bool:
        """检查是否可以热更新
        
        Args:
            module_id: 模块 ID
            new_version: 新版本号
            
        Returns:
            是否可以热更新
        """
        version_info = self.get_version(module_id)
        if not version_info:
            return False

        # 新版本必须在兼容列表中
        return new_version in version_info.compatible_versions

    # ==================== 性能监控 ====================
    
    def get_metrics(self, module_id: str) -> Optional[ModuleMetrics]:
        """获取模块性能指标
        
        Args:
            module_id: 模块 ID
            
        Returns:
            性能指标
        """
        return self.module_metrics.get(module_id)

    def get_all_metrics(self) -> Dict[str, ModuleMetrics]:
        """获取所有模块性能指标
        
        Returns:
            性能指标字典
        """
        return self.module_metrics.copy()

    def record_message_processing(self, module_id: str, duration: float, success: bool) -> None:
        """记录消息处理
        
        Args:
            module_id: 模块 ID
            duration: 处理耗时（秒）
            success: 是否成功
        """
        if module_id not in self.module_metrics:
            return

        metrics = self.module_metrics[module_id]
        metrics.update_processing_time(duration)
        metrics.last_message_time = datetime.now()

        if not success:
            metrics.error_count += 1
    
    
    
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

    def auto_detect_dependencies(self) -> None:
        """自动检测模块依赖"""
        # 基于配置自动检测依赖关系
        # 例如：渠道模块依赖于 CommandHandler
        # IFlow 模块依赖于渠道模块

        # 清空现有依赖
        self.dependencies.clear()

        # 检测 CommandHandler 依赖
        for module_id, module in self.modules.items():
            if hasattr(module, 'command_handler'):
                cmd_id = module.command_handler.module_id
                if cmd_id in self.modules:
                    self.add_dependency(module_id, cmd_id)

        # 检测 IFlow 依赖
        for module_id, module in self.modules.items():
            if module_id.startswith("iflow_"):
                # IFlow 模块依赖于其绑定的渠道
                if self.message_bus:
                    # 找到绑定到此 IFlow 的渠道
                    bindings = self.message_bus.list_bindings()
                    for from_module, to_module in bindings.items():
                        if to_module == module_id:
                            self.add_dependency(module_id, from_module)

        logger.info(f"[ModuleManager] 自动检测依赖: {self.dependencies}")

    def get_startup_order(self, module_ids: List[str] = None) -> List[str]:
        """获取模块启动顺序

        Args:
            module_ids: 要排序的模块列表，如果为 None 则使用所有模块

        Returns:
            排序后的模块列表

        Raises:
            CircularDependencyError: 检测到循环依赖
        """
        if module_ids is None:
            module_ids = list(self.modules.keys())

        # 构建依赖关系
        deps = {}
        for module_id in module_ids:
            deps[module_id] = [
                dep for dep in self.get_dependencies(module_id)
                if dep in module_ids
            ]

        # 执行拓扑排序
        return self._topological_sort(module_ids, deps)

    def _topological_sort(self, nodes: List[str], dependencies: Dict[str, List[str]]) -> List[str]:
        """拓扑排序

        Args:
            nodes: 节点列表
            dependencies: 依赖关系 {node: [dependencies]}

        Returns:
            排序后的节点列表

        Raises:
            CircularDependencyError: 检测到循环依赖
        """
        # 计算入度
        in_degree = {node: 0 for node in nodes}
        for node in nodes:
            for dep in dependencies.get(node, []):
                if dep in in_degree:
                    in_degree[node] += 1

        # 找出入度为 0 的节点
        queue = [node for node in nodes if in_degree[node] == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # 减少依赖此节点的其他节点的入度
            for other_node in nodes:
                if node in dependencies.get(other_node, []):
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)

        # 检查是否有循环依赖
        if len(result) != len(nodes):
            # 找出循环依赖
            remaining = set(nodes) - set(result)
            raise CircularDependencyError(list(remaining))

        return result

    async def start_with_dependencies(self, module_id: str) -> Result:
        """根据依赖关系启动模块

        Args:
            module_id: 模块 ID

        Returns:
            启动结果
        """
        logger.info(f"[ModuleManager] 根据依赖启动模块: {module_id}")

        # 检查模块是否存在
        if module_id not in self.modules:
            error = f"模块不存在: {module_id}"
            logger.error(f"[ModuleManager] {error}")
            return Result.fail(error, "MODULE_NOT_FOUND", {"module_id": module_id})

        try:
            # 获取启动顺序
            startup_order = self.get_startup_order()

            # 找到目标模块的位置
            try:
                target_index = startup_order.index(module_id)
            except ValueError:
                return Result.fail(
                    f"模块不在启动顺序中: {module_id}",
                    "MODULE_NOT_IN_ORDER",
                    {"module_id": module_id}
                )

            # 启动目标模块及其依赖
            modules_to_start = startup_order[:target_index + 1]

            for m_id in modules_to_start:
                if self.is_module_running(m_id):
                    logger.info(f"[ModuleManager] 模块已在运行: {m_id}")
                    continue

                result = await self.start_module(m_id)
                if not result.success:
                    logger.error(f"[ModuleManager] 依赖启动失败: {m_id}")
                    return result

            return Result.ok({"startup_order": modules_to_start})

        except CircularDependencyError as e:
            logger.error(f"[ModuleManager] 检测到循环依赖: {e.cycle}")
            return Result.fail(
                str(e),
                "CIRCULAR_DEPENDENCY",
                {"cycle": e.cycle}
            )
        except Exception as e:
            logger.error(f"[ModuleManager] 启动失败: {e}", exc_info=True)
            return Result.fail(str(e), "START_FAILED", {"module_id": module_id})

    def check_circular_dependencies(self) -> List[List[str]]:
        """检查循环依赖

        Returns:
            循环依赖列表
        """
        cycles = []

        try:
            # 尝试获取启动顺序，如果失败则捕获循环依赖
            self.get_startup_order()
        except CircularDependencyError as e:
            cycles.append(e.cycle)

        return cycles

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
        """检查 IFlow 是否可用(不在生成中)
        
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
            state: 状态(idle | generating)
            duration: 生成持续时间(秒)
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
    
    # ==================== 接收方状态检查 ====================
    
    async def check_receiver_availability(
        self,
        receiver_id: str
    ) -> Dict[str, Any]:
        """检查接收方是否可用
        
        Args:
            receiver_id: 接收方模块 ID
            
        Returns:
            {
                "available": bool,      # 是否可用
                "error": str,          # 错误类型（不可用时）
                "error_message": str,  # 错误消息（不可用时）
                "details": dict        # 详细信息
            }
        """
        # 检查模块是否存在
        if receiver_id not in self.modules:
            return {
                "available": False,
                "error": "MODULE_NOT_FOUND",
                "error_message": f"接收方模块不存在: {receiver_id}",
                "details": {}
            }
        
        # 检查模块是否运行
        if not self.is_module_running(receiver_id):
            return {
                "available": False,
                "error": "MODULE_NOT_RUNNING",
                "error_message": "接收方模块未运行",
                "details": {}
            }
        
        # 检查模块是否健康
        if not self.is_module_healthy(receiver_id):
            status = self.get_module_status(receiver_id)
            error_msg = status.get("error", "未知错误")
            return {
                "available": False,
                "error": "MODULE_UNHEALTHY",
                "error_message": f"接收方模块异常: {error_msg}",
                "details": {"status": status}
            }
        
        # 特殊处理：IFlow 模块检查生成状态
        if receiver_id.startswith("iflow_"):
            if not self.is_iflow_available(receiver_id):
                iflow_status = self.get_iflow_status(receiver_id)
                duration = iflow_status.get("generating_duration", 0)
                return {
                    "available": False,
                    "error": "IFLOW_GENERATING",
                    "error_message": f"iflow 正在生成中，已持续 {duration} 秒，请稍后再试",
                    "details": {
                        "state": iflow_status.get("state"),
                        "duration": duration
                    }
                }
        
        # 状态正常
        return {
            "available": True,
            "error": None,
            "error_message": None,
            "details": {}
        }
    
    def generate_error_message(
        self,
        error_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成错误消息
        
        Args:
            error_type: 错误类型
            details: 详细信息
            
        Returns:
            格式化的错误消息
        """
        details = details or {}
        
        error_messages = {
            "MODULE_NOT_FOUND": "接收方模块不存在",
            "MODULE_NOT_RUNNING": "接收方模块未运行",
            "MODULE_UNHEALTHY": f"接收方模块状态异常: {details.get('status', {}).get('error', '未知错误')}",
            "IFLOW_GENERATING": f"iflow 正在生成中，已持续 {details.get('duration', 0)} 秒，请稍后再试"
        }
        
        error_message = error_messages.get(error_type, "未知错误")
        
        return f"❌ 消息发送失败\n\n{error_message}"
    
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

                await asyncio.sleep(self.health_check_config.interval)

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
            # 使用超时
            health_result = await asyncio.wait_for(
                self._do_health_check(module_id),
                timeout=self.health_check_config.timeout
            )

            healthy = health_result.get('healthy', False)

            # 如果健康，重置失败计数
            if healthy:
                self.health_check_failures[module_id] = 0

            # 更新状态
            self.module_states[module_id].healthy = healthy
            self.module_states[module_id].last_check = datetime.now()

            # 检查状态变更
            old_healthy = self.module_states[module_id].healthy
            if old_healthy != healthy:
                await self._notify_state_change(module_id, "healthy" if healthy else "unhealthy")

                # 如果模块变为不健康，增加失败计数
                if not healthy:
                    self.health_check_failures[module_id] = self.health_check_failures.get(module_id, 0) + 1

                    # 检查是否达到最大失败次数
                    if self.health_check_failures[module_id] >= self.health_check_config.max_failures:
                        logger.info(f"[ModuleManager] 模块达到最大失败次数，尝试自动恢复: {module_id}")
                        await self._auto_recovery(module_id)

        except asyncio.TimeoutError:
            logger.warning(f"[ModuleManager] 健康检查超时: {module_id}")
            self.module_states[module_id].healthy = False
            self.module_states[module_id].error = "健康检查超时"
        except Exception as e:
            logger.error(f"[ModuleManager] 健康检查失败: {module_id}, {e}")
            self.module_states[module_id].healthy = False
            self.module_states[module_id].error = str(e)

    async def _do_health_check(self, module_id: str) -> Dict[str, Any]:
        """执行健康检查

        Args:
            module_id: 模块 ID

        Returns:
            健康检查结果
        """
        module = self.modules.get(module_id)
        if not module:
            return {
                'healthy': False,
                'reason': 'module_not_found',
                'details': {'module_id': module_id}
            }
        
        # 如果模块有 health_check 方法，调用它
        if hasattr(module, 'health_check'):
            try:
                return await module.health_check()
            except Exception as e:
                logger.error(f"[ModuleManager] 健康检查异常: {module_id}, {e}", exc_info=True)
                return {
                    'healthy': False,
                    'reason': 'health_check_exception',
                    'details': {'error': str(e)}
                }
        else:
            # 对于没有实现 health_check 的模块，检查 _running 状态
            if hasattr(module, 'running'):
                if module.running:
                    return {
                        'healthy': True,
                        'reason': 'no_health_check_but_running',
                        'details': {'module_id': module_id}
                    }
                else:
                    return {
                        'healthy': False,
                        'reason': 'module_not_running',
                        'details': {'module_id': module_id}
                    }
            
            # 默认认为不健康（保守策略）
            logger.warning(f"[ModuleManager] 模块 {module_id} 未实现 health_check，标记为不健康")
            return {
                'healthy': False,
                'reason': 'no_health_check_implementation',
                'details': {'module_id': module_id}
            }

    async def _auto_recovery(self, module_id: str) -> bool:
        """自动恢复故障模块

        Args:
            module_id: 模块 ID

        Returns:
            是否恢复成功
        """
        logger.info(f"[ModuleManager] 尝试自动恢复模块: {module_id}")
        
        # 先停止模块
        stop_result = await self.stop_module(module_id)
        if not stop_result.success:
            logger.error(f"[ModuleManager] 停止模块失败: {module_id}")
            return False
        
        # 等待恢复延迟
        await asyncio.sleep(self.health_check_config.recovery_delay)
        
        # 重启模块
        start_result = await self.start_module(module_id)
        
        if start_result.success:
            logger.info(f"[ModuleManager] 模块恢复成功: {module_id}")
            # 重置失败计数
            self.health_check_failures[module_id] = 0
            # 更新状态
            self.module_states[module_id].healthy = True
            self.module_states[module_id].error = None
            # 通知状态变更
            await self._notify_state_change(module_id, "healthy")
            return True
        else:
            logger.error(f"[ModuleManager] 模块恢复失败: {module_id}")
            # 增加失败计数
            self.health_check_failures[module_id] = \
                self.health_check_failures.get(module_id, 0) + 1
            
            # 如果超过最大失败次数的 2 倍，停止监控
            max_failures = self.health_check_config.max_failures * 2
            if self.health_check_failures[module_id] >= max_failures:
                logger.error(
                    f"[ModuleManager] 模块恢复失败次数过多，停止自动恢复: {module_id} "
                    f"(失败次数: {self.health_check_failures[module_id]}, 最大: {max_failures})"
                )
                self.module_states[module_id].healthy = False
                self.module_states[module_id].error = "auto_recovery_failed_too_many_times"
                # 通知状态变更
                await self._notify_state_change(module_id, "unhealthy")
            
            return False

    async def _notify_state_change(
        self,
        module_id: str,
        new_state: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """通知状态变更

        Args:
            module_id: 模块 ID
            new_state: 新状态
            details: 详细信息
        """
        details = details or {}
        
        logger.info(f"[ModuleManager] 状态变更: {module_id} -> {new_state}")
        
        # 记录状态转换
        from_state = self.module_states[module_id].running
        self._record_state_transition(
            module_id,
            "running" if from_state else "stopped",
            new_state,
            reason="health_check",
            details=details
        )
        
        # 更新状态
        if new_state == "healthy":
            self.module_states[module_id].healthy = True
            self.module_states[module_id].error = None
        elif new_state == "unhealthy":
            self.module_states[module_id].healthy = False
            self.module_states[module_id].error = details.get('reason', 'unknown')
        
        # 调用回调函数
        if self.state_callbacks:
            logger.debug(f"[ModuleManager] 调用 {len(self.state_callbacks)} 个状态回调")
            for callback in self.state_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(module_id, new_state, details)
                    else:
                        callback(module_id, new_state, details)
                except Exception as e:
                    logger.error(f"[ModuleManager] 状态回调失败: {e}", exc_info=True)
        else:
            logger.debug(f"[ModuleManager] 没有状态回调函数")

    def on_state_change(self, callback: Callable) -> None:
        """注册状态变更回调
        
        Args:
            callback: 回调函数
        """
        self.state_callbacks.append(callback)
        logger.info(f"[ModuleManager] 状态变更回调已注册，总数: {len(self.state_callbacks)}")
    
    # ==================== 消息应答检查 ====================
    
    def check_receiver(self, module_id: str) -> Dict[str, Any]:
        """检查接收方状态
        
        Args:
            module_id: 接收方模块 ID
            
        Returns:
            检查结果字典
        """
        # 检查模块是否存在
        if module_id not in self.modules:
            return {
                "exists": False,
                "available": False,
                "reason": "receiver_not_found",
                "message": f"接收方模块不存在: {module_id}"
            }
        
        # 检查模块是否运行
        if not self.is_module_running(module_id):
            return {
                "exists": True,
                "available": False,
                "reason": "receiver_not_running",
                "message": f"接收方模块未运行: {module_id}"
            }
        
        # 检查模块是否健康
        if not self.is_module_healthy(module_id):
            return {
                "exists": True,
                "available": False,
                "reason": "receiver_unhealthy",
                "message": f"接收方模块状态异常: {module_id}"
            }
        
        # 特殊检查：IFlow 生成中状态
        if module_id.startswith("iflow_"):
            # 如果模块在 iflow_status 中，检查状态
            if module_id in self.iflow_status:
                if not self.is_iflow_available(module_id):
                    iflow_status = self.get_iflow_status(module_id)
                    duration = iflow_status.get("generating_duration", 0)
                    return {
                        "exists": True,
                        "available": False,
                        "reason": "iflow_generating",
                        "message": f"iflow 正在生成中，已持续 {duration} 秒",
                        "duration": duration
                    }
            else:
                # 如果模块不在 iflow_status 中，初始化状态为 idle
                self.update_iflow_state(module_id, "idle")
                logger.debug(f"[ModuleManager] 初始化 iflow 模块状态: {module_id} -> idle")
        
        # 接收方可用
        return {
            "exists": True,
            "available": True,
            "reason": "ok",
            "message": "接收方可用"
        }
    
    def generate_error_response(self, error_type: str, **kwargs) -> Dict[str, Any]:
        """生成错误响应
        
        Args:
            error_type: 错误类型
            **kwargs: 额外参数
            
        Returns:
            错误响应字典
        """
        error_messages = {
            "sender_not_found": "发送方模块不存在",
            "receiver_not_found": "接收方模块不存在",
            "receiver_not_running": "接收方模块未运行",
            "receiver_unhealthy": "接收方模块状态异常",
            "iflow_generating": "iflow 正在生成中，请稍后再试"
        }
        
        base_response = {
            "success": False,
            "error": error_type,
            "message": error_messages.get(error_type, "未知错误")
        }
        
        # 添加额外参数
        base_response.update(kwargs)
        
        return base_response
    
    async def send_with_check(self, message: Message) -> Dict[str, Any]:
        """发送消息并检查接收方状态
        
        Args:
            message: 消息对象
            
        Returns:
            发送结果
        """
        # 检查发送方
        sender_id = message.from_module
        if sender_id:
            sender_check = self.check_receiver(sender_id)
            if not sender_check["exists"]:
                return {
                    "success": False,
                    "error": "sender_not_found",
                    "message": sender_check["message"],
                    "route_info": {
                        "from": sender_id,
                        "to": None,
                        "action": "sender_not_found"
                    }
                }
        
        # 确定接收方
        target_module_id = message.to_module
        
        # 如果没有指定接收方，使用绑定关系
        if not target_module_id and sender_id:
            target_module_id = self.message_bus.bindings.get(sender_id)
        
        # 检查接收方
        if target_module_id:
            receiver_check = self.check_receiver(target_module_id)
            
            if not receiver_check["available"]:
                # 接收方不可用
                return {
                    "success": False,
                    "error": receiver_check["reason"],
                    "message": receiver_check["message"],
                    "route_info": {
                        "from": sender_id,
                        "to": target_module_id,
                        "action": receiver_check["reason"]
                    },
                    "duration": receiver_check.get("duration", 0)
                }
        
        # 正常路由到消息总线
        try:
            if target_module_id:
                # 直接发送到目标模块
                if target_module_id in self.modules:
                    target_module = self.modules[target_module_id]
                    await target_module.receive(message)
                    return {
                        "success": True,
                        "message": "消息已发送",
                        "route_info": {
                            "from": sender_id,
                            "to": target_module_id,
                            "action": "routed"
                        }
                    }
                else:
                    # 模块不存在
                    return {
                        "success": False,
                        "error": "target_not_found",
                        "message": f"目标模块不存在: {target_module_id}",
                        "route_info": {
                            "from": sender_id,
                            "to": target_module_id,
                            "action": "target_not_found"
                        }
                    }
            else:
                # 使用消息总线路由
                if self.message_bus:
                    await self.message_bus.route(message)
                    return {
                        "success": True,
                        "message": "消息已发送",
                        "route_info": {
                            "from": sender_id,
                            "to": None,
                            "action": "routed_via_bus"
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": "no_message_bus",
                        "message": "消息总线未设置"
                    }
                    
        except Exception as e:
            logger.error(f"[ModuleManager] 发送消息失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": "send_error",
                "message": f"发送失败: {str(e)}",
                "route_info": {
                    "from": sender_id,
                    "to": target_module_id,
                    "action": "send_error"
                }
            }
    
    # ==================== 启动顺序控制 ====================
    
    async def start_with_order(self, module_ids: List[str]) -> Dict[str, bool]:
        """按启动顺序启动模块

        Args:
            module_ids: 模块 ID 列表(按启动顺序)

        Returns:
            每个模块的启动结果
        """
        logger.info(f"[ModuleManager] 按顺序启动模块: {module_ids}")

        results = {}

        for module_id in module_ids:
            # 检查依赖是否满足
            if not self.check_dependencies(module_id):
                logger.warning(f"[ModuleManager] 依赖未满足，跳过: {module_id}")
                results[module_id] = False
                continue

            # 启动模块
            result = await self.start_module(module_id)
            results[module_id] = result.success

            if not result.success:
                logger.warning(f"[ModuleManager] 模块启动失败，停止后续启动: {module_id}")
                break

        return results

    async def stop_with_order(self, module_ids: List[str]) -> Dict[str, bool]:
        """按停止顺序停止模块(启动顺序的逆序)

        Args:
            module_ids: 模块 ID 列表(按启动顺序)

        Returns:
            每个模块的停止结果
        """
        logger.info(f"[ModuleManager] 按逆序停止模块: {module_ids[::-1]}")

        results = {}

        # 按逆序停止
        for module_id in reversed(module_ids):
            result = await self.stop_module(module_id)
            results[module_id] = result.success

        return results
