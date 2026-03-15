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
│   │   ├── wechat/     # 企业微信模块
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

配置项说明：
- `tmux_sessions`: iflow 会话配置（支持多实例）
- `bots`: 企业微信机器人配置（支持多机器人）
- `log_level`: 日志级别

### 启动

#### 方式1: 使用管理脚本（推荐）

```bash
# 启动服务
./manage.py start

# 后台启动
./manage.py start -d

# 使用指定配置
./manage.py start -c config-dev.json

# 停止服务
./manage.py stop

# 重启服务
./manage.py restart

# 查看状态
./manage.py status

# 查看日志
./manage.py logs

# 持续跟踪日志
./manage.py logs -f

# 清理日志和缓存
./manage.py clean
```

#### 方式2: 直接启动

```bash
# 使用默认配置启动
python3 -m src.bot

# 指定配置文件启动
python3 -m src.bot config.json
```

**推荐使用方式1**，提供更完整的管理功能。

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

- ✅ IFlow 完整管理（启动/停止/消息注入/输出监控）
- ✅ 企业微信回调接收和消息发送
- ✅ 消息总线路由和绑定
- ✅ 命令处理（/help, /status, /new, /sessions）
- ✅ 多 iflow 实例支持
- ✅ 多企业微信机器人支持
- ✅ 消息状态检测（idle/generating）
- ✅ 消息分类（reply/other/complete）
- ✅ 拒绝机制（生成中拒绝新消息）
- ✅ 多轮对话来源归属
- ✅ 交互日志记录
- ✅ 项目管理脚本（manage.py）
- ✅ 服务生命周期管理（启动/停止/重启/状态/日志）
- ✅ 启动/停止通知机制
- ✅ Message 对象规范化
- ✅ 模块管理器统一管理模块生命周期
- ✅ 模块健康监控和自动恢复
- ✅ 消息应答检查机制
- ✅ 模块依赖管理和启动顺序控制

### 待实现 🚧

- 🚧 错误处理和重试机制
- 🚧 日志系统优化
- 🚧 Web 控制台
- 🚧 配置热更新
- 🚧 监控告警

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

MIT License