# IFlow 模块设计方案

## 概述

IFlowModule 是 iflow CLI 的完整管理模块，负责 iflow 进程的生命周期管理、消息注入、输出监控和会话管理。

## 模块职责

| 职责 | 说明 |
|------|------|
| 进程管理 | 通过 tmux 启动、停止、重启 iflow CLI |
| 消息注入 | 将消息发送到 iflow 进行处理 |
| 输出监控 | 持续监听 iflow 的 tmux 输出，提取回复 |
| 会话管理 | 管理 iflow 的会话文件（session-*.jsonl） |
| 消息清理 | 移除 iflow UI 元素，提取纯净消息 |

## 架构设计

```
IFlowModule
├── IFlowController    # 进程管理
│   ├── tmux 会话管理
│   ├── iflow 启动/停止
│   └── 消息注入
├── IFlowMonitor       # 输出监控
│   ├── tmux 输出捕获
│   ├── 消息提取
│   ├── 消息清理
│   └── 消息去重
└── SessionManager     # 会话管理
    ├── 会话查询
    ├── 会话创建
    └── 会话删除
```

## 组件设计

### 1. IFlowController

**文件**：`src/modules/iflow/controller.py`

**职责**：iflow 进程和 tmux 会话管理

**主要方法**：

| 方法 | 说明 |
|------|------|
| `check_tmux_session()` | 检查 tmux 会话是否存在 |
| `check_iflow_running()` | 检查 iflow CLI 是否运行 |
| `start_iflow(model)` | 启动 iflow CLI |
| `stop_iflow()` | 停止 iflow CLI |
| `send_message(message)` | 发送消息到 iflow |
| `capture_output(lines)` | 捕获 tmux 输出 |
| `get_session_info()` | 获取 tmux 会话信息 |

**实现方式**：
- 使用 `tmux new-session` 创建会话
- 使用 `tmux send-keys` 注入消息
- 使用 `tmux capture-pane` 捕获输出

### 2. IFlowMonitor

**文件**：`src/modules/iflow/monitor.py`

**职责**：持续监听 iflow 输出，提取消息

**主要方法**：

| 方法 | 说明 |
|------|------|
| `start()` | 启动监控 |
| `stop()` | 停止监控 |
| `add_listener(callback)` | 添加消息监听器 |
| `_extract_messages(output)` | 从输出中提取消息 |
| `_filter_new_messages(messages)` | 过滤新消息 |
| `_clean_message_content(content)` | 清理消息内容 |

**消息提取逻辑**：

1. **标记识别**：
   - `✦` 标记：实际回复消息
   - `✻` 标记：思考过程消息（过滤掉）

2. **消息去重**：
   - 使用 MD5 哈希消息内容
   - 维护已处理消息集合
   - 限制缓存大小（最多 1000 条）

3. **消息清理**：
   - 识别分隔符：`---`、`══`、`────────` 等
   - 截取第一个分隔符之前的内容

**监听器模式**：
```python
def add_listener(self, callback: Callable) -> None:
    """添加消息监听器"""
    self._listeners.append(callback)

async def _notify_listeners(self, message: Message) -> None:
    """通知所有监听器"""
    for listener in self._listeners:
        await listener(message)
```

### 3. SessionManager

**文件**：`src/modules/iflow/session_manager.py`

**职责**：管理 iflow 会话文件

**主要方法**：

| 方法 | 说明 |
|------|------|
| `get_latest_session()` | 获取最新会话 |
| `get_all_sessions(limit)` | 获取所有会话列表 |
| `create_new_session()` | 创建新会话（重置状态） |
| `delete_session(session_id)` | 删除指定会话 |
| `get_current_session_info()` | 获取当前会话信息 |
| `get_status_message()` | 获取状态信息（Markdown） |
| `get_sessions_message(limit)` | 获取会话列表信息（Markdown） |

**会话文件格式**：
- 位置：`~/.iflow/projects/{project-path}/session-{id}.jsonl`
- 内容：每行一个 JSON 对象，记录对话历史

**会话状态管理**：
```python
class SessionManager:
    def __init__(self, workspace: str = "~/.iflow"):
        self.workspace = Path(workspace).expanduser()
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
```

## 模块集成

### IFlowModule 类

**文件**：`src/modules/iflow/module.py`

**初始化参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `module_id` | str | 必填 | 模块唯一标识符 |
| `tmux_session` | str | "iflow" | tmux 会话名称 |
| `model` | str | "kimi-k2.5" | iflow 模型 |
| `workspace` | str | "~/.iflow" | iflow 工作目录 |
| `auto_start` | bool | True | 是否自动启动 iflow |

**生命周期方法**：

```python
async def _on_start(self) -> None:
    """启动时的钩子方法"""
    # 1. 自动启动 iflow
    if self.auto_start:
        await self.controller.start_iflow(self.model)
    
    # 2. 启动监控器
    await self.monitor.start()
    
    # 3. 创建监控任务
    self.create_background_task(self._monitor_task())

async def _on_stop(self) -> None:
    """停止时的钩子方法"""
    # 1. 停止监控器
    await self.monitor.stop()
    
    # 2. 可选：停止 iflow
    # await self.controller.stop_iflow()

async def _on_receive(self, message: Message) -> None:
    """接收消息时的钩子方法"""
    # 注入消息到 iflow
    await self.controller.send_message(message.content.text)
```

**后台监控任务**：
```python
async def _monitor_task(self) -> None:
    """监控任务（后台运行）"""
    while self._running:
        # 检查 iflow 状态
        iflow_running = await self.controller.check_iflow_running()
        
        if not iflow_running:
            logger.warning("iflow 未运行，尝试重启...")
            await self.controller.start_iflow(self.model)
        
        await asyncio.sleep(60)
```

## 消息流转

### 入站消息（企业微信 → iflow）

```
WeChatModule 接收企业微信消息
    ↓
MessageBus 路由消息
    ↓
IFlowModule._on_receive() 处理消息
    ↓
IFlowController.send_message() 注入到 tmux
    ↓
iflow CLI 处理消息
```

### 出站消息（iflow → 企业微信）

```
iflow CLI 生成回复
    ↓
IFlowMonitor._check() 捕获 tmux 输出
    ↓
IFlowMonitor._extract_messages() 提取消息
    ↓
IFlowMonitor._filter_new_messages() 过滤和清理
    ↓
IFlowMonitor._notify_listeners() 通知监听器
    ↓
IFlowModule._on_new_message() 处理新消息
    ↓
MessageBus 广播消息
    ↓
WeChatModule 发送到企业微信
```

## 配置示例

```json
{
  "iflow": {
    "enabled": true,
    "tmux_session": "iflow",
    "model": "kimi-k2.5",
    "workspace": "~/.iflow",
    "auto_start": true
  }
}
```

## 使用示例

### 基本使用

```python
from src.modules import IFlowModule
from src.core import MessageBus

# 创建消息总线
bus = MessageBus()

# 创建 iflow 模块
iflow = IFlowModule(
    module_id="iflow_main",
    tmux_session="iflow",
    model="kimi-k2.5"
)

# 注册模块
bus.register_module(iflow)

# 启动模块
await iflow.start()
```

### 会话管理

```python
# 获取状态信息
status_msg = iflow.get_status_message()
print(status_msg)

# 获取会话列表
sessions_msg = iflow.get_sessions_message(limit=10)
print(sessions_msg)

# 创建新会话
result = iflow.create_new_session()
print(result["message"])
```

### 监听 iflow 输出

```python
async def on_iflow_message(message: Message):
    """处理 iflow 回复"""
    print(f"收到 iflow 回复: {message.content}")

# 添加监听器
iflow.monitor.add_listener(on_iflow_message)
```

## 与旧版本对比

| 功能 | 旧版本 | 新版本 |
|------|--------|--------|
| 进程管理 | IFlowController | IFlowController（相同） |
| 输出监控 | SessionMonitor | IFlowMonitor（增强） |
| 会话管理 | SessionManager | SessionManager（相同） |
| 消息清理 | BotIntegration | IFlowMonitor（移入） |
| 回复提取 | BotIntegration | IFlowMonitor（移入） |
| 模块集成 | BotIntegration | IFlowModule（独立模块） |

**改进点**：
1. 模块化：独立模块，职责清晰
2. 消息总线：通过消息总线与其他模块通信
3. 监听器模式：支持多个监听器订阅 iflow 输出
4. 后台任务：自动监控 iflow 状态并重启

## 测试方案

### 单元测试

- IFlowController：tmux 会话管理测试
- IFlowMonitor：消息提取、过滤、清理测试
- SessionManager：会话管理测试

### 集成测试

- iflow 启动/停止测试
- 消息注入测试
- 回复提取测试

### 功能测试

- 使用测试工具验证完整的消息流转
- 验证会话管理功能
- 验证自动重启功能

## 注意事项

1. **tmux 依赖**：系统必须安装 tmux
2. **iflow CLI**：必须先安装 iflow CLI 并登录
3. **工作目录**：默认 `~/.iflow`，确保有读写权限
4. **会话文件**：会话文件会持续增长，需定期清理
5. **监控间隔**：默认 0.5 秒，可根据需要调整
