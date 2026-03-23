# Ling-iflow 项目上下文文档

## 项目概述

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信、飞书等渠道的双向消息同步。基于消息总线的松耦合架构，支持多渠道、多实例。

## 核心架构

### 设计模式
基于**发布-订阅模式**和**消息总线**设计，实现模块解耦。

### 三大核心模块
1. **消息渠道 (Channel)** - 处理与外部系统的消息交互
   - `WeChatChannel` - 企业微信渠道（回调模式）
   - `FeishuChannel` - 飞书渠道（WebSocket 长连接，无需公网 IP）
   - `SimulatorChannel` - 模拟器渠道（本地测试）
2. **消息总线 (MessageBus)** - 模块间消息路由和分发
3. **iflow 模块 (IFlowModule)** - iflow CLI 的完整管理

### 核心组件
- **ModuleManager** - 模块生命周期管理、健康监控、状态历史、性能指标
- **MessageConverter** - 消息格式转换
- **NotificationManager** - 事件通知管理
- **CommandHandler** - 命令解析和执行

## 目录结构

```
Ling-iflow/
├── src/                    # 源代码
│   ├── bot.py             # 主程序入口
│   ├── cli.py             # CLI 入口点
│   ├── core/              # 核心基础类
│   │   ├── base.py        # 模块基类
│   │   ├── bus.py         # 消息总线
│   │   ├── manager.py     # 模块管理器
│   │   ├── message.py     # 消息定义
│   │   └── result.py      # 操作结果
│   └── modules/           # 模块实现
│       ├── channel/       # 渠道（wechat, feishu, simulator）
│       ├── iflow/         # iflow 模块
│       │   ├── module.py  # 主模块
│       │   ├── controller.py  # tmux 控制
│       │   ├── monitor.py     # 输出监控
│       │   ├── session_manager.py  # 会话管理
│       │   ├── message_store.py    # 消息存储
│       │   └── logger.py  # 交互日志
│       ├── command/       # 命令处理器
│       └── common/        # 通用组件
├── design-v2/             # 设计文档
├── tests/                 # 测试文件
├── tools/                 # 工具
│   ├── iflow_interactive_tool.py  # iflow 交互工具（AI Skill）
│   ├── test_client.py     # 模拟器测试客户端
│   ├── feishu_test_tool.py  # 飞书测试工具
│   └── tmux_viewer.py     # tmux 查看器
├── manage.py              # 管理脚本
├── config.example.json    # 配置示例
└── config.json            # 配置文件
```

## 技术栈

- **Python**: 3.10+
- **pydantic**: 数据验证
- **loguru**: 日志记录
- **typer**: CLI 命令
- **asyncio**: 异步编程
- **tmux**: 会话管理
- **lark-oapi**: 飞书 SDK（可选）

## 安装和配置

```bash
# 基础安装
pip install -e .

# 完整安装（包含所有可选依赖）
pip install -e ".[all]"

# 单独安装可选功能
pip install -e ".[wechat]"    # 企业微信
pip install -e ".[feishu]"    # 飞书
pip install -e ".[dev]"       # 开发依赖

# 配置
cp config.example.json config.json
vim config.json
```

## 配置文件结构

```json
{
  "bots": [
    {
      "name": "wecom1",
      "corp_id": "your_corp_id",
      "agent_id": "your_agent_id",
      "secret": "your_secret",
      "user_id": "your_user_id",
      "token": "your_token",
      "encoding_aes_key": "your_key",
      "callback_port": 8787
    }
  ],
  "feishu_channels": [
    {
      "name": "feishu1",
      "app_id": "cli_xxxxxxxxxxxxx",
      "app_secret": "your_app_secret",
      "verification_token": "your_token",
      "notify_user_id": "ou_xxxxxxxxxxxxx"
    }
  ],
  "simulator_channels": [
    {
      "name": "simulator1",
      "host": "localhost",
      "port": 19999
    }
  ],
  "log_level": "INFO",
  "filter_thinking": true
}
```

## 启动和管理

```bash
# 查看帮助
./manage.py --help

# 启动服务
./manage.py start                    # 启动默认渠道
./manage.py start -a                 # 启动所有渠道
./manage.py start -f                 # 前台模式（进入 tmux）
./manage.py start --channel feishu1  # 启动指定渠道
./manage.py start --channel ls       # 列出所有可用渠道

# 停止服务
./manage.py stop                     # 停止默认渠道
./manage.py stop -a                  # 停止所有渠道
./manage.py stop --channel wecom1    # 停止指定渠道

# 重启服务
./manage.py restart                  # 重启默认渠道
./manage.py restart -f               # 前台模式重启

# 查看状态
./manage.py status                   # 查看所有已启动模块状态

# 查看日志
./manage.py logs -f                  # 实时查看日志

# 渠道管理
./manage.py channel list             # 列出渠道
./manage.py channel status           # 查看状态
```

## 命令系统

支持以下命令（在企业微信/飞书中发送）：

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/status` | 查看服务状态 |
| `/new` | 开始新会话（清除上下文） |
| `/sessions` | 查看历史会话 |
| `/history [模块ID]` | 查看模块状态历史 |
| `/metrics [模块ID]` | 查看模块性能指标 |
| `/snapshot [channel]` | 查看 tmux 界面快照 |
| `/scope [reply\|all]` | 切换回复模式 |
| `/channel list` | 列出所有渠道 |
| `/channel start/stop/restart <name>` | 渠道管理 |
| `/tmux list/create/kill` | tmux 会话管理 |
| `/lscmd` | 列出所有命令 |

**注意**：未知的斜杠命令会自动透传给 iflow 处理（如 `/run`、`/config` 等）。

## 核心组件说明

### BaseModule（模块基类）
- `start()` / `stop()`: 生命周期管理
- `receive(message)`: 接收消息
- `send_to_bus(message)`: 发送消息到消息总线
- `create_background_task(coro)`: 创建后台任务

### MessageBus（消息总线）
- `register_module()` / `unregister_module()`: 模块注册
- `bind()` / `unbind()`: 模块绑定
- `route()`: 消息路由（按绑定关系）
- `broadcast_to_bindings()`: 广播消息

### IFlowModule（iflow 模块）
- 通过 tmux 启动/停止 iflow CLI
- 监控会话文件，提取 AI 回复
- 消息状态检测（idle/generating）
- 消息分类（reply/other/complete）
- 健康检查、状态历史、性能指标

**核心子组件：**
- `IFlowController`: tmux 会话控制
- `IFlowMonitor`: 会话文件监控
- `SessionManager`: 会话文件管理
- `MessageStore`: 消息存储和归属
- `InteractionLogger`: 交互记录

### ModuleManager（模块管理器）
- 模块创建、启动、停止
- 健康监控（定期检查）
- 状态历史记录
- 性能指标收集
- iflow 状态跟踪

### CommandHandler（命令处理器）
解析和执行用户命令，支持渠道管理、状态查询等。

### FeishuChannel（飞书渠道）
- 使用 WebSocket 长连接，无需公网 IP
- 支持文本、图片、文件、流式输出
- 消息去重、反应处理

## 关键技术细节

### IFlowMonitor 消息提取原则
1. **延迟记录原则**：检测到 2 条或更多消息时才开始记录
2. **倒数第二原则**：倒数第二的标记已经完整，不会再变化
3. **状态检测原则**：连续 3 次扫描"生成中"消失，记录最后一条消息

### 回复模式（scope）
- `reply_only`：只返回 ✦ 标记的回复消息（默认）
- `all`：返回所有消息（包括 ✻ 思考过程）

### 消息类型
- `reply`：AI 回复（✦ 标记）
- `other`：思考过程（✻ 标记或无标记）
- `complete`：交互完成通知

### 缓存管理策略
- 最大缓存：100 条
- 保留数量：50 条
- 用于消息去重，避免重复发送

### tmux 会话命名规则
- 格式：`<渠道名>+iflow`
- 示例：`feishu1+iflow`、`wecom1+iflow`

### Unix Socket 控制接口
- 路径：`/tmp/ling-iflow.sock`
- 命令：`start`、`stop`、`restart`、`status`、`list`
- 用于外部程序控制服务

## 测试工具

### iflow_interactive_tool.py（AI Skill）
用于控制 tmux 中的 iflow CLI，支持完整的 tmux 会话管理。

```bash
# JSON 格式输出（AI 调用必须使用）
python3 tools/iflow_interactive_tool.py --json tmux list
python3 tools/iflow_interactive_tool.py --json tmux create myproject --workspace /path/to/project --mode yolo
python3 tools/iflow_interactive_tool.py --json --tmux-session myproject send "请帮我实现..." --timeout 600
python3 tools/iflow_interactive_tool.py --json tmux snapshot myproject --lines 50
python3 tools/iflow_interactive_tool.py --json session new
```

详见 `tools/SKILL.md`。

### test_client.py
模拟器测试客户端，用于本地测试。

```bash
python3 tools/test_client.py
```

### feishu_test_tool.py
飞书独立测试工具，用于测试飞书渠道。

```bash
python3 tools/feishu_test_tool.py
```

## 设计文档

详见 `design-v2/README.md`

主要文档：
- `01-总体架构设计.md` - 系统架构
- `02-消息总线与模块管理.md` - 核心组件
- `03-IFlow模块设计.md` - iflow 模块详解
- `04-渠道架构设计.md` - 渠道设计
- `20-飞书渠道设计方案.md` - 飞书集成
- `21-消息来源差异化处理方案.md` - 消息处理
- `22-scope命令历史消息重复问题修复方案.md` - 问题修复

## 待办任务

详见 `TODO.md`

当前重点：
- 阶段 8：单进程多组管理
- P1：错误处理和重试机制
- P2：Web 控制台、配置热更新

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| 找不到 ling-iflow 命令 | `pip install -e .` 后检查 PATH |
| 启动失败 | 检查 config.json 和日志 |
| 消息无回复 | 使用 `/snapshot` 查看 tmux 界面 |
| tmux 会话问题 | `tmux ls` 检查会话状态 |
| 飞书连接失败 | 检查 app_id 和 app_secret |
| 企业微信回调失败 | 检查端口和回调配置 |

## 开发规范

### 代码风格
- 使用 Python 3.10+ 类型注解
- 遵循 PEP 8 代码规范
- 使用 loguru 记录日志

### 测试
```bash
pytest tests/                          # 运行测试
pytest tests/ -v --tb=short           # 详细输出
```

### 提交规范
- 清晰的提交信息
- 包含必要的文档更新
- 通过所有测试

## 环境信息

- **平台**: Linux (WSL2)
- **Python**: 3.13.11
- **Git**: 2.34.1
- **仓库**: `git@github.com:lingzhia/Ling-iflow-message.git`

---

*最后更新: 2026-03-23*