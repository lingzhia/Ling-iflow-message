# Ling-iflow 项目上下文文档

## 项目概述

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信的双向消息同步。项目已完成从紧耦合架构到基于消息总线的松耦合架构的重构。

## 核心架构

### 设计模式
基于**发布-订阅模式**和**消息总线**设计，实现模块解耦：

### 三大核心模块
1. **企业微信渠道 (WeChatChannel)** - 纯粹的企业微信 API 封装，处理消息接收和发送
2. **消息总线 (MessageBus)** - 模块间消息路由和分发的核心组件
3. **iflow 模块 (IFlowModule)** - iflow CLI 的完整管理，包括启动、停止、消息注入和输出监控

### 核心组件
- **模块管理器 (ModuleManager)** - 统一管理模块生命周期和状态监控
- **消息转换器 (MessageConverter)** - 统一的消息格式转换
- **通知管理器 (NotificationManager)** - 模块事件通知管理

### 架构优势
- ✅ **解耦清晰** - 模块间通过消息总线通信
- ✅ **扩展性强** - 添加新功能无需修改现有代码
- ✅ **灵活度高** - 支持多对多绑定和动态绑定
- ✅ **易于维护** - 模块独立开发测试，故障隔离

## 目录结构

```
Ling-iflow/
├── src/                          # 新版本（重构完成）
│   ├── core/                     # 核心基础类
│   │   ├── base.py              # 模块基类 (BaseModule)
│   │   ├── bus.py               # 消息总线 (MessageBus)
│   │   ├── manager.py           # 模块管理器 (ModuleManager)
│   │   └── message.py           # 消息定义 (Message, MessageContent)
│   ├── modules/                  # 模块实现
│   │   ├── channel/             # 消息渠道
│   │   │   ├── wechat.py        # 企业微信渠道 (WeChatChannel)
│   │   │   └── simulator.py     # 模拟器渠道 (SimulatorChannel)
│   │   ├── common/              # 通用组件
│   │   │   ├── converter.py     # 消息转换器 (MessageConverter)
│   │   │   └── notifications.py # 通知管理器 (NotificationManager)
│   │   ├── iflow/               # iflow 模块
│   │   │   ├── controller.py    # IFlowController (tmux 控制)
│   │   │   ├── monitor.py       # IFlowMonitor (会话监控)
│   │   │   ├── session_manager.py # 会话管理
│   │   │   ├── message_store.py # 消息存储
│   │   │   ├── logger.py        # 交互日志记录
│   │   │   └── module.py        # IFlowModule
│   │   └── command/             # 命令处理器
│   │       └── handler.py       # CommandHandler
│   └── bot.py                    # 主程序入口 (LingIflowBot)
├── src_old/                      # 旧版本（备份）
│   ├── channels/                 # 旧版渠道模块
│   ├── interactive/              # 旧版交互模式核心模块
│   ├── config/                   # 旧版配置管理模块
│   ├── cli/                      # 旧版 CLI 命令模块
│   ├── utils/                    # 旧版工具函数模块
│   ├── tool/                     # 旧版测试工具模块
│   ├── design/                   # 旧版设计文档
│   ├── manage.py                 # 旧版项目管理脚本
│   ├── wechat_bot.py             # 旧版企业微信 Bot 主程序
│   ├── tmux_manager.py           # 旧版 tmux 管理工具
│   └── README-old.md             # 旧版 README 备份
├── design-v2/                    # 重构设计方案
│   ├── 01-模块重构方案.md
│   ├── 02-重构计划.md
│   ├── 03-微信模块增强方案.md
│   ├── 04-IFlow模块设计方案.md
│   ├── 05-消息总线设计方案.md
│   ├── 06-启动方案设计.md
│   ├── 07-消息提取优化方案.md
│   ├── 08-IFlowModule测试工具方案.md
│   ├── 11-模块管理器设计方案.md
│   ├── 12-消息模拟器和测试工具方案.md
│   ├── 13-渠道架构重构方案.md
│   └── 14-多渠道支持方案.md
├── tests/                        # 测试文件
│   ├── test_message_bus.py
│   ├── test_base_module.py
│   ├── test_iflow_module.py
│   ├── test_iflow_module_core.py
│   ├── test_wechat_module.py
│   ├── test_command_handler.py
│   ├── test_integration.py
│   ├── test_full_integration.py
│   ├── test_message.py
│   ├── iflow_test_tool.py
│   └── mock_wechat.py
├── tools/                        # 测试工具
│   ├── iflow_interactive_tool.py  # IFlow 交互测试工具
│   ├── wechat_test_tool.py        # 企业微信测试工具
│   ├── test_client.py             # 模拟器测试客户端
│   └── tmux_viewer.py             # Tmux 查看工具
├── logs/                         # 日志目录
│   └── interactions/             # 交互日志
├── config.json                   # 配置文件
├── config.example.json           # 配置示例
├── pyproject.toml                # 项目依赖配置
├── manage.py                     # 项目管理脚本
├── README.md                     # 项目说明文档
├── TODO.md                       # 待办任务列表
└── AGENTS.md                     # 本文档（用于 iFlow 上下文）
```

## 技术栈

### 核心依赖
- **Python**: 3.10+
- **pydantic**: 2.0.0+ (数据验证和配置管理)
- **pydantic-settings**: 2.0.0+ (从环境变量和配置文件加载配置)
- **loguru**: 0.7.0+ (日志记录)
- **typer**: 0.9.0+ (CLI 命令行界面)
- **asyncio**: 异步编程框架

### 可选依赖
- **dev**: pytest 7.0.0+, pytest-asyncio 0.21.0+ (测试框架)
- **wechat**: httpx 0.24.0+, aiohttp 3.8.0+, cryptography 41.0.0+ (企业微信功能)

### 系统依赖
- **tmux**: 会话管理工具
- **iflow CLI**: iflow 命令行工具

## 安装和配置

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

### 配置

```bash
# 复制配置文件
cp config.example.json config.json

# 编辑配置文件
vim config.json
```

### 配置项说明

配置文件位置：`config.json`

主要配置项：
```json
{
  "tmux_sessions": [
    {
      "name": "iflow",
      "workspace": "~/.iflow",
      "model": "kimi-k2.5"
    }
  ],
  "bots": [
    {
      "name": "bot1",
      "enabled": true,
      "tmux_session": "iflow",
      "corp_id": "企业ID",
      "agent_id": "应用AgentId",
      "secret": "应用Secret",
      "user_id": "用户账号",
      "token": "回调Token",
      "encoding_aes_key": "EncodingAESKey",
      "callback_host": "0.0.0.0",
      "callback_port": 8788,
      "allow_from": [],
      "group_policy": "mention",
      "group_allow_from": []
    }
  ],
  "log_level": "INFO"
}
```

## 启动和管理

### 方式1: 使用管理脚本（推荐）

```bash
# 启动服务
./manage.py start

# 后台启动
./manage.py start -d

# 启动指定组（g1: bot1+iflow, g2: bot2+iflow2）
./manage.py start -g g1

# 使用指定配置
./manage.py start -c config-dev.json

# 停止服务
./manage.py stop

# 停止指定组
./manage.py stop -g g1

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

### 方式2: 直接启动

```bash
# 使用默认配置启动
python3 -m src.bot

# 指定配置文件启动
python3 -m src.bot config.json

# 启动指定组
python3 -m src.bot config.json --group g1
```

## 消息流转流程

```
企业微信用户发送消息
        ↓
[WeChatChannel] 接收回调
        ↓
[WeChatChannel] 处理消息
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

## 核心组件说明

### BaseModule（模块基类）

所有模块的基类，定义标准接口：

**主要方法：**
- `start()`: 启动模块
- `stop()`: 停止模块
- `receive(message)`: 接收消息（由消息总线调用）
- `send_to_bus(message)`: 发送消息到消息总线（根据绑定关系路由）
- `publish_to_bus(topic, message)`: 发布消息到消息总线（广播）
- `create_background_task(coro)`: 创建后台任务

**抽象方法（子类必须实现）：**
- `_on_start()`: 启动时的钩子方法
- `_on_stop()`: 停止时的钩子方法
- `_on_receive(message)`: 接收消息时的钩子方法

### MessageBus（消息总线）

核心组件，负责模块注册、消息路由、绑定关系管理和发布-订阅机制。

**主要方法：**
- `register_module(module)`: 注册模块
- `unregister_module(module_id)`: 注销模块
- `bind(from_module, to_module)`: 绑定两个模块
- `unbind(from_module)`: 解绑模块
- `route(message)`: 路由消息（根据绑定关系）
- `send_to_module(message)`: 发送消息到指定模块
- `publish(topic, message)`: 发布消息到主题（广播）
- `subscribe(topic, callback)`: 订阅主题
- `unsubscribe(topic, callback)`: 取消订阅

### WeChatChannel（企业微信渠道）

企业微信消息渠道，纯粹的企业微信 API 封装。

**主要功能：**
- 接收企业微信回调
- 解析消息内容
- 处理命令（/help, /status, /new, /sessions）
- 发送消息到企业微信
- 与 IFlowModule 集成
- 启动/停止通知

### IFlowModule（iflow 模块）

iflow CLI 的完整管理模块。

**主要功能：**
- 通过 tmux 启动/停止 iflow CLI
- 向 iflow CLI 注入消息
- 监控会话文件，提取 AI 回复
- 消息状态检测（idle/generating）
- 消息分类（reply/other/complete）
- 拒绝机制（生成中拒绝新消息）
- 多轮对话来源归属
- 交互日志记录

**核心子组件：**
- `IFlowController`: tmux 会话控制
- `IFlowMonitor`: 会话文件监控和消息提取
- `SessionManager`: 会话管理
- `MessageStore`: 消息存储
- `InteractionLogger`: 交互日志记录

### CommandHandler（命令处理器）

命令解析和执行模块。

**支持命令：**
- `/help`: 显示帮助信息
- `/status`: 查看服务状态
- `/new`: 创建新会话
- `/sessions`: 查看历史会话

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/test_message_bus.py
pytest tests/test_iflow_module.py

# 显示详细输出
pytest tests/ -v

# 显示覆盖率
pytest tests/ --cov=src
```

### 测试工具

```bash
# IFlow 交互测试工具
python3 tools/iflow_interactive_tool.py

# 支持的命令：
#   /source <wechat|tool> - 切换身份
#   /scope <all|reply> - 切换模式
#   /status - 状态查询
#   /history - 历史记录
#   /spam - 拒绝机制测试

# 企业微信测试工具
python3 tools/wechat_test_tool.py listen
python3 tools/wechat_test_tool.py send "测试消息"
python3 tools/wechat_test_tool.py test
```

## 已实现功能

### 核心功能 ✅
- ✅ IFlow 完整管理（启动/停止/消息注入/输出监控）
- ✅ 企业微信回调接收和消息发送
- ✅ 消息总线路由和绑定
- ✅ 命令处理（/help, /status, /new, /sessions）
- ✅ 多 iflow 实例支持
- ✅ 多企业微信机器人支持
- ✅ 多渠道支持（企业微信、模拟器）
- ✅ 渠道最小化架构
- ✅ 消息状态检测（idle/generating）
- ✅ 消息分类（reply/other/complete）
- ✅ 拒绝机制（生成中拒绝新消息）
- ✅ 多轮对话来源归属
- ✅ 交互日志记录
- ✅ 项目管理脚本（manage.py）
- ✅ 服务生命周期管理（启动/停止/重启/状态/日志）
- ✅ 启动/停止通知机制
- ✅ Message 对象规范化
- ✅ 消息提取优化（倒数第二原则）
- ✅ 状态检测顺序优化
- ✅ 模块管理器统一管理模块生命周期
- ✅ 模块健康监控和自动恢复
- ✅ 通用组件复用（消息转换器、通知管理器）

## 待实现功能

### P1 - 增强功能 🚧
- 🚧 错误处理和重试机制
- 🚧 日志系统优化
- 🚧 消息去重机制测试（需企业微信快速重发）

### P2 - 扩展功能
- 🚧 Web 控制台
- 🚧 配置热更新
- 🚧 监控告警

## 设计文档

### 重构设计文档
- [design-v2/01-模块重构方案.md](design-v2/01-模块重构方案.md) - 详细的模块拆分方案
- [design-v2/02-重构计划.md](design-v2/02-重构计划.md) - 重构计划和进度
- [design-v2/03-微信模块增强方案.md](design-v2/03-微信模块增强方案.md) - 微信模块设计
- [design-v2/04-IFlow模块设计方案.md](design-v2/04-IFlow模块设计方案.md) - IFlow模块设计
- [design-v2/05-消息总线设计方案.md](design-v2/05-消息总线设计方案.md) - 消息总线设计
- [design-v2/06-启动方案设计.md](design-v2/06-启动方案设计.md) - 启动方案和管理脚本设计
- [design-v2/07-消息提取优化方案.md](design-v2/07-消息提取优化方案.md) - 消息提取优化
- [design-v2/08-IFlowModule测试工具方案.md](design-v2/08-IFlowModule测试工具方案.md) - 测试工具方案

### 旧版本文档（参考）
- [src_old/README-old.md](src_old/README-old.md) - 旧版本 README
- [src_old/WECHAT_SETUP.md](src_old/WECHAT_SETUP.md) - 企业微信配置说明

## 开发规范

### 代码风格
- 使用 Python 3.10+ 类型注解
- 遵循 PEP 8 代码规范
- 使用 logging 模块记录日志
- 使用 asyncio 进行异步编程

### 测试
- 使用 pytest 进行单元测试
- 使用 pytest-asyncio 进行异步测试
- 测试文件命名：`test_*.py`

### 提交规范
- 清晰的提交信息
- 包含必要的文档更新
- 通过所有测试

## 重要记忆

- 项目状态：重构完成，基于消息总线的松耦合架构
- 核心技术：Python 3.10+, pydantic, loguru, typer, asyncio, tmux
- 配置文件位置：`config.json`
- 日志位置：`logs/interactions/`
- 环境信息：Linux (WSL2), Python 3.13.11
- Git 仓库：`git@github.com:lingzhia/Ling-iflow-message.git`
- 当前分支：refactor-v2
- 专注于交互模式管理和消息总线架构
- 使用 tmux 管理 iflow CLI 会话
- 通过监控会话文件（session-*.jsonl）捕获 AI 回复
- 支持企业微信消息与 iflow CLI 的双向同步
- 支持命令系统：`/run`, `/new`, `/sessions`, `/status`, `/help`
- 支持连续对话，自动保持上下文
- 提供多个测试工具，支持不同测试场景

## 已知问题和修复历史

### 已修复问题
1. **history 接口 BUG**：服务端 history 函数数据过滤逻辑错误，导致只返回最后一支股票的数据。修复方法是将数据过滤逻辑移到 pivot 转换之后。服务端版本已更新到 v4.4。
2. **get_history_fundamentals 接口测试失败**：
   - 测试5失败：聚宽端执行错误 'IncomeStatementAcc' - 服务端状态不一致问题
   - 测试13、20失败：TypeError: agg function failed - pandas版本差异导致（本地pandas 2.3.3 vs 聚宽pandas 1.x）
3. **IFlowMonitor 消息提取逻辑**：修复了消息提取逻辑，实现完整的倒数第二原则
4. **IFlowMonitor 状态检测顺序**：修复状态检测顺序，确保状态正确更新
5. **IFlowMonitor 标记更新处理**：避免重复发送中间版本

## 常见问题

### Q: 如何启动服务？
A: 推荐使用管理脚本：`./manage.py start -d`

### Q: 如何查看日志？
A: 使用管理脚本：`./manage.py logs -f`

### Q: 如何停止服务？
A: 使用管理脚本：`./manage.py stop`

### Q: 如何运行测试？
A: 使用 pytest：`pytest tests/`

### Q: 如何配置企业微信？
A: 参考 `src_old/WECHAT_SETUP.md` 文档

### Q: 如何添加新的 iflow 实例？
A: 在 `config.json` 的 `tmux_sessions` 中添加新配置，并在 `bots` 中配置对应的机器人

## 下一步工作

1. **P1 增强**：多机器人支持、错误处理、日志优化
2. **可选**：消息去重机制测试（需快速重发消息）
3. **P2 扩展**：Web 控制台、配置热更新、监控告警

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

MIT License