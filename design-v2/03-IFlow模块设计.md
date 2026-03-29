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
   等待 0.2 秒

2. 发送消息内容（使用 -l 选项逐字发送）
   tmux send-keys -t <session> -l <message>
   等待 1.0 秒

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
| 轻量级 | IDLE 状态 | **20 行** | 0.5 秒 |
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

**重要**：交互记录中的**所有消息内容均从 tmux 读取**，而不是使用模块收到的原始内容。这样可以确保日志准确反映 tmux 中实际发生的内容，包括：
- 发送的消息（从 tmux 中以 `>` 开头的行读取）
- 接收的回复（从 tmux 中以 ✦/✻ 标记的行读取）

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
- 文件命名：`iflow_<渠道名>_<YYYYMMDD>_<HHMMSS>.json`

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
- 使用标记行字符串优先定位已记录的消息
- 字符串定位失败时，使用内容哈希作为备用定位机制
- 支持未来任意新标记符号的扩展
- 避免重复发送相同消息
- 记录已发送的消息标识

**定位策略**：

**策略1：字符串定位（优先）**
- 使用标记行字符串（去掉标记符号）作为消息的唯一标识
- 提取标记行：从包含标记符号的行中提取内容
- 字符串格式：`marker_only = line.replace(marker_symbol, '').strip()`
- 优势：快速、准确，不需要计算哈希值

**策略2：哈希定位（备用）**
- 当字符串定位失败时（如消息内容发生变化），使用内容哈希定位
- 计算内容哈希：`content_hash = hashlib.md5(full_content.encode()).hexdigest()`
- 构造唯一标识：`unique_id = f"{marker_symbol}:{marker_only}:{content_hash}"`
- 优势：准确区分内容相同但标记不同的消息

**定位流程**：
1. 首先尝试使用标记行字符串定位
2. 如果找到匹配的字符串，认为是同一条消息
3. 如果找不到匹配的字符串，计算内容哈希，再次定位
4. 如果仍然找不到，认为是新消息

**去重优势**：
1. **快速定位**：字符串定位比哈希定位更快
2. **准确区分**：相同标记行 + 相同内容 → 同一条消息；内容不同 → 不同消息
3. **支持任意标记符号**：不依赖预定义的标记类型，未来新增标记符号无需修改代码
4. **处理内容变化**：当消息内容更新时，哈希定位可以准确识别
5. **保持唯一性**：字符串定位 + 哈希定位双重保障，确保不会重复

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

### 无来源消息处理

#### 场景定义

**无来源消息**：用户直接在 tmux 会话中的 iflow 输入框输入消息，而不是通过外部渠道（企业微信、飞书等）发送。

**特点**：
- 没有外部渠道触发的入站消息
- IFlowModule 没有记录 source
- 无法确定回复应该发给谁

#### 检测机制

**检测方式**：IFlowMonitor 持续监控 tmux 输出，检测用户直接输入的消息。

```
用户在 iflow 中输入消息
    ↓
iflow 处理消息
    ↓
IFlowMonitor 检测到新的用户输入
    ↓
判断：是否有对应的入站消息记录？
    ├─ 有 → 正常归属流程（source 不为空）
    └─ 无 → 无来源消息处理流程
```

**检测方法**：

1. **消息输入检测**：检测 iflow 输出中出现的用户输入（`>` 开头的行）
2. **归属判断**：查询 MessageStore 中是否有 processing 状态的消息
3. **无来源标记**：如果没有对应的入站记录，标记为无来源消息

#### 处理流程

```
检测到无来源消息
    ↓
记录到 MessageStore（source=""）
    ↓
等待 iflow 生成回复
    ↓
IFlowMonitor 提取回复消息
    ↓
合并所有 ✦ 标记的消息为一条
    ↓
构造 OutboundMessage：
  - type: reply
  - content: 合并后的回复内容
  - receiver: ""（空，表示无特定接收者）
    ↓
发送到消息总线
    ↓
MessageBus 广播给所有订阅者
    ↓
订阅者（渠道模块）根据业务逻辑决定是否处理
```

#### 消息合并规则

**原则**：将一次对话的所有 ✦ 标记消息合并为一条完整消息。

**合并逻辑**：
```python
def merge_reply_messages(messages: List[Dict]) -> str:
    """合并回复消息"""
    reply_contents = []
    for msg in messages:
        if msg.get('marker_type') == '✦':
            reply_contents.append(msg.get('content', ''))
    return '\n\n'.join(reply_contents)
```

#### 消息总线路由

**路由策略**：无来源消息（receiver=""）使用**广播模式**。

```python
# MessageBus 路由逻辑
if message.receiver == "":
    # 广播给所有订阅 iflow 输出的模块
    for subscriber in self._iflow_subscribers:
        await subscriber.on_message(message)
else:
    # 点对点路由
    target_module = self.get_module(message.receiver)
    if target_module:
        await target_module.on_message(message)
```

#### 渠道处理策略

**渠道模块的处理策略**：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 忽略 | 不处理无来源消息 | 企业微信、飞书（无法确定发给谁） |
| 通知 | 发送通知给管理员 | 运维监控场景 |
| 记录 | 仅记录日志 | 审计场景 |
| 广播 | 发送给所有关联用户 | 公告场景 |

**默认策略**：忽略无来源消息（渠道模块自行决定是否处理）

#### 配置项

```json
{
  "iflow": {
    "handle_no_source": true,        // 是否处理无来源消息
    "no_source_strategy": "ignore",  // 处理策略：ignore/notify/log/broadcast
    "no_source_notify_user": ""      // 通知目标用户（strategy=notify 时）
  }
}
```

#### 与有来源消息的对比

| 项目 | 有来源消息 | 无来源消息 |
|------|-----------|-----------|
| 触发方式 | 外部渠道发送 | 用户直接在 iflow 输入 |
| source 字段 | 渠道标识（如 `wechat_bot1`） | 空字符串 |
| MessageStore 记录 | 有入站记录 | 只有出站记录 |
| 回复归属 | 点对点（指定 receiver） | 广播（receiver=""） |
| 渠道处理 | 发送给对应用户 | 根据策略处理 |

---

## 完整消息链路

### 概述

本章节详细描述一次完整的消息处理流程，从用户发送消息开始，到 iflow 完成回复并结束，涵盖所有关键步骤：消息接收、状态变更、消息记录、消息发送、结束判断等。

### 场景设定

假设用户通过企业微信发送一条消息："帮我写一个 Python 脚本"，配置为 reply_only 模式（只发送 ✦ 标记的消息）。

### 完整流程

#### 阶段 1：消息接收与注入

**步骤 1：用户发送消息**
- 用户在企业微信中输入："帮我写一个 Python 脚本"
- 消息通过企业微信 API 回调到 WeChatChannel
- WeChatChannel 解析消息内容，构造 Message 对象

**步骤 2：消息路由**
- WeChatChannel 调用 send_to_bus() 方法
- MessageBus 根据绑定关系，将消息路由到 IFlowModule
- IFlowModule 的 receive() 方法被调用

**步骤 3：消息预处理**
- IFlowModule 的 _on_receive() 钩子方法被触发
- 检查当前状态（IDLE 或 GENERATING）
- 如果是 GENERATING 状态（iflow 正在生成中），拒绝消息并返回错误提示
- 如果是 IDLE 状态，继续处理

**步骤 4：记录消息**
- IFlowModule 调用 MessageStore 记录入站消息
- 生成唯一的 message_id
- 记录 source（发送方，如 "wechat_bot1"）
- 记录 scope（如 "reply_only"）
- 保存到交互日志

**步骤 5：消息注入**
- IFlowModule 调用 IFlowController 的 send_message() 方法
- IFlowController 通过 tmux 的 send-keys 命令将消息注入到 iflow CLI
- 消息出现在 iflow 的输入框中
- iflow 开始处理消息

#### 阶段 2：状态变更与生成中检测

**步骤 6：生成中状态检测**
- IFlowMonitor 持续监听 tmux 输出（每 0.5 秒检查一次）
- 检测到输出中出现 "生成中" 关键字
- IFlowMonitor 判断状态从 IDLE 切换到 GENERATING
- 更新内部状态变量 _state = IFlowState.GENERATING
- 记录状态变更时间：_generating_state_started = 当前时间

**步骤 7：通知状态变更**
- IFlowMonitor 调用 _notify_state_change() 方法
- 通过消息总线发布状态变更通知
- 订阅者（如 ModuleManager）收到通知，更新模块状态
- 模块管理器记录 iflow 处于生成中状态

#### 阶段 3：消息记录与发送（GENERATING 状态）

**步骤 8：提取消息**
- IFlowMonitor 进入 GENERATING 状态后，开始完整提取模式
- 每次检查提取 tmux 输出的最后 1000 行
- 过滤 TUI 界面内容（包含 ✦ 或 ✻ 的行）
- 扫描标记行（✦、✻、或其他标记符号）

**步骤 9：第一次提取（T1 时刻）**
- tmux 输出显示：
  ```
  ✻ 思考中...
  ```
- IFlowMonitor 提取到 1 条消息：
  - 消息1：标记类型 ✻，内容 "思考中..."
- 根据"延迟记录原则"，只记录不发送（等待下一个消息）
- 更新 _current_messages = [消息1]
- _sent_count = 0

**步骤 10：第二次提取（T2 时刻）**
- tmux 输出显示：
  ```
  ✻ 思考中...
    正在分析需求...

  ✦ 好的，我来帮你写一个 Python 脚本
  ```
- IFlowMonitor 提取到 2 条消息：
  - 消息1：标记类型 ✻，内容 "思考中...\n正在分析需求..."
  - 消息2：标记类型 ✦，内容 "好的，我来帮你写一个 Python 脚本"
- 根据"延迟记录原则"，记录并发送消息1（倒数第二，已完整）
- 检查消息1 的唯一标识（标记符号 + 标记行内容 + 内容哈希）
- 如果唯一标识未发送过，发送消息1
- 更新 _sent_count = 1
- 消息1 的 scope 为 "reply_only"，因为是 ✻ 标记，被过滤掉，不发送

**步骤 11：第三次提取（T3 时刻）**
- tmux 输出显示：
  ```
  ✻ 思考中...
    正在分析需求...

  ✦ 好的，我来帮你写一个 Python 脚本
    这是一个简单的示例脚本：

  ✦ ```python
  ✦ def hello():
  ✦     print("Hello, World!")
  ✦ ```
  ```
- IFlowMonitor 提取到 3 条消息：
  - 消息1：标记类型 ✻，内容 "思考中...\n正在分析需求..."
  - 消息2：标记类型 ✦，内容 "好的，我来帮你写一个 Python 脚本\n这是一个简单的示例脚本："
  - 消息3：标记类型 ✦，内容 "```python\ndef hello():\n    print(\"Hello, World!\")\n```"
- 根据"延迟记录原则"，记录并发送消息2（倒数第二，已完整）
- 检查消息2 的唯一标识，未发送过
- 消息2 的 scope 为 "reply_only"，因为是 ✦ 标记，通过过滤
- 构造 OutboundMessage，设置 receiver 为请求时的 source（"wechat_bot1"）
- 调用 _send_message() 发送到消息总线
- MessageBus 路由到 WeChatChannel
- WeChatChannel 发送到企业微信
- 用户收到："好的，我来帮你写一个 Python 脚本\n这是一个简单的示例脚本："
- 更新 _sent_count = 2

**步骤 12：持续监控（T4、T5、... 时刻）**
- 每次检查都执行相同的逻辑：
  - 提取所有消息
  - 找出新增的消息（current_messages[_sent_count:]）
  - 按顺序记录并发送新增的消息
  - 每条消息都检查唯一标识，避免重复发送
  - ✻ 标记的消息被过滤，不发送
  - ✦ 标记的消息通过过滤，立即发送

#### 阶段 4：结束检测与最后消息处理

**步骤 13：生成中消失检测**
- iflow 完成回复，"生成中" 从 tmux 输出中消失
- IFlowMonitor 检测到 is_generating = False
- 开始等待稳定

**步骤 14：连续检测（3次扫描）**
- 持续检查 tmux 输出
- 如果 "生成中" 重新出现（可能 iflow 继续生成），重置计数器
- 如果 "生成中" 持续消失，记录消失次数
- 当连续3次扫描中"生成中"的标志消失，确认结束
- 记录日志：生成中连续3次消失，交互结束

**步骤 15：记录并发送最后一条消息**
- IFlowMonitor 提取所有消息
- 找出剩余未发送的消息（current_messages[_sent_count:]）
- 按顺序记录并发送剩余的消息
- 假设最后一条消息是：
  - 消息4：标记类型 ✦，内容 "脚本完成，你可以运行这个示例。"
- 检查消息4 的唯一标识，未发送过
- 消息4 的 scope 为 "reply_only"，通过过滤
- 发送到消息总线，路由到 WeChatChannel
- 用户收到："脚本完成，你可以运行这个示例。"
- 更新 _sent_count = 4

**步骤 16：清理状态**
- 清空 _current_messages = []
- 重置 _sent_count = 0
- 清空 _sent_message_hashes = set()（为下一次对话准备）
- 清空 _stable_start_time = None
- 切换到 IDLE 状态：_state = IFlowState.IDLE
- 通知状态变更

#### 阶段 5：消息记录完成

**步骤 17：完整交互记录**
- InteractionLogger 记录完整的交互过程
- 包括：入站消息、出站消息、时间戳、状态变化
- 保存到日志文件（如 iflow_bot1_20260317_190046.json）

**步骤 18：MessageStore 更新**
- 更新对话状态
- 记录对话结束时间
- 保存消息统计数据（如消息数量、类型分布）

### 关键时序图

```
时间线：
T0: 用户发送消息
T1: IFlowModule 接收消息
T2: IFlowController 注入消息到 iflow
T3: iflow 开始处理
T4: 检测到"生成中"，切换到 GENERATING 状态
T5: 第一次提取，提取到消息1（✻），只记录不发送
T6: 第二次提取，提取到消息1、2，发送消息1（✻，被过滤）
T7: 第三次提取，提取到消息1、2、3，发送消息2（✦，发送给用户）
T8: 第四次提取，提取到消息1、2、3、4，发送消息3（✦，发送给用户）
T9: 第五次提取，提取到消息1、2、3、4、5，发送消息4（✦，发送给用户）
T10: "生成中"消失，开始稳定计时
T11: 稳定计时 1 秒
T12: 稳定计时 2 秒，确认结束
T13: 发送最后一条消息（✦，发送给用户）
T14: 清理状态，切换到 IDLE
```

### 异常情况处理

**情况 1：生成中短暂消失又重新出现**
- 检测到 "生成中" 消失，开始稳定计时
- 1 秒后 "生成中" 重新出现
- 重置 _stable_start_time = None
- 继续正常记录和发送消息
- 不触发结束逻辑

**情况 2：消息内容更新（同一标记的消息内容变化）**
- T1 时刻：消息1 内容为 "思考中..."
- T2 时刻：消息1 内容更新为 "思考中...\n正在分析..."
- IFlowMonitor 重新计算消息1 的唯一标识（标记符号 + 标记行内容 + 内容哈希）
- 由于内容哈希不同，识别为新的消息
- 记录并发送更新后的消息1
- 避免发送不完整的中间版本

**情况 3：重复消息（tmux 输出中同一消息多次出现）**
- T1 时刻：提取到消息1
- T2 时刻：提取到消息1、消息1（重复）
- IFlowMonitor 检查消息1 的唯一标识
- 发现已在 _sent_message_hashes 中
- 跳过发送，避免重复

### 性能优化

**轻量级检测（IDLE 状态）**
- 每次只提取 tmux 输出的最后 50 行
- 只检测 "生成中" 关键字
- 不提取消息，不处理内容
- 减少资源消耗

**完整记录（GENERATING 状态）**
- 每次提取 tmux 输出的最后 1000 行
- 完整提取消息内容
- 实时发送新增消息
- 保证用户体验

### 总结

一次完整的消息链路包含 18 个步骤，涵盖消息接收、状态变更、消息记录、消息发送、结束判断等所有关键环节。

**核心原则**：
1. 延迟记录原则：等待下一个消息出现后再发送上一个，保证消息完整
2. 状态管理原则：准确检测 IDLE 和 GENERATING 状态
3. 消息去重原则：使用唯一标识避免重复发送
4. 立即发送原则：每记录一条消息，立即判断并发送
5. Scope 过滤原则：由 IFlowModule 根据 reply_mode 决定是否发送

**优势**：
- 消息完整：只发送完整的消息，不发送中间版本
- 实时性好：消息生成过程中实时发送，用户体验好
- 去重可靠：使用字符串定位 + 哈希定位，准确去重
- 状态准确：连续3次扫描"生成中"消失，避免误判结束
- 性能优化：IDLE 状态轻量级检测，减少资源消耗

---

## 消息提取优化

### 核心设计原则

#### 1. 消息记录原则

**所有标记都是消息**：
- ✦、✻、◇、◆、★ 等所有标记都是一条消息
- 不区分消息类型，统一记录

**延迟记录原则**：
- 消息1出现：不记录（可能不完整）
- 消息2出现：记录消息1（此时消息1已完整）
- 消息3出现：记录消息2（此时消息2已完整）
- 消息4、5、6、7同时出现：按顺序记录消息3、4、5、6

**目的**：保证记录的消息是完整的，不会记录中间版本

**完整记录流程**：

**步骤 1：iflow 收到消息，出现生成中**
- 用户通过渠道（如企业微信）发送消息
- IFlowController 将消息注入到 iflow CLI
- iflow 开始处理，tmux 输出中出现 "生成中" 标志
- 状态从 IDLE 切换到 GENERATING

**步骤 2：状态变更，更改扫描频率**
- 状态变更：IDLE → GENERATING
- 扫描频率变更：
  - IDLE 状态：每 0.5 秒扫描 tmux 输出的最后 50 行（轻量级检测）
  - GENERATING 状态：每 0.5 秒扫描 tmux 输出的最后 1000 行（完整记录）

**步骤 3：扫描并提取**
- 扫描 tmux 输出（GENERATING 状态扫描 1000 行）
- 将回复消息按标记行为分界，分成多条消息
- 每条消息包含：标记类型、标记行字符串、完整内容
- 标记行分界：以 ✦、✻、◇、◆、★ 等标记符号为分界线

**步骤 4：只有 1 条消息**
- 如果回复消息只有一条（消息1），则不做任何处理
- 原因：可能不完整，等待下一个消息出现

**步骤 5：有 2 条消息**
- 记录消息1所在到消息2上方的内容
- 从消息1所在行提取一段字符串作为消息的唯一标识记录
- 计算消息1的完整哈希值并记录
- 示例：
  - 消息1：✻ 思考中...
  - 标记行字符串："思考中..."
  - 内容哈希：md5_hash1

**步骤 6：第二次扫描定位**
- 第二次扫描如果消息有5条，根据字符串找到记录的最新消息（消息1）的字符串所在位置
- 按字符串只能搜到一条说明定位成功
- 如果按字符串能找到多条消息，则进一步使用哈希值定位消息1的位置
- 定位成功后，消息1与消息5之间的消息逐个记录

**步骤 7：记录逻辑**
- 记录消息2、消息3、消息4
- 更新最新记录的消息是消息4
- 记录每条消息的标记行字符串和完整哈希值
- 示例：
  - 消息2：✦ 好的，我来帮你写... → 标记行字符串："好的，我来帮你写..."
  - 消息3：✦ ```python... → 标记行字符串："```python..."
  - 消息4：✦ 这是一个示例... → 标记行字符串："这是一个示例..."

**步骤 8：后续记录**
- 第三次扫描如果有新消息，重复步骤6和7
- 定位最新记录的消息（消息4），记录中间的消息
- 更新最新记录的消息

**步骤 9：结束判断**
- 当连续3次扫描中"生成中"的标志消失，记录最新的一条消息
- 更改状态为 IDLE
- 示例：
  - T1: 扫描，有"生成中"
  - T2: 扫描，有"生成中"
  - T3: 扫描，没有"生成中"
  - T4: 扫描，没有"生成中"
  - T5: 扫描，没有"生成中"（连续3次消失）
  - 记录最新的一条消息
  - 状态切换：GENERATING → IDLE

#### 2. 消息发送原则

**立即发送原则**：
- 每记录一条消息，立即判断是否需要发送
- 需要则立即发送
- 不等待

**发送判断原则**：
- 由IFlowModule根据reply_mode判断是否发送
- reply_only：只发送✦标记的消息
- all_messages：发送所有消息（✦+✻+其他）

#### 3. 状态管理原则

**GENERATING状态原则**：
- iflow正在生成中
- 变成GENERATING时：扫描消息内容并记录（但按延迟记录原则）
- 持续扫描，检测新消息
- 不关心是否"生成中"，只关注标记消息

**IDLE状态原则**：
- 不是生成中
- 只检查是否出现"生成中""按ESC取消"等
- 检测到则切换到GENERATING状态
- 扫描并记录已完整的消息

**状态切换原则**：
- GENERATING→IDLE：当连续3次扫描中"生成中"的标志消失，记录最新的一条消息，更改状态为 IDLE
- IDLE→GENERATING：检测到"生成中"标志出现，切换到 GENERATING 状态

#### 4. 消息去重原则

**字符串定位和哈希定位机制**：
- 使用标记行字符串优先定位已记录的消息
- 字符串定位失败时，使用内容哈希作为备用定位机制
- 确保每条消息只会被记录一次

**定位策略**：

**策略1：字符串定位（优先）**
- 使用标记行字符串（去掉标记符号）作为消息的唯一标识
- 提取标记行：从包含标记符号的行中提取内容
- 字符串格式：`marker_only = line.replace(marker_symbol, '').strip()`
- 定位逻辑：从后往前遍历消息列表，查找匹配的字符串
- 定位成功条件：找到唯一一条匹配的消息

**策略2：哈希定位（备用）**
- 当字符串定位失败时（如找到多条匹配的消息），使用内容哈希定位
- 计算内容哈希：`content_hash = hashlib.md5(full_content.encode()).hexdigest()`
- 定位逻辑：使用哈希值精确匹配
- 定位成功条件：找到唯一一条匹配的消息

**定位流程**：
1. 首先尝试使用标记行字符串定位
2. 如果找到唯一一条匹配的消息，定位成功
3. 如果找到多条匹配的消息，计算内容哈希，再次定位
4. 如果仍然找不到或找到多条，认为是新消息或定位失败

**示例**：
```
已记录消息：
- 消息1：✻ 思考中... → 标记行字符串："思考中..."，哈希：md5_hash1
- 消息2：✦ 好的，我来帮你写... → 标记行字符串："好的，我来帮你写..."，哈希：md5_hash2

第二次扫描提取到消息：
[消息1, 消息2, 消息3, 消息4, 消息5]

定位过程：
1. 从后往前查找字符串："思考中..."
2. 找到消息1，定位成功
3. 记录消息2、消息3、消息4
4. 更新最新记录的消息是消息4

第三次扫描提取到消息：
[消息1, 消息2, 消息3, 消息4, 消息5, 消息6]

定位过程：
1. 从后往前查找字符串："这是一个示例..."（消息4的标记行字符串）
2. 找到消息4，定位成功
3. 记录消息5
4. 更新最新记录的消息是消息5
```

#### 5. Scope字段原则

**Scope无关原则**：
- IFlowMonitor记录所有消息，不关心scope
- OutboundMessage不需要scope字段
- 完全由IFlowModule根据reply_mode决定是否发送

### 核心逻辑流程

#### 消息记录与发送流程

**场景1：逐个消息出现**
```
T1: 检测到消息1 [✦ 回复1]
    → 不记录（等待下一个消息）
    
T2: 检测到消息2 [✦ 回复2]
    → 记录消息1（已完整）
    → 发送消息1（根据reply_mode判断）
    
T3: 检测到消息3 [✦ 回复3]
    → 记录消息2（已完整）
    → 发送消息2（根据reply_mode判断）
    
T4: 检测到消息4 [✻ 思考A]
    → 记录消息3（已完整）
    → 发送消息3（根据reply_mode判断）
```

**场景2：多个消息同时出现**
```
T5: 检测到消息5、6、7、8 [✦ 回复4, ✦ 回复5, ✦ 回复6, ✦ 回复7]
    → 按顺序记录消息4、5、6
    → 按顺序发送消息4、5、6（根据reply_mode判断）
```

**场景3：生成中结束**
```
GENERATING→IDLE：
    → 记录最后一条消息（消息7）
    → 发送消息7（根据reply_mode判断）
```

#### 状态管理流程

```
初始状态：IDLE
    ↓
检测到"生成中"
    ↓
切换到GENERATING状态
    ↓
扫描消息内容
    ↓
检测到新消息？
    ├─ 是 → 记录上一条消息 → 发送 → 继续扫描
    └─ 否 → 继续扫描
    ↓
检测到"生成中"消失？
    ├─ 是 → 切换到IDLE状态 → 记录最后一条消息 → 发送
    └─ 否 → 继续GENERATING状态
```

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
| **去重机制** | 哈希去重 | 字符串定位（基于标记行）+ 哈希定位（备用） |
| **结束检测** | 稳定检测（2 秒） | 连续3次扫描"生成中"消失 |

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
- 未在生成中时，性能提升约 **50 倍**（20 行 vs 1000 行）
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
- [启动方案设计](./06-启动与部署.md)
- [scope命令历史消息重复问题修复方案](./19-scope命令历史消息重复问题修复方案.md)

---

## 六、缓存管理策略

### 6.1 缓存设计

**缓存用途**：
- 消息去重：避免重复发送相同消息
- 定位机制：使用字符串定位和哈希定位

**缓存数据结构**：
```python
# 标记行字符串集合（用于字符串定位）
_sent_marker_strings: Set[str]

# 内容哈希集合（用于哈希定位）
_sent_message_hashes: Set[str]
```

### 6.2 缓存管理原则

**原则1：保留缓存，避免清空**

**问题**：
- 原始设计在每次 `GENERATING → IDLE` 时清空缓存
- 导致历史消息可以被重复发送
- 触发 /scope 命令时会出现历史消息重复问题

**解决方案**：
- 不在 `GENERATING → IDLE` 时清空缓存
- 保留缓存用于持续去重
- 只在必要时清理旧缓存

**原则2：定期清理，控制内存**

**清理策略**：
- 设置最大缓存大小（如：100 条）
- 当缓存超过阈值时，清理旧缓存
- 保留最近的消息（如：50 条）

**清理逻辑**：
```python
def _cleanup_cache(self):
    """清理旧缓存，保留最近的 N 条消息"""
    max_cache_size = 100
    keep_count = 50

    if len(self._sent_marker_strings) > max_cache_size:
        # 保留最近的 keep_count 条消息
        self._sent_marker_strings = set(list(self._sent_marker_strings)[-keep_count:])
        self._sent_message_hashes = set(list(self._sent_message_hashes)[-keep_count:])
```

**清理时机**：
- 在添加新消息到缓存后检查
- 达到阈值时自动清理

### 6.3 行号不可靠性

**问题**：
- tmux 有 history-limit 限制（默认：2000 行）
- 超过限制后，旧内容会被删除
- 行号会发生变化

**结论**：
- 不能依赖行号过滤消息
- 必须使用缓存去重机制

### 6.4 已知问题修复

**问题1：/scope 命令历史消息重复**

**问题描述**：
- 执行 `/scope all` 后，历史消息被重复发送
- 导致 iflow 进入"生成中"状态
- 新消息被拒绝

**根本原因**：
1. 缓存在 `GENERATING → IDLE` 时被清空
2. 历史消息通过去重检查，被重新发送

**修复方案**：
- 修改 monitor.py 第 318-323 行
- 注释掉缓存清空逻辑
- 添加定期清理机制

**修复代码**：
```python
# 原代码（monitor.py 第 318-323 行）：
# 清理去重集合（为下一次对话准备）
self._sent_message_hashes.clear()
self._sent_marker_strings.clear()

# 修改为：
# 不清空缓存，保留去重机制
# 只在新会话开始时清空缓存（可选）
# self._sent_message_hashes.clear()  # 注释掉
# self._sent_marker_strings.clear()  # 注释掉
```

**修复效果**：
- 历史消息不会被重复发送
- /scope 命令正常工作
- 内存占用可控

**修复时间**：2026-03-18

---

## 七、测试用例

### 7.1 消息去重测试

**测试1：基本去重**
- 发送 "1+1=?" → 收到 "1+1=2"
- 再次发送 "1+1=?" → 收到 "1+1=2"
- 验证：消息不会被重复发送

**测试2：长文本去重**
- 发送 "写一个 Python 脚本" → 收到多条回复
- 验证：每条回复只发送一次

### 7.2 Scope 命令测试

**测试1：/scope all 命令**
- 发送 "1+1=?" → 收到 "1+1=2"
- 发送 "/scope all" → 切换模式
- 发送 "2+2=?" → 收到 "2+2=4"
- 验证：历史消息 "1+1=2" 不被重复发送

**测试2：/scope reply 命令**
- 发送 "1+1=?" → 收到 "1+1=2"
- 发送 "/scope all" → 切换到全部消息模式
- 发送 "/scope reply" → 切换回回复模式
- 发送 "2+2=?" → 收到 "2+2=4"
- 验证：历史消息不被重复发送

### 7.3 缓存管理测试

**测试1：缓存增长**
- 发送多条消息（超过 100 条）
- 验证：缓存自动清理，保留最近 50 条

**测试2：内存占用**
- 长时间运行服务
- 监控 Python 进程内存使用
- 验证：内存占用稳定

---

## 八、版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| v1.0 | 2025-01-15 | 初始版本 |
| v1.1 | 2025-01-20 | 添加延迟记录原则 |
| v1.2 | 2025-01-25 | 优化状态检测逻辑 |
| v1.3 | 2025-02-01 | 添加字符串定位机制 |
| v1.4 | 2026-03-18 | 添加缓存管理策略，修复 /scope 命令历史消息重复问题 |
| v1.5 | 2026-03-22 | 添加无来源消息处理章节，明确用户直接在 iflow 中输入消息的处理流程 |