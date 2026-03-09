# Ling-iflow 项目设计方案

## 项目概述

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信的双向消息同步。项目从 iflow-bot 迁移而来，专注于提供轻量级的交互模式管理功能。

### 核心目标

1. 通过 tmux 管理 iflow CLI 会话
2. 实时监控 iflow 的会话文件，捕获 AI 回复
3. 支持企业微信消息与 iflow CLI 的双向同步
4. 提供简化的企业微信渠道，便于测试
5. 支持会话管理和连续对话

## 整体架构

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户层                                    │
│  ┌──────────────┐                  ┌──────────────┐             │
│  │  企业微信     │                  │   CLI 命令   │             │
│  │  (应用/群)   │                  │   (ling-iflow) │           │
│  └──────┬───────┘                  └──────┬───────┘             │
└─────────┼──────────────────────────────────┼────────────────────┘
          │                                  │
          │                                  │
┌─────────┼──────────────────────────────────┼────────────────────┐
│         │        Channels 层                │                    │
│  ┌──────▼──────┐                  ┌────────▼────────┐          │
│  │WechatWork   │                  │ BaseChannel     │          │
│  │Channel      │                  │ (抽象基类)       │          │
│  └──────┬──────┘                  └─────────────────┘          │
└─────────┼──────────────────────────────────────────────────────┘
          │
┌─────────┼──────────────────────────────────────────────────────┐
│         │        Interactive 层（核心层）                        │
│  ┌──────▼─────────────────────────────────────────────────┐     │
│  │               SyncManager                              │     │
│  │  (同步管理器 - 协调双向同步)                             │     │
│  └──────┬─────────────────────────────────────────────────┘     │
│         │                                                       │
│  ┌──────┴──────┐    ┌──────────────┐    ┌────────────────┐     │
│  │WechatWork   │    │SessionMonitor│    │IFlowController │     │
│  │Channel      │◄──►│(会话监控器)  │◄──►│(iflow控制器)   │     │
│  └─────────────┘    └──────────────┘    └────────────────┘     │
│         │                                                       │
│  ┌──────┴──────────┐    ┌──────────────────┐                   │
│  │BotIntegration    │    │SessionManager    │                   │
│  │(机器人集成)      │    │(会话管理器)      │                   │
│  └─────────────────┘    └──────────────────┘                   │
└──────────────────────────────────────────────────────────────┘
          │
┌─────────┼──────────────────────────────────────────────────────┐
│         │        系统层                                          │
│  ┌──────▼──────┐    ┌──────────────┐    ┌────────────────┐     │
│  │  tmux       │    │ iflow CLI    │    │ session 文件   │     │
│  │  会话管理    │    │ (AI 助手)    │    │ (session-*.jsonl) │ │
│  └─────────────┘    └──────────────┘    └────────────────┘     │
└──────────────────────────────────────────────────────────────┘
          │
┌─────────┼──────────────────────────────────────────────────────┐
│         │        Config 层                                      │
│  ┌──────▼──────┐    ┌──────────────┐    ┌────────────────┐     │
│  │Schema       │    │Loader        │    │ 配置文件        │     │
│  │(配置模型)   │◄──►│(配置加载)    │◄──►│ config.json    │     │
│  └─────────────┘    └──────────────┘    └────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### 消息流向

#### 企业微信 → iflow CLI

```
企业微信消息
  → WechatWorkChannel._process_xml_message()
  → WechatWorkChannel._handle_message()
  → SyncManager.receive_wechat_message()
  → 放入 _wechat_queue
  → SyncManager._wechat_loop() 取出消息
  → SyncManager._send_to_iflow()
  → IFlowController.send_message()
  → tmux send-keys 注入消息
  → iflow CLI 接收并处理
  → AI 生成回复
```

#### iflow CLI → 企业微信

```
iflow CLI 生成回复
  → 写入 session-*.jsonl 文件
  → SessionMonitor.read_new_assistant_messages()
  → 检测到新消息
  → SyncManager._monitor_loop() 处理
  → SyncManager.send_to_wechat()
  → WechatWorkChannel.send()
  → 企业微信 API 发送
  → 用户收到回复
```

### 完整消息流转流程

从手机微信发送消息到返回消息的完整流程图：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              第一阶段：消息接收                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│  用户手机    │ 1. 用户在企业微信中发送消息（私聊或群聊）
│  企业微信    │
└──────┬───────┘
       │ HTTPS 回调
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    企业微信服务器                                            │
│  - 接收用户消息                                                              │
│  - 根据配置的回调 URL 推送消息到我们的服务器                                   │
│  - URL: http://<server>:8788/wechat/callback                                │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │ HTTPS POST (加密的 XML)
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           WechatWorkChannel._handle_callback_message()                       │
│  (channels/wechat_work.py)                                                   │
│                                                                             │
│  2. 立即返回 "success" 响应，避免企业微信重试                                │
│  3. 创建后台任务异步处理消息                                                 │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │ 异步任务
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│       WechatWorkChannel._process_callback_async()                           │
│  (channels/wechat_work.py)                                                   │
│                                                                             │
│  4. 解析请求体和查询参数                                                     │
│  5. 调用 handle_callback() 处理回调                                         │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           WechatWorkChannel.handle_callback()                                │
│  (channels/wechat_work.py)                                                   │
│                                                                             │
│  6. 验证签名（msg_signature）                                                │
│  7. 解密消息（使用 AES-256-CBC）                                             │
│  8. 解析 XML，提取消息内容                                                   │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           WechatWorkChannel._process_xml_message()                          │
│  (channels/wechat_work.py)                                                   │
│                                                                             │
│  9. 提取消息信息：                                                          │
│     - MsgType: 消息类型（text/image/voice/video等）                          │
│     - FromUserName: 发送者 ID                                               │
│     - ChatId: 群聊 ID（如果是群聊）                                          │
│     - Content: 消息内容                                                      │
│     - MsgId: 消息唯一 ID                                                    │
│                                                                             │
│  10. 消息去重检查（基于 MsgId，缓存 1 小时）                                 │
│                                                                             │
│  11. 群聊权限检查：                                                          │
│      - 检查是否 @ 机器人（group_policy=mention）                             │
│      - 检查群聊是否在白名单中（group_allow_from）                             │
│                                                                             │
│  12. 用户权限检查：                                                          │
│      - 检查用户 ID 是否在白名单中（allow_from）                              │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           WechatWorkChannel._handle_message()                               │
│  (channels/wechat_work.py)                                                   │
│                                                                             │
│  13. 立即发送确认消息到企业微信：                                            │
│      "✅ 收到消息\n\n正在处理中...\n\n消息内容: <内容>"                        │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           SyncManager.receive_wechat_message()                              │
│  (interactive/sync_manager.py)                                               │
│                                                                             │
│  14. 将消息放入企业微信消息队列（_wechat_queue: asyncio.Queue）              │
│      队列项格式：                                                            │
│      {                                                                       │
│        "content": "消息内容",                                                │
│        "sender_id": "发送者ID",                                              │
│        "chat_id": "聊天ID",                                                  │
│        "metadata": {...}                                                     │
│      }                                                                       │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              第二阶段：消息处理                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│           SyncManager._wechat_loop()                                        │
│  (interactive/sync_manager.py)                                               │
│                                                                             │
│  15. 异步循环，从队列中取出消息：                                            │
│      msg = await self._wechat_queue.get()                                   │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           SyncManager._send_to_iflow()                                      │
│  (interactive/sync_manager.py)                                               │
│                                                                             │
│  16. 发送同步确认消息：                                                      │
│      "✅ 已同步到 iflow CLI\n\n消息内容: <内容>"                              │
│                                                                             │
│  17. 调用 IFlowController.send_message() 发送到 iflow                        │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           IFlowController.send_message()                                    │
│  (interactive/iflow_controller.py)                                          │
│                                                                             │
│  18. 检查 tmux 会话是否存在                                                  │
│                                                                             │
│  19. 使用 tmux send-keys 命令注入消息：                                      │
│      a. tmux send-keys -t iflow "C-c"  (清除当前输入)                        │
│      b. tmux send-keys -t iflow -l "<消息内容>"  (逐字发送)                   │
│      c. tmux send-keys -t iflow "C-m"  (发送回车)                            │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              第三阶段：AI 处理                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    iflow CLI (运行在 tmux 会话中)                            │
│                                                                             │
│  20. iflow CLI 接收用户输入                                                  │
│                                                                             │
│  21. 解析用户意图，调用对应的工具函数                                        │
│                                                                             │
│  22. 执行相应的操作（如搜索、分析、代码生成等）                               │
│                                                                             │
│  23. 生成 AI 回复内容                                                        │
│                                                                             │
│  24. 将回复写入会话文件：~/.iflow/projects/<project>/session-<id>.jsonl      │
│      格式：                                                                  │
│      {                                                                       │
│        "type": "assistant",                                                  │
│        "message": {                                                          │
│          "id": "msg-id",                                                     │
│          "content": [                                                        │
│            {"type": "text", "text": "回复内容"}                              │
│          ]                                                                   │
│        },                                                                    │
│        "timestamp": "2026-03-08T12:00:00Z",                                  │
│        "sessionId": "session-id"                                             │
│      }                                                                       │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │ 文件写入
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              第四阶段：回复同步                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│           SessionMonitor.read_new_assistant_messages()                       │
│  (interactive/session_monitor.py)                                           │
│                                                                             │
│  25. 定期检查（每 0.2 秒）：should_check()                                   │
│                                                                             │
│  26. 查找所有会话文件：find_session_files()                                 │
│                                                                             │
│  27. 读取文件的新增内容（从上次读取位置继续）                                │
│                                                                             │
│  28. 解析 JSON，提取 assistant 类型的消息                                    │
│                                                                             │
│  29. 消息去重（基于 message.id）                                             │
│                                                                             │
│  30. 返回新增消息列表                                                       │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           SyncManager._monitor_loop()                                       │
│  (interactive/sync_manager.py)                                               │
│                                                                             │
│  31. 异步循环，定期检查新消息：                                              │
│      if self.monitor.should_check():                                        │
│          new_messages = self.monitor.read_new_assistant_messages()          │
│                                                                             │
│  32. 遍历新消息，调用 send_to_wechat() 发送                                  │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           SyncManager.send_to_wechat()                                      │
│  (interactive/sync_manager.py)                                               │
│                                                                             │
│  33. 检查企业微信渠道是否可用                                                │
│                                                                             │
│  34. 调用 WechatWorkChannel.send() 发送消息                                  │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│           WechatWorkChannel.send()                                          │
│  (channels/wechat_work.py)                                                   │
│                                                                             │
│  35. 获取 access_token（如果过期则刷新）                                     │
│                                                                             │
│  36. 构建消息体：                                                            │
│      {                                                                       │
│        "touser": "<用户ID>" 或 "",                                           │
│        "chatid": "<群ID>" 或 "",                                             │
│        "msgtype": "text",                                                    │
│        "agentid": <AgentId>,                                                 │
│        "text": {                                                             │
│          "content": "<回复内容>"                                             │
│        }                                                                     │
│      }                                                                       │
│                                                                             │
│  37. 调用企业微信 API 发送消息：                                             │
│      POST https://qyapi.weixin.qq.com/cgi-bin/message/send                  │
│      ?access_token=<token>                                                   │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │ HTTPS POST
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    企业微信服务器                                            │
│  - 接收发送消息请求                                                          │
│  - 验证 access_token                                                        │
│  - 推送消息到用户手机                                                        │
└──────┬──────────────────────────────────────────────────────────────────────┘
       │ 推送消息
       ▼
┌──────────────┐
│  用户手机    │ 38. 用户在企业微信中收到 AI 回复
│  企业微信    │
└──────────────┘
```

#### 关键时间节点

| 阶段 | 时间估算 | 说明 |
|------|---------|------|
| 消息接收 | < 100ms | 从企业微信服务器到我们服务器 |
| 消息解析 | < 50ms | 解密、验证、解析 XML |
| 消息确认 | < 200ms | 发送确认消息到企业微信 |
| 消息注入 | < 100ms | 通过 tmux send-keys 注入到 iflow |
| AI 处理 | 2-10s | iflow CLI 处理并生成回复（取决于任务复杂度） |
| 回复同步 | < 200ms | 检测到新消息并发送 |
| **总时长** | **3-12s** | 从发送到收到回复 |

#### 并行处理机制

```
┌─────────────────────────────────────────────────────────────┐
│                     SyncManager                             │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │  _monitor_loop   │    │  _wechat_loop    │              │
│  │  (监控会话文件)   │    │  (处理微信消息)   │              │
│  │                  │    │                  │              │
│  │  每 0.2 秒检查    │    │  异步等待队列     │              │
│  │  新增 AI 回复     │    │  新消息到达       │              │
│  └────────┬─────────┘    └────────┬─────────┘              │
│           │                       │                          │
│           ▼                       ▼                          │
│    发送到企业微信           发送到 iflow                      │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       │                                      │
│                       ▼                                      │
│              共享统计信息 (stats)                             │
└─────────────────────────────────────────────────────────────┘
```

#### 错误处理机制

| 错误类型 | 处理方式 |
|---------|---------|
| 签名验证失败 | 记录日志，跳过处理 |
| 消息解密失败 | 记录日志，返回 success |
| iflow 未运行 | 发送错误提示到企业微信 |
| 消息发送失败 | 记录错误，增加错误计数 |
| 网络超时 | 自动重试，超时返回错误 |

## 核心模块设计

### 1. Channels 层

#### 1.1 BaseChannel（基类）

**职责**：定义渠道的抽象接口

**主要功能**：
- 定义 send() 方法
- 定义消息处理回调
- 生命周期管理（start/stop）

**关键方法**：
```python
- async start(): 启动渠道
- async stop(): 停止渠道
- async send(content, chat_id, **kwargs): 发送消息
- set_message_handler(handler): 设置消息处理器
```

#### 1.2 WechatWorkChannel（企业微信渠道）

**职责**：实现企业微信应用机器人和群机器人的消息收发

**主要功能**：
- 应用机器人：通过企业微信 API 接收消息（回调模式）
- 群机器人：通过 Webhook 发送消息
- 消息加解密（AES-256-CBC）
- 消息去重（基于 MsgId）
- 权限控制（白名单）
- 内嵌 HTTP 回调服务

**关键组件**：

1. **WechatWorkCrypto**：加解密工具
   - AES-256-CBC 加解密
   - PKCS7 填充
   - SHA1 签名生成

2. **WechatWorkWebhookBot**：群机器人
   - 文本消息发送
   - Markdown 消息发送
   - 图片消息发送
   - 图文消息发送

**配置项**：
```python
- corp_id: 企业 ID
- agent_id: 应用 AgentId
- secret: 应用 Secret
- token: 回调 Token
- encoding_aes_key: 回调 EncodingAESKey
- callback_port: 回调服务端口（默认 8788）
- callback_host: 回调服务监听地址（默认 0.0.0.0）
- stream_mode: 是否启用 Stream Mode（长轮询）
- poll_interval: 轮询间隔（秒）
- allow_from: 用户 ID 白名单
- group_policy: 群聊消息响应策略（mention/all/none）
- group_allow_from: 群聊白名单
```

**工作流程**：
1. 启动时获取 access_token
2. 启动内嵌 HTTP 回调服务
3. 接收企业微信回调请求
4. 验证签名并解密消息
5. 解析消息内容（文本、图片、语音等）
6. 检查权限和白名单
7. 调用消息处理器
8. 发送回复消息

### 2. Interactive 层（核心层）

#### 2.1 SyncManager（同步管理器）

**职责**：协调各个组件，实现 iflow CLI 和企业微信的双向同步

**主要功能**：
- 启动/停止同步服务
- 企业微信消息队列管理
- iflow 回复监控
- 统计信息收集

**关键属性**：
```python
- monitor: SessionMonitor 实例
- controller: IFlowController 实例
- wechat_channel: WechatWorkChannel 实例
- _wechat_queue: 企业微信消息队列
- running: 运行状态
- stats: 统计信息
```

**关键方法**：
```python
- async start(auto_start_iflow): 启动同步服务
- async stop(): 停止同步服务
- async _monitor_loop(): 监控 iflow 输出循环
- async _wechat_loop(): 企业微信消息处理循环
- async send_to_wechat(content): 发送消息到企业微信
- async receive_wechat_message(...): 接收企业微信消息
```

**工作流程**：
1. 检查并启动 iflow CLI
2. 初始化企业微信渠道
3. 启动两个异步循环：
   - `_monitor_loop()`: 监控 session 文件，捕获 AI 回复
   - `_wechat_loop()`: 处理企业微信消息队列

#### 2.2 IFlowController（iflow 控制器）

**职责**：通过 tmux send-keys 命令向 iflow CLI 会话注入消息

**主要功能**：
- 检查 tmux 会话是否存在
- 检查 iflow CLI 是否运行
- 发送消息到 iflow CLI
- 启动/停止 iflow CLI

**关键方法**：
```python
- check_tmux_session(): 检查 tmux 会话是否存在
- check_iflow_running(): 检查 iflow CLI 是否运行
- send_message(message): 发送消息到 iflow CLI
- start_iflow(model): 在 tmux 会话中启动 iflow CLI
- stop_iflow(): 停止 iflow CLI
- get_session_info(): 获取会话信息
```

**技术实现**：
- 使用 `tmux send-keys` 命令注入消息
- 使用 `tmux capture-pane` 命令捕获输出
- 使用 `tmux list-panes` 命令检查进程

#### 2.3 SessionMonitor（会话监控器）

**职责**：监控 iflow CLI 的会话文件，实时读取 AI 回复

**主要功能**：
- 查找所有会话文件
- 读取新增的 AI 回复消息
- 消息去重
- 自动检测新会话

**关键属性**：
```python
- workspace: iflow 工作目录
- session_files: 会话文件字典（文件 -> 读取位置）
- processed_ids: 已处理的消息 ID 集合
- check_interval: 检查间隔（默认 0.2 秒）
```

**关键方法**：
```python
- find_session_files(): 查找所有会话文件
- read_new_assistant_messages(): 读取新增的 AI 回复消息
- should_check(): 检查是否应该执行监控检查
- reset(): 重置监控器状态
```

**消息格式**（session-*.jsonl）：
```json
{
  "type": "assistant",
  "message": {
    "id": "msg-id",
    "content": [
      {"type": "text", "text": "回复内容"}
    ]
  },
  "timestamp": "2026-03-08T12:00:00Z",
  "sessionId": "session-id"
}
```

#### 2.4 SessionManager（会话管理器）

**职责**：管理 iflow 的会话文件，提供会话查询、创建等功能

**主要功能**：
- 获取最新的会话文件
- 获取所有会话列表
- 创建新会话
- 删除指定会话
- 获取当前会话信息

**关键方法**：
```python
- get_latest_session(): 获取最新的会话文件
- get_all_sessions(limit): 获取所有会话列表
- create_new_session(): 创建新会话
- delete_session(session_id): 删除指定会话
- get_current_session_info(): 获取当前会话信息
- get_status_message(): 获取状态信息的 Markdown 文本
- get_sessions_message(limit): 获取会话列表信息的 Markdown 文本
```

#### 2.5 BotIntegration（机器人集成）

**职责**：连接企业微信渠道和 iflow CLI，实现消息双向流转

**主要功能**：
- 接收企业微信消息
- 解析命令（/run, /new, /sessions, /help, /status）
- 调用 iflow CLI
- 发送回复到企业微信
- 支持连续对话（自动恢复上次会话）

**关键方法**：
```python
- async handle_message(...): 处理入站消息
- _parse_command(content): 解析用户消息，提取命令
- async _handle_command(...): 处理命令
- async _run_command(...): 运行 iFlow 命令
- _extract_reply_from_tmux(): 从 tmux 输出中提取回复
- _filter_thinking_messages(message): 过滤思考消息
- _split_message(message, max_length): 分段消息
```

**命令格式**：
- 直接发送消息：执行 iFlow 命令（自动恢复上次会话）
- `/run <命令>`：执行 iFlow 命令
- `/new`：开始新会话（清除上下文）
- `/sessions`：查看历史会话
- `/status`：查看服务状态
- `/help`：显示帮助

### 3. Config 层

#### 3.1 Schema（配置模型）

**职责**：定义配置的数据模型和验证规则

**主要模型**：

1. **WechatWorkConfig**：企业微信配置
```python
- enabled: 是否启用
- corp_id: 企业 ID
- agent_id: 应用 AgentId
- secret: 应用 Secret
- token: 回调 Token
- encoding_aes_key: 回调 EncodingAESKey
- callback_port: 回调服务端口
- callback_host: 回调服务监听地址
- stream_mode: 是否启用 Stream Mode
- poll_interval: 轮询间隔
- allow_from: 用户 ID 白名单
- group_policy: 群聊消息响应策略
- group_allow_from: 群聊白名单
```

2. **InteractiveConfig**：交互模式配置
```python
- workspace: iflow 工作目录
- model: iflow 模型名称
- tmux_session: tmux 会话名称
- wechat_work: 企业微信配置
- log_level: 日志级别
- log_file: 日志文件路径
- filter_thinking: 是否过滤思考消息
```

**配置加载优先级**：
1. 命令行参数（最高优先级）
2. 环境变量（前缀：LING_IFLOW__）
3. 配置文件（~/.ling-iflow/config.json）
4. 默认值（最低优先级）

#### 3.2 Loader（配置加载器）

**职责**：加载和管理配置文件

**主要功能**：
- 获取配置文件路径
- 加载配置文件
- 创建默认配置
- 合并配置（命令行参数、环境变量、配置文件）

**关键方法**：
```python
- get_config_path(): 获取配置文件路径
- load_config(): 加载配置
- _create_default_config(path): 创建默认配置
```

### 4. CLI 层

#### 4.1 Commands（CLI 命令）

**职责**：提供命令行接口

**主要命令**：

1. **start**：启动交互模式服务
```bash
ling-iflow start [--workspace] [--model] [--tmux-session] [--no-auto-start] [--wechat]
```

2. **stop**：停止 iflow CLI
```bash
ling-iflow stop [--tmux-session]
```

3. **status**：查看状态
```bash
ling-iflow status [--tmux-session] [--workspace]
```

4. **test**：运行测试程序
```bash
ling-iflow test [--simple]
```

5. **init**：初始化配置
```bash
ling-iflow init [--config]
```

## 关键技术点

### 1. Tmux 集成

**技术方案**：
- 使用 `tmux new-session -d -s <session> "command"` 创建后台会话
- 使用 `tmux send-keys -t <session> -l <message>` 发送消息
- 使用 `tmux capture-pane -t <session> -p` 捕获输出
- 使用 `tmux list-panes -t <session> -F "#{pane_pid}"` 获取进程信息

**优势**：
- 无需修改 iflow CLI 源码
- 支持远程控制
- 可复用现有 tmux 会话

### 2. 异步架构

**技术方案**：
- 使用 asyncio 实现异步消息处理
- 使用 asyncio.Queue 实现消息队列
- 使用 asyncio.create_task 启动后台任务
- 使用 asyncio.gather 并发执行任务

**优势**：
- 高并发处理能力
- 非阻塞 I/O
- 资源利用率高

### 3. 消息去重

**技术方案**：
- 使用 MsgId 作为消息唯一标识
- 使用字典缓存已处理的消息 ID
- 定期清理过期的缓存（TTL：1 小时）

**优势**：
- 避免重复处理
- 内存占用可控
- 处理企业微信重试机制

### 4. 消息过滤

**技术方案**：
- 过滤思考消息（以 * 开头的行）
- 过滤用户输入（以 > 开头的行）
- 可配置是否启用过滤

**优势**：
- 减少噪音
- 提升用户体验

### 5. 消息分段

**技术方案**：
- 按行分割消息
- 控制每段最大长度（默认 4096 字符）
- 在段之间添加延迟（0.3 秒）

**优势**：
- 避免超过消息长度限制
- 避免触发企业微信限流

## 数据模型

### 1. 会话文件格式（session-*.jsonl）

每行一个 JSON 对象：

```json
{
  "type": "user|assistant|system",
  "message": {
    "id": "msg-id",
    "content": [
      {
        "type": "text",
        "text": "消息内容"
      }
    ]
  },
  "timestamp": "2026-03-08T12:00:00Z",
  "sessionId": "session-id",
  "uuid": "msg-uuid"
}
```

### 2. 配置文件格式（config.json）

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
  "log_file": "",
  "filter_thinking": true
}
```

## 部署架构

### 单机部署

```
┌─────────────────────────────────────────────────────────┐
│                        服务器                             │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Ling-iflow 服务                      │  │
│  │  ┌──────────────┐  ┌──────────────┐              │  │
│  │  │  CLI 命令    │  │  回调服务    │              │  │
│  │  │  (typer)     │  │  (aiohttp)   │              │  │
│  │  └──────┬───────┘  └──────┬───────┘              │  │
│  │         │                  │                       │  │
│  │  ┌──────▼──────────────────▼───────┐              │  │
│  │  │       SyncManager                │              │  │
│  │  └──────┬──────────────────┬───────┘              │  │
│  │         │                  │                       │  │
│  │  ┌──────▼──────┐  ┌───────▼───────┐              │  │
│  │  │  tmux       │  │  session 文件  │              │  │
│  │  │  会话        │  │  监控          │              │  │
│  │  └─────────────┘  └───────────────┘              │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │              iflow CLI (tmux)                    │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         │ HTTPS/Webhook
         ▼
┌─────────────────────────────────────────────────────────┐
│                  企业微信服务器                           │
└─────────────────────────────────────────────────────────┘
```

### 网络要求

1. **内网部署**：
   - 服务器需要能访问企业微信 API（qyapi.weixin.qq.com）
   - 需要开放回调端口（默认 8788）

2. **公网部署**：
   - 需要配置域名和 SSL 证书
   - 企业微信回调 URL 需要使用 HTTPS

## 安全设计

### 1. 消息加密

**技术方案**：
- 使用 AES-256-CBC 加密消息
- 使用 PKCS7 填充
- 使用 SHA1 验证签名

**实现**：
```python
class WechatWorkCrypto:
    - decrypt(encrypted_msg): 解密消息
    - encrypt(msg): 加密消息
    - generate_signature(token, timestamp, nonce, encrypted_msg): 生成签名
```

### 2. 权限控制

**技术方案**：
- 用户 ID 白名单（allow_from）
- 群聊白名单（group_allow_from）
- 群聊 @ 机器人策略（group_policy）

**配置**：
```json
{
  "allow_from": ["user-id-1", "user-id-2"],
  "group_policy": "mention",
  "group_allow_from": ["group-id-1"]
}
```

### 3. 输入验证

**技术方案**：
- 使用 Pydantic 进行配置验证
- 检查必填字段
- 验证字段类型和格式

## 性能优化

### 1. 异步 I/O

**技术方案**：
- 使用 httpx.AsyncClient 进行 HTTP 请求
- 使用 aiohttp 提供 HTTP 服务
- 使用 asyncio.Queue 进行消息队列

### 2. 消息批处理

**技术方案**：
- 会话监控器定时检查（0.2 秒间隔）
- 一次性读取所有新增消息
- 减少文件 I/O 次数

### 3. 缓存策略

**技术方案**：
- Access Token 缓存（提前 60 秒刷新）
- 消息 ID 缓存（TTL：1 小时）
- 会话文件位置缓存

## 监控和日志

### 1. 日志系统

**技术方案**：
- 使用 loguru 作为日志库
- 支持多级别日志（DEBUG, INFO, WARNING, ERROR）
- 支持日志文件输出

**配置**：
```json
{
  "log_level": "INFO",
  "log_file": "/path/to/log/file"
}
```

### 2. 统计信息

**技术方案**：
- 实时统计发送/接收消息数量
- 统计错误数量
- 获取服务运行状态

**统计字段**：
```python
{
  "messages_sent_to_iflow": int,
  "messages_synced_to_wechat": int,
  "errors": int,
  "wechat_enabled": bool,
  "running": bool
}
```

## 测试策略

### 1. 单元测试

**测试范围**：
- 配置加载和验证
- 会话管理器功能
- iflow 控制器功能
- 消息解析和过滤

### 2. 集成测试

**测试范围**：
- 企业微信渠道功能
- 同步管理器功能
- 完整消息流转

### 3. 模拟测试

**测试范围**：
- 使用简化的企业微信渠道
- 模拟消息发送和接收
- 测试命令解析和处理

## 扩展性设计

### 1. 渠道扩展

**设计思路**：
- 定义 BaseChannel 抽象基类
- 统一消息处理接口
- 支持动态加载渠道

**扩展示例**：
```python
class TelegramChannel(BaseChannel):
    name = "telegram"
    
    async def send(self, content, chat_id, **kwargs):
        # 实现发送逻辑
        pass
```

### 2. 命令扩展

**设计思路**：
- 支持自定义命令前缀
- 支持命令注册机制
- 支持命令别名

**扩展示例**：
```python
# 注册自定义命令
bot_integration.register_command("/custom", custom_handler)
```

### 3. 消息处理器扩展

**设计思路**：
- 支持多个消息处理器
- 支持处理器优先级
- 支持处理器链

**扩展示例**：
```python
async def handler1(content, sender_id, chat_id, is_group, metadata):
    # 处理逻辑
    pass

async def handler2(content, sender_id, chat_id, is_group, metadata):
    # 处理逻辑
    pass

# 添加多个处理器
wechat_channel.add_message_handler(handler1, priority=1)
wechat_channel.add_message_handler(handler2, priority=2)
```

## 故障处理

### 1. iflow CLI 异常

**处理方案**：
- 定期检查 iflow 是否运行
- 自动重启 iflow
- 记录错误日志
- 通知用户

### 2. 网络异常

**处理方案**：
- HTTP 请求超时重试
- 网络断开自动重连
- 消息队列缓存
- 错误信息反馈

### 3. 消息发送失败

**处理方案**：
- 记录失败消息
- 支持手动重发
- 提供失败原因
- 通知用户

## 未来改进

### 1. 功能增强

- 支持更多渠道（Telegram、Discord、Slack 等）
- 添加消息历史记录功能
- 支持多会话管理
- 增强 Web 控制台
- 支持文件传输
- 支持语音消息

### 2. 性能优化

- 使用数据库存储会话
- 实现消息索引
- 优化文件监控（使用 inotify）
- 实现连接池管理

### 3. 用户体验

- 添加消息编辑功能
- 支持消息撤回
- 添加快捷回复
- 支持表情回复
- 添加消息搜索功能

### 4. 运维支持

- 添加健康检查接口
- 实现指标导出（Prometheus）
- 添加分布式追踪
- 实现配置热更新

## 总结

Ling-iflow 是一个设计精良的 iflow CLI 交互模式管理工具，具有以下特点：

1. **模块化设计**：清晰的分层架构，各模块职责明确
2. **异步架构**：基于 asyncio 的高性能异步处理
3. **灵活配置**：支持多种配置方式，易于定制
4. **安全可靠**：消息加密、权限控制、输入验证
5. **易于扩展**：支持渠道扩展、命令扩展、处理器扩展
6. **完善的测试**：单元测试、集成测试、模拟测试
7. **详细的日志**：多级别日志、统计信息、错误追踪

通过合理的设计和实现，Ling-iflow 实现了企业微信与 iflow CLI 的双向同步，为用户提供了便捷的 AI 助手交互体验。