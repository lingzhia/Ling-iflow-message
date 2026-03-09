# Ling-iflow 项目上下文文档

## 项目概述

Ling-iflow 是一个 iflow CLI 交互模式管理工具，支持通过 tmux 启动 iflow，并实现与企业微信的双向消息同步。项目从 iflow-bot 迁移而来，专注于提供轻量级的交互模式管理功能。

## 核心功能

1. **tmux 集成**：通过 tmux 启动和管理 iflow CLI 会话
2. **会话监控**：实时监控 iflow 的会话文件，捕获 AI 回复
3. **消息同步**：支持企业微信消息与 iflow CLI 的双向同步
4. **命令系统**：支持 `/run`, `/new`, `/sessions`, `/status`, `/help` 等命令
5. **连续对话**：自动保持上下文，支持连续对话
6. **会话管理**：提供会话查询、创建、切换等功能
7. **消息来源差异化处理**：支持工具消息、企业微信消息、iflow 交互界面消息的差异化处理
8. **后台监控功能**：检测 iflow 交互界面的消息并自动同步到企业微信
9. **测试工具**：提供 iflow 交互式测试工具和企业微信测试工具

## 目录结构

```
Ling-iflow/
├── channels/           # 渠道模块
│   ├── __init__.py
│   ├── base.py        # 渠道基类
│   └── wechat_work.py # 企业微信渠道
├── cli/               # CLI 命令模块
│   ├── __init__.py
│   └── commands.py    # CLI 命令接口
├── config/            # 配置管理模块
│   ├── __init__.py
│   ├── schema.py      # 配置 Schema
│   └── loader.py      # 配置加载器
├── interactive/       # 交互模式核心模块
│   ├── __init__.py
│   ├── bot_integration.py  # 机器人集成模块
│   ├── iflow_controller.py # iflow CLI 控制器
│   ├── session_manager.py  # 会话管理器
│   ├── session_monitor.py  # 会话监控器
│   └── sync_manager.py     # 同步管理器
├── tool/              # 测试工具模块
│   ├── iflow_interactive.py # iflow 交互式测试工具
│   └── wechat_debug.py     # 企业微信调试工具
├── utils/             # 工具函数模块
│   ├── __init__.py
│   └── helpers.py     # 工具函数
├── config.example.json  # 配置示例文件
├── pyproject.toml      # 项目依赖配置
├── wechat_bot.py       # 企业微信 Bot 主程序
├── manage.py           # 项目管理脚本
├── logs_view.py        # 日志查看工具
├── WECHAT_SETUP.md     # 企业微信配置说明文档
├── README.md           # 项目说明文档
└── AGENTS.md           # 本文档
```

## 安装和使用

### 安装依赖

```bash
# 基础安装
pip install -e .

# 开发环境安装（包含测试工具）
pip install -e ".[dev]"

# 企业微信功能安装（包含企业微信相关依赖）
pip install -e ".[wechat]"

# 完整安装（包含开发和微信功能）
pip install -e ".[dev,wechat]"
```

### 初始化配置

```bash
ling-iflow init
```

配置文件位置：`~/.ling-iflow/config.json`

### 启动交互模式

```bash
# 使用默认配置启动
ling-iflow start

# 指定工作目录和模型
ling-iflow start --workspace ~/.iflow --model kimi-k2.5

# 启用企业微信同步
ling-iflow start --wechat

# 不自动启动 iflow（假设已运行）
ling-iflow start --no-auto-start
```

### 停止 iflow

```bash
ling-iflow stop
```

### 查看状态

```bash
ling-iflow status
```

### 运行测试

```bash
# 运行 iflow 交互式测试工具
python tool/iflow_interactive.py

# 运行企业微信调试工具（监听模式）
python tool/wechat_debug.py listen

# 运行企业微信调试工具（发送消息）
python tool/wechat_debug.py send "测试消息"

# 运行企业微信调试工具（测试配置）
python tool/wechat_debug.py test
```

### 启动企业微信 Bot

```bash
# 前置条件：已安装企业微信依赖
pip install -e ".[wechat]"

# 启动企业微信 Bot
python wechat_bot.py
```

详细的企业微信配置说明请查看 [WECHAT_SETUP.md](WECHAT_SETUP.md)。

## 核心组件说明

### BotIntegration

机器人集成模块，连接企业微信渠道和 iflow CLI，实现消息双向流转。

**主要功能：**
- 接收企业微信消息
- 解析命令（支持 `/run`, `/new`, `/sessions`, `/status`, `/help`）
- 调用 iflow CLI 执行命令
- 发送回复到企业微信
- 支持连续对话，自动保持上下文
- **消息来源差异化处理**：支持工具消息、企业微信消息、iflow 交互界面消息的差异化处理
- **后台监控功能**：检测 iflow 交互界面的消息并自动同步到企业微信
- **测试模式切换**：支持提取全部消息（包括非✦标记的消息）用于测试

**主要方法：**
- `handle_message(...)`: 处理入站消息
- `_parse_command(content)`: 解析用户消息，提取命令
- `_handle_command(...)`: 处理不同类型的命令
- `_run_command(...)`: 运行 iFlow 命令并获取回复
- `_extract_reply_from_tmux()`: 从 tmux 输出中提取回复
- `_merge_messages(messages)`: 合并多条消息为一条
- `_clean_message_content(content)`: 清理消息内容，去除 iflow 的 UI 元素

**消息来源差异化处理：**

1. **工具消息（source="tool"）**：
   - 只返回给工具，不发企业微信
   - 用于工具调用场景

2. **企业微信消息（source="wechat"）**：
   - 逐条发送到企业微信
   - 添加完成提示
   - 支持连续对话

3. **iflow 交互界面消息（source=""）**：
   - 检测未知来源的消息
   - 合并所有 ✦ 标记的消息
   - 发送合并后的一条消息到企业微信

### SessionManager

会话管理器，管理 iflow 的会话（session）文件，提供会话查询、创建等功能。

**主要功能：**
- 获取最新的 session 文件
- 获取所有 session 列表
- 创建新会话（清除上下文）
- 获取当前会话信息
- 删除指定 session

**主要方法：**
- `get_latest_session()`: 获取最新的 session 文件
- `get_all_sessions(limit)`: 获取所有 session 列表
- `create_new_session()`: 创建新会话
- `delete_session(session_id)`: 删除指定 session
- `get_current_session_info()`: 获取当前会话信息
- `get_status_message()`: 获取状态信息的 Markdown 格式字符串
- `get_sessions_message(limit)`: 获取会话列表信息的 Markdown 格式字符串

### IFlowController

iflow CLI 控制器，通过 tmux 命令管理 iflow CLI 会话。

**主要方法：**
- `check_tmux_session()`: 检查 tmux 会话是否存在
- `check_iflow_running()`: 检查 iflow CLI 是否运行
- `send_message(message)`: 发送消息到 iflow CLI
- `start_iflow(model)`: 在 tmux 会话中启动 iflow CLI
- `stop_iflow()`: 停止 iflow CLI
- `get_session_info()`: 获取会话信息

### SessionMonitor

会话文件监控器，实时读取 iflow 的会话文件（session-*.jsonl），捕获 AI 回复。

**主要方法：**
- `find_session_files()`: 查找所有会话文件
- `read_new_assistant_messages()`: 读取新增的 AI 回复消息
- `should_check()`: 检查是否应该执行监控检查
- `reset()`: 重置监控器状态

### SyncManager

同步管理器，协调各个组件，实现 iflow CLI 和企业微信的双向同步。

**主要方法：**
- `start(auto_start_iflow)`: 启动同步服务
- `stop()`: 停止同步服务
- `send_to_wechat(content)`: 发送消息到企业微信
- `receive_wechat_message(...)`: 接收企业微信消息

### WechatWorkChannel

企业微信渠道，用于与企业微信 API 交互。

**主要方法：**
- `start()`: 启动渠道
- `stop()`: 停止渠道
- `send(content, chat_id, **kwargs)`: 发送消息
- `receive_message(...)`: 接收外部消息
- `set_message_handler(handler)`: 设置消息处理器
- `set_send_callback(callback)`: 设置发送回调函数

## 配置说明

### 配置文件位置

默认位置：`~/.ling-iflow/config.json`

### 配置项

```json
{
  "workspace": "~/.iflow",
  "model": "kimi-k2.5",
  "tmux_session": "iflow",
  "wechat_work": {
    "enabled": false,
    "corp_id": "",
    "agent_id": "",
    "secret": "",
    "user_id": "",
    "token": "",
    "encoding_aes_key": "",
    "callback_port": 8788,
    "callback_host": "0.0.0.0",
    "stream_mode": false,
    "poll_interval": 5,
    "allow_from": [],
    "group_policy": "mention",
    "group_allow_from": []
  },
  "log_level": "INFO",
  "log_file": ""
}
```

**配置项说明：**
- `workspace`: iflow 工作目录
- `model`: iflow 模型名称
- `tmux_session`: tmux 会话名称
- `wechat_work`: 企业微信配置
  - `enabled`: 是否启用企业微信
  - `corp_id`: 企业 ID
  - `agent_id`: 应用 AgentId
  - `secret`: 应用 Secret
  - `user_id`: 用户账号（用于发送消息）
  - `token`: 回调配置的 Token
  - `encoding_aes_key`: 回调配置的 EncodingAESKey
  - `callback_port`: 回调服务端口
  - `callback_host`: 回调服务监听地址
  - `stream_mode`: 是否启用 Stream Mode
  - `poll_interval`: 轮询间隔（秒）
  - `allow_from`: 允许的用户 ID 白名单
  - `group_policy`: 群聊消息响应策略
  - `group_allow_from`: 群聊白名单
- `log_level`: 日志级别
- `log_file`: 日志文件路径

## 使用示例

### 示例 1：基本使用

```bash
# 1. 启动 iflow CLI（在 tmux 会话中）
tmux new-session -d -s iflow "iflow --model kimi-k2.5"

# 2. 启动交互模式服务
ling-iflow start --no-auto-start

# 3. 在另一个终端运行测试程序
python test_wechat.py

# 4. 在测试程序中输入消息，观察 iflow 的回复
```

### 示例 2：启用企业微信同步

```bash
# 1. 配置企业微信
ling-iflow init
# 编辑 ~/.ling-iflow/config.json，设置企业微信配置

# 2. 启动交互模式服务（自动启动 iflow）
ling-iflow start --wechat

# 3. 通过企业微信发送消息，观察 iflow 的回复
```

详细的企业微信配置步骤请查看 [WECHAT_SETUP.md](WECHAT_SETUP.md)。

### 示例 3：使用命令系统

在企业微信中发送命令：

```bash
# 直接发送消息（自动恢复上次会话）
帮我写一个 Python 脚本

# 使用 /run 命令
/run 帮我分析这个代码

# 开始新会话（清除上下文）
/new

# 查看历史会话
/sessions

# 查看服务状态
/status

# 显示帮助
/help
```

### 示例 4：连续对话

```
你: 帮我写一个 Python 脚本
bot: ⏳ 正在执行: 帮我写一个 Python 脚本
bot: ✅ [脚本内容]

你: 再帮我添加一个函数
bot: ⏳ 正在执行: 再帮我添加一个函数
bot: ✅ [更新后的脚本]

你: 继续完善这个脚本
bot: ⏳ 正在执行: 继续完善这个脚本
bot: ✅ [完善后的脚本]

你: /new
bot: ✅ 已开始新会话
```

### 示例 5：查看状态

```bash
ling-iflow status
```

输出示例：
```
============================================================
Ling-iflow 状态
============================================================
tmux 会话: iflow
  存在: 是
  iflow 运行中: 是

会话文件: ~/.iflow/projects/
  会话数量: 1
  会话列表:
    1. session-abc123.jsonl
```

## 技术架构

### 消息流向

**企业微信 → iflow CLI：**
```
企业微信消息
  → WechatWorkChannel.receive_message()
  → BotIntegration.handle_message()
  → 解析命令（/run, /new, /sessions, /status, /help）
  → BotIntegration._handle_command()
  → IFlowController.send_message()
  → tmux send-keys 注入消息
  → iflow CLI 接收并处理
  → BotIntegration._extract_reply_from_tmux()
  → WechatWorkChannel.send()
  → 用户收到回复
```

**iflow CLI → 企业微信（通过会话监控）：**
```
iflow CLI 生成回复
  → 写入 session-*.jsonl 文件
  → SessionMonitor.read_new_assistant_messages()
  → 检测到新消息
  → SyncManager.send_to_wechat()
  → WechatWorkChannel.send()
  → 企业微信 API 发送
  → 用户收到回复
```

### 依赖项

**核心依赖：**
- **pydantic**: 数据验证和配置管理
- **pydantic-settings**: 从环境变量和配置文件加载配置
- **loguru**: 日志记录
- **typer**: CLI 命令行界面

**开发依赖（可选）：**
- **pytest**: 单元测试框架
- **pytest-asyncio**: 异步测试支持

**企业微信依赖（可选）：**
- **httpx**: HTTP 客户端
- **aiohttp**: 异步 HTTP 客户端
- **cryptography**: 加密库（用于消息加解密）

## 注意事项

1. **tmux 要求**：
   - 系统必须安装 tmux
   - tmux 会话名称默认为 "iflow"
   - 避免与现有会话冲突

2. **iflow 要求**：
   - 必须先安装 iflow CLI
   - 需要登录 iflow 账号
   - 工作目录默认为 `~/.iflow`

3. **企业微信配置**：
   - 必须配置 `corp_id`、`agent_id`、`secret`
   - 需要配置 `user_id` 用于发送消息
   - 回调模式需要配置 `token` 和 `encoding_aes_key`
   - 确保防火墙开放回调端口（默认 8788）
   - 详细配置步骤请查看 [WECHAT_SETUP.md](WECHAT_SETUP.md)

4. **依赖安装**：
   - 基础功能：`pip install -e .`
   - 开发环境：`pip install -e ".[dev]"`
   - 企业微信功能：`pip install -e ".[wechat]"`
   - 完整安装：`pip install -e ".[dev,wechat]"`

5. **测试程序**：
   - `tool/iflow_interactive.py`: iflow 交互式测试工具
   - `tool/wechat_debug.py`: 企业微信调试工具

## 开发规范

### 代码风格
- 使用 Python 3.10+ 类型注解
- 遵循 PEP 8 代码规范
- 使用 loguru 记录日志

### 测试
- 使用 pytest 进行单元测试
- 使用 pytest-asyncio 进行异步测试
- 测试文件命名：`test_*.py`

### 提交规范
- 清晰的提交信息
- 包含必要的文档更新
- 通过所有测试

## 重要记忆

- 项目从 iflow-bot 迁移而来，专注于交互模式管理
- 使用 tmux 管理 iflow CLI 会话
- 通过监控会话文件（session-*.jsonl）捕获 AI 回复
- 支持企业微信消息与 iflow CLI 的双向同步
- 支持命令系统：`/run`, `/new`, `/sessions`, `/status`, `/help`
- 支持连续对话，自动保持上下文
- 提供多个测试程序，支持不同测试场景
- 配置文件位置：`~/.ling-iflow/config.json`
- 环境信息：Linux (WSL2), Python 3.13.11
- GitHub 仓库：`git@github.com:lingzhia/Ling-iflow-message.git`

## 与 iflow-bot 的区别

1. **简化设计**：只包含交互模式核心功能，移除其他渠道和复杂功能
2. **独立运行**：不依赖 iflow-bot 的消息总线和其他组件
3. **增强功能**：提供命令系统、连续对话、会话管理等功能
4. **轻量级**：依赖项更少，安装和配置更简单
5. **测试完善**：提供多个测试程序，覆盖不同测试场景

## 未来改进

1. 支持更多渠道（Telegram、Discord 等）
2. 添加消息历史记录功能
3. 支持多会话管理
4. 增强 Web 控制台
5. 添加更多测试用例
6. 优化命令解析和执行逻辑
7. 添加会话持久化功能
8. 支持更多 iflow 命令和参数

## 消息来源差异化处理方案

### 方案概述

实现三种消息来源的差异化处理：

1. **工具消息**：只返回给工具，不发企业微信
2. **企业微信消息**：逐条返回企业微信（保持原有逻辑）
3. **iflow 交互界面消息**：合并成一条返回企业微信

### 技术实现

#### 1. 参数设计

在 `BotIntegration._run_command` 方法中添加 `source` 参数：

```python
async def _run_command(
    self,
    chat_id: str,
    is_group: bool,
    command: str,
    source: str = "wechat"  # 新增参数：消息来源
) -> None:
```

**source 参数取值**：
- `"wechat"`：企业微信来源（默认）
- `"tool"`：工具来源
- `""`：未知来源（iflow 交互界面）

#### 2. 来源跟踪

在 `BotIntegration` 类中添加实例变量：

```python
self._current_source: str = ""  # 当前正在处理的请求来源
self._pending_messages: list = []  # 待处理的未知来源消息
```

#### 3. 消息发送逻辑

根据来源决定发送方式：

- **工具消息（source="tool"）**：只返回给工具，不发企业微信
- **企业微信消息（source="wechat"）**：逐条发送到企业微信
- **iflow 交互界面消息（source=""）**：合并所有 ✦ 标记的消息，发送合并后的一条消息

#### 4. 未知来源消息检测

在监控循环中，检测不在 `_sent_marker_ids` 中的消息，判断为 iflow 交互界面的消息。

#### 5. 消息合并方法

```python
def _merge_messages(self, messages: list) -> str:
    """合并多条消息为一条。只合并 ✦ 标记的消息。"""
    merged_lines = []
    for msg in messages:
        if '✦' in msg.get('full_marker', '') and '✻' not in msg.get('full_marker', ''):
            content = msg.get('content', '').strip()
            if content:
                merged_lines.append(content)
    return '\n'.join(merged_lines)
```

### 处理流程图

```
收到 iflow 回复
    ↓
提取所有消息
    ↓
检查消息来源
    ↓
┌─────────────────────────────────────┐
│ source = "tool"                    │
│ → 只返回给工具，不发企业微信          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ source = "wechat"                  │
│ → 逐条发送到企业微信                 │
│ → 添加完成提示                      │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ source = "" (未知来源)              │
│ → 检测到 iflow 交互界面消息          │
│ → 合并所有 ✦ 标记消息               │
│ → 发送合并后的一条消息到企业微信      │
└─────────────────────────────────────┘
```

### 使用示例

#### 工具调用

```python
# tool/iflow_interactive.py
await self.bot.handle_message("test_user", False, "run", command, source="tool")
```

#### 企业微信调用

```python
# wechat_bot.py（使用默认值）
await self.bot.handle_message("test_user", False, "run", command, source="wechat")
```

### 关键改动点

| 文件 | 改动内容 |
|------|---------|
| `interactive/bot_integration.py` | 1. 添加 `source` 参数<br>2. 添加 `_current_source` 和 `_pending_messages` 变量<br>3. 修改消息发送逻辑，根据来源决定发送方式<br>4. 添加未知来源消息检测<br>5. 添加 `_merge_messages` 方法 |
| `tool/iflow_interactive.py` | 修改调用方式，传入 `source="tool"` |

### 注意事项

1. **来源清理**：每次 `_run_command` 完成后，需要清理 `_current_source`
2. **避免重复发送**：确保 `_sent_marker_ids` 正确更新
3. **消息合并**：只合并 ✦ 标记的消息，过滤 ✻ 标记的消息
4. **企业微信配置**：需要确保 `wechat_channel.user_id` 有值，用于发送 iflow 交互界面的消息
5. **向后兼容**：`source` 参数有默认值 "wechat"，不影响现有调用