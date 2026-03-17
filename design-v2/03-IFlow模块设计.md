# IFlow 模块设计文档

## 目录

1. [概述](#概述)
2. [核心架构](#核心架构)
3. [模块组成](#模块组成)
4. [状态管理](#状态管理)
5. [消息处理](#消息处理)
6. [消息提取优化](#消息提取优化)
7. [测试工具设计](#测试工具设计)
8. [使用示例](#使用示例)
9. [故障排查](#故障排查)

---

## 概述

### 设计理念

**模块实例与 tmux/iflow 生命周期同步**

- 创建 IFlowModule 实例 → 自动创建对应的 tmux 会话并启动 iflow
- 销毁 IFlowModule 实例 → 自动停止 iflow 并销毁 tmux 会话

### 核心职责

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

## 核心架构

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     IFlowModule                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │ IFlowController  │    │  IFlowMonitor    │              │
│  │  (进程管理层)     │    │  (消息同步层)     │              │
│  │                  │    │                  │              │
│  │ • tmux 会话管理   │    │ • 输出监控       │              │
│  │ • iflow 启动/停止 │    │ • 状态检测       │              │
│  │ • 消息注入       │    │ • 消息提取       │              │
│  │ • 捕获输出       │    │ • 消息去重       │              │
│  └──────────────────┘    └──────────────────┘              │
│           │                        │                        │
│           └────────────┬───────────┘                        │
│                        │                                     │
│  ┌─────────────────────┼─────────────────────────────────┐  │
│  │                     │                                 │  │
│  │  ┌──────────────────▼──────────────────┐             │  │
│  │  │        MessageStore (消息库)        │             │  │
│  │  │  • 消息记录                         │             │  │
│  │  │  • 来源查询                         │             │  │
│  │  │  • 状态更新                         │             │  │
│  │  └─────────────────────────────────────┘             │  │
│  │                                                     │  │
│  │  ┌──────────────────┐    ┌──────────────────────┐ │  │
│  │  │ InteractionLogger│    │   订阅管理           │ │  │
│  │  │  (交互记录器)     │    │  • 订阅者列表        │ │  │
│  │  │  • 发送记录       │    │  • 消息通知          │ │  │
│  │  │  • 接收记录       │    │  • 回调处理          │ │  │
│  │  │  • 持久化存储     │    └──────────────────────┘ │  │
│  │  └──────────────────┘                           │  │
│  │                                                  │  │
│  └──────────────────────────────────────────────────┘  │
│                                                           │
│  消息交互层 (与 MessageBus 交互)                           │
│  • 接收消息总线消息                                       │
│  • 发送消息到消息总线                                     │
│  • 管理订阅者通知                                         │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 开发语言 |
| asyncio | 内置 | 异步编程 |
| tmux | 3.0+ | 会话管理 |
| iflow CLI | 最新 | AI 交互 |
| loguru | 0.7.0+ | 日志记录 |

---

## 模块组成

### 1. IFlowController - 进程管理层

#### 职责

管理 tmux 会话和 iflow 进程，实现完整的生命周期管理。

#### 主要方法

```python
class IFlowController:
    async def start_iflow(self, model: str) -> bool:
        """启动 iflow CLI
        
        创建 tmux 会话并启动 iflow
        
        Returns:
            bool: 是否成功启动
        """
        
    async def stop_iflow(self) -> bool:
        """停止 iflow CLI
        
        Returns:
            bool: 是否成功停止
        """
        
    async def send_message(self, message: str) -> bool:
        """发送消息到 iflow
        
        Args:
            message: 消息内容
            
        Returns:
            bool: 是否成功发送
        """
        
    async def capture_output(self, lines: int = 1000) -> str:
        """捕获 tmux 输出
        
        Args:
            lines: 捕获的行数
            
        Returns:
            str: tmux 输出内容
        """
        
    async def check_iflow_running(self) -> bool:
        """检查 iflow 是否在运行
        
        Returns:
            bool: 是否在运行
        """
        
    async def check_iflow_ready(self) -> bool:
        """检查 iflow 是否就绪
        
        Returns:
            bool: 是否就绪
        """
        
    async def destroy_session(self) -> bool:
        """销毁 tmux 会话
        
        Returns:
            bool: 是否成功销毁
        """
```

#### 实现细节

**启动 iflow**：
```bash
tmux new-session -d -s <session_name> 'iflow --model <model>'
```

**发送消息**：
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

---

### 2. IFlowMonitor - 消息同步层

#### 职责

监控 iflow 输出并提取消息，实现消息同步。

#### 主要方法

```python
class IFlowMonitor:
    async def start(self):
        """启动监控"""
        
    async def stop(self):
        """停止监控"""
        
    async def _check(self):
        """检查周期性任务（监控循环）"""
        
    def _detect_generating(self, output: str) -> bool:
        """检测是否生成中
        
        Args:
            output: tmux 输出
            
        Returns:
            bool: 是否生成中
        """
        
    def _extract_messages(self, output: str) -> List[Dict]:
        """提取消息
        
        Args:
            output: tmux 输出
            
        Returns:
            List[Dict]: 消息列表
        """
        
    async def _handle_state_change(self, old_state: IFlowState, new_state: IFlowState):
        """处理状态变化"""
```

#### 状态检测

**状态定义**：

| 状态 | 说明 | 可接受新消息 |
|------|------|-------------|
| **空闲** (IDLE) | iflow 等待输入 | ✅ 是 |
| **生成中** (GENERATING) | iflow 正在处理/生成回复 | ❌ 否 |

**检测逻辑**：

iflow 状态指示器（位于界面底部状态栏）：
- **"生成中"** - 正在生成回复（**唯一判断标准**）
- **"思考: 开启"** - 思考模式开启（**与是否生成无关**）

```python
def _detect_generating(self, output: str) -> bool:
    """检测是否生成中"""
    lines = output.split('\n')
    
    for line in lines:
        line_stripped = line.strip()
        
        # 检测生成中标志
        if ('按esc取消' in line_stripped or 
            re.search(r'\d+[ms]\s*\d+s', line_stripped) or
            re.search(r'生成中\s+\d+[ms]', line_stripped)):
            return True
    
    return False
```

**关键改进**：
- ✅ 使用正则表达式精确匹配
- ✅ 避免用户消息中包含"生成中"的误判
- ✅ 要求时间/超时指示器

#### 性能优化

**双模式监控**：

| 模式 | 触发条件 | 提取行数 | 检测频率 |
|------|---------|---------|---------|
| 轻量级 | IDLE 状态 | 50 行 | 0.5 秒 |
| 完整 | GENERATING 状态 | 1000 行 | 0.5 秒 |

**性能提升**：
- IDLE 状态下性能提升 50 倍
- 减少不必要的文本处理
- 保持完整功能

#### 消息提取

**提取逻辑**：

```python
def _extract_messages(self, output: str) -> List[Dict]:
    """提取消息
    
    提取所有标记消息（✦ 和 ✻）
    """
    lines = output.split('\n')
    messages = []
    
    # 提取带标记的消息
    for i, line in enumerate(lines):
        if '✦' in line or '✻' in line:
            marker_type = '✦' if '✦' in line else '✻'
            marker_content = line.replace('✦', '').replace('✻', '').strip()
            
            # 收集缩进内容
            content_lines = [marker_content]
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if '✦' in next_line or '✻' in next_line:
                    break
                if not next_line.strip():
                    continue
                if next_line.startswith('  ') or next_line.startswith('\t'):
                    content_lines.append(next_line.strip())
                else:
                    break
            
            full_content = '\n'.join(content_lines)
            
            messages.append({
                'content': full_content,
                'marker_type': marker_type,
                'full_marker': line,
                'line_index': i
            })
    
    return messages
```

**消息分类**：

| 标记 | 类型 | 说明 |
|------|------|------|
| `✦` | 回复 | 正式回复内容 |
| `✻` | 思考 | 思考过程内容 |

---

### 3. SessionManager - 会话管理器

#### 职责

管理 iflow 的会话文件，提供会话查询、创建等功能。

#### 主要方法

```python
class SessionManager:
    def get_latest_session(self) -> Optional[str]:
        """获取最新的 session 文件
        
        Returns:
            session 文件路径或 None
        """
        
    def get_all_sessions(self, limit: int = 10) -> List[str]:
        """获取所有 session 列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            session 文件路径列表
        """
        
    def create_new_session(self) -> bool:
        """创建新会话（清除上下文）
        
        Returns:
            bool: 是否成功
        """
        
    def get_current_session_info(self) -> dict:
        """获取当前会话信息
        
        Returns:
            会话信息字典
        """
```

---

### 4. MessageStore - 消息库

#### 职责

记录消息来源、管理消息状态。

#### 数据结构

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
    reply_count: int = 0      # 回复数量
```

#### 主要方法

```python
class MessageStore:
    def add(self, message_id: str, source: str, content: str, scope: str):
        """添加消息记录"""
        
    def get_processing(self) -> Optional[MessageRecord]:
        """获取正在处理的消息"""
        
    def mark_completed(self, message_id: str):
        """标记消息为已完成"""
        
    def increment_reply(self, message_id: str):
        """增加回复计数"""
```

#### 来源识别

| 来源 | 说明 | 识别方式 |
|------|------|---------|
| `wechat_bot1` | 企业微信机器人1 | 消息体 `source` 字段 |
| `tool_xxx` | 运维工具 | 消息体 `source` 字段 |
| `""` (空) | 无来源（tmux 直接操作） | 无 `source` 字段或为空 |

---

### 5. InteractionLogger - 交互记录器

#### 职责

记录所有交互信息，持久化存储。

#### 日志格式

```json
{
  "timestamp": "2024-03-15T10:30:00",
  "type": "sent",
  "message_id": "abc123",
  "source": "wechat_bot1",
  "content": "帮我写一个Python脚本"
}
```

```json
{
  "timestamp": "2024-03-15T10:30:05",
  "type": "received",
  "message_type": "reply",
  "content": "好的，这是脚本...",
  "marker_type": "✦"
}
```

#### 日志位置

- 默认目录：`logs/interactions/`
- 文件命名：`interactions-YYYYMMDD.jsonl`

---

### 6. IFlowModule - 消息交互层

#### 职责

与消息总线交互，管理消息流转。

#### 主要方法

```python
class IFlowModule(BaseModule):
    async def _on_start(self):
        """启动钩子"""
        
    async def _on_stop(self):
        """停止钩子"""
        
    async def _on_receive(self, message: Message):
        """接收消息钩子"""
        
    async def send(self, content: str, source: str = "", scope: str = "reply_only"):
        """发送消息到 iflow
        
        Args:
            content: 消息内容
            source: 来源模块 ID
            scope: 返回范围（reply_only / all）
            
        Returns:
            Response: 成功或拒绝响应
        """
        
    def subscribe(self, callback: Callable):
        """订阅 iflow 输出消息"""
        
    def unsubscribe(self, callback: Callable):
        """取消订阅"""
```

#### 消息处理流程

**入站流程（外部 → iflow）**：

```
收到消息
    ↓
解析消息体，提取 source、content、scope
    ↓
检查 iflow 状态
    ↓
┌─────────────────────────────────────┐
│ iflow 生成中                         │
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
│ iflow 空闲                           │
│ → 记录到消息库（status=processing）  │
│ → 记录发送日志                       │
│ → 发送给 iflow                       │
│ → 返回成功响应                       │
└─────────────────────────────────────┘
```

**出站流程（iflow → 外部）**：

```
监控捕获 iflow 输出
    ↓
提取消息，分类（回复 / 思考）
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
调用钩子（用于测试）
    ↓
发送到消息总线
    ↓
通知订阅者
    ↓
订阅方根据 receiver 决定是否处理
```

---

## 状态管理

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

### 状态检测顺序

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

### 超时保护

**超时机制**：
- 如果状态稳定检测超过 10 秒，强制完成
- 避免无限等待
- 确保系统可靠性

```python
if stable_duration > 10:
    # 强制完成
    logger.warning("状态稳定超过 10 秒，强制完成")
    state = IFlowState.IDLE
```

---

## 消息处理

### 消息分类

| 标记 | 类型 | 说明 |
|------|------|------|
| `✦` | 回复 | 正式回复内容 |
| `✻` | 思考 | 思考过程内容 |
| 其他 | 其他 | 其他输出 |

### 返回范围（scope）

| scope | 说明 | 返回内容 |
|-------|------|---------|
| `reply_only` | 仅回复（默认） | ✦ 标记的消息 |
| `all` | 全部 | ✦ + ✻ + 其他所有消息 |

### 记录原则

**所有消息都完整记录**：
- ✦ 回复消息 → 记录
- ✻ 思考消息 → 记录
- 其他输出 → 记录
- 记录位置：InteractionLogger + MessageStore
- 记录时机：不受 scope 影响

### 发送原则

**发送时按 scope 过滤**：

| scope | ✦ 回复 | ✻ 思考 | 其他 |
|-------|--------|---------|------|
| reply_only (默认) | ✅ 发送 | ❌ 过滤 | ❌ 过滤 |
| all | ✅ 发送 | ✅ 发送 | ✅ 发送 |

- 发送位置：消息总线 + 订阅者
- 发送时机：根据 scope 参数过滤

### 消息去重

**去重机制**：
- 使用标记行字符串定位
- 避免重复发送相同消息
- 记录已发送的标记行

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

## 消息提取优化

### 问题分析

#### 当前问题

1. **消息内容缺失** - 只提取标记行，丢失了后续行的内容
2. **消息重复发送** - 检测机制不准确导致重复
3. **生成中消失不稳定** - 有时会短暂消失又重新出现，导致误判结束

#### iflow 输出格式

```
✦ 回复标题
  缩进的内容行1
  缩进的内容行2

✻ 思考中...
  思考内容

⠦ 生成中 6m 37s ... (按esc取消)
```

#### 标记说明

- **✦ (回复标记)** - iflow 的实际回复内容，默认对外发送
- **✻ (思考标记)** - iflow 的思考过程，内部记录但不对外发送
- **⠦ 生成中** - 状态指示器，表示 iflow 正在生成回复

#### 核心原则

1. **完整记录** - IFlowMonitor 必须记录 iflow 中的全部消息，无论前面是什么标记（✦ 或 ✻）
2. **选择性发送** - 对外回复的消息默认情况下只发送 ✦ 标记的消息，✻ 标记的消息不发送
3. **状态检测** - 状态检测只关注"生成中"关键词及其持续时间，不依赖前面的符号 ⠦

---

### 倒数第二原则

#### 核心策略：延迟提取

**核心思想**：检测到新标记时，提取并发送**倒数第二个**标记消息（它是完整的，不会再变化）。

#### 工作流程

```
时间线：
T1: 检测到标记1 [✦ 回复1] → 记录（候选）
T2: 检测到标记2 [✦ 回复2] → 发送标记1（倒数第二，完整），记录标记2
T3: 检测到标记3 [✦ 回复3] → 发送标记2（倒数第二，完整），记录标记3
...
Tn: 生成中消失（稳定2秒）→ 发送最后一个标记（此时也是完整的）
```

#### 关键特性

1. **倒数第二原则** - 每次检测到新标记时，发送上一个标记（倒数第二）
2. **完整保证** - 倒数第二的标记已经完整，不会再变化
3. **生成中也会发送** - 生成中时的新标记也会被记录并发送
4. **稳定结束** - "生成中"消失并稳定2秒后，才判断回复结束

#### 实现逻辑

```python
# 倒数第二原则伪代码
last_messages = []  # 记录所有标记消息
stable_start_time = None  # 稳定开始时间

while monitoring:
    current_messages = extract_all_messages(output)
    is_generating = detect_generating(output)
    
    # 检测新标记
    if len(current_messages) > len(last_messages):
        # 有新标记
        if len(last_messages) >= 1:
            # 发送倒数第二的（即 last_messages 的最后一个）
            send_message(last_messages[-1])
        
        # 更新记录
        last_messages = current_messages
        stable_start_time = None  # 重置稳定计时器
    
    # 检测生成中消失（需要稳定2秒）
    elif not is_generating and len(last_messages) > 0:
        if stable_start_time is None:
            # 第一次检测到消失，开始计时
            stable_start_time = now()
        elif (now() - stable_start_time) >= 2:
            # 稳定2秒，确认结束
            send_message(last_messages[-1])
            last_messages = []
            stable_start_time = None
    else:
        # 生成中重新出现，重置计时器
        stable_start_time = None
```

---

### 两阶段检测策略

#### 方案概述

采用**两阶段检测策略**和**字符串定位机制**，进一步提升性能和准确性。

**核心改进**：
1. **两阶段检测**：未在生成中时只提取 50 行，减少不必要的处理
2. **内容清理**：去掉 TUI 界面和无关内容
3. **精确提取**：区分 iflow 收到的消息和带标记的消息
4. **字符串定位**：用标记行字符串定位，简化去重逻辑
5. **延迟发送**：最后统一发送，避免发送不完整的中间版本

#### 监测流程（两阶段）

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

#### 核心差异对比

| 方面 | 延迟提取方案 | 两阶段检测方案 |
|-----|----------------|-------------------|
| **提取行数** | 固定 1000 行 | 动态：50 行（检测中）→ 1000 行（记录中） |
| **状态检测** | 始终检测"生成中" | 检测到"生成中"才开始记录 |
| **消息发送** | 立即发送新增标记 | 延迟记录，最后统一发送 |
| **内容处理** | 完整保留 | 去掉 TUI 界面 + 去掉发送消息前的内容 |
| **消息类型** | 只提取带标记的消息 | 提取 iflow 收到的消息 + 带标记的消息 |
| **去重机制** | 哈希去重 | 字符串定位（基于标记行） |
| **结束检测** | 稳定检测（2 秒） | "生成中"消失 + 记录最后一条 |

#### 性能优化

**阶段1（轻量级检测）**：
- 提取行数：50 行
- 处理内容：仅检测"生成中"关键字
- 资源消耗：极低

**阶段2（完整记录）**：
- 提取行数：1000 行
- 处理内容：完整提取和记录
- 资源消耗：正常

**效果**：
- 未在生成中时，性能提升约 **20 倍**（50 行 vs 1000 行）
- 减少不必要的字符串处理和内存分配

---

### 状态检测顺序优化

#### 检测逻辑

1. **先检测状态变化**
   - 检测"生成中"关键字
   - 记录状态变化时间
   - 触发状态变更回调

2. **再处理消息提取**
   - 根据当前状态选择提取策略
   - IDLE 状态：轻量级检测
   - GENERATING 状态：完整记录

3. **最后发送消息**
   - scope 过滤
   - 构造 OutboundMessage
   - 调用钩子
   - 发送到消息总线
   - 通知订阅者

#### 优化效果

- ✅ 避免状态检测和消息提取的时序问题
- ✅ 确保状态正确更新后再处理消息
- ✅ 减少重复检测和无效处理

---

### 标记更新处理

#### 问题

- 检测到新标记时，立即发送可能导致发送不完整的中间版本
- 需要确保发送的消息是完整的

#### 解决方案

1. **延迟发送** - 记录候选消息，等待下一个标记出现后再发送上一个
2. **完整保证** - 倒数第二的标记已经完整，不会再变化
3. **统一发送** - 生成中消失后，统一发送所有记录的消息

#### 实现逻辑

```python
# 标记更新处理
candidate_messages = []  # 候选消息缓存

# 检测到新标记
if len(current_messages) > len(candidate_messages):
    # 有新标记
    if len(candidate_messages) > 0:
        # 发送倒数第二的（保证完整）
        message_to_send = candidate_messages[-1]
        await self._send_message(message_to_send)
    
    # 更新候选缓存
    candidate_messages = current_messages

# 生成中消失
elif not is_generating and len(candidate_messages) > 0:
    # 发送最后一个
    message_to_send = candidate_messages[-1]
    await self._send_message(message_to_send)
    
    # 清空缓存
    candidate_messages = []
```

---

### 预期效果

| 项目 | 当前状态 | 修复后 |
|------|---------|--------|
| 消息内容完整 | ❌ 只有标记行 | ✅ 完整内容 |
| 发送时机 | ❌ 立即发送（可能不完整） | ✅ 延迟发送（保证完整） |
| 重复发送 | ❌ 误判 | ✅ 基于哈希去重 |
| 生成中处理 | ❌ 无处理 | ✅ 正常发送 |
| 结束判断 | ❌ 不稳定，误判 | ✅ 稳定2秒确认 |
| 性能 | ❌ 固定1000行 | ✅ 动态50/1000行 |

---

## 测试工具设计

### 概述

`tools/iflow_interactive_tool.py` 是 iflow 模块的交互式测试工具，提供两种模式：

1. **交互模式**：持续交互，支持多种命令
2. **命令行模式**：发送单条消息后退出，支持会话保持

### 设计原则

1. **消息格式一致** - 发送和接收的消息格式与消息总线完全一致
2. **排除消息总线风险** - 使用模拟的消息总线，不依赖真实的消息总线实现
3. **介于消息总线与 IFlowModule 之间** - 工具模拟消息总线的功能
4. **完整测试流程** - 测试 IFlowModule 的完整消息处理流程
5. **工具不感知 tmux** - 工具只对接 IFlowModule，不感知 tmux 的存在
6. **保持 IFlowModule 接口不变** - 不修改 IFlowModule 的接口，不影响现有代码

### 架构设计

```
工具 (IFlowInteractiveTool)
  ↓ 从配置文件读取参数
  ↓ 传递给 IFlowModule
IFlowModule (接口不变)
  ↓ 发送 Message
模拟消息总线 (MockMessageBus)
  ↓ 路由
IFlowModule.receive(Message)
  ↓ _on_receive
IFlowModule.send()
  ↓ controller.send_message()

Monitor 提取 OutboundMessage
  ↓ _on_monitor_message
scope 过滤
  ↓ 转换为 Message
调用钩子 _message_sent_hook(Message)  ← 工具拦截
  ↓ send_to_bus
真实消息总线（可选）
```

### 工具特性

| 特性 | 说明 |
|------|------|
| 模拟消息总线 | 完全模拟消息总线行为 |
| 实时显示 | 实时显示 iflow 输出 |
| 消息分类 | 按标记分类显示（✦/✻） |
| 状态监控 | 实时显示 iflow 状态 |
| 历史记录 | 保存完整的交互历史 |
| 中断机制 | 支持中断等待，发送新消息 |
| 会话保持 | 命令行模式默认保持会话 |
| 日志文件 | 详细日志记录到文件 |

### 使用方法

#### 交互模式

```bash
# 基本使用
python tools/iflow_interactive_tool.py

# 指定配置文件
python tools/iflow_interactive_tool.py --config config.json

# 清理残留会话
python tools/iflow_interactive_tool.py --clean
```

**交互命令**：

| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 显示帮助信息 | `/help` |
| `/status` | 查看状态 | `/status` |
| `/source` | 切换来源 | `/source wechat_bot1` |
| `/scope` | 切换范围 | `/scope all` |
| `/history` | 查看历史 | `/history` |
| `/spam` | 拒绝机制测试 | `/spam` |
| `/quit` | 退出 | `/quit` |
| 直接输入 | 发送消息 | `你好` |

#### 命令行模式（默认保持会话）

```bash
# 基本使用（保持会话）
python tools/iflow_interactive_tool.py --message "你好"

# 指定范围
python tools/iflow_interactive_tool.py --message "你好" --scope all

# 销毁会话
python tools/iflow_interactive_tool.py --message "你好" --cleanup
```

**会话保持**：

```bash
# 第一次执行（创建新会话）
python tools/iflow_interactive_tool.py --message "第一条消息"

# 第二次执行（复用现有会话）
python tools/iflow_interactive_tool.py --message "第二条消息"

# 第三次执行（复用现有会话）
python tools/iflow_interactive_tool.py --message "第三条消息"

# 销毁会话
python tools/iflow_interactive_tool.py --message "最后一条消息" --cleanup
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config PATH` | 配置文件路径 | `config.json` |
| `--message TEXT` | 命令行模式：发送消息后退出 | 无 |
| `--scope MODE` | scope 模式：`all` 或 `reply_only` | `reply_only` |
| `--clean` | 清理残留的 tmux 会话 | `False` |
| `--keep-alive` | 保持 tmux 会话（默认，命令行模式） | `True` |
| `--cleanup` | 销毁 tmux 会话（命令行模式） | `False` |

### 测试场景

1. **基本消息发送** - 验证消息能正确发送到 iflow
2. **scope 过滤** - 验证只发送 ✦ 标记的消息
3. **✻ 标记记录** - 验证 ✻ 标记的消息被正确记录但不发送
4. **状态检测** - 验证状态正确变化
5. **重复消息** - 验证去重逻辑
6. **多行内容** - 验证多行内容正确提取
7. **拒绝机制** - 验证生成中时拒绝新消息
8. **会话保持** - 验证多次执行能复用会话

### 关键优势

1. **消息格式一致** - 发送和接收的都是 `Message` 对象
2. **不依赖真实消息总线** - 使用模拟的消息总线
3. **测试完整流程** - 包括 scope 过滤、消息转换
4. **代码改动最小** - 只在 IFlowModule 中添加钩子，不影响现有代码
5. **工具介于消息总线与 IFlowModule 之间** - 符合要求
6. **工具不感知 tmux** - 工具只对接 IFlowModule
7. **保持 IFlowModule 接口不变** - 不影响现有代码（bot.py）

---

## 使用示例

### 示例 1：交互模式基本使用

```bash
# 启动交互模式
python tools/iflow_interactive_tool.py

# 输入消息
你好

# 查看状态
/status

# 切换范围
/scope all

# 发送消息
帮我写一个Python脚本

# 查看历史
/history

# 退出
/quit
```

### 示例 2：命令行模式单次执行

```bash
# 发送单条消息
python tools/iflow_interactive_tool.py --message "你好"

# 发送消息并显示所有内容
python tools/iflow_interactive_tool.py --message "你好" --scope all

# 发送消息后销毁会话
python tools/iflow_interactive_tool.py --message "你好" --cleanup
```

### 示例 3：命令行模式连续执行（会话保持）

```bash
# 第一次执行
python tools/iflow_interactive_tool.py --message "第一条消息"

# 第二次执行（复用会话）
python tools/iflow_interactive_tool.py --message "你记得刚才我问你什么吗"

# 第三次执行（复用会话）
python tools/iflow_interactive_tool.py --message "继续完成上次的任务"

# 销毁会话
python tools/iflow_interactive_tool.py --message "再见" --cleanup
```

### 示例 4：测试拒绝机制

```bash
# 启动交互模式
python tools/iflow_interactive_tool.py

# 发送消息
发送第一条消息

# 在生成中时尝试发送第二条消息
发送第二条消息

# 观察拒绝响应
# {"success": false, "error": "iflow_generating", "message": "iflow 生成中，请稍后再试", "duration": 15}

# 或使用 /spam 命令测试
/spam
```

### 示例 5：查看日志

```bash
# 查看工具日志
tail -f logs/iflow_tool.log

# 查看交互日志
tail -f logs/interactions/interactions-*.jsonl

# 查看特定日期的交互日志
cat logs/interactions/interactions-20240315.jsonl | jq
```

### 示例 6：调试模式

```bash
# 清理残留会话后启动
python tools/iflow_interactive_tool.py --clean

# 查看详细日志
python tools/iflow_interactive_tool.py 2>&1 | tee debug.log

# 指定配置文件
python tools/iflow_interactive_tool.py --config config-dev.json
```

---

## 故障排查

### 问题 1：iflow 启动失败

**症状**：
```
等待 iflow 启动...
错误：等待 iflow 就绪超时（60秒）
```

**可能原因**：
1. tmux 未安装
2. iflow CLI 未安装或未登录
3. 网络问题
4. 配置文件错误

**解决方案**：
```bash
# 检查 tmux
tmux -V

# 检查 iflow
iflow --version

# 测试 iflow 手动启动
tmux new-session -s test 'iflow --model kimi-k2.5'

# 检查配置文件
cat config.json
```

### 问题 2：消息发送失败

**症状**：
```
发送消息失败：iflow 未就绪
```

**可能原因**：
1. iflow 未启动
2. tmux 会话已销毁
3. 状态检测错误

**解决方案**：
```bash
# 检查 tmux 会话
tmux ls

# 检查 iflow 进程
ps aux | grep iflow

# 重新启动
python tools/iflow_interactive_tool.py --clean
```

### 问题 3：消息重复显示

**症状**：
```
消息显示两次
```

**可能原因**：
1. 钩子和消息总线双重调用
2. 去重机制失效

**解决方案**：
- 已在代码中修复（v4.4+）
- 确保使用最新版本

### 问题 4：状态检测错误

**症状**：
```
iflow 已回复完成，但工具仍显示生成中
```

**可能原因**：
1. 状态检测误判
2. 用户消息包含"生成中"

**解决方案**：
- 已在代码中修复（v4.4+）
- 使用正则表达式精确匹配
- 确保使用最新版本

### 问题 5：性能问题

**症状**：
```
监控占用大量 CPU
```

**可能原因**：
1. 提取行数过多
2. 处理频率过高

**解决方案**：
- 已在代码中优化（v4.4+）
- 使用双模式监控
- IDLE 状态下性能提升 50 倍

### 问题 6：会话保持失败

**症状**：
```
第二次执行时未复用会话
```

**可能原因**：
1. 第一次执行使用了 `--cleanup`
2. tmux 会话被外部销毁
3. iflow 进程异常退出

**解决方案**：
```bash
# 检查 tmux 会话
tmux ls

# 检查 iflow 进程
ps aux | grep iflow

# 重新执行（不要使用 --cleanup）
python tools/iflow_interactive_tool.py --message "消息"
```

### 问题 7：中断机制不工作

**症状**：
```
按 Ctrl+C 无法中断等待
```

**可能原因**：
1. 中断信号未捕获
2. 事件未正确触发

**解决方案**：
- 已在代码中修复（v4.4+）
- 确保使用最新版本

---

## 总结

### 核心特性

1. **自动化生命周期**：模块与 tmux/iflow 完全同步
2. **完整记录**：所有消息都记录，不丢失任何信息
3. **灵活过滤**：scope 参数控制发送内容
4. **状态管理**：生成中时拒绝新消息
5. **消息归属**：记录消息来源，支持多轮对话
6. **订阅机制**：通过订阅通知关注方
7. **性能优化**：双模式监控，性能提升 50 倍
8. **倒数第二原则**：延迟发送，保证消息完整
9. **中断机制**：支持中断等待，发送新消息
10. **会话保持**：命令行模式默认保持会话

### 最佳实践

1. **开发测试**：使用交互模式快速测试
2. **批量任务**：使用命令行模式，保持会话
3. **生产环境**：使用消息总线集成
4. **故障排查**：查看日志文件 `logs/iflow_tool.log`
5. **性能监控**：观察 IDLE 状态的监控效率

### 文件清单

| 文件 | 说明 |
|------|------|
| `src/modules/iflow/__init__.py` | 模块导出 |
| `src/modules/iflow/module.py` | IFlowModule 主类 |
| `src/modules/iflow/controller.py` | tmux/iflow 控制器 |
| `src/modules/iflow/monitor.py` | 输出监控器 |
| `src/modules/iflow/session_manager.py` | 会话管理器 |
| `src/modules/iflow/logger.py` | 交互记录器 |
| `src/modules/iflow/message_store.py` | 消息库 |
| `tools/iflow_interactive_tool.py` | 交互式测试工具 |

### 相关文档

- [消息总线设计方案](./05-消息总线设计方案.md)
- [模块重构方案](./01-模块重构方案.md)
- [启动方案设计](./06-启动方案设计.md)