# Ling-iflow

iflow CLI 交互模式管理工具，支持通过 tmux 启动 iflow，并实现与企业微信的双向消息同步。

## 功能特性

- ✅ 通过 tmux 启动和管理 iflow CLI 会话
- ✅ 实时监控 iflow 的会话文件，捕获 AI 回复
- ✅ 支持企业微信消息与 iflow CLI 的双向同步
- ✅ 消息来源差异化处理（工具消息、企业微信消息、iflow 交互界面消息）
- ✅ 后台监控功能，检测 iflow 交互界面的消息并自动同步到企业微信
- ✅ 提供交互式测试工具和企业微信调试工具
- ✅ 轻量级设计，易于安装和使用

## 快速开始

### 1. 安装依赖

```bash
pip install -e .
```

### 2. 启动 iflow CLI

```bash
tmux new-session -d -s iflow "iflow --model kimi-k2.5"
```

### 3. 启动交互模式服务

```bash
ling-iflow start
```

### 4. 测试消息同步

在另一个终端运行测试工具：

```bash
# 运行 iflow 交互式测试工具
python tool/iflow_interactive.py
```

在测试工具中输入消息，观察 iflow 的回复。

## 使用说明

### CLI 命令

```bash
# 启动交互模式服务
ling-iflow start

# 停止 iflow
ling-iflow stop

# 查看状态
ling-iflow status

# 运行测试
ling-iflow test

# 初始化配置
ling-iflow init
```

### 配置文件

配置文件位置：`~/.ling-iflow/config.json`

示例配置：

```json
{
  "workspace": "~/.iflow",
  "model": "kimi-k2.5",
  "tmux_session": "iflow",
  "wechat_work": {
    "enabled": false,
    "corp_id": "",
    "agent_id": "",
    "secret": ""
  },
  "log_level": "INFO"
}
```

## 项目结构

```
Ling-iflow/
├── channels/           # 渠道模块
├── cli/               # CLI 命令模块
├── config/            # 配置管理模块
├── interactive/       # 交互模式核心模块
├── tool/              # 测试工具模块
├── utils/             # 工具函数模块
├── wechat_bot.py      # 企业微信 Bot 主程序
└── AGENTS.md          # 详细文档
```

## 技术架构

### 核心组件

- **IFlowController**: iflow CLI 控制器，通过 tmux 管理会话
- **SessionMonitor**: 会话文件监控器，实时捕获 AI 回复
- **SyncManager**: 同步管理器，协调双向消息同步
- **WechatWorkChannel**: 企业微信渠道（简化版）

### 消息流向

**企业微信 → iflow CLI：**
```
企业微信消息 → WechatWorkChannel → SyncManager → IFlowController → tmux → iflow CLI
```

**iflow CLI → 企业微信：**
```
iflow CLI → session-*.jsonl → SessionMonitor → SyncManager → WechatWorkChannel → 企业微信
```

## 注意事项

1. 需要安装 tmux
2. 需要安装 iflow CLI
3. 测试程序使用简化版的企业微信渠道，仅用于测试

## 详细文档

查看 [AGENTS.md](AGENTS.md) 了解更多详细信息。

## 许可证

MIT License