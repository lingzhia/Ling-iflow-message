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

---

## 模块组成总结

### 三大核心组件

IFlowModule 由以下三大部分组成：

#### 1. IFlowController - 进程管理层
**职责**：管理 tmux 会话和 iflow 进程
- 创建/销毁 tmux 会话
- 启动/停止 iflow CLI
- 发送消息到 iflow
- 捕获 tmux 输出

**特点**：
- 模块启动时自动创建 tmux 会话并启动 iflow
- 模块停止时自动停止 iflow 并销毁 tmux 会话
- 完全自动化生命周期管理

#### 2. IFlowMonitor - 消息同步层
**职责**：监控 iflow 输出并提取消息
- 持续监听 tmux 输出
- 检测状态变化（空闲/生成中）
- 提取标记消息（✦ 回复、✻ 思考）
- 消息去重和过滤

**特点**：
- 所有消息都会被提取（✦ 和 ✻ 都会提取）
- 提取的消息全部记录，不受 scope 影响
- 消息分类：✦ 为回复，✻ 为思考

#### 3. IFlowModule - 消息交互层
**职责**：与消息总线交互，管理消息流转
- 接收消息总线的消息
- 管理消息库和交互记录
- 发送消息到消息总线
- 管理订阅者通知

**特点**：
- 默认 scope="reply_only"，只发送 ✦ 回复
- scope="all" 时，发送所有消息（✦ 和 ✻）
- 所有消息都完整记录到日志

### 辅助组件

#### MessageStore - 消息库
- 记录消息来源（source）
- 管理消息状态（pending/processing/completed）
- 统计回复数量

#### InteractionLogger - 交互记录器
- 记录所有发送和接收的消息
- 持久化存储到文件
- 提供交互历史查询

#### SessionManager - 会话管理器
- 管理 iflow 会话
- 提供会话查询和创建功能

### 生命周期管理

```
启动流程：
  IFlowModule._on_start()
    ↓
  IFlowController.start_iflow()
    ↓
  创建 tmux 会话
    ↓
  启动 iflow CLI
    ↓
  IFlowMonitor.start()
    ↓
  开始监控输出

停止流程：
  IFlowModule._on_stop()
    ↓
  IFlowMonitor.stop()
    ↓
  停止监控
    ↓
  IFlowController.destroy_session()
    ↓
  销毁 tmux 会话
    ↓
  停止 iflow CLI
```

### 消息处理原则

#### 记录原则
**所有消息都完整记录**：
- ✦ 回复消息 → 记录
- ✻ 思考消息 → 记录
- 其他输出 → 记录
- 记录位置：InteractionLogger + MessageStore
- 记录时机：不受 scope 影响

#### 发送原则
**发送时按 scope 过滤**：

| scope | ✦ 回复 | ✻ 思考 | 其他 |
|-------|--------|---------|------|
| reply_only (默认) | ✅ 发送 | ❌ 过滤 | ❌ 过滤 |
| all | ✅ 发送 | ✅ 发送 | ✅ 发送 |

- 发送位置：消息总线 + 订阅者
- 发送时机：根据 scope 参数过滤

### 核心特性

1. **自动化生命周期**：模块与 tmux/iflow 完全同步
2. **完整记录**：所有消息都记录，不丢失任何信息
3. **灵活过滤**：scope 参数控制发送内容
4. **状态管理**：生成中时拒绝新消息
5. **消息归属**：记录消息来源，支持多轮对话
6. **订阅机制**：通过订阅通知关注方

---

## 完整消息流转图

### 入站流程（外部 → iflow）

```
消息总线
    ↓
IFlowModule._on_receive(message)
    ↓
提取消息信息：
  - content: 消息内容
  - source: 来源模块 ID
  - scope: 返回范围（reply_only / all）
    ↓
IFlowModule.send(content, source, scope)
    ↓
┌─────────────────────────────────────┐
│ 状态检查                             │
│ - 空闲 → 继续处理                   │
│ - 生成中 → 拒绝（返回 duration）    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 记录消息（全部记录）                 │
│ - MessageStore.add()                │
│ - InteractionLogger.log_sent()      │
│ - 状态更新为 processing             │
└─────────────────────────────────────┘
    ↓
IFlowController.send_message(content)
    ↓
发送 C-c 清除输入框
    ↓
发送消息内容（tmux send-keys -l）
    ↓
发送回车键（C-m）
    ↓
iflow 处理并输出
```

### 出站流程（iflow → 外部）

```
iflow 输出（tmux）
    ↓
IFlowMonitor 持续监控
    ↓
┌─────────────────────────────────────┐
│ 捕获 tmux 输出                       │
│ tmux capture-pane -S -1000 -p       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 提取消息（全部提取）                 │
│ - 检测标记行（✦ 或 ✻）              │
│ - 收集后续缩进内容                   │
│ - 清理 UI 元素                       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 分类消息                             │
│ - ✦ → MessageType.REPLY             │
│ - ✻ → MessageType.OTHER             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 记录消息（全部记录）                 │
│ - InteractionLogger.log_received()  │
│ - MessageStore.increment_reply()    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ scope 过滤                           │
│ - reply_only → 只发送 ✦             │
│ - all → 发送所有（✦ + ✻）          │
└─────────────────────────────────────┘
    ↓
构造 OutboundMessage
    ↓
┌─────────────────────────────────────┐
│ 调用钩子（用于测试）                 │
│ - _message_sent_hook()              │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 发送到消息总线                       │
│ - send_to_bus(message)               │
│ - 根据 binding 路由到目标模块       │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 通知订阅者                           │
│ - _notify_subscribers(message)      │
│ - 所有订阅者都会收到通知             │
└─────────────────────────────────────┘
```

### 状态变化流程

```
IFlowMonitor 监控状态
    ↓
┌─────────────────────────────────────┐
│ 检测到 "生成中" 关键字               │
│ - 状态：IDLE → GENERATING           │
│ - 记录生成开始时间                   │
│ - 触发状态变更回调                   │
└─────────────────────────────────────┘
    ↓
iflow 正在生成
    ↓
┌─────────────────────────────────────┐
│ "生成中" 不再显示                    │
│ - 等待稳定 2 秒                      │
│ - 状态：GENERATING → IDLE           │
│ - 记录生成持续时间                   │
│ - 触发状态变更回调                   │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 生成结束处理                         │
│ - 查询消息库 processing 状态记录     │
│ - 构造 COMPLETE 消息                 │
│ - 通知订阅者                         │
│ - 更新状态为 completed               │
└─────────────────────────────────────┘
```

### 记录 vs 发送对比

```
所有消息的记录和发送：

消息类型       │ 记录          │ 发送（scope=reply_only）│ 发送（scope=all）
───────────────┼───────────────┼────────────────────────┼────────────────────
✦ 回复消息     │ ✅ 全部记录   │ ✅ 发送                │ ✅ 发送
✻ 思考消息     │ ✅ 全部记录   │ ❌ 过滤                │ ✅ 发送
其他输出       │ ✅ 全部记录   │ ❌ 过滤                │ ✅ 发送

关键原则：
1. 所有消息都完整记录（InteractionLogger + MessageStore）
2. 记录不受 scope 影响
3. 发送时按 scope 过滤
4. 默认 scope="reply_only"（只发送 ✦ 回复）
```

### 多轮对话消息归属

```
第一次对话（source="wechat_bot1", scope="reply_only"）
  ↓
MessageStore 记录：message_id="abc123", source="wechat_bot1", scope="reply_only"
  ↓
iflow 返回 ✦ 回复1、✻ 思考1、✦ 回复2
  ↓
IFlowMonitor 提取所有消息
  ↓
scope 过滤：只发送 ✦ 回复1 和 ✦ 回复2
  ↓
设置 receiver="wechat_bot1"
  ↓
发送到消息总线，路由到 wechat_bot1

第二次对话（source="wechat_bot1", scope="reply_only"）
  ↓
MessageStore 记录：message_id="def456", source="wechat_bot1", scope="reply_only"
  ↓
iflow 返回 ✦ 回复3
  ↓
设置 receiver="wechat_bot1"
  ↓
发送到消息总线，路由到 wechat_bot1

消息归属原则：
1. 每次对话都有唯一的 message_id
2. 回复时使用请求时的 source 作为 receiver
3. 支持多轮对话，每次对话独立归属
```

---

## 新消息监测和记录方案（两阶段检测）

### 核心理念

**两阶段检测策略**：
- **阶段1（轻量级检测）**：未检测到"生成中"时，每 0.5 秒提取 50 行，仅检测状态
- **阶段2（完整记录）**：检测到"生成中"后，每 0.5 秒提取 1000 行，完整记录消息

**核心改进**：
1. **性能优化**：未在生成中时只提取 50 行，减少不必要的处理
2. **内容清理**：去掉 TUI 界面和无关内容
3. **精确提取**：区分 iflow 收到的消息和带标记的消息
4. **字符串定位**：用标记行字符串定位，简化去重逻辑
5. **延迟发送**：最后统一发送，避免发送不完整的中间版本

---

### 监测流程（两阶段）

```
┌─────────────────────────────────────────────────────────┐
│ 阶段1：轻量级检测（未检测到"生成中"）                    │
└─────────────────────────────────────────────────────────┘
    ↓
每 0.5 秒提取 tmux 中的 50 行
    ↓
检测是否有"生成中"
    ↓
┌─────────────────────────────────────┐
│ 没有"生成中" → 不处理，继续检测    │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 有"生成中" → 切换到阶段2            │
│ - 切换为提取 1000 行                │
│ - 开始记录模式                      │
└─────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 阶段2：完整记录（检测到"生成中"）                          │
└─────────────────────────────────────────────────────────┘
    ↓
每 0.5 秒提取 tmux 中的 1000 行
    ↓
内容处理
    ↓
┌─────────────────────────────────────┐
│ 1. 去掉 TUI 界面内容               │
│ 2. 去掉最新一条发送消息前的内容     │
└─────────────────────────────────────┘
    ↓
消息提取
    ↓
┌─────────────────────────────────────┐
│ 1. 提取 iflow 收到的消息           │
│ 2. 提取带标记的消息（✦、✻）        │
│ 3. 保留原始顺序                    │
└─────────────────────────────────────┘
    ↓
消息记录
    ↓
┌─────────────────────────────────────┐
│ 首次扫描：                          │
│ - 记录除最后一条外的所有消息        │
│ - 保存最后一条标记消息的标记行      │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 后续扫描：                          │
│ - 找到上次记录的最后标记行          │
│ - 记录中间的新消息                  │
│ - 更新最后标记行                    │
└─────────────────────────────────────┘
    ↓
检查"生成中"是否存在
    ↓
┌─────────────────────────────────────┐
│ 仍存在 → 继续记录                  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 不存在 → 记录最后一条，结束         │
│ - 记录最后一条标记消息              │
│ - 统一发送所有记录的消息            │
│ - 清空缓存                          │
└─────────────────────────────────────┘
```

---

### 内容处理逻辑

```python
def process_output(raw_output: str, last_sent_message: str) -> str:
    """处理 tmux 输出
    
    Args:
        raw_output: 原始 tmux 输出
        last_sent_message: 最新一条发送给 iflow 的消息
    
    Returns:
        处理后的输出
    """
    lines = raw_output.split('\n')
    processed_lines = []
    
    # 1. 去掉 TUI 界面内容
    tui_markers = ['生成中', '思考:', '上下文剩余', '---', '══', '────']
    
    for line in lines:
        is_tui = False
        for marker in tui_markers:
            if marker in line:
                is_tui = True
                break
        
        if not is_tui:
            processed_lines.append(line)
    
    # 2. 去掉最新一条发送消息前的内容
    if last_sent_message:
        sent_message_idx = -1
        for i, line in enumerate(processed_lines):
            if last_sent_message in line:
                sent_message_idx = i
                break
        
        if sent_message_idx >= 0:
            processed_lines = processed_lines[sent_message_idx:]
    
    return '\n'.join(processed_lines)
```

---

### 消息提取逻辑

```python
def extract_messages(processed_output: str) -> Dict[str, List[Dict]]:
    """提取消息
    
    Returns:
        {
            'received_messages': [...],  # iflow 收到的消息
            'marked_messages': [...]       # 带标记的消息
        }
    """
    lines = processed_output.split('\n')
    
    received_messages = []
    marked_messages = []
    
    # 提取带标记的消息
    for i, line in enumerate(lines):
        if '✦' in line or '✻' in line:
            marker_type = '✦' if '✦' in line else '✻'
            marker_content = line.replace('✦', '').replace('✻', '').strip()
            
            content_lines = [marker_content]
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if '✦' in next_line or '✻' in next_line or next_line.startswith('---'):
                    break
                if not next_line.strip():
                    continue
                if next_line.startswith('  ') or next_line.startswith('\t'):
                    content_lines.append(next_line.strip())
                else:
                    break
            
            full_content = '\n'.join(content_lines)
            
            marked_messages.append({
                'content': full_content,
                'marker_type': marker_type,
                'marker_line': line,
                'line_index': i
            })
    
    # 提取 iflow 收到的消息
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if '✦' in line or '✻' in line or not line_stripped:
            continue
        if '生成中' in line or '思考:' in line:
            continue
        
        in_marked_section = False
        for marked_msg in marked_messages:
            if i > marked_msg['line_index']:
                in_marked_section = True
                break
        
        if not in_marked_section:
            received_messages.append({
                'content': line_stripped,
                'line_index': i
            })
    
    return {
        'received_messages': received_messages,
        'marked_messages': marked_messages
    }
```

---

### 消息记录逻辑

#### 首次扫描

```python
def first_scan_record(messages: Dict[str, List[Dict]]) -> str:
    """首次扫描记录
    
    Returns:
        最后一条标记消息的标记行
    """
    marked_messages = messages['marked_messages']
    
    if len(marked_messages) < 2:
        return ""
    
    # 记录除最后一条外的所有消息
    for i in range(len(marked_messages) - 1):
        msg = marked_messages[i]
        record_message(msg)
    
    # 返回最后一条标记消息的标记行
    return marked_messages[-1]['marker_line']
```

#### 后续扫描

```python
def subsequent_scan_record(
    messages: Dict[str, List[Dict]],
    last_marker_line: str
) -> str:
    """后续扫描记录
    
    Returns:
        最新的最后标记行
    """
    marked_messages = messages['marked_messages']
    marker_lines = [msg['marker_line'] for msg in marked_messages]
    
    try:
        last_idx = marker_lines.index(last_marker_line)
    except ValueError:
        return first_scan_record(messages)
    
    # 记录中间的新消息
    for i in range(last_idx + 1, len(marked_messages)):
        msg = marked_messages[i]
        record_message(msg)
    
    return marked_messages[-1]['marker_line']
```

#### 结束检测

```python
def finish_record(messages: Dict[str, List[Dict]], last_marker_line: str) -> None:
    """结束记录（生成中消失）"""
    marked_messages = messages['marked_messages']
    
    if not marked_messages:
        return
    
    # 记录最后一条标记消息
    last_msg = marked_messages[-1]
    record_message(last_msg)
    
    # 发送所有记录的消息
    send_all_recorded_messages()
    
    # 清空缓存
    clear_message_cache()
```

---

### 与旧方案的对比

| 方面 | 旧方案 | 新方案 | 改进 |
|-----|-------|--------|------|
| **提取行数** | 固定 1000 行 | 动态：50 行（检测中）→ 1000 行（记录中） | ✅ 性能优化 |
| **状态检测** | 始终检测"生成中" | 检测到"生成中"才开始记录 | ✅ 减少不必要处理 |
| **消息发送** | 立即发送新增标记 | 延迟记录，最后统一发送 | ✅ 避免中间版本 |
| **内容处理** | 完整保留 | 去掉 TUI 界面 + 去掉发送消息前的内容 | ✅ 精确提取 |
| **消息类型** | 只提取带标记的消息 | 提取 iflow 收到的消息 + 带标记的消息 | ✅ 更完整 |
| **去重机制** | 哈希去重 | 字符串定位（基于标记行） | ✅ 简化逻辑 |
| **结束检测** | 稳定检测（2 秒） | "生成中"消失 + 记录最后一条 | ✅ 简化逻辑 |

---

### 需要去掉的旧方案内容

- ❌ 哈希去重
- ❌ 稳定检测（2秒）
- ❌ 交互完成标志
- ❌ 消息重叠检测
- ❌ 立即发送新增标记
- ❌ 标记更新处理

---

### 需要新增的功能

- ✅ 两阶段检测（50/1000行）
- ✅ 内容处理（去掉TUI界面 + 去掉发送消息前的内容）
- ✅ 提取 iflow 收到的消息
- ✅ 标记行字符串定位
- ✅ 首次扫描逻辑
- ✅ 后续扫描逻辑（增量）
- ✅ 结束检测和统一发送

---

### 待解决的问题

1. **如何识别 iflow 收到的消息？**
   - 方法1：查找符合特定格式的行（如用户输入格式）
   - 方法2：查找在"用户:"、"You:"等标识符之后的行
   - 方法3：查找没有标记，但在标记之前的行
   - 建议：先分析 iflow 的实际输出格式，再确定具体方法

2. **如何准确识别 TUI 界面？**
   - 可能的特征：包含"生成中"、"思考:"、"上下文剩余"、分隔符等
   - 建议：收集实际的 iflow 输出样本，分析 TUI 界面的特征

3. **如何准确识别发送消息的分界线？**
   - 方法：通过 IFlowController 记录最后发送的消息
   - 建议：使用 IFlowController 记录最后发送的消息，然后在提取时过滤
