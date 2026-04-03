# Claude Code 渠道设计

## 一、概述

本文档描述如何在 Ling-iflow 项目中添加 Claude Code 渠道支持。通过实现 ClaudeCodeModule，使其与现有的 IFlowModule 架构平行，支持通过企业微信、飞书等渠道与 Claude Code CLI 进行交互。

### 1.1 设计目标

- **平行实现**：ClaudeCodeModule 与 IFlowModule 采用相同的架构模式
- **渠道复用**：通过现有渠道（企业微信、飞书等）控制 Claude Code
- **状态感知**：监控 Claude Code 的运行状态（空闲/处理中）
- **多实例支持**：支持同时运行多个 Claude Code 实例

### 1.2 Claude Code CLI 关键特性

| 特性 | 说明 |
|------|------|
| 启动命令 | `claude`（默认交互模式） |
| 非交互模式 | `claude -p "prompt"`（打印并退出） |
| 继续对话 | `claude -c` |
| Tmux 模式 | 由 Claude Code 自己管理（`--tmux --worktree`），不建议使用 |
| 模型指定 | `claude --model <model>` |
| 权限模式 | `claude --permission-mode <mode>` |
| 输出格式 | `--output-format stream-json` 支持实时流 |

**注意**：Claude Code 的 `--tmux --worktree` 参数是 Claude Code 内部使用的 tmux 集成，我们不能直接控制这个 tmux 会话。应使用与 IFlow 相同的方式：

```bash
tmux new-session -d -s {session} 'claude -c'
```

### 1.3 与 IFlow 的对比

| 特性 | IFlow | Claude Code |
|------|-------|-------------|
| CLI 命令 | `iflow` | `claude` |
| 启动参数 | `--model xxx --yolo -c` | `--model <model> -c` |
| Tmux 支持 | 直接创建 tmux 会话 | 直接创建 tmux 会话（相同方式） |
| 安全确认 | 无 | **有（启动时显示信任对话框，且 root 用户无法跳过）** |
| 状态检测 | "生成中" 关键词 | 待研究 |
| 消息标记 | ✦ / ✻ | 待研究 |
| 会话管理 | tmux session + 文件 | 内置 `--session-id` 或 tmux session |

### 1.4 Claude Code TUI 输出格式

经过实际测试，Claude Code TUI 在 tmux 中的输出格式如下：

**状态指示器：**
- `❯` - 输入提示符（空闲状态，等待输入）
- `* Choreographing…` - 处理中状态（类似 IFlow 的"生成中"）
- `●` - 消息前缀（用于回复内容）
- `✻ Baked for Xm Xs` - 处理完成，显示耗时

**示例输出：**
```
❯ 1+1=?

● 2

❯ What is Python?

* Choreographing…

● Python 是一种高级编程语言，具有以下特点：
  - 简洁易读
  - 解释型
  - 动态类型
  - 跨平台
  - 丰富的库

✻ Baked for 1m 32s

────────────────────────────────────────────────────────────────────────────────
❯
```

### 1.5 安全确认处理

Claude Code 启动时显示安全确认对话框：

```
 Quick safety check: Is this a project you created or one you trust?

 ❯ 1. Yes, I trust this folder
   2. No, exit

 Enter to confirm
```

**自动处理方法：**发送 **Enter** 即可确认（默认选择第一项）。

### 1.6 关键发现

| 发现 | 说明 |
|------|------|
| **root 限制** | `--dangerously-skip-permissions` 不能用于 root 用户 |
| **解决方案** | 使用非 root 用户（如 vboxuser）启动 Claude Code |
| **安全确认** | 发送 Enter 即可自动确认 |
| **tmux 捕获** | 需要设置正确的 TMUX 环境变量才能捕获输出 |
| **状态检测** | 使用 "Choreographing…" 检测处理中状态 |
| **消息标记** | 使用 `❯` 作为用户消息前缀，`●` 作为回复前缀 |

---

## 二、架构设计

### 2.1 模块结构

```
src/modules/claudecode/
├── __init__.py
├── module.py          # ClaudeCodeModule 主模块
├── controller.py      # ClaudeCodeController - 与 CLI 交互
├── monitor.py        # ClaudeCodeMonitor - 监控 CLI 输出
└── session_manager.py # 会话管理（可选，Claude Code 有内置会话管理）
```

### 2.2 核心交互流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        MessageBus                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ClaudeCodeModule                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   ClaudeCodeMonitor                        │   │
│  │  - 持续监控 tmux 输出                                     │   │
│  │  - 提取响应消息                                           │   │
│  │  - 检测状态变化 (IDLE/GENERATING)                        │   │
│  │  - 通知订阅者                                             │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                              │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐    │
│  │                   ClaudeCodeController                   │    │
│  │  - start_claude_code(): 启动 Claude Code CLI           │    │
│  │  - send_message(): 发送消息                             │    │
│  │  - capture_output(): 捕获 tmux 输出                     │    │
│  │  - check_ready(): 检查是否就绪                          │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ tmux 命令
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      tmux 会话                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    Claude Code CLI (TUI)                   │  │
│  │  - 交互界面                                               │  │
│  │  - 状态指示器                                             │  │
│  │  - 消息输出                                                │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 ClaudeCodeModule 类设计

```python
class ClaudeCodeModule(BaseModule):
    """Claude Code 主模块

    类似于 IFlowModule，集成 Controller 和 Monitor，
    通过 MessageBus 与其他模块通信。
    """

    def __init__(
        self,
        module_id: str,
        tmux_session: str = None,
        model: str = "sonnet",
        workspace: str = None,
        **kwargs
    ):
        """初始化 Claude Code 模块

        Args:
            module_id: 模块 ID
            tmux_session: tmux 会话名称，默认使用 {channel_name}+claude
            model: 使用的模型，默认 sonnet
            workspace: 工作目录
        """
        self.module_id = module_id
        self.tmux_session = tmux_session or f"{module_id}+claude"
        self.model = model
        self.workspace = workspace or os.getcwd()

        # 组件
        self.controller: ClaudeCodeController = None
        self.monitor: ClaudeCodeMonitor = None

        # 状态
        self._running = False
        self._ready = False

    async def send(
        self,
        content: str,
        source: str = None,
        scope: str = "reply_only",
        chat_id: str = None,
        user_id: str = None,
        is_group: bool = False
    ) -> Response:
        """发送消息到 Claude Code

        Args:
            content: 消息内容
            source: 来源标识（用于路由回复）
            scope: 回复范围 ('reply_only' 或 'all')
            chat_id: 聊天 ID
            user_id: 用户 ID
            is_group: 是否群聊

        Returns:
            Response 对象
        """
        pass

    def subscribe(self, callback: Callable) -> None:
        """订阅 Claude Code 输出"""
        pass

    def unsubscribe(self, callback: Callable) -> None:
        """取消订阅"""
        pass

    async def get_status() -> dict:
        """获取模块状态"""
        pass

    async def health_check() -> Dict[str, Any]:
        """健康检查"""
        pass

    async def wait_for_ready(self, timeout: float = 60.0) -> bool:
        """等待 Claude Code 就绪"""
        pass

    def set_reply_mode(self, mode: str) -> bool:
        """设置回复模式

        Args:
            mode: 'reply_only' 或 'all'

        Returns:
            是否设置成功
        """
        pass

    def get_reply_mode() -> str:
        """获取当前回复模式"""
        pass

    # ==================== 生命周期钩子 ====================

    async def _on_start(self) -> None:
        """启动模块"""
        # 1. 创建 tmux 会话
        # 2. 启动 Claude Code CLI
        # 3. 启动 Monitor
        # 4. 等待就绪
        pass

    async def _on_stop(self) -> None:
        """停止模块"""
        # 1. 停止 Monitor
        # 2. 停止 Claude Code CLI
        # 3. 销毁 tmux 会话
        pass
```

### 2.4 ClaudeCodeController 类设计

```python
class ClaudeCodeController:
    """Claude Code 控制器

    负责与 Claude Code CLI 的底层交互：
    - 启动/停止 CLI
    - 发送消息
    - 捕获输出
    - 状态检查
    """

    def __init__(
        self,
        tmux_session: str,
        model: str = "sonnet",
        workspace: str = None
    ):
        self.tmux_session = tmux_session
        self.model = model
        self.workspace = workspace or os.getcwd()

    async def start_claude_code(self) -> bool:
        """启动 Claude Code CLI

        使用 tmux 创建会话并启动 Claude Code：

        tmux new-session -d -s {session} \
            'claude --model {model} -c'

        注意：Claude Code 启动后会显示安全确认对话框，
        需要自动处理（如发送 Enter 或选择 "1"）来确认信任工作目录。

        Returns:
            是否启动成功
        """
        pass

    async def stop_claude_code(self) -> bool:
        """停止 Claude Code CLI"""
        pass

    async def send_message(self, message: str) -> bool:
        """发送消息到 Claude Code

        实现步骤：
        1. 检查 Claude Code 是否就绪
        2. 清除当前输入（如有）
        3. 发送消息内容
        4. 发送回车执行

        Returns:
            是否发送成功
        """
        pass

    async def capture_output(self, lines: int = 500) -> str:
        """捕获 tmux pane 输出

        Args:
            lines: 捕获的行数

        Returns:
            tmux pane 的文本内容
        """
        pass

    async def check_ready(self) -> bool:
        """检查 Claude Code 是否就绪

        就绪条件：
        1. tmux 会话存在
        2. CLI 已完全启动
        3. 安全确认已通过
        4. 不在处理中状态

        Returns:
            是否就绪
        """
        pass

    async def is_generating(self) -> bool:
        """检查是否正在生成回复

        Claude Code 的"处理中"状态特征（待验证）：
        - 可能显示 "Thinking..." 或类似指示器
        - 可能显示进度指示器

        Returns:
            是否正在生成
        """
        pass
```

### 2.5 ClaudeCodeMonitor 类设计

```python
class ClaudeCodeState(Enum):
    """Claude Code 状态"""
    IDLE = "idle"           # 空闲，等待输入
    GENERATING = "generating"  # 生成回复中


class ClaudeCodeMonitor:
    """Claude Code 监控器

    持续监听 tmux 输出，提取消息并检测状态变化。
    架构与 IFlowMonitor 完全平行。
    """

    def __init__(self, controller: ClaudeCodeController):
        self.controller = controller
        self._state = ClaudeCodeState.IDLE
        self._subscribers: List[Callable] = []
        self._state_callbacks: List[Callable] = []

        # 消息去重
        self._sent_message_hashes: set = set()
        self._sent_marker_strings: set = set()

        # 发送模式
        self._send_mode: str = "STREAM_MODE"  # 或 BUFFER_MODE

        # 无来源消息缓冲
        self._no_source_buffer: List[str] = []
        self._no_source_request_content: str = ""

    def subscribe(self, callback: Callable) -> None:
        """订阅监控输出"""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        """取消订阅"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def set_state_change_callback(self, callback: Callable) -> None:
        """设置状态变更回调"""
        self._state_callbacks.append(callback)

    async def start(self) -> None:
        """启动监控"""
        pass

    async def stop(self) -> None:
        """停止监控"""
        pass

    def _extract_messages(self, output: str) -> List[Dict]:
        """从 tmux 输出中提取消息

        Claude Code 的输出格式（待研究）：
        - 消息是否使用特殊标记？
        - 用户输入是否有前缀？
        - 思考过程如何标记？

        Returns:
            消息列表，每条消息包含：
            - content: 消息内容
            - marker_type: 标记类型
            - marker_only: 标记行字符串
            - is_user: 是否用户消息
        """
        pass

    def _detect_state(self, output: str) -> ClaudeCodeState:
        """检测 Claude Code 状态

        检测方法（待研究）：
        - IDLE: 显示输入提示符
        - GENERATING: 显示处理指示器

        Returns:
            检测到的状态
        """
        pass

    def _cleanup_cache(self) -> None:
        """清理旧缓存，控制内存"""
        pass
```

---

## 三、实现步骤

### 阶段 1：基础框架

#### 1.1 创建目录结构

```bash
mkdir -p src/modules/claudecode/
touch src/modules/claudecode/__init__.py
```

#### 1.2 实现 ClaudeCodeController

**关键方法：**
- `start_claude_code()`: 使用 tmux 启动 Claude Code
- `send_message()`: 发送消息（使用 tmux send-keys）
- `capture_output()`: 捕获 tmux pane
- `check_ready()`: 检查就绪状态

**待研究：Claude Code 的输入输出特征**
```bash
# 需要验证以下内容：
# 1. Claude Code 的提示符格式
# 2. 正在处理时的输出特征
# 3. 消息是否使用标记（如 ✦ ✻）
# 4. 如何检测输入框就绪
```

#### 1.3 实现 ClaudeCodeMonitor

**关键方法：**
- `_extract_messages()`: 提取消息（需要先研究输出格式）
- `_detect_state()`: 检测状态
- `start()/stop()`: 监控生命周期

#### 1.4 实现 ClaudeCodeModule

**关键方法：**
- `send()`: 发送消息到 Claude Code
- `subscribe()/unsubscribe()`: 订阅输出
- `_on_start()/_on_stop()`: 生命周期

### 阶段 2：渠道集成

#### 2.1 修改 bot.py

```python
# 在 LingIflowBot 中添加

async def _create_claudecode_modules(self) -> None:
    """创建所有 Claude Code 模块"""
    claude_config = self.config.get("claude_channels", [])
    logger.info(f"创建 {len(claude_config)} 个 Claude Code 模块...")

    for cc_config in claude_config:
        if not cc_config.get("enabled", True):
            continue

        name = cc_config.get("name")
        try:
            module_id = f"claude_{name}"
            claude = await self.manager.create_module(
                module_type="claude",
                module_id=module_id,
                config=cc_config
            )
            claude.set_manager(self.manager)
            claude.set_bot(self)
            self.claude_modules[name] = claude
            await self.manager.register_module(module_id)
            logger.info(f"创建 Claude Code 模块: {module_id}")
        except Exception as e:
            logger.error(f"创建 Claude Code 模块失败 {name}: {e}")
```

#### 2.2 修改 ModuleManager

```python
# 在 manager.py 的 create_module 中添加

elif module_type == "claude":
    from ..modules.claudecode import ClaudeCodeModule
    module = ClaudeCodeModule(
        module_id=module_id,
        tmux_session=config.get("tmux_session", f"{module_id}+claude"),
        model=config.get("model", "sonnet"),
        workspace=config.get("workspace", self.workspace)
    )
```

#### 2.3 修改 manage.py

添加 Claude Code 渠道管理命令。

### 阶段 3：配置支持

#### 3.1 配置文件结构

```json
{
  "claude_channels": [
    {
      "name": "claude1",
      "model": "sonnet",
      "tmux_session": "claude1+claude",
      "workspace": "/path/to/workspace",
      "enabled": true
    }
  ]
}
```

---

## 四、待研究事项

在实现前，需要先研究以下内容：

### 4.1 Claude Code 安全确认对话框处理

Claude Code 启动后会显示安全确认对话框，这是与 IFlow 的主要差异：

```
 Quick safety check: Is this a project you created or one you trust?

 ❯ 1. Yes, I trust this folder
   2. No, exit

 Enter to confirm
```

**自动处理方案：**
1. 启动后检测是否显示此对话框
2. 自动发送 "1" 选择信任选项
3. 再发送 Enter 确认
4. 或者研究是否有环境变量/参数跳过此确认

### 4.2 Claude Code CLI 输出格式

**需要观察的内容：**
1. Claude Code 启动后的完整输出
2. 就绪状态的指示器
3. 处理中状态的指示器
4. 消息输出是否使用标记符号
5. 用户输入的显示格式

**研究方法：**
```bash
# 在 tmux 中手动启动 Claude Code，观察输出
tmux new-session -d -s test_claude 'claude -c'
tmux capture-pane -t test_claude -p

# 发送测试消息，观察响应
tmux send-keys -t test_claude "Hello" Enter
sleep 5
tmux capture-pane -t test_claude -p
```

### 4.3 Claude Code 的 --output-format stream-json

Claude Code 支持 `--output-format stream-json`，可能可以更方便地获取实时输出：

```bash
claude -p "Hello" --output-format stream-json
```

这可能比解析 tmux 输出更可靠。

### 4.4 Claude Code 的会话管理

Claude Code 有内置的 `--session-id` 选项，可能不需要额外的会话文件管理。

---

## 五、TODO 列表

- [x] **P0 - 研究阶段**
  - [x] 研究 Claude Code 安全确认对话框的自动处理方法
  - [x] 研究 Claude Code CLI 输出格式
  - [x] 确认状态检测方法（检测 "Choreographing…"）
  - [x] 确认消息提取方法（提取 `❯` 和 `●` 标记的内容）

- [ ] **P1 - 基础实现**
  - [ ] 创建 src/modules/claudecode/ 目录
  - [ ] 实现 ClaudeCodeController
  - [ ] 实现 ClaudeCodeMonitor
  - [ ] 实现 ClaudeCodeModule

- [ ] **P2 - 渠道集成**
  - [ ] 修改 bot.py 支持 claude_channels
  - [ ] 修改 ModuleManager 支持 claude 类型
  - [ ] 修改 manage.py 支持 Claude Code 管理

- [ ] **P3 - 配置支持**
  - [ ] 添加 claude_channels 配置支持
  - [ ] 添加多 Claude Code 实例支持

---

## 六、关键实现细节

### 6.1 用户切换

由于 root 用户无法使用 `--dangerously-skip-permissions`，需要使用非 root 用户启动 Claude Code：

```python
import pwd
import os

def run_as_user(user: str, command: str) -> None:
    """以指定用户身份运行命令"""
    pwd.getpwnam(user)
    os.setuid(pwd.getpwnam(user).pw_uid)
    os.system(command)
```

### 6.2 ClaudeCodeController 实现要点

```python
class ClaudeCodeController:
    async def start_claude_code(self) -> bool:
        """启动 Claude Code"""
        # 1. 创建 tmux 会话
        subprocess.run([
            'tmux', 'new-session', '-d', '-s', self.tmux_session,
            f'su - {self.run_user} -c "claude -c --dangerously-skip-permissions"'
        ])

        # 2. 等待 Claude Code 启动
        await asyncio.sleep(10)

        # 3. 发送 Enter 处理安全确认
        subprocess.run(['tmux', 'send-keys', '-t', self.tmux_session, 'Enter'])

        # 4. 等待安全确认完成
        await asyncio.sleep(5)

        return True

    async def check_ready(self) -> bool:
        """检查 Claude Code 是否就绪"""
        output = await self.capture_output()
        # 就绪条件：显示 ❯ 提示符，且没有 "Quick safety check"
        return '❯' in output and 'Quick safety check' not in output

    async def is_generating(self) -> bool:
        """检查是否正在生成回复"""
        output = await self.capture_output()
        return 'Choreographing' in output
```

### 6.3 ClaudeCodeMonitor 实现要点

```python
class ClaudeCodeMonitor:
    def _extract_messages(self, output: str) -> List[Dict]:
        """从 tmux 输出中提取消息"""
        messages = []

        # 用户消息：以 ❯ 开头的行
        for line in output.split('\n'):
            if line.strip().startswith('❯'):
                content = line.strip()[1:].strip()  # 去掉 ❯ 前缀
                messages.append({
                    'type': 'user',
                    'content': content
                })

        # 回复消息：以 ● 开头的行
        for line in output.split('\n'):
            if '●' in line:
                content = line.split('●', 1)[1].strip()  # 去掉 ● 前缀
                messages.append({
                    'type': 'assistant',
                    'content': content
                })

        return messages
```

### 6.4 tmux 环境变量

捕获 tmux pane 输出时需要设置 TMUX 环境变量：

```python
import subprocess

def capture_pane(session: str, pane_id: str = '0') -> str:
    """捕获 tmux pane 输出"""
    result = subprocess.run(
        ['tmux', 'capture-pane', '-t', f'{session}.{pane_id}', '-p'],
        capture_output=True,
        text=True,
        env={**os.environ, 'TMUX': f'/tmp/tmux-1000/default,{pane_id},0'}
    )
    return result.stdout
```

---

## 六、测试验证

### 6.1 单元测试

```bash
# 测试 Controller
pytest tests/test_claudecode_controller.py

# 测试 Monitor
pytest tests/test_claudecode_monitor.py

# 测试 Module
pytest tests/test_claudecode_module.py
```

### 6.2 集成测试

```bash
# 启动 Claude Code 渠道
./manage.py start --channel claude1

# 发送测试消息
python tools/test_client.py --send "Hello, Claude!"

# 观察响应
```

---

## 七、相关文件

| 文件 | 说明 |
|------|------|
| `src/modules/iflow/module.py` | IFlowModule 参考实现 |
| `src/modules/iflow/controller.py` | IFlowController 参考实现 |
| `src/modules/iflow/monitor.py` | IFlowMonitor 参考实现 |
| `src/modules/channel/` | 渠道实现参考 |
