# IFlow 模块完整设计文档

## 目录

1. [概述](#概述)
2. [核心架构](#核心架构)
3. [模块组成](#模块组成)
4. [状态管理](#状态管理)
5. [消息处理](#消息处理)
6. [交互式测试工具](#交互式测试工具)
7. [使用示例](#使用示例)
8. [故障排查](#故障排查)

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

### 3. MessageStore - 消息库

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

### 4. InteractionLogger - 交互记录器

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

### 5. IFlowModule - 消息交互层

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

## 交互式测试工具

### 概述

`tools/iflow_interactive_tool.py` 是 iflow 模块的交互式测试工具，提供两种模式：

1. **交互模式**：持续交互，支持多种命令
2. **命令行模式**：发送单条消息后退出，支持会话保持

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

### 日志文件

- **日志位置**：`logs/iflow_tool.log`
- **日志级别**：
  - 文件：DEBUG（所有日志）
  - 控制台：WARNING+（仅警告和错误）

### 工具功能详解

#### 1. 模拟消息总线

```python
class MockMessageBus:
    """模拟消息总线"""
    
    async def route(self, message: Message):
        """路由消息
        
        - 来自 iflow 的消息通过回调处理
        - 来自其他模块的消息发送到 iflow
        - 避免循环：不将 iflow 消息发送回 iflow
        """
```

#### 2. 消息去重

```python
self._processed_message_ids = set()  # 已处理的消息 ID

# 去重检查
if message.id in self._processed_message_ids:
    logger.debug(f"消息已处理，跳过: {message.id}")
    return
```

#### 3. 实时显示

```python
async def _on_iflow_message(self, message: Message):
    """接收 IFlowModule 返回的消息"""
    
    # 解析消息类型
    msg_type = message.content.type
    content = message.content.content
    
    # 按类型显示
    if msg_type == CoreMessageType.REPLY:
        print(f"  [{time}] [reply] {content}")
    elif msg_type == CoreMessageType.OTHER:
        print(f"  [{time}] [other] {content}")
    elif msg_type == CoreMessageType.COMPLETE:
        print(f"  [{time}] [complete] 生成完成")
```

#### 4. 中断机制

```python
# 中断事件
self._interrupt_event = asyncio.Event()

# 等待完成（可中断）
async def wait_for_complete(self):
    """等待回复完成（可中断）"""
    
    while self.module and self.module.monitor.get_state() == IFlowState.GENERATING:
        try:
            await asyncio.wait_for(
                self._interrupt_event.wait(),
                timeout=1.0
            )
            # 被中断
            logger.info("等待被中断")
            return False
        except asyncio.TimeoutError:
            # 继续等待
            continue
    
    return True

# 中断处理
async def _handle_interrupt(self):
    """处理中断信号（Ctrl+C）"""
    
    if self.module and self.module.monitor.get_state() == IFlowState.GENERATING:
        print("\n⚠️ 检测到中断信号")
        print("   当前 iflow 正在生成回复")
        print("   可以继续输入新消息，但 iflow 可能仍在生成中")
        
        # 触发中断事件
        self._interrupt_event.set()
    else:
        print("\n正在退出...")
        raise KeyboardInterrupt
```

#### 5. 会话保持

```python
def __init__(self, ..., keep_alive: bool = True):
    """初始化工具
    
    Args:
        keep_alive: 是否保持 tmux 会话（默认 True）
    """
    self.keep_alive = keep_alive

async def start(self):
    """启动工具"""
    
    # 检查 iflow 是否已经在运行
    temp_controller = IFlowController(tmux_session)
    iflow_running = await temp_controller.check_iflow_running()
    
    if iflow_running and self.keep_alive:
        print(f"  检测到 iflow 已在运行（会话: {tmux_session}）")
        print(f"  将复用现有 iflow 实例，保持会话上下文")

async def stop(self, keep_alive: Optional[bool] = None):
    """停止工具
    
    Args:
        keep_alive: 是否保持 tmux 会话（None 表示使用实例变量）
    """
    should_keep_alive = keep_alive if keep_alive is not None else self.keep_alive
    
    if should_keep_alive:
        # 保持会话，只停止监控器
        await self.module.monitor.stop()
        self.module._running = False
        print("✅ 模块已停止（tmux 和 iflow 进程已保留）")
    else:
        # 销毁会话
        await self.module.stop()
        print("✅ 模块已停止（tmux 会话已销毁）")
```

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
8. **中断机制**：支持中断等待，发送新消息
9. **会话保持**：命令行模式默认保持会话

### 最佳实践

1. **开发测试**：使用交互模式快速测试
2. **批量任务**：使用命令行模式，保持会话
3. **生产环境**：使用消息总线集成
4. **故障排查**：查看日志文件 `logs/iflow_tool.log`
5. **性能监控**：观察 IDLE 状态的监控效率

### 相关文档

- [IFlow 模块设计方案](./04-IFlow模块设计方案.md)
- [消息总线设计方案](./05-消息总线设计方案.md)
- [消息提取优化方案](./07-消息提取优化方案.md)
- [IFlowModule 测试工具方案](./08-IFlowModule测试工具方案.md)