# Ling-iflow 项目上下文文档

## 项目概述

Ling-iflow 是一个 iflow CLI 交互模式管理工具，支持通过 tmux 启动 iflow，并实现与企业微信的双向消息同步。项目从 iflow-bot 迁移而来，专注于提供轻量级的交互模式管理功能。

## 核心功能

1. **tmux 集成**：通过 tmux 启动和管理 iflow CLI 会话
2. **会话监控**：实时监控 iflow 的会话文件，捕获 AI 回复
3. **消息同步**：支持企业微信消息与 iflow CLI 的双向同步
4. **测试工具**：提供模拟企业微信消息的测试程序

## 目录结构

```
Ling-iflow/
├── channels/           # 渠道模块
│   ├── __init__.py
│   ├── base.py        # 渠道基类
│   └── wechat_work.py # 企业微信渠道（简化版）
├── cli/               # CLI 命令模块
│   ├── __init__.py
│   └── commands.py    # CLI 命令接口
├── config/            # 配置管理模块
│   ├── __init__.py
│   ├── schema.py      # 配置 Schema
│   └── loader.py      # 配置加载器
├── interactive/       # 交互模式核心模块
│   ├── __init__.py
│   ├── iflow_controller.py  # iflow CLI 控制器
│   ├── session_monitor.py   # 会话监控器
│   └── sync_manager.py      # 同步管理器
├── utils/             # 工具函数模块
│   ├── __init__.py
│   └── helpers.py     # 工具函数
├── config.example.json # 配置示例文件
├── pyproject.toml     # 项目依赖配置
├── test_wechat_mock.py # 企业微信消息模拟测试程序
└── AGENTS.md          # 本文档
```

## 安装和使用

### 安装依赖

```bash
pip install -e .
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
# 运行完整测试
ling-iflow test

# 运行简单测试
ling-iflow test --simple

# 或直接运行测试脚本
python test_wechat_mock.py
python test_wechat_mock.py --simple
```

## 核心组件说明

### IFlowController

iflow CLI 控制器，通过 tmux 命令管理 iflow CLI 会话。

**主要方法：**
- `check_tmux_session()`: 检查 tmux 会话是否存在
- `check_iflow_running()`: 检查 iflow CLI 是否运行
- `send_message(message)`: 发送消息到 iflow CLI
- `start_iflow(model)`: 在 tmux 会话中启动 iflow CLI
- `stop_iflow()`: 停止 iflow CLI

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

企业微信渠道（简化版），用于测试程序模拟企业微信消息。

**主要方法：**
- `start()`: 启动渠道
- `stop()`: 停止渠道
- `send(content, chat_id, **kwargs)`: 发送消息
- `receive_message(...)`: 接收外部消息（用于测试）
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
python test_wechat_mock.py

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

### 示例 3：查看状态

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
  → SyncManager.receive_wechat_message()
  → 放入 _wechat_queue
  → _wechat_loop() 取出消息
  → IFlowController.send_message()
  → tmux send-keys 注入消息
  → iflow CLI 接收并处理
```

**iflow CLI → 企业微信：**
```
iflow CLI 生成回复
  → 写入 session-*.jsonl 文件
  → SessionMonitor.read_new_assistant_messages()
  → 检测到新消息
  → _monitor_loop() 处理
  → SyncManager.send_to_wechat()
  → WechatWorkChannel.send()
  → 企业微信 API 发送
  → 用户收到回复
```

### 依赖项

- **pydantic**: 数据验证和配置管理
- **pydantic-settings**: 从环境变量和配置文件加载配置
- **loguru**: 日志记录
- **typer**: CLI 命令行界面

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
   - 回调模式需要配置 `token` 和 `encoding_aes_key`
   - 确保防火墙开放回调端口（默认 8788）

4. **测试程序**：
   - 测试程序使用简化版的企业微信渠道
   - 仅用于测试消息流，不支持实际的企业微信 API
   - 如需完整功能，请使用 iflow-bot 项目

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
- 提供测试程序模拟企业微信消息
- 配置文件位置：`~/.ling-iflow/config.json`
- 环境信息：Linux (WSL2), Python 3.13.11

## 与 iflow-bot 的区别

1. **简化设计**：只包含交互模式核心功能，移除其他渠道和复杂功能
2. **独立运行**：不依赖 iflow-bot 的消息总线和其他组件
3. **测试导向**：提供简化的企业微信渠道，便于测试
4. **轻量级**：依赖项更少，安装和配置更简单

## 未来改进

1. 支持更多渠道（Telegram、Discord 等）
2. 添加消息历史记录功能
3. 支持多会话管理
4. 增强 Web 控制台
5. 添加更多测试用例