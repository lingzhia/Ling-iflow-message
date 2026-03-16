# ModuleManager 优化方案

## 概述

本文档详细描述了 ModuleManager 模块的优化方案，包括统一错误处理、状态历史记录、模块元数据、版本管理、健康监控配置、性能监控和依赖管理完善。

---

## 优化背景

### 当前状态

ModuleManager 已经实现了核心功能：
- 模块生命周期管理
- 状态管理
- 健康监控
- 依赖管理
- 组管理
- 消息应答检查

### 发现的问题

1. **错误处理不统一**：有些方法返回 `bool`，有些返回 `Dict[str, Any]`
2. **缺少状态历史**：只有当前状态，无法追溯历史
3. **缺少模块元数据**：只有 `module_id`，缺少描述、作者等信息
4. **缺少版本管理**：无法追踪模块更新和兼容性
5. **健康监控固定**：检查间隔固定为 30 秒，无法配置
6. **缺少性能监控**：没有启动时间、处理延迟等指标
7. **依赖管理未充分利用**：有依赖功能但未在实际启动中使用

---

## 优化方案

### 1. 统一错误处理策略

#### 问题
- 返回类型不统一（`bool` vs `Dict[str, Any]`）
- 缺少统一的异常类
- 错误信息不够结构化

#### 解决方案

**1.1 定义异常类**

```python
# src/core/exceptions.py

class ModuleManagerError(Exception):
    """模块管理器基础异常"""
    pass

class ModuleNotFoundError(ModuleManagerError):
    """模块不存在异常"""
    def __init__(self, module_id: str):
        self.module_id = module_id
        super().__init__(f"模块不存在: {module_id}")

class ModuleNotRunningError(ModuleManagerError):
    """模块未运行异常"""
    def __init__(self, module_id: str):
        self.module_id = module_id
        super().__init__(f"模块未运行: {module_id}")

class ModuleUnhealthyError(ModuleManagerError):
    """模块状态异常"""
    def __init__(self, module_id: str):
        self.module_id = module_id
        super().__init__(f"模块状态异常: {module_id}")

class DependencyNotSatisfiedError(ModuleManagerError):
    """依赖不满足异常"""
    def __init__(self, module_id: str, missing_deps: List[str]):
        self.module_id = module_id
        self.missing_deps = missing_deps
        super().__init__(f"依赖不满足: {module_id}, 缺少: {missing_deps}")

class CircularDependencyError(ModuleManagerError):
    """循环依赖异常"""
    def __init__(self, cycle: List[str]):
        self.cycle = cycle
        super().__init__(f"检测到循环依赖: {' -> '.join(cycle)}")

class IFlowNotAvailableError(ModuleManagerError):
    """IFlow 不可用异常"""
    def __init__(self, module_id: str, duration: int):
        self.module_id = module_id
        self.duration = duration
        super().__init__(f"IFlow 正在生成中，已持续 {duration} 秒")
```

**1.2 定义统一返回类型**

```python
from dataclasses import dataclass
from typing import Optional, Any, Dict

@dataclass
class Result:
    """统一返回类型"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def ok(cls, data: Any = None) -> 'Result':
        """创建成功结果"""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str, error_code: str = None, details: Dict = None) -> 'Result':
        """创建失败结果"""
        return cls(success=False, error=error, error_code=error_code, details=details)
```

**1.3 更新方法签名**

```python
# 旧版本
async def start_module(self, module_id: str) -> bool:
    pass

# 新版本
async def start_module(self, module_id: str) -> Result:
    pass

async def stop_module(self, module_id: str) -> Result:
    pass

async def restart_module(self, module_id: str) -> Result:
    pass
```

---

### 2. 状态转换历史记录

#### 问题
- 只有当前状态，无法追溯历史
- 不便于问题排查
- 无法分析状态变更模式

#### 解决方案

**2.1 定义状态转换记录**

```python
@dataclass
class StateTransition:
    """状态转换记录"""
    module_id: str
    from_state: str
    to_state: str
    timestamp: datetime
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
```

**2.2 在 ModuleManager 中添加历史管理**

```python
class ModuleManager:
    def __init__(self, message_bus: MessageBus):
        # ... 现有代码

        # 状态历史
        self.state_history: Dict[str, List[StateTransition]] = {}
        self.max_history_size = 100  # 每个模块最多保留 100 条记录

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

    def get_state_history(self, module_id: str, limit: int = 10) -> List[StateTransition]:
        """获取状态历史"""
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
        """查询状态转换"""
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
```

---

### 3. 模块元数据管理

#### 问题
- 只有 `module_id`，缺少描述、作者、创建时间等元数据
- 不便于模块管理和文档生成
- 缺少模块分类和标签

#### 解决方案

**3.1 定义模块元数据**

```python
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
    tags: List[str]
    category: str
    dependencies: List[str]
```

**3.2 在 ModuleManager 中添加元数据管理**

```python
class ModuleManager:
    def __init__(self, message_bus: MessageBus):
        # ... 现有代码

        # 模块元数据
        self.module_metadata: Dict[str, ModuleMetadata] = {}

    def register_metadata(self, metadata: ModuleMetadata) -> None:
        """注册模块元数据"""
        self.module_metadata[metadata.module_id] = metadata
        logger.info(f"[ModuleManager] 注册元数据: {metadata.module_id}")

    def get_metadata(self, module_id: str) -> Optional[ModuleMetadata]:
        """获取模块元数据"""
        return self.module_metadata.get(module_id)

    def get_metadata_by_tag(self, tag: str) -> List[ModuleMetadata]:
        """按标签获取模块元数据"""
        return [
            m for m in self.module_metadata.values()
            if tag in m.tags
        ]

    def get_metadata_by_category(self, category: str) -> List[ModuleMetadata]:
        """按分类获取模块元数据"""
        return [
            m for m in self.module_metadata.values()
            if m.category == category
        ]

    def list_all_metadata(self) -> List[ModuleMetadata]:
        """列出所有模块元数据"""
        return list(self.module_metadata.values())
```

---

### 4. 模块版本管理

#### 问题
- 没有模块版本信息
- 无法追踪模块更新
- 难以处理兼容性问题

#### 解决方案

**4.1 定义版本信息**

```python
@dataclass
class ModuleVersion:
    """模块版本信息"""
    version: str  # 语义化版本，如 "1.2.3"
    compatible_versions: List[str]  # 兼容的版本列表
    changelog: str  # 变更日志
    released_at: datetime  # 发布时间
```

**4.2 在 ModuleManager 中添加版本管理**

```python
class ModuleManager:
    def __init__(self, message_bus: MessageBus):
        # ... 现有代码

        # 模块版本
        self.module_versions: Dict[str, ModuleVersion] = {}

    def register_version(self, module_id: str, version: ModuleVersion) -> None:
        """注册模块版本"""
        self.module_versions[module_id] = version
        logger.info(f"[ModuleManager] 注册版本: {module_id} v{version.version}")

    def get_version(self, module_id: str) -> Optional[ModuleVersion]:
        """获取模块版本"""
        return self.module_versions.get(module_id)

    def check_compatibility(self, module_id: str, required_version: str) -> bool:
        """检查版本兼容性"""
        version_info = self.get_version(module_id)
        if not version_info:
            return False

        current_version = version_info.version
        return required_version in version_info.compatible_versions

    def can_hot_reload(self, module_id: str, new_version: str) -> bool:
        """检查是否可以热更新"""
        version_info = self.get_version(module_id)
        if not version_info:
            return False

        # 新版本必须在兼容列表中
        return new_version in version_info.compatible_versions
```

---

### 5. 健康监控配置

#### 问题
- 健康检查间隔固定为 30 秒
- 没有配置化的健康检查策略
- 缺少健康检查失败的重试机制

#### 解决方案

**5.1 定义健康检查配置**

```python
@dataclass
class HealthCheckConfig:
    """健康检查配置"""
    interval: int = 30  # 检查间隔（秒）
    max_failures: int = 3  # 最大失败次数
    recovery_delay: int = 5  # 恢复延迟（秒）
    retry_interval: int = 10  # 重试间隔（秒）
    timeout: int = 5  # 健康检查超时（秒）
```

**5.2 更新 ModuleManager**

```python
class ModuleManager:
    def __init__(
        self,
        message_bus: MessageBus,
        health_check_config: HealthCheckConfig = None
    ):
        # ... 现有代码

        # 健康检查配置
        self.health_check_config = health_check_config or HealthCheckConfig()

        # 健康检查失败计数
        self.health_check_failures: Dict[str, int] = {}

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
        """检查单个模块健康"""
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
        except Exception as e:
            logger.error(f"[ModuleManager] 健康检查失败: {module_id}, {e}")
            self.module_states[module_id].healthy = False
            self.module_states[module_id].error = str(e)

    async def _do_health_check(self, module_id: str) -> Dict[str, Any]:
        """执行健康检查"""
        module = self.modules.get(module_id)
        if not module:
            return {'healthy': False}

        if hasattr(module, 'health_check'):
            return await module.health_check()
        else:
            return {'healthy': True}

    async def _auto_recovery(self, module_id: str) -> bool:
        """自动恢复故障模块"""
        logger.info(f"[ModuleManager] 尝试自动恢复模块: {module_id}")

        # 等待恢复延迟
        await asyncio.sleep(self.health_check_config.recovery_delay)

        try:
            # 尝试重启模块
            success = await self.restart_module(module_id)

            if success:
                logger.info(f"[ModuleManager] 模块恢复成功: {module_id}")
                # 重置失败计数
                self.health_check_failures[module_id] = 0
                # 更新状态
                self.module_states[module_id].healthy = True
                self.module_states[module_id].error = None
                return True
            else:
                logger.error(f"[ModuleManager] 模块恢复失败: {module_id}")
                return False

        except Exception as e:
            logger.error(f"[ModuleManager] 自动恢复失败: {module_id}, {e}")
            return False
```

---

### 6. 性能监控

#### 问题
- 没有模块性能指标（启动时间、处理延迟等）
- 没有资源使用监控（内存、CPU）
- 难以发现性能瓶颈

#### 解决方案

**6.1 定义性能指标**

```python
@dataclass
class ModuleMetrics:
    """模块性能指标"""
    module_id: str
    start_time: Optional[datetime] = None  # 启动时间
    startup_duration: float = 0  # 启动耗时（秒）
    message_count: int = 0  # 处理消息数量
    avg_processing_time: float = 0  # 平均处理时间（秒）
    max_processing_time: float = 0  # 最大处理时间（秒）
    error_count: int = 0  # 错误数量
    last_message_time: Optional[datetime] = None  # 最后消息时间

    def update_processing_time(self, duration: float) -> None:
        """更新处理时间"""
        self.message_count += 1
        self.max_processing_time = max(self.max_processing_time, duration)
        self.avg_processing_time = (
            (self.avg_processing_time * (self.message_count - 1) + duration) / self.message_count
        )
```

**6.2 在 ModuleManager 中添加性能监控**

```python
class ModuleManager:
    def __init__(self, message_bus: MessageBus):
        # ... 现有代码

        # 性能指标
        self.module_metrics: Dict[str, ModuleMetrics] = {}

    async def start_module(self, module_id: str) -> Result:
        """启动模块"""
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
            self.module_states[module_id].running = True
            self.module_states[module_id].started_at = datetime.now()
            self.module_states[module_id].healthy = True

            # 记录状态转换
            self._record_state_transition(
                module_id, "stopped", "running",
                reason="module_started",
                details={"startup_duration": startup_duration}
            )

            logger.info(f"[ModuleManager] 模块已启动: {module_id} (耗时: {startup_duration:.2f}s)")
            return Result.ok({"startup_duration": startup_duration})

        except Exception as e:
            logger.error(f"[ModuleManager] 启动模块失败: {module_id}, {e}", exc_info=True)
            self.module_states[module_id].error = str(e)
            return Result.fail(str(e), "START_FAILED", {"module_id": module_id})

    def get_metrics(self, module_id: str) -> Optional[ModuleMetrics]:
        """获取模块性能指标"""
        return self.module_metrics.get(module_id)

    def get_all_metrics(self) -> Dict[str, ModuleMetrics]:
        """获取所有模块性能指标"""
        return self.module_metrics.copy()

    def record_message_processing(self, module_id: str, duration: float, success: bool) -> None:
        """记录消息处理"""
        if module_id not in self.module_metrics:
            return

        metrics = self.module_metrics[module_id]
        metrics.update_processing_time(duration)
        metrics.last_message_time = datetime.now()

        if not success:
            metrics.error_count += 1
```

---

### 7. 完善依赖管理

#### 问题
- 有依赖管理功能但未在实际启动中使用
- 缺少拓扑排序
- 缺少循环依赖检测
- 缺少自动依赖检测

#### 解决方案

**7.1 添加拓扑排序**

```python
def topological_sort(nodes: List[str], dependencies: Dict[str, List[str]]) -> List[str]:
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
```

**7.2 在 ModuleManager 中添加依赖管理增强**

```python
class ModuleManager:
    def __init__(self, message_bus: MessageBus):
        # ... 现有代码

        # 依赖关系
        self.dependencies: Dict[str, List[str]] = {}

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
        return topological_sort(module_ids, deps)

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
```

---

## 实施计划

### 阶段 1：基础优化（1-2 天）

1. **实现异常类定义**
   - 创建 `src/core/exceptions.py`
   - 定义所有异常类

2. **实现统一返回类型**
   - 创建 `Result` 类
   - 更新方法签名

### 阶段 2：状态和元数据（1-2 天）

3. **实现状态历史记录**
   - 定义 `StateTransition`
   - 添加历史记录方法

4. **实现模块元数据**
   - 定义 `ModuleMetadata`
   - 添加元数据管理方法

### 阶段 3：版本和配置（1 天）

5. **实现版本管理**
   - 定义 `ModuleVersion`
   - 添加版本管理方法

6. **实现健康监控配置**
   - 定义 `HealthCheckConfig`
   - 更新健康监控逻辑

### 阶段 4：性能和依赖（1-2 天）

7. **实现性能监控**
   - 定义 `ModuleMetrics`
   - 添加性能指标收集

8. **完善依赖管理**
   - 实现拓扑排序
   - 实现循环依赖检测
   - 实现自动依赖检测

### 阶段 5：测试和文档（1 天）

9. **编写测试用例**
   - 单元测试
   - 集成测试

10. **更新文档**
    - API 文档
    - 使用示例

---

## 测试计划

### 单元测试

- 异常类测试
- Result 类测试
- 状态历史记录测试
- 元数据管理测试
- 版本管理测试
- 健康监控测试
- 性能监控测试
- 依赖管理测试

### 集成测试

- 完整的模块启动流程测试
- 健康监控和自动恢复测试
- 依赖启动顺序测试
- 循环依赖检测测试
- 性能指标收集测试

---

## 总结

通过以上优化，ModuleManager 将具备：

✅ **统一的错误处理** - 所有方法返回统一的结果类型
✅ **完整的状态追溯** - 记录所有状态转换历史
✅ **丰富的模块信息** - 元数据和版本管理
✅ **灵活的监控配置** - 可配置的健康检查策略
✅ **全面的性能监控** - 启动时间、处理延迟等指标
✅ **智能的依赖管理** - 拓扑排序、循环检测、自动检测

这些优化将使 ModuleManager 更加健壮、可维护和易于调试。