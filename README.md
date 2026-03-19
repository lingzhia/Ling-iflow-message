# Ling-iflow

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信的双向消息同步。

## 目录

- [快速开始](#快速开始)
- [安装和配置](#安装和配置)
- [启动和管理](#启动和管理)
- [使用方法](#使用方法)
- [测试](#测试)
- [功能特性](#功能特性)
- [贡献](#贡献)

## 快速开始

### 5 分钟快速开始

```bash
# 1. 克隆项目
git clone git@github.com:lingzhia/Ling-iflow-message.git
cd Ling-iflow

# 2. 安装依赖
pip install -e ".[dev,wechat]"

# 3. 配置文件
cp config.example.json config.json
# 编辑 config.json，填入企业微信配置

# 4. 启动服务
./manage.py start

# 5. 查看状态
./manage.py status

# 6. 查看日志
./manage.py logs -f
```

### 测试模式（无需企业微信）

如果你想先测试功能而不配置企业微信，可以使用模拟器：

```bash
# 1. 启动模拟器渠道
./manage.py start --channel simulator1

# 2. 使用测试工具
python3 tools/iflow_interactive_tool.py --tmux-session simulator1+iflow

# 3. 在测试工具中输入消息
1+1=?
写一个 Python 脚本
quit

# 4. 停止服务
./manage.py stop
```

### 常用命令速查

```bash
# 启动服务
./manage.py start

# 停止服务
./manage.py stop

# 重启服务
./manage.py restart

# 查看状态
./manage.py status

# 查看日志
./manage.py logs -f

# 渠道管理
./manage.py channel list
./manage.py channel status
./manage.py channel start bot1
./manage.py channel stop bot1
```

## 安装和配置

### 前置要求

在安装之前，请确保系统满足以下要求：

- **Python**: 3.10 或更高版本
- **pip**: Python 包管理器
- **tmux**: 会话管理工具（用于 iflow CLI 会话管理）
- **iflow CLI**: iflow 命令行工具

**检查 Python 版本：**
```bash
python3 --version
# 输出示例：Python 3.10.0 或更高
```

**检查 tmux 是否安装：**
```bash
tmux -V
# 输出示例：tmux 3.0a 或更高
```

**安装 tmux（如果未安装）：**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tmux

# CentOS/RHEL
sudo yum install tmux

# macOS
brew install tmux
```

### 克隆项目

```bash
# 克隆项目到本地
git clone git@github.com:lingzhia/Ling-iflow-message.git

# 进入项目目录
cd Ling-iflow
```

### 安装依赖

#### 基础安装（仅核心功能）

```bash
# 安装基础依赖（仅包含核心功能）
pip install -e .
```

**此安装方式包含：**
- ✅ pydantic (数据验证)
- ✅ pydantic-settings (配置管理)
- ✅ loguru (日志记录)
- ✅ typer (CLI 命令行)

#### 开发环境安装（包含测试工具）

```bash
# 安装开发环境依赖（包含测试工具）
pip install -e ".[dev]"
```

**此安装方式额外包含：**
- ✅ pytest (测试框架)
- ✅ pytest-asyncio (异步测试支持)

#### 企业微信功能安装

```bash
# 安装企业微信依赖（包含企业微信相关依赖）
pip install -e ".[wechat]"
```

**此安装方式额外包含：**
- ✅ httpx (HTTP 客户端)
- ✅ aiohttp (异步 HTTP 客户端)
- ✅ cryptography (加密库，用于消息加解密)

#### 完整安装（推荐）

```bash
# 完整安装（包含开发和微信功能）
pip install -e ".[dev,wechat]"
```

**此安装方式包含所有依赖，适合开发和使用企业微信功能。**

### 验证安装

```bash
# 检查命令是否可用
ling-iflow --help

# 应该看到帮助信息输出，例如：
# Usage: ling-iflow [OPTIONS] COMMAND [ARGS]...
#
#   Ling-iflow CLI - iflow CLI 交互模式管理工具
#
# Options:
#   --help  Show this message and exit.
#
# Commands:
#   start   启动服务
#   stop    停止服务
#   restart 重启服务
#   status  查看服务状态
#   logs    查看日志
#   channel 渠道管理
```

### 配置文件

#### 复制配置文件

```bash
# 复制示例配置文件
cp config.example.json config.json

# 使用你喜欢的编辑器编辑配置
vim config.json  # 或使用其他编辑器
```

#### 配置文件结构

```json
{
  "bots": [
    {
      "name": "bot1",
      "corp_id": "企业ID",
      "agent_id": "应用AgentId",
      "secret": "应用Secret",
      "user_id": "用户账号",
      "token": "回调Token",
      "encoding_aes_key": "EncodingAESKey",
      "callback_host": "0.0.0.0",
      "callback_port": 8788,
      "stream_mode": false,
      "poll_interval": 5,
      "allow_from": [],
      "group_policy": "mention",
      "group_allow_from": [],
      "tmux_session": "wechat_bot1+iflow"
    }
  ],
  "simulator_channels": [
    {
      "name": "simulator1",
      "host": "localhost",
      "port": 19999,
      "tmux_session": "simulator1+iflow"
    }
  ],
  "log_level": "INFO",
  "filter_thinking": true
}
```

#### 配置项说明

**bots 配置（企业微信机器人）：**

| 配置项 | 说明 | 示例 | 必填 |
|--------|------|------|------|
| name | 机器人名称（唯一标识） | "bot1" | ✅ |
| corp_id | 企业 ID | "ww1234567890abcdef" | ✅ |
| agent_id | 应用 AgentId | "1234567890" | ✅ |
| secret | 应用 Secret | "your_secret_here" | ✅ |
| user_id | 用户账号（用于发送消息） | "user@example.com" | ✅ |
| token | 回调配置的 Token | "your_token_here" | ✅ |
| encoding_aes_key | 回调配置的 EncodingAESKey | "your_key_here" | ✅ |
| callback_host | 回调服务监听地址 | "0.0.0.0" | ✅ |
| callback_port | 回调服务端口 | 8788 | ✅ |
| stream_mode | 是否启用 Stream Mode | false | ❌ |
| poll_interval | 轮询间隔（秒） | 5 | ❌ |
| allow_from | 允许的用户 ID 白名单 | [] | ❌ |
| group_policy | 群聊消息响应策略 | "mention" | ❌ |
| group_allow_from | 群聊白名单 | [] | ❌ |
| tmux_session | 关联的 tmux 会话名称 | "wechat_bot1+iflow" | ✅ |

**simulator_channels 配置（模拟器渠道）：**

| 配置项 | 说明 | 示例 | 必填 |
|--------|------|------|------|
| name | 模拟器名称 | "simulator1" | ✅ |
| host | 监听地址 | "localhost" | ✅ |
| port | 监听端口 | 19999 | ✅ |
| tmux_session | 关联的 tmux 会话名称 | "simulator1+iflow" | ✅ |

**全局配置：**

| 配置项 | 说明 | 示例 |
|--------|------|------|
| log_level | 日志级别（INFO, DEBUG, WARNING, ERROR） | "INFO" |
| filter_thinking | 是否过滤思考过程 | true |

## 启动和管理

Ling-iflow 提供三种启动方式，推荐使用**管理脚本**方式。

### 方式1: 使用管理脚本（推荐）

**基本命令：**

```bash
# 启动服务（默认后台启动第一个渠道）
./manage.py start

# 启动所有渠道（后台）
./manage.py start -a

# 前台启动默认渠道
./manage.py start -f

# 前台启动所有渠道
./manage.py start -a -f

# 停止服务（默认停止默认渠道）
./manage.py stop

# 停止所有渠道
./manage.py stop -a

# 重启服务（默认后台重启默认渠道）
./manage.py restart

# 重启所有渠道（后台）
./manage.py restart -a

# 前台重启默认渠道
./manage.py restart -f

# 查看状态
./manage.py status

# 查看日志（最近100行）
./manage.py logs

# 实时跟踪日志
./manage.py logs -f

# 查看最近 N 行日志
./manage.py logs -n 200

# 清理日志和缓存
./manage.py clean
```

**指定渠道操作：**

```bash
# 启动指定渠道
./manage.py start --channel bot1            # 启动企业微信渠道 bot1
./manage.py start --channel simulator1     # 启动模拟器渠道 simulator1

# 停止指定渠道
./manage.py stop --channel bot1             # 停止企业微信渠道 bot1
./manage.py stop --channel simulator1      # 停止模拟器渠道 simulator1

# 重启指定渠道
./manage.py restart --channel bot1          # 重启企业微信渠道 bot1
./manage.py restart --channel simulator1   # 重启模拟器渠道 simulator1
```

**查看可用渠道：**

```bash
# 列出所有可用渠道
./manage.py start --channel ls
```

**渠道管理命令：**

```bash
# 列出所有渠道
./manage.py channel list

# 查看所有渠道状态
./manage.py channel status

# 查看指定渠道状态
./manage.py channel status bot1

# 启动指定渠道
./manage.py channel start bot1

# 停止指定渠道
./manage.py channel stop bot1

# 重启指定渠道
./manage.py channel restart bot1
```

**参数说明：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `-a, --all` | 启动/停止/重启所有渠道 | `./manage.py start -a` |
| `-f, --foreground` | 前台运行（默认后台运行） | `./manage.py start -f` |
| `--channel <渠道名>` | 指定要操作的渠道 | `./manage.py start --channel bot1` |
| `--channel ls` | 列出所有可用渠道 | `./manage.py start --channel ls` |

### 方式2: 使用全局命令（安装后）

**先执行项目安装：**
```bash
pip install -e .
```

**然后可以在任意目录使用：**
```bash
# 启动服务
ling-iflow start

# 停止服务
ling-iflow stop

# 重启服务
ling-iflow restart

# 查看状态
ling-iflow status

# 查看日志
ling-iflow logs -f

# 渠道管理
ling-iflow channel list
ling-iflow channel status
ling-iflow channel start bot1
ling-iflow channel stop bot1
```

### 方式3: 直接启动

```bash
# 使用默认配置启动
python3 -m src.bot

# 指定配置文件启动
python3 -m src.bot config.json

# 指定渠道启动
python3 -m src.bot config.json --channel bot1

# 启动所有渠道
python3 -m src.bot config.json --channel all
```

**推荐使用方式1（管理脚本）**，提供更完整的管理功能和参数支持。

## 使用方法

### 一、企业微信使用

#### 1. 基本对话

**在企业微信中发送消息：**

```
你: 帮我写一个 Python 脚本
bot: ⏳ 正在执行: 帮我写一个 Python 脚本
bot: ✅ [脚本内容]
```

**iflow 会自动：**
- 接收消息
- 通过 tmux 注入到 iflow CLI
- 监控 iflow 的回复
- 提取并返回给用户

#### 2. 连续对话

**保持上下文：**

```
你: 帮我写一个 Python 脚本
bot: ✅ [脚本内容]

你: 再帮我添加一个函数
bot: ⏳ 正在执行: 再帮我添加一个函数
bot: ✅ [更新后的脚本]

你: 继续完善这个脚本
bot: ⏳ 正在执行: 继续完善这个脚本
bot: ✅ [完善后的脚本]
```

**iflow 会自动：**
- 保持会话上下文
- 支持连续对话
- 记住之前的对话内容

#### 3. 命令使用

**支持的命令：**

```bash
# 查看帮助
/help

# 查看服务状态
/status

# 创建新会话（清除上下文）
/new

# 查看历史会话
/sessions

# 查看消息历史
/history

# 查看性能指标
/metrics

# 列出可用命令
/lscmd

# 切换消息范围
/scope all        # 显示所有消息（包括思考过程）
/scope reply      # 只显示回复消息（默认）
```

**命令示例：**

```
你: /status
bot: ✅ 服务状态：
    - tmux 会话: iflow
    - iflow 运行中: 是
    - 当前会话: session-abc123.jsonl
    - 消息统计: 已发送 5 条，已接收 5 条

你: /new
bot: ✅ 已开始新会话

你: /sessions
bot: ✅ 历史会话：
    1. session-abc123.jsonl (2026-03-18 10:00:00)
    2. session-def456.jsonl (2026-03-18 11:30:00)
```

#### 4. 群聊使用

**在群聊中使用：**

```
# @机器人发送消息
@bot1 帮我分析这个代码

# 机器人会回复
bot1: ⏳ 正在执行: 帮我分析这个代码
bot1: ✅ [分析结果]
```

**群聊配置：**
- `group_policy`: 群聊消息响应策略
  - `"mention"`: 只响应 @机器人 的消息（推荐）
  - `"all"`: 响应所有消息
- `group_allow_from`: 群聊白名单

### 二、模拟器使用（测试）

#### 1. 启动模拟器

```bash
# 启动模拟器渠道
./manage.py start --channel simulator1
```

#### 2. 使用测试客户端

```bash
# 运行测试客户端
python3 tools/test_client.py

# 连接到模拟器服务器
connect

# 发送消息
send "测试消息"

# 断开连接
disconnect

# 退出
quit
```

#### 3. 使用交互式测试工具

```bash
# 运行交互式测试工具
python3 tools/iflow_interactive_tool.py

# 支持的命令：
#   /source <wechat|tool> - 切换身份
#   /scope <all|reply> - 切换模式
#   /status - 状态查询
#   /history - 历史记录
#   /spam - 拒绝机制测试
#   quit - 退出
```

**测试工具示例：**

```
============================================================
IFlowModule 交互式体验工具
============================================================
💬 你: 1+1=?
📤 iflow 回复: 2
✅ 收到 1 条消息

💬 你: /scope all
✅ 已切换模式: all

💬 你: 写一个 Python 脚本
📤 iflow 回复: [脚本内容]
📤 iflow 回复: ✻ 思考中...
📤 iflow 回复: [更多内容]
✅ 收到 3 条消息
```

### 三、查看日志

#### 1. 使用管理脚本

```bash
# 查看最近 100 行日志
./manage.py logs

# 查看最近 N 行日志
./manage.py logs -n 200

# 实时跟踪日志
./manage.py logs -f
```

#### 2. 直接查看日志文件

```bash
# 查看主日志
tail -f logs/bot.log

# 查看交互日志
tail -f logs/interactions/*.jsonl
```

#### 3. 日志内容示例

```
2026-03-18 10:00:00 [INFO] [src.bot] 启动服务...
2026-03-18 10:00:01 [INFO] [src.modules.iflow.module] [iflow_bot1] 启动 iflow 模块
2026-03-18 10:00:02 [INFO] [src.modules.iflow.controller] 创建 tmux 会话: wechat_bot1+iflow
2026-03-18 10:00:05 [INFO] [src.modules.iflow.module] [iflow_bot1] iflow 已就绪
2026-03-18 10:00:10 [INFO] [src.modules.channel.wechat] 收到消息: 帮我写一个 Python 脚本
2026-03-18 10:00:11 [INFO] [src.core.bus] 路由消息: wechat_bot1 -> iflow_bot1
2026-03-18 10:00:12 [INFO] [src.modules.iflow.controller] 注入消息到 iflow: 帮我写一个 Python 脚本
2026-03-18 10:00:20 [INFO] [src.modules.iflow.monitor] 提取消息: ✦ [脚本内容]
2026-03-18 10:00:21 [INFO] [src.modules.iflow.module] [iflow_bot1] 发送回复到 wechat_bot1
2026-03-18 10:00:22 [INFO] [src.modules.channel.wechat] 发送消息到企业微信
```

### 四、故障排查

#### 1. 服务无法启动

**检查依赖：**
```bash
# 检查 Python 版本
python3 --version

# 检查 tmux 是否安装
tmux -V

# 检查 iflow 是否可用
iflow --version
```

**检查配置：**
```bash
# 验证配置文件格式
python3 -c "import json; json.load(open('config.json'))"

# 检查配置文件语法
cat config.json | python3 -m json.tool
```

**查看日志：**
```bash
# 查看详细日志
./manage.py logs -f
```

#### 2. 消息无法发送

**检查 tmux 会话：**
```bash
# 查看 tmux 会话列表
tmux ls

# 查看 iflow 会话
tmux attach -t wechat_bot1+iflow
```

**检查 iflow 状态：**
```bash
# 查看服务状态
./manage.py status

# 查看模块状态
./manage.py channel status
```

**检查网络连接（企业微信）：**
```bash
# 测试企业微信 API 连通性
curl -X POST https://qyapi.weixin.qq.com/cgi-bin/gettoken
```

#### 3. 消息重复发送

**检查缓存设置：**
```bash
# 查看日志中的缓存清理信息
./manage.py logs | grep "清理缓存"
```

**切换 scope 模式：**
```bash
# 只显示回复消息（默认）
/scope reply

# 显示所有消息（包括思考过程）
/scope all
```

#### 4. iflow 生成中被拒绝

**检查 iflow 状态：**
```bash
# 查看 iflow 是否在生成中
./manage.py status

# 查看 tmux 中的 iflow 输出
tmux capture-pane -t wechat_bot1+iflow -p
```

**等待 iflow 完成：**
```bash
# 等待 iflow 完成当前任务后再发送新消息
# 或者使用 /new 命令创建新会话
/new
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
- ✅ 延迟记录原则和字符串定位机制
- ✅ 缓存管理（修复历史消息重复问题）

**多实例支持：**
- ✅ 多 iflow 实例支持
- ✅ 多企业微信机器人支持
- ✅ 多渠道支持（企业微信、模拟器）
- ✅ 多 tmux 会话管理
- ✅ 渠道最小化架构
- ✅ 模块化设计
- ✅ 渠道架构简化（移除 enabled 字段）

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
- ✅ 渠道控制命令（channel list/status/start/stop/restart）
- ✅ 项目安装支持（pip install -e .）
- ✅ 全局命令支持（ling-iflow）
- ✅ Unix Socket 控制接口
- ✅ 日志和缓存清理

### 最新修复（2026-03-19）✅

- ✅ 修复 /scope 命令历史消息重复问题
- ✅ 实现缓存清理机制（最大 100 条，保留 50 条）
- ✅ 更新缓存管理策略文档

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