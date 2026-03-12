# IFlow 模块设计方案

## 概述

IFlowModule 是 iflow CLI 的完整管理模块，负责 iflow 进程的生命周期管理、消息注入、输出监控、消息分类、状态管理和交互记录。

## 核心理念

**模块实例与 tmux/iflow 生命周期同步**

- 创建 IFlowModule 实例 → 自动创建对应的 tmux 会话并启动 iflow
- 销毁 IFlowModule 实例 → 自动停止 iflow 并销毁 tmux 会话

---

## 模块职责

| 职责 | 说明 |
|------|------|
| 生命周期管理 | 模块实例与 tmux/iflow 同步启动/停止 |
| 进程管理 | 通过 tmux 启动、停止、重启 iflow CLI |
| 状态管理 | 检测 iflow 空闲/生成中状态，生成中时拒绝新消息 |
| 消息注入 | 将消息发送到 iflow 进行处理 |
| 输出监控 | 持续监听 iflow 的 tmux 输出，提取回复 |
| 消息分类 | 按 ✦ 标记分类消息（回复/其他） |
| 消息归属 | 记录消息来源，回复时指定接收方 |
| 交互记录 | 完整记录所有交互信息 |
| 订阅通知 | 通过订阅机制通知关注方 |

---

## iflow 状态管理

### 状态定义

| 状态 | 说明 | 可接受新消息 |
|------|------|-------------|
| **空闲** | iflow 等待输入 | ✅ 是 |
| **生成中** | iflow 正在处理/生成回复 | ❌ 否 |

### 状态判断逻辑

iflow 状态指示器（位于界面底部状态栏）：
- **"生成中"** - 正在生成回复（**唯一判断标准**）
- **"思考: 开启"** - 思考模式开启（**与是否生成无关**）

```
监控 iflow 输出（tmux 界面底部状态栏）
    ↓
┌─────────────────────────────────────┐
│ 检测到 "生成中" 显示                 │
│ → 状态 = 生成中                      │
│ → 记录生成开始时间                   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ "生成中" 不再显示                    │
│ → 状态 = 空闲                        │
│ → 触发回复结束处理                   │
└─────────────────────────────────────┘
```

**注意**：不要将"思考: 开启"作为生成中的判断依据，该标识只表示思考模式开启，与是否正在生成回复无关。

### 生成中拒绝机制

```
收到新消息请求
    ↓
检查 iflow 状态
    ↓
┌─────────────────────────────────────┐
│ 状态 = 生成中                        │
│ → 返回拒绝响应：                     │
│   {                                 │
│     "success": false,               │
│     "error": "iflow_generating",    │
│     "message": "iflow 生成中，       │
│                请稍后再试",          │
│     "duration": 15  # 已持续秒数     │
│   }                                 │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 状态 = 空闲                          │
│ → 正常处理消息                       │
└─────────────────────────────────────┘
```

---

## 消息分类

### 分类标准

| 标记 | 类型 | 说明 |
|------|------|------|
| `✦` | 回复 | 正式回复内容 |
| 其他 | 其他 | ✻ 思考中 + 无标记输出 |

### 返回范围

| scope | 说明 | 返回内容 |
|-------|------|---------|
| `reply_only` | 仅回复（默认） | ✦ 标记的消息 |
| `all` | 全部 | ✦ + 其他所有消息 |

### 记录策略

**所有消息都完整记录保存**，返回时按 scope 过滤。

---

## 消息库设计

### 数据结构

```python
@dataclass
class MessageRecord:
    message_id: str           # 消息唯一标识
    source: str               # 来源（wechat_bot1, tool_xxx, ""表示无来源）
    content: str              # 消息内容
    scope: str                # 返回范围（reply_only / all）
    status: str               # pending / processing / completed
    created_at: datetime      # 创建时间
    processing_at: datetime   # 开始处理时间
    completed_at: datetime    # 完成时间
```

### 来源识别

| 来源 | 说明 | 识别方式 |
|------|------|---------|
| `wechat_bot1` | 企业微信机器人1 | 消息体 `source` 字段 |
| `tool_xxx` | 运维工具 | 消息体 `source` 字段 |
| `""` (空) | 无来源（tmux 直接操作） | 无 `source` 字段或为空 |

---

## iflow 交互实现

### 启动 iflow

参考旧版本实现，直接在创建 tmux 会话时启动 iflow：

```bash
tmux new-session -d -s <session_name> 'iflow --model <model>'
```

**优点**：
- 避免分两步启动可能导致的时序问题
- iflow 直接成为 tmux 会话的主进程

### 发送消息

参考旧版本实现，发送消息前先清除输入框：

```
1. 发送 C-c 清除当前输入框
   tmux send-keys -t <session> C-c
   等待 0.1 秒

2. 发送消息内容（使用 -l 选项逐字发送）
   tmux send-keys -t <session> -l <message>
   等待 0.1 秒

3. 发送回车键
   tmux send-keys -t <session> C-m
```

**为什么要先发送 C-c**：
- iflow 输入框可能已有残留内容
- 确保消息从空白输入框开始
- 避免与之前的输入混淆

### 读取消息

从 tmux 输出中提取消息：

```
1. 捕获最后 1000 行 tmux 输出
   tmux capture-pane -t <session> -S -1000 -p

2. 检测状态：查找"生成中"关键字

3. 提取标记消息（✦ 回复、✻ 思考）
   - 找到标记行
   - 收集标记后的扩展内容
   - 清理 UI 元素
```

---

## 消息处理流程

### 入站流程（外部 → iflow）

```
收到消息
    ↓
解析消息体，提取 source、content、scope
    ↓
检查 iflow 状态
    ↓
┌─────────────────────────────────────┐
│ iflow 生成中                         │
│ → 返回拒绝响应（包含持续时间）       │
│ → 不记录到消息库                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ iflow 空闲                           │
│ → 记录到消息库（status=processing）  │
│ → 记录发送日志                       │
│ → 发送给 iflow                       │
│ → 返回成功响应                       │
└─────────────────────────────────────┘
```

### 出站流程（iflow → 订阅方）

```
监控捕获 iflow 输出
    ↓
提取消息，分类（回复 / 其他）
    ↓
完整记录到交互日志
    ↓
查询消息库，获取当前处理的消息来源
    ↓
构造输出消息：
  - type: reply / other
  - content: 消息内容
  - receiver: source（来源，可能为空）
  - scope: 请求时指定的范围
    ↓
通知所有订阅方
    ↓
订阅方根据 receiver 决定是否处理
```

### 生成结束处理

```
检测到 "生成中" 不再显示
    ↓
查询消息库中 processing 状态的记录
    ↓
┌─────────────────────────────────────┐
│ 找到记录（有来源）                   │
│ → 构造结束消息：                     │
│   {                                 │
│     "type": "complete",             │
│     "receiver": source,             │
│     "duration": XX秒,               │
│     "reply_count": X条              │
│   }                                 │
│ → 通知订阅方                         │
│ → 更新消息库 status=completed        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 未找到记录（无来源）                 │
│ → 所有消息已正常发出                 │
│ → 无需额外处理                       │
└─────────────────────────────────────┘
```

---

## 订阅机制

### 设计理念

- IFlowModule 不负责消息转发
- 通过订阅机制通知关注方
- 订阅方根据消息中的 `receiver` 字段决定是否处理

### 订阅接口

```python
def subscribe(self, callback: Callable) -> None:
    """订阅 iflow 输出消息
    
    Args:
        callback: 回调函数，接收 OutboundMessage
    """

def unsubscribe(self, callback: Callable) -> None:
    """取消订阅"""
```

### 消息通知

```python
async def _notify_subscribers(self, message: dict) -> None:
    """通知所有订阅者
    
    Args:
        message: {
            "type": "reply" | "other" | "complete",
            "content": "消息内容",
            "receiver": "来源模块ID或空",
            "scope": "reply_only" | "all"
        }
    """
    for callback in self._subscribers:
        await callback(message)
```

---

## 架构设计

```
IFlowModule
├── IFlowController    # 进程管理
│   ├── tmux 会话管理
│   ├── iflow 启动/停止
│   ├── 消息注入
│   └── 自动命名检查
├── IFlowMonitor       # 输出监控
│   ├── tmux 输出捕获
│   ├── 状态检测（生成中/空闲）
│   ├── 消息提取与分类
│   └── 消息去重
├── MessageStore       # 消息库
│   ├── 消息记录
│   ├── 来源查询
│   └── 状态更新
├── InteractionLogger  # 交互记录
│   ├── 发送记录
│   ├── 接收记录
│   └── 持久化存储
└── 订阅管理
    ├── 订阅者列表
    └── 消息通知
```

---

## 数据结构汇总

### 入站消息

```python
@dataclass
class InboundMessage:
    message_id: str           # 消息唯一标识
    source: str               # 来源模块 ID（空表示无来源）
    content: str              # 消息内容
    scope: str                # 返回范围（reply_only / all，默认 reply_only）
```

### 出站消息

```python
@dataclass
class OutboundMessage:
    type: str                 # reply / other / complete
    content: str              # 消息内容
    receiver: str             # 接收方（来源模块 ID，空表示无特定接收方）
    scope: str                # 请求时指定的范围
    timestamp: datetime       # 时间戳
```

### 响应消息

```python
@dataclass
class Response:
    success: bool             # 是否成功
    error: str                # 错误类型（如 iflow_generating）
    message: str              # 说明信息
    duration: int             # 生成已持续时间（秒）
```

---

## 关键接口

### 请求接口

```python
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
```

### 订阅接口

```python
def subscribe(self, callback: Callable[[OutboundMessage], None]) -> None:
    """订阅 iflow 输出消息"""

def unsubscribe(self, callback: Callable) -> None:
    """取消订阅"""
```

### 状态查询接口

```python
async def get_status(self) -> dict:
    """获取模块状态
    
    Returns:
        {
            "iflow_state": "idle" | "generating",
            "generating_duration": 0,
            "current_message": {...}
        }
    """
```

---

## 订阅方处理逻辑

订阅方（如 MessageBus）根据 `receiver` 字段处理消息：

```python
async def _on_iflow_message(self, message: OutboundMessage):
    """处理 iflow 输出消息"""
    
    receiver = message.receiver
    
    if receiver:
        # 有明确接收方，转发给对应模块
        target_module = self.modules.get(receiver)
        if target_module:
            await target_module.receive(message)
    else:
        # 无接收方，可选择广播或忽略
        pass
```

---

## 命名规则

### 自动命名机制

- 未显式指定 tmux_session 时，自动分配名称
- 检查当前已存在的 tmux 会话列表
- 按顺序命名：第一个实例叫 iflow1，第二个叫 iflow2，以此类推

---

## 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| module_id | str | 自动生成 | 模块唯一标识符 |
| tmux_session | str | 自动分配 | tmux 会话名称 |
| model | str | kimi-k2.5 | iflow 模型 |
| workspace | str | ~/.iflow | iflow 工作目录 |
| auto_restart | bool | true | iflow 异常时是否自动重启 |
| log_interactions | bool | true | 是否记录交互 |
| log_dir | str | logs/interactions | 交互日志目录 |

---

## 多实例支持

每个 IFlowModule 实例通过以下参数区分：

| 参数 | 说明 | 用途 |
|------|------|------|
| `module_id` | 模块唯一标识符 | MessageBus 注册和消息路由 |
| `tmux_session` | tmux 会话名称 | 标识要连接的 tmux/iflow |

### 实例隔离

- 每个实例对应独立的 tmux 会话
- 每个实例对应独立的 iflow 进程
- 每个实例维护独立的交互记录
- 实例之间完全隔离，互不干扰

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `src/modules/iflow/__init__.py` | 模块导出 |
| `src/modules/iflow/module.py` | IFlowModule 主类 |
| `src/modules/iflow/controller.py` | tmux/iflow 控制器 |
| `src/modules/iflow/monitor.py` | 输出监控器 |
| `src/modules/iflow/session_manager.py` | 会话管理器 |
| `src/modules/iflow/logger.py` | 交互记录器 |
| `src/modules/iflow/message_store.py` | 消息库（新增） |

---

## 实现优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 状态管理 | 检测 iflow "生成中" 状态 |
| P0 | 生成中拒绝 | 返回明确拒绝响应 |
| P0 | 订阅机制 | 通知订阅方 |
| P1 | 消息库 | 消息记录和来源查询 |
| P1 | 消息分类 | 回复/其他分类 |
| P2 | scope 过滤 | 按 scope 过滤返回内容 |
| P2 | 结束通知 | 生成结束发送 complete 消息 |

---

## 注意事项

1. **tmux 依赖**：系统必须安装 tmux
2. **iflow CLI**：必须先安装 iflow CLI 并登录
3. **工作目录**：默认 `~/.iflow`，确保有读写权限
4. **状态检测**：通过监控界面左下角"生成中"指示器判断状态
5. **日志目录**：默认 `logs/interactions`，确保有写入权限
