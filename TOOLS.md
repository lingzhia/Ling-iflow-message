# Ling-iflow 工具使用文档

本文档介绍 Ling-iflow 项目中所有工具和管理脚本的使用方法。

## 目录

- [管理脚本 (manage.py)](#管理脚本-managepy)
- [测试工具](#测试工具)
  - [iflow 交互式测试工具 (iflow_interactive.py)](#iflow-交互式测试工具-iflow_interactivepy)
  - [企业微信调试工具 (wechat_debug.py)](#企业微信调试工具-wechat_debugpy)
  - [企业微信模拟器 (wechat_simulator.py)](#企业微信模拟器-wechat_simulatorpy)
  - [消息分发器测试工具 (test_dispatcher.py)](#消息分发器测试工具-test_dispatcherpy)
  - [对话提取工具 (conversation_extractor.py)](#对话提取工具-conversation_extractorpy)

---

## 管理脚本 (manage.py)

`manage.py` 是 Ling-iflow 项目的统一管理脚本，提供启动、停止、重启等服务管理功能。

### 功能特性

- 启动/停止 iflow CLI 和企业微信 Bot
- 多机器人管理
- 查看服务状态
- 查看日志
- 清理临时文件

### 基本命令

#### 1. 启动服务

```bash
# 启动默认服务（序号1）
python manage.py start

# 启动指定序号的服务
python manage.py start 2

# 仅启动 iflow
python manage.py start --no-wechat

# 仅启动企业微信
python manage.py start --no-iflow

# 前台模式（直接显示 iflow 界面）
python manage.py start --foreground

# 临时指定模型
python manage.py start --model gpt-4

# 临时指定工作目录
python manage.py start --workspace ~/.iflow2

# 启用详细日志
python manage.py start --verbose
```

#### 2. 停止服务

```bash
# 停止默认服务（序号1）
python manage.py stop

# 停止指定序号的服务
python manage.py stop 2

# 仅停止 iflow
python manage.py stop --no-wechat

# 仅停止企业微信
python manage.py stop --no-iflow
```

#### 3. 重启服务

```bash
# 重启默认服务（序号1）
python manage.py restart

# 重启指定序号的服务
python manage.py restart 2

# 重启并切换模型
python manage.py restart --model gpt-4

# 重启并切换工作目录
python manage.py restart --workspace ~/.iflow2
```

#### 4. 批量操作

```bash
# 启动所有服务
python manage.py start-all

# 停止所有服务
python manage.py stop-all

# 重启所有服务
python manage.py restart-all
```

#### 5. 查看状态

```bash
# 查看服务详细状态
python manage.py status

# 列出所有配置的资源和序号
python manage.py list-resources
```

#### 6. 查看日志

```bash
# 查看 iflow 日志
python manage.py logs --iflow

# 查看企业微信 Bot 日志
python manage.py logs --wechat

# 实时跟踪 iflow 日志
python manage.py logs --iflow --follow

# 实时跟踪企业微信日志
python manage.py logs --wechat --follow
```

#### 7. 清理临时文件

```bash
# 清理 __pycache__ 和日志文件
python manage.py clean
```

#### 8. 其他命令

```bash
# 运行所有测试
python manage.py test

# 启动 tmux 管理器
python manage.py tmux
```

### 序号系统

每个序号对应一个机器人和一个 tmux 会话：

| 序号 | 机器人名称 | tmux 会话 | 回调端口 |
|------|-----------|----------|---------|
| 1    | bot1      | iflow    | 8787    |
| 2    | bot2      | iflow2   | 8788    |

使用 `list-resources` 命令查看所有可用的序号和配置。

---

## 测试工具

### iflow 交互式测试工具 (iflow_interactive.py)

直接与 iflow CLI 交互的测试工具，用于测试 iflow 的回复和处理逻辑。

#### 功能特性

- 直接向 iflow 发送消息
- 实时接收 iflow 回复
- 支持命令模式（`/run`, `/new`, `/sessions`, `/status`, `/help`）
- 支持连续对话
- 记录对话历史

#### 使用方法

```bash
# 启动交互式测试工具
python tool/iflow_interactive.py

# 指定 tmux 会话
python tool/iflow_interactive.py --session iflow2

# 指定工作目录
python tool/iflow_interactive.py --workspace ~/.iflow2

# 提取全部消息（包括非✦标记的消息）
python tool/iflow_interactive.py --extract-all
```

#### 交互命令

在交互模式中，你可以：

1. **发送普通消息**：直接输入消息内容
2. **发送命令**：
   - `/run <命令>` - 执行 iflow 命令
   - `/new` - 开始新会话
   - `/sessions` - 查看历史会话
   - `/status` - 查看服务状态
   - `/help` - 显示帮助
3. **退出**：输入 `exit` 或 `quit`

#### 示例

```bash
$ python tool/iflow_interactive.py

[选择 tmux 会话]
可用会话:
  1. iflow
  2. iflow2

选择会话序号 [1]: 1

[iflow 交互测试]
输入消息或命令（输入 exit 退出）:

> 你好
[iflow 回复 #1 (23:45:12)]
你好！有什么我可以帮助你的吗？

> /run 帮我写一个Python脚本
[iflow 回复 #2 (23:45:35)]
好的，这是一个简单的Python脚本...

> exit
[退出]
```

---

### 企业微信调试工具 (wechat_debug.py)

用于调试和测试企业微信消息接收和发送的工具。

#### 功能特性

- 列出所有配置的机器人
- 测试机器人配置
- 监听企业微信消息
- 通过指定机器人发送消息
- 查看机器人与 tmux 会话的绑定关系
- 检查端口监听状态

#### 使用方法

```bash
# 列出所有机器人
python tool/wechat_debug.py list

# 测试机器人配置
python tool/wechat_debug.py test bot1

# 监听机器人消息
python tool/wechat_debug.py listen bot1

# 通过机器人发送消息
python tool/wechat_debug.py send bot1 "测试消息"

# 查看帮助
python tool/wechat_debug.py --help
```

#### 命令详解

##### 1. list - 列出所有机器人

```bash
python tool/wechat_debug.py list
```

输出示例：
```
======================================================================
已配置的机器人 (2 个)
======================================================================

1. bot1
   状态: ✓ 运行中
   回调端口: 8787
   用户ID: YuLingZhi
   tmux会话: iflow
   回调URL: http://be.mmszxc.xin:8787/wechat/callback
   端口状态: ✓ 监听中 (PID: 12345)

2. bot2
   状态: ✗ 未运行
   回调端口: 8788
   用户ID: YuLingZhi
   tmux会话: iflow2
   回调URL: http://be.mmszxc.xin:8788/wechat/callback
   端口状态: ✗ 未监听
```

##### 2. test - 测试机器人配置

```bash
python tool/wechat_debug.py test bot1
```

输出示例：
```
======================================================================
测试机器人配置: bot1
======================================================================

✓ 配置文件存在
✓ 机器人已启用
✓ 企业ID配置正确
✓ 应用ID配置正确
✓ Secret配置正确
✓ 回调端口: 8787
✓ 用户ID: YuLingZhi
✓ tmux会话: iflow
✓ 回调Token配置正确
✓ 回调EncodingAESKey配置正确

✓ 配置检查通过
```

##### 3. listen - 监听机器人消息

```bash
python tool/wechat_debug.py listen bot1
```

功能：
- 实时监听企业微信消息
- 显示消息内容
- 显示发送者和接收者信息
- 按 Ctrl+C 退出

##### 4. send - 发送消息

```bash
python tool/wechat_debug.py send bot1 "测试消息"
```

功能：
- 通过指定机器人发送消息到企业微信
- 显示发送结果
- 支持多行消息

---

### 企业微信模拟器 (wechat_simulator.py)

使用 WechatBot 的测试模式，模拟企业微信消息交互。不启动 HTTP 服务器，直接调用消息处理逻辑。

#### 功能特性

- 发送消息到 iflow
- 交互模式（持续对话）
- 监听模式（只监听 iflow 回复）
- 批量发送（发送多条消息）
- 命令模式（发送命令）
- 记录消息历史

#### 使用方法

```bash
# 发送单条消息
python tool/wechat_simulator.py send bot1 "测试消息"

# 交互模式
python tool/wechat_simulator.py interactive bot1

# 监听模式（只监听 iflow 回复）
python tool/wechat_simulator.py listen bot1

# 批量发送
python tool/wechat_simulator.py send-sequence bot1 "第一条\n第二条\n第三条"

# 命令模式
python tool/wechat_simulator.py send bot1 "/run 帮我写一个Python脚本"

# 查看帮助
python tool/wechat_simulator.py --help
```

#### 命令详解

##### 1. send - 发送消息

```bash
python tool/wechat_simulator.py send bot1 "测试消息"
```

输出示例：
```
✓ 消息已发送
✓ 等待回复...

[iflow 回复]
你好！有什么我可以帮助你的吗？
```

##### 2. interactive - 交互模式

```bash
python tool/wechat_simulator.py interactive bot1
```

功能：
- 持续对话模式
- 自动保存对话历史
- 支持所有命令（`/run`, `/new`, `/sessions`, `/status`, `/help`）
- 输入 `exit` 退出

示例：
```bash
$ python tool/wechat_simulator.py interactive bot1

[企业微信模拟器 - bot1]
输入消息或命令（输入 exit 退出）:

> 你好
✓ 消息已发送

[iflow 回复]
你好！有什么我可以帮助你的吗？

> 帮我写一个Python脚本
✓ 消息已发送

[iflow 回复]
好的，这是一个简单的Python脚本...

> exit
✓ 退出模拟器
```

##### 3. listen - 监听模式

```bash
python tool/wechat_simulator.py listen bot1
```

功能：
- 只监听 iflow 回复
- 不发送消息
- 适合测试后台监控功能
- 按 Ctrl+C 退出

##### 4. send-sequence - 批量发送

```bash
python tool/wechat_simulator.py send-sequence bot1 "第一条\n第二条\n第三条"
```

功能：
- 一次性发送多条消息
- 每条消息之间自动等待
- 收集所有回复

---

### 消息分发器测试工具 (test_dispatcher.py)

用于测试消息分发器（MessageDispatcher）功能的工具。

#### 功能特性

- 测试基本订阅和广播功能
- 测试取消订阅功能
- 测试多订阅者并发处理
- 测试消息过滤功能

#### 使用方法

```bash
# 运行所有测试
python tool/test_dispatcher.py
```

#### 测试内容

##### 测试1: 基本订阅和广播

```
======================================================================
测试1: 基本订阅和广播
======================================================================

[步骤1] 注册订阅者...
当前订阅者: ['subscriber1', 'subscriber2']
订阅者数量: 2

[步骤2] 广播第一条消息...
🔵 [订阅者1] 收到消息: 这是第一条测试消息
   元数据: {'source': 'test', 'type': 'broadcast'}
🟢 [订阅者2] 收到消息: 这是第一条测试消息
   元数据: {'source': 'test', 'type': 'broadcast'}
发送成功: 2 个订阅者
```

##### 测试2: 取消订阅

```
======================================================================
测试2: 取消订阅
======================================================================

[步骤1] 注册3个订阅者...
当前订阅者: ['subscriber1', 'subscriber2', 'subscriber3']

[步骤2] 广播消息...
🔵 [订阅者1] 收到消息: 取消订阅测试
🟢 [订阅者2] 收到消息: 取消订阅测试
🟡 [订阅者3] 收到消息: 取消订阅测试

[步骤3] 取消订阅者2...
✓ 已取消订阅: subscriber2
当前订阅者: ['subscriber1', 'subscriber3']

[步骤4] 再次广播消息...
🔵 [订阅者1] 收到消息: 再次广播
🟡 [订阅者3] 收到消息: 再次广播
发送成功: 2 个订阅者
```

##### 测试3: 多订阅者并发处理

```
======================================================================
测试3: 多订阅者并发处理
======================================================================

[步骤1] 注册多个订阅者...
当前订阅者: ['subscriber1', 'subscriber2', 'subscriber3']

[步骤2] 广播多条消息...
🔵 [订阅者1] 收到消息: 消息1
🟢 [订阅者2] 收到消息: 消息1
🟡 [订阅者3] 收到消息: 消息1
🔵 [订阅者1] 收到消息: 消息2
🟢 [订阅者2] 收到消息: 消息2
🟡 [订阅者3] 收到消息: 消息2
...
```

---

### 对话提取工具 (conversation_extractor.py)

从日志文件中提取完整的对话链路，用于分析和调试消息流转过程。

#### 功能特性

- 提取企业微信消息
- 提取发送到 iflow 的消息
- 提取 iflow 的回复
- 提取发送回企业微信的消息
- 按时间顺序组织成完整的对话链路
- 导出为 JSON 格式

#### 使用方法

```bash
# 提取对话（默认提取最近的对话）
python tool/conversation_extractor.py logs/wechat_bot_2026-03-10.log

# 指定提取的对话数量
python tool/conversation_extractor.py logs/wechat_bot_2026-03-10.log --count 10

# 导出为 JSON
python tool/conversation_extractor.py logs/wechat_bot_2026-03-10.log --output conversations.json

# 只显示摘要
python tool/conversation_extractor.py logs/wechat_bot_2026-03-10.log --summary

# 查看帮助
python tool/conversation_extractor.py --help
```

#### 输出示例

##### 控制台输出

```
正在解析日志文件: logs/wechat_bot_2026-03-10.log
找到 5 个完整对话

======================================================================
对话 ID: conversation_1
时间: 2026-03-10 23:08:32
======================================================================

【1. 收到企业微信消息】
  sender: YuLingZhi
  content: 你好
  type: text

【2. 发送到 iflow】
  command: 你好
  tmux_session: iflow2
  source: wechat

【3. iflow 回复】
  content: 你好！有什么我可以帮助你的吗？
  marker: ✦
  timestamp: 2026-03-10 23:08:33

【4. 发送回企业微信】
  receiver: YuLingZhi
  type: 私聊
  success: True

======================================================================

...
```

##### JSON 输出

```json
{
  "conversations": [
    {
      "conversation_id": "conversation_1",
      "timestamp": "2026-03-10 23:08:32",
      "receive_wechat": {
        "sender": "YuLingZhi",
        "content": "你好",
        "type": "text"
      },
      "send_iflow": {
        "command": "你好",
        "tmux_session": "iflow2",
        "source": "wechat"
      },
      "receive_iflow": {
        "content": "你好！有什么我可以帮助你的吗？",
        "marker": "✦",
        "timestamp": "2026-03-10 23:08:33"
      },
      "send_wechat": {
        "receiver": "YuLingZhi",
        "type": "私聊",
        "success": true
      }
    }
  ]
}
```

#### 对话链路

完整的对话链路包括以下4个步骤：

1. **收到企业微信消息** - 用户通过企业微信发送消息
2. **发送到 iflow** - 机器人将消息转发给 iflow CLI
3. **iflow 回复** - iflow CLI 处理并生成回复
4. **发送回企业微信** - 机器人将 iflow 的回复发送回企业微信

---

## 工具对比

| 工具 | 用途 | 是否启动 HTTP 服务器 | 适用场景 |
|------|------|-------------------|---------|
| iflow_interactive.py | 直接与 iflow 交互 | 否 | 测试 iflow 功能 |
| wechat_debug.py | 调试企业微信消息 | 是 | 调试企业微信配置 |
| wechat_simulator.py | 模拟企业微信消息 | 否 | 测试消息流转 |
| test_dispatcher.py | 测试消息分发器 | 否 | 测试消息分发功能 |
| conversation_extractor.py | 提取对话链路 | 否 | 分析日志 |

---

## 常见问题

### 1. 如何选择合适的测试工具？

- **测试 iflow 功能**：使用 `iflow_interactive.py`
- **调试企业微信配置**：使用 `wechat_debug.py`
- **测试消息流转**：使用 `wechat_simulator.py`
- **分析日志**：使用 `conversation_extractor.py`

### 2. 如何启动多个机器人？

```bash
# 启动所有机器人
python manage.py start-all

# 或单独启动
python manage.py start 1
python manage.py start 2
```

### 3. 如何查看某个机器人的日志？

```bash
# 查看所有机器人日志
python manage.py logs --wechat

# 或直接查看日志文件
tail -f logs/wechat_bot_bot1_2026-03-10.log
```

### 4. 如何清理临时文件？

```bash
# 清理 __pycache__ 和日志文件
python manage.py clean
```

---

## 总结

Ling-iflow 提供了丰富的工具集，帮助开发者：

1. **管理服务**：使用 `manage.py` 启动、停止、重启服务
2. **测试功能**：使用各种测试工具验证功能
3. **调试问题**：使用调试工具定位问题
4. **分析日志**：使用对话提取工具分析消息流转

根据不同的需求选择合适的工具，可以大大提高开发和调试效率。