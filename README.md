# Ling-iflow

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信的双向消息同步。

## 项目状态

✅ **重构完成**

项目已完成从紧耦合架构到基于消息总线的松耦合架构的重构。

## 架构概述

基于**发布-订阅模式**和**消息总线**设计，实现模块解耦：

### 核心组件

1. **企业微信消息模块** - 纯粹的企业微信 API 封装
2. **消息总线** - 模块间消息路由和分发
3. **iflow 消息模块** - iflow CLI 的完整管理
4. **模块管理器** - 模块生命周期管理和状态监控

### 核心优势

- ✅ **解耦清晰** - 模块间通过消息总线通信
- ✅ **扩展性强** - 添加新功能无需修改现有代码
- ✅ **灵活度高** - 支持多对多绑定和动态绑定
- ✅ **易于维护** - 模块独立开发测试，故障隔离
- ✅ **统一管理** - 模块管理器统一管理模块生命周期和状态

## 目录结构

```
Ling-iflow/
├── src/                # 新版本（重构完成）
│   ├── core/           # 核心基础类
│   │   ├── base.py     # 模块基类
│   │   ├── bus.py      # 消息总线
│   │   ├── manager.py  # 模块管理器
│   │   └── message.py  # 消息定义
│   ├── modules/        # 模块实现
│   │   ├── channel/    # 消息渠道
│   │   │   ├── wechat.py    # 企业微信渠道
│   │   │   └── simulator.py # 模拟器渠道
│   │   ├── common/     # 通用组件
│   │   │   ├── converter.py     # 消息转换器
│   │   │   └── notifications.py # 通知管理器
│   │   ├── iflow/      # iflow 模块
│   │   └── command/    # 命令处理器
│   └── bot.py          # 主程序入口
├── manage.py           # 项目管理脚本
├── src_old/            # 旧版本（备份）
│   ├── channels/       # 渠道模块
│   ├── interactive/    # 交互模式核心模块
│   ├── config/         # 配置管理模块
│   ├── cli/            # CLI 命令模块
│   ├── utils/          # 工具函数模块
│   ├── tool/           # 测试工具模块
│   ├── design/         # 旧版本设计文档
│   ├── manage.py       # 项目管理脚本
│   ├── wechat_bot.py   # 企业微信 Bot 主程序
│   ├── tmux_manager.py # tmux 管理工具
│   └── README-old.md   # 旧版本 README 备份
├── design-v2/          # 重构设计方案
│   ├── 01-模块重构方案.md
│   ├── 02-重构计划.md
│   ├── 03-微信模块增强方案.md
│   ├── 04-IFlow模块设计方案.md
│   ├── 05-消息总线设计方案.md
│   ├── 06-启动方案设计.md
│   └── README.md
├── tests/              # 测试文件
│   ├── test_message_bus.py
│   ├── test_base_module.py
│   ├── test_iflow_module.py
│   ├── test_wechat_module.py
│   ├── test_command_handler.py
│   ├── test_integration.py
│   ├── test_full_integration.py
│   └── mock_wechat.py
├── tools/              # 测试工具
│   ├── iflow_interactive_tool.py
│   └── wechat_test_tool.py
├── logs/               # 日志目录
├── config.json         # 配置文件
├── config.example.json # 配置示例
├── pyproject.toml      # 项目依赖配置
└── README.md           # 本文档
```

## 文档

### 设计文档
- [design-v2/01-模块重构方案.md](design-v2/01-模块重构方案.md) - 详细的模块拆分方案
- [design-v2/02-重构计划.md](design-v2/02-重构计划.md) - 重构计划和进度
- [design-v2/03-微信模块增强方案.md](design-v2/03-微信模块增强方案.md) - 微信模块设计
- [design-v2/04-IFlow模块设计方案.md](design-v2/04-IFlow模块设计方案.md) - IFlow模块设计
- [design-v2/05-消息总线设计方案.md](design-v2/05-消息总线设计方案.md) - 消息总线设计
- [design-v2/06-启动方案设计.md](design-v2/06-启动方案设计.md) - 启动方案和管理脚本设计
- [design-v2/11-模块管理器设计方案.md](design-v2/11-模块管理器设计方案.md) - 模块管理器设计
- [design-v2/13-渠道架构重构方案.md](design-v2/13-渠道架构重构方案.md) - 渠道架构重构方案
- [design-v2/14-多渠道支持方案.md](design-v2/14-多渠道支持方案.md) - 多渠道支持方案

### 旧版本文档（参考）
- [src_old/README-old.md](src_old/README-old.md) - 旧版本 README
- [src_old/WECHAT_SETUP.md](src_old/WECHAT_SETUP.md) - 企业微信配置说明

## 快速开始

### 安装依赖

```bash
# 安装基础依赖
pip install -e .

# 安装企业微信依赖
pip install -e ".[wechat]"

# 完整安装（包含开发和微信功能）
pip install -e ".[dev,wechat]"
```

### 配置

```bash
# 复制配置文件
cp config.example.json config.json

# 编辑配置文件
vim config.json
```

### 配置项说明

**核心配置：**
- `groups`: 组定义（支持多组管理）
  - `modules`: 组包含的模块列表
  - `default`: 是否为默认组
  - `auto_start`: 是否自动启动
  - `description`: 组描述
- `tmux_sessions`: iflow 会话配置（支持多实例）
  - `name`: 会话名称
  - `workspace`: 工作目录
  - `model`: 模型名称（如 glm-4.7）
- `bots`: 企业微信机器人配置（支持多机器人）
  - `name`: 机器人名称
  - `enabled`: 是否启用
  - `corp_id`: 企业ID
  - `agent_id`: 应用AgentId
  - `secret`: 应用Secret
  - `user_id`: 用户账号
  - `token`: 回调Token
  - `encoding_aes_key`: EncodingAESKey
  - `callback_port`: 回调端口
  - `tmux_session`: 关联的tmux会话
- `simulator_channels`: 模拟器渠道配置（支持多模拟器）
  - `name`: 模拟器名称
  - `enabled`: 是否启用
  - `host`: 监听地址
  - `port`: 监听端口
  - `tmux_session`: 关联的tmux会话
- `log_level`: 日志级别（INFO, DEBUG, ERROR等）

### 启动

#### 方式1: 使用管理脚本（推荐）

**基本命令：**

```bash
# 启动服务（默认后台启动组1）
./manage.py start

# 启动所有组（后台）
./manage.py start -a

# 前台启动组1
./manage.py start -f

# 前台启动所有组
./manage.py start -a -f

# 停止服务（默认停止组1）
./manage.py stop

# 停止所有组
./manage.py stop -a

# 重启服务（默认后台重启组1）
./manage.py restart

# 重启所有组（后台）
./manage.py restart -a

# 前台重启组1
./manage.py restart -f

# 查看状态
./manage.py status

# 查看日志（最近100行）
./manage.py logs

# 实时跟踪日志
./manage.py logs -f

# 清理日志和缓存
./manage.py clean
```

**指定组操作：**

```bash
# 启动指定组
./manage.py start -g g1              # 启动 g1 组
./manage.py start -g g2              # 启动 g2 组
./manage.py start -g g_simulator     # 启动模拟器组

# 停止指定组
./manage.py stop -g g1               # 停止 g1 组
./manage.py stop -g g2               # 停止 g2 组

# 重启指定组
./manage.py restart -g g1            # 重启 g1 组
./manage.py restart -g g2            # 重启 g2 组
```

**查看可用组：**

```bash
# 列出所有可用组
./manage.py start -g ls
./manage.py stop -g ls
./manage.py restart -g ls
```

**指定渠道操作：**

```bash
# 启动指定渠道
./manage.py start --channel wechat_bot1   # 指定企业微信渠道
./manage.py start --channel simulator1    # 指定模拟器渠道

# 后台启动指定渠道
./manage.py start --channel wechat_bot1 -d
```

**使用自定义配置：**

```bash
# 使用指定配置文件
./manage.py start -c config-dev.json
./manage.py start -c config-test.json -g g1

# 后台启动使用指定配置
./manage.py start -c config.json -g g1 -d
```

**参数组合示例：**

```bash
# 启动指定组（后台）
./manage.py start -g g2

# 启动指定组（前台）
./manage.py start -g g2 -f

# 启动所有组（后台）
./manage.py start -a

# 启动所有组（前台）
./manage.py start -a -f

# 重启指定组（后台）
./manage.py restart -g g2

# 重启指定组（前台）
./manage.py restart -g g2 -f

# 使用自定义配置启动指定组（后台）
./manage.py start -c config.json -g g1

# 使用自定义配置启动指定组（前台）
./manage.py start -c config.json -g g1 -f
```

**参数说明：**

- `-a, --all`: 启动/停止/重启所有组
- `-g, --group <组名>`: 指定要操作的组
- `-f, --foreground`: 前台运行（默认后台运行）
- `-c, --config <文件>`: 指定配置文件
- `--channel <渠道名>`: 指定要启动的渠道

**参数限制：**

- `-a` 和 `-g` 参数互斥，不能同时使用
- `-g` 支持特殊值 `ls`，用于列出所有可用组
- `--channel` 和 `-g` 参数互斥，优先使用 `--channel`
- 默认组为配置文件中标记为 `default` 的组（通常为 g1）
- 默认为后台运行，使用 `-f` 启用前台运行

#### 方式2: 直接启动

```bash
# 使用默认配置启动
python3 -m src.bot

# 指定配置文件启动
python3 -m src.bot config.json

# 指定组启动
python3 -m src.bot config.json --group g1

# 启动所有组
python3 -m src.bot config.json --group all
```

**推荐使用方式1**，提供更完整的管理功能和参数支持。

## 消息流转流程

```
企业微信用户发送消息
        ↓
[WeChatChannel] 接收回调
        ↓
[WeChatModule] 处理消息
        ↓
[MessageBus] 路由到 iflow 模块
        ↓
[IFlowController] 注入到 iflow CLI
        ↓
iflow CLI 处理并返回
        ↓
[IFlowMonitor] 监听并提取输出
        ↓
[IFlowModule] 封装为消息
        ↓
[MessageBus] 路由回 WeChat 模块
        ↓
[WeChatChannel] 发送到企业微信
        ↓
用户收到回复
```

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_message_bus.py
pytest tests/test_iflow_module.py
```

### 测试工具

```bash
# IFlow 交互测试工具
python3 tools/iflow_interactive_tool.py

# 企业微信测试工具
python3 tools/wechat_test_tool.py listen
```

## 功能特性

### 已实现 ✅

**核心功能：**
- ✅ IFlow 完整管理（启动/停止/消息注入/输出监控）
- ✅ 企业微信回调接收和消息发送
- ✅ 消息总线路由和绑定
- ✅ 命令处理（/help, /status, /new, /sessions, /history, /metrics, /lscmd）
- ✅ 消息状态检测（idle/generating）
- ✅ 消息分类（reply/other/complete）
- ✅ 拒绝机制（生成中拒绝新消息）
- ✅ 多轮对话来源归属
- ✅ 交互日志记录

**多组管理（单进程多组架构）：**
- ✅ 单进程管理多个组
- ✅ 组定义支持（groups 配置）
- ✅ 默认组自动识别
- ✅ 动态组管理（启动/停止/重启）
- ✅ Unix Socket 控制接口
- ✅ 组管理命令（/groups, /group status/start/stop/restart）
- ✅ 管理脚本组管理（./manage.py group）
- ✅ 模块预创建和按需启动
- ✅ 组间状态独立管理
- ✅ 健康监控和状态同步

**多实例支持：**
- ✅ 多 iflow 实例支持
- ✅ 多企业微信机器人支持
- ✅ 多渠道支持（企业微信、模拟器）
- ✅ 多 tmux 会话管理
- ✅ 渠道最小化架构
- ✅ 模块化设计

**模块管理：**
- ✅ 模块管理器统一管理模块生命周期
- ✅ 模块健康监控和自动恢复
- ✅ 消息应答检查机制
- ✅ 模块依赖管理和启动顺序控制
- ✅ 通用组件复用（消息转换器、通知管理器）
- ✅ 模拟器渠道和测试工具

**项目管理：**
- ✅ 项目管理脚本（manage.py）
- ✅ 服务生命周期管理（启动/停止/重启/状态/日志）
- ✅ 启动/停止通知机制
- ✅ Message 对象规范化
- ✅ 参数化配置管理
- ✅ 日志和缓存清理

### 待实现 🚧

- 🚧 错误处理和重试机制
- 🚧 日志系统优化
- 🚧 Web 控制台
- 🚧 配置热更新
- 🚧 监控告警
- 🚧 消息去重机制测试（需企业微信快速重发）

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

MIT License