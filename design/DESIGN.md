# Ling-iflow 项目设计方案

## 项目概述

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信的双向消息同步。专注于提供轻量级的交互模式管理功能。

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
- 解析命令（/run, /new, /sessions, /help, /status, /lscmd, /start-iflow, /stop-iflow, /restart-iflow）
- 调用 iflow CLI
- 发送回复到企业微信
- 支持连续对话（自动恢复上次会话）
- 管理 iflow 服务（启动、停止、重启）

**关键方法**：
```python
- async handle_message(...): 处理入站消息
- _parse_command(content): 解析用户消息，提取命令
- async _handle_command(...): 处理命令
- async _run_command(...): 运行 iFlow 命令
- async _start_iflow(...): 启动 iflow CLI
- async _stop_iflow(...): 停止 iflow CLI
- async _restart_iflow(...): 重启 iflow CLI
- async _list_commands(...): 列出所有可用命令
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
- `/lscmd`：列出所有可用命令
- `/start-iflow`：启动 iflow CLI
- `/stop-iflow`：停止 iflow CLI
- `/restart-iflow`：重启 iflow CLI
- `/help`：显示帮助

**详细说明：** 参见 [2.5.7 企业微信命令系统](#257-企业微信命令系统)

#### 2.5.1 消息提取方案（基于标记的改进版）

**设计目标**：
- 准确提取 iflow 的完整回复
- 避免消息截断和遗漏
- 支持长消息和多行消息
- 提供可靠的去重机制

**核心原理**：
以标记（✦ 和 ✻）作为消息边界，通过标记行的完整内容作为唯一标识（修复了前10字符重复的问题）。

**实现步骤**：

**1. 捕获 tmux 输出**
```bash
tmux capture-pane -t iflow -S -1000 -p
```
- `-S -1000`：从底部开始捕获最后1000行
- `-p`：输出到标准输出

**2. 定位当前对话**
扫描捕获的内容，查找用户提问（以 `>` 开头的行），保留提问之后的内容，过滤掉历史对话。

**3. 提取标记消息**
在当前对话范围内，扫描所有标记行：
- ✦ 标记：实际回复消息
- ✻ 标记：思考、工具调用等（根据配置过滤）

**4. 消息唯一标识**
从每个标记行提取完整内容作为唯一标识（修复版本）：
```python
def extract_marker_id(line):
    # 清理标记符号和空白
    clean = line.replace('✦', '').replace('✻', '').strip()
    # 使用完整内容作为唯一标识
    return clean if clean else ''
```

**5. 消息绑定**
两条标记之间的内容是前一条消息的扩展内容，应该与前面的消息绑定在一起：
```
✦ 第一条消息
  扩展内容1
  扩展内容2
✦ 第二条消息
```
结果：
- 消息1：✦ 第一条消息\n  扩展内容1\n  扩展内容2
- 消息2：✦ 第二条消息

**6. 发送逻辑**

**场景1：没有发送记录**
- 生成完成后，发送所有消息（包括最后一条）

**场景2：有发送记录**
- 从 tmux 消息中定位到已发送的消息标识
- 发送其后所有未发送的消息（包括最后一条）

**7. 完整示例**

**iflow 输出**：
```
> 用户提问

✻ 思考中...
  思考内容

✦ 第一条回复
  扩展内容1

✦ 第二条回复
  扩展内容2
```

**提取结果**：
```python
messages = [
    {
        'marker_id': '第一条回复',
        'content': '✦ 第一条回复\n  扩展内容1',
        'full_marker': '✦ 第一条回复'
    },
    {
        'marker_id': '第二条回复',
        'content': '✦ 第二条回复\n  扩展内容2',
        'full_marker': '✦ 第二条回复'
    }
]
```

**优势对比**：

| 维度 | 旧方案 | 新方案 |
|------|--------|--------|
| 捕获范围 | 不确定 | 固定1000行 |
| 对话定位 | 无 | 扫描用户提问 |
| 唯一标识 | 前10字符 | 完整内容 |
| 消息扩展 | 不明确 | 明确绑定 |
| 发送逻辑 | 复杂 | 清晰 |
| 可靠性 | 一般 | 高 |

#### 2.5.2 消息来源差异化处理

**设计目标**：
实现三种消息来源的差异化处理，支持工具调用、企业微信交互和 iflow 交互界面的不同需求。

**技术方案**：

**1. 参数设计**
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

**2. 来源跟踪**
在 `BotIntegration` 类中添加实例变量：

```python
self._current_source: str = ""  # 当前正在处理的请求来源
self._pending_messages: list = []  # 待处理的未知来源消息
```

**3. 消息发送逻辑**

根据来源决定发送方式：

| 来源 | 发送方式 | 说明 |
|------|---------|------|
| `tool` | 只返回给工具，不发企业微信 | 用于工具调用场景 |
| `wechat` | 逐条发送到企业微信 | 支持连续对话 |
| `""` | 合并发送到企业微信 | 检测 iflow 交互界面消息 |

**4. 未知来源消息检测**
在监控循环中，检测不在 `_sent_marker_ids` 中的消息，判断为 iflow 交互界面的消息。

**5. 消息合并方法**
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

**处理流程图**：

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

**使用示例**：

```python
# 工具调用
await self.bot.handle_message("test_user", False, "run", command, source="tool")

# 企业微信调用（使用默认值）
await self.bot.handle_message("test_user", False, "run", command, source="wechat")
```

**关键改动点**：

| 文件 | 改动内容 |
|------|---------|
| `interactive/bot_integration.py` | 1. 添加 `source` 参数<br>2. 添加 `_current_source` 和 `_pending_messages` 变量<br>3. 修改消息发送逻辑，根据来源决定发送方式<br>4. 添加未知来源消息检测<br>5. 添加 `_merge_messages` 方法 |
| `tool/iflow_interactive.py` | 修改调用方式，传入 `source="tool"` |

**注意事项**：
1. **来源清理**：每次 `_run_command` 完成后，需要清理 `_current_source`
2. **避免重复发送**：确保 `_sent_marker_ids` 正确更新
3. **消息合并**：只合并 ✦ 标记的消息，过滤 ✻ 标记的消息
4. **企业微信配置**：需要确保 `wechat_channel.user_id` 有值，用于发送 iflow 交互界面的消息
5. **向后兼容**：`source` 参数有默认值 "wechat"，不影响现有调用

#### 2.5.3 消息清理机制

**设计目标**：
去除 iflow 输出中的 UI 元素，只保留有用的消息内容，提升用户体验。

**技术方案**：

**1. 检测分隔符**
查找以下分隔符：
```
---
══
────────
────────────────
════════════════
══════════════════════════
══════════════════════════════════════
══════════════════════════════════════════════════
══════════════════════════════════════════════════════════════
══════════════════════════════════════════════════════════════════════════
```

**2. 清理逻辑**
- 找到第一个分隔符的位置
- 只保留分隔符之前的内容
- 去除首尾空白字符

**3. 实现代码**
```python
def _clean_message_content(self, content: str) -> str:
    """清理消息内容，去除 iflow 的 UI 元素。"""
    if not content:
        return content

    # 类型检查
    if not isinstance(content, str):
        logger.error(f"收到非字符串类型: {type(content)}")
        return ''

    # 查找分隔符
    separators = [
        '---', '══', '────────', '────────────────',
        '════════════════', '══════════════════════════',
        '══════════════════════════════════════',
        '══════════════════════════════════════════════════',
        '══════════════════════════════════════════════════════════════',
        '══════════════════════════════════════════════════════════════════════════',
    ]

    # 找到第一个分隔符的位置
    first_separator_pos = -1
    for sep in separators:
        pos = content.find(sep)
        if pos != -1 and (first_separator_pos == -1 or pos < first_separator_pos):
            first_separator_pos = pos

    # 如果找到分隔符，只保留之前的内容
    if first_separator_pos != -1:
        cleaned_content = content[:first_separator_pos].strip()
        logger.debug(f"清理消息：移除 {len(content) - len(cleaned_content)} 个字符")
        return cleaned_content

    return content.strip()
```

**4. 应用场景**
- 发送消息前清理内容
- 合并消息时清理内容
- 过滤空消息

**优势**：
- 提升用户体验，去除冗余信息
- 减少消息长度，避免超限
- 保持消息内容简洁清晰

#### 2.5.4 测试模式切换

**设计目标**：
支持测试模式，可以提取全部消息（包括非✦标记的消息），便于调试和测试。

**技术方案**：

**1. 参数设计**
在 `BotIntegration.__init__` 方法中添加 `extract_all_messages` 参数：

```python
def __init__(
    self,
    wechat_channel: Any,
    tmux_session: str = "iflow",
    workspace: str = "~/.iflow",
    filter_thinking: bool = True,
    extract_all_messages: bool = False  # 新增参数
):
```

**2. 消息提取逻辑**
根据 `extract_all_messages` 参数决定提取哪些消息：

```python
# 在 _extract_reply_from_tmux 方法中
if self.extract_all_messages:
    # 提取全部消息（包括非✦标记的消息）
    filtered_messages = current_messages
else:
    # 只提取 ✦ 标记的消息
    filtered_messages = [
        msg for msg in current_messages
        if '✦' in msg.get('full_marker', '')
    ]
```

**3. 使用场景**
- **正常模式（extract_all_messages=False）**：只提取 ✦ 标记的消息，过滤思考和工具调用
- **测试模式（extract_all_messages=True）**：提取全部消息，包括思考和工具调用，便于调试

**4. 配置方式**
```python
# 正常模式
bot = BotIntegration(
    wechat_channel=channel,
    extract_all_messages=False
)

# 测试模式
bot = BotIntegration(
    wechat_channel=channel,
    extract_all_messages=True
)
```

**优势**：
- 灵活的消息提取策略
- 便于调试和测试
- 不影响正常使用

#### 2.5.5 iflow 交互式测试工具

**设计目标**：
提供一个交互式测试工具，可以直接在命令行中测试 iflow 功能，无需企业微信环境。

**技术方案**：

**1. 模拟企业微信渠道**
创建 `MockWeChatChannel` 类，模拟企业微信渠道：

```python
class MockWeChatChannel:
    """模拟企业微信渠道，用于测试。"""
    
    def __init__(self):
        self.message_count = 0
    
    async def send(self, content, chat_id, is_group=False, **kwargs):
        """模拟发送消息（打印到控制台）"""
        self.message_count += 1
        time_str = datetime.now().strftime("%H:%M:%S")
        
        print()
        print(f"[iflow 回复] #{self.message_count} ({time_str})")
        print(f"{content}")
        print()
        
        return True
    
    def set_message_handler(self, handler):
        """设置消息处理器（测试模式不需要）"""
        pass
```

**2. 测试器类**
创建 `IFlowTester` 类，封装测试逻辑：

```python
class IFlowTester:
    """iflow 测试器（使用 BotIntegration）。"""
    
    def __init__(self, tmux_session="iflow", workspace="~/.iflow", extract_all_messages=False):
        """初始化测试器。"""
        self.tmux_session = tmux_session
        self.workspace = workspace
        self.extract_all_messages = extract_all_messages
        
        # 创建模拟渠道
        self.mock_channel = MockWeChatChannel()
        
        # 创建 BotIntegration（与企业微信使用相同的逻辑）
        self.bot = BotIntegration(
            wechat_channel=self.mock_channel,
            tmux_session=tmux_session,
            workspace=workspace,
            filter_thinking=True,
            extract_all_messages=extract_all_messages
        )
        
        # 测试模式：tool（工具模式）/ iflow（模拟 iflow 交互界面）
        self.mode = "tool"
```

**3. 交互式命令**
支持以下内置命令：
- `quit/exit/q`：退出程序
- `clear`：清屏
- `status`：查看状态
- `mode`：切换测试模式（tool/iflow）
- `help`：显示帮助

**4. 命令行功能**
- ↑↓ 方向键：浏览历史记录
- ←→ 方向键：移动光标
- Backspace：删除字符
- Home/End：跳到行首/行尾
- Tab：命令自动补全

**5. 使用方式**
```bash
# 启动测试工具
python tool/iflow_interactive.py

# 在测试工具中输入命令
> 帮我写一个 Python 脚本

# 查看状态
> status

# 切换模式
> mode

# 退出
> quit
```

**优势**：
- 无需企业微信环境
- 与实际使用相同的逻辑
- 支持命令行编辑和历史记录
- 便于调试和测试

#### 2.5.6 后台监控功能

**设计目标**：
检测用户在 tmux iflow 交互界面中直接输入的消息，并将这些消息合并后自动发送到企业微信。

**技术方案**：

**1. 监控逻辑**
在后台持续运行，定期检查 iflow 的输出：

```python
async def start_background_monitor(self) -> None:
    """启动后台监控，检测 iflow 交互界面的消息。"""
    logger.info("[BotIntegration] 启动后台监控")
    
    last_known_messages = set()
    
    while True:
        try:
            # 等待一段时间再检查（避免频繁检查）
            await asyncio.sleep(5)
            
            # 提取当前所有消息
            current_messages, is_generating, generation_time, user_question = self._extract_reply_from_tmux()
            
            # 获取当前所有消息的 marker_id
            current_marker_ids = set()
            for msg in current_messages:
                marker_id = msg.get('marker_id', '')
                if marker_id:
                    current_marker_ids.add(marker_id)
            
            # 检测新的消息（不在 last_known_messages 中）
            new_messages = []
            for msg in current_messages:
                marker_id = msg.get('marker_id', '')
                if marker_id and marker_id not in last_known_messages:
                    new_messages.append(msg)
            
            # 如果有新消息且不在处理中
            if new_messages and not is_generating and self._current_source == "":
                logger.info(f"[BotIntegration] 后台监控检测到新消息: {len(new_messages)} 条")
                
                # 合并所有 ✦ 标记的消息
                merged_content = self._merge_messages(new_messages)
                
                if merged_content.strip():
                    # 构造开头标记
                    header = f"🔔 iflow交互模式请求：原消息=[{user_question}]，当前回复完成，回复结果如下：\n\n"
                    # 合并开头标记和内容
                    full_message = header + merged_content
                    
                    # 发送到企业微信
                    await self.wechat_channel.send(full_message, self.wechat_channel.config.user_id, is_group=False)
                    logger.info(f"[BotIntegration] 已发送 iflow 交互界面消息到企业微信")
                
                # 更新已知消息
                last_known_messages.update(current_marker_ids)
            else:
                # 定期更新已知消息（避免内存泄漏）
                if len(last_known_messages) > 1000:
                    last_known_messages = current_marker_ids
                else:
                    last_known_messages = current_marker_ids
            
        except Exception as e:
            logger.error(f"[BotIntegration] 后台监控错误: {e}", exc_info=True)
            await asyncio.sleep(10)  # 出错后等待一段时间再继续
```

**2. 检测条件**
同时满足以下条件才会发送消息：
1. 有新消息（不在 last_known_messages 中）
2. 不在生成中（is_generating=False）
3. 没有当前请求来源（self._current_source=""）

**3. 消息格式**
发送的消息包含开头标记：
```
🔔 iflow交互模式请求：原消息=[用户问题]，当前回复完成，回复结果如下：

[合并后的回复内容]
```

**4. 内存管理**
定期清理 last_known_messages，避免内存泄漏：
- 当已知消息数量超过 1000 时，使用当前消息替换
- 否则，合并当前消息

**5. 错误处理**
- 捕获所有异常，避免监控循环中断
- 出错后等待 10 秒再继续
- 记录详细错误日志

**6. 使用场景**
- 用户在 tmux iflow 中直接输入问题
- AI 回复后自动发送到企业微信
- 无需手动触发，实现双向同步

**优势**：
- 自动检测和同步
- 无需手动干预
- 支持完整的消息追踪
- 包含原始问题信息

#### 2.5.7 企业微信命令系统

**设计目标**：
提供完整的企业微信命令系统，让用户可以直接通过企业微信管理 iflow 和查看状态。

**技术方案**：

**1. 命令列表**
系统支持以下命令：

| 命令 | 功能 | 说明 |
|------|------|------|
| 直接发送消息 | 执行 iFlow 命令 | 自动恢复上次会话 |
| `/run <命令>` | 执行 iFlow 命令 | 显式执行命令 |
| `/new` | 开始新会话 | 清除上下文 |
| `/sessions` | 查看历史会话 | 显示会话列表 |
| `/status` | 查看服务状态 | 显示 tmux 和 iflow 状态 |
| `/lscmd` | 列出所有命令 | 显示完整命令列表 |
| `/start-iflow` | 启动 iflow CLI | 启动 iflow 服务 |
| `/stop-iflow` | 停止 iflow CLI | 停止 iflow 服务 |
| `/restart-iflow` | 重启 iflow CLI | 重启 iflow 服务 |
| `/help` | 显示帮助信息 | 显示详细帮助 |

**2. 命令解析**
```python
def _parse_command(self, content: str) -> Dict:
    """解析用户消息，提取命令。"""
    trimmed = content.strip()
    
    # 支持的命令格式
    if trimmed.startswith("/run "):
        return {"valid": True, "type": "run", "command": trimmed[5:].strip()}
    if trimmed == "/new":
        return {"valid": True, "type": "new"}
    if trimmed == "/sessions":
        return {"valid": True, "type": "sessions"}
    if trimmed == "/status":
        return {"valid": True, "type": "status"}
    if trimmed == "/lscmd":
        return {"valid": True, "type": "lscmd"}
    if trimmed == "/start-iflow":
        return {"valid": True, "type": "start-iflow"}
    if trimmed == "/stop-iflow":
        return {"valid": True, "type": "stop-iflow"}
    if trimmed == "/restart-iflow":
        return {"valid": True, "type": "restart-iflow"}
    if trimmed == "/help":
        return {"valid": True, "type": "help"}
    
    # 直接发送命令（不带前缀）
    if trimmed and not trimmed.startswith("/"):
        return {"valid": True, "type": "run", "command": trimmed}
    
    return {"valid": False, "type": "unknown"}
```

**3. iflow 管理命令实现**

**启动 iflow** - `/start-iflow`
```python
async def _start_iflow(self, chat_id: str, is_group: bool) -> None:
    """启动 iflow CLI。"""
    # 检查 iflow 是否已经在运行
    session_info = self.iflow_controller.get_session_info()
    if session_info and session_info.get('iflow_running', False):
        await self.wechat_channel.send("✅ iflow 已经在运行中", chat_id, is_group=is_group)
        return
    
    # 尝试启动 iflow
    await self.wechat_channel.send("⏳ 正在启动 iflow，请稍候...", chat_id, is_group=is_group)
    success = self.iflow_controller.start_iflow(model="kimi-k2.5")
    
    if success:
        await asyncio.sleep(3)
        # 验证启动状态
        session_info = self.iflow_controller.get_session_info()
        if session_info and session_info.get('iflow_running', False):
            await self.wechat_channel.send("✅ iflow 启动成功！现在可以开始使用了", chat_id, is_group=is_group)
        else:
            await self.wechat_channel.send("⚠️ iflow 启动失败，请检查日志", chat_id, is_group=is_group)
    else:
        await self.wechat_channel.send("❌ iflow 启动失败，请检查服务器日志", chat_id, is_group=is_group)
```

**停止 iflow** - `/stop-iflow`
```python
async def _stop_iflow(self, chat_id: str, is_group: bool) -> None:
    """停止 iflow CLI。"""
    # 检查 iflow 是否在运行
    session_info = self.iflow_controller.get_session_info()
    if not session_info or not session_info.get('tmux_exists', False):
        await self.wechat_channel.send("✅ iflow 未运行，无需停止", chat_id, is_group=is_group)
        return
    
    # 尝试停止 iflow
    await self.wechat_channel.send("⏳ 正在停止 iflow，请稍候...", chat_id, is_group=is_group)
    success = self.iflow_controller.stop_iflow()
    
    if success:
        await asyncio.sleep(2)
        session_info = self.iflow_controller.get_session_info()
        if not session_info or not session_info.get('tmux_exists', False):
            await self.wechat_channel.send("✅ iflow 已停止", chat_id, is_group=is_group)
        else:
            await self.wechat_channel.send("⚠️ iflow 停止失败，请检查日志", chat_id, is_group=is_group)
    else:
        await self.wechat_channel.send("❌ iflow 停止失败，请检查服务器日志", chat_id, is_group=is_group)
```

**重启 iflow** - `/restart-iflow`
```python
async def _restart_iflow(self, chat_id: str, is_group: bool) -> None:
    """重启 iflow CLI。"""
    # 先停止 iflow（如果正在运行）
    session_info = self.iflow_controller.get_session_info()
    if session_info and session_info.get('tmux_exists', False):
        await self.wechat_channel.send("⏳ 正在停止 iflow，请稍候...", chat_id, is_group=is_group)
        success = self.iflow_controller.stop_iflow()
        if not success:
            await self.wechat_channel.send("❌ iflow 停止失败，无法重启", chat_id, is_group=is_group)
            return
        await asyncio.sleep(2)
    
    # 启动 iflow
    await self.wechat_channel.send("⏳ 正在启动 iflow，请稍候...", chat_id, is_group=is_group)
    success = self.iflow_controller.start_iflow(model="kimi-k2.5")
    
    if success:
        await asyncio.sleep(3)
        session_info = self.iflow_controller.get_session_info()
        if session_info and session_info.get('iflow_running', False):
            await self.wechat_channel.send("✅ iflow 重启成功！现在可以开始使用了", chat_id, is_group=is_group)
        else:
            await self.wechat_channel.send("⚠️ iflow 重启失败，请检查日志", chat_id, is_group=is_group)
    else:
        await self.wechat_channel.send("❌ iflow 重启失败，请检查服务器日志", chat_id, is_group=is_group)
```

**列出命令** - `/lscmd`
```python
async def _list_commands(self, chat_id: str, is_group: bool) -> None:
    """列出所有可用命令。"""
    # 检查 iflow 状态
    session_info = self.iflow_controller.get_session_info()
    iflow_running = session_info.get('iflow_running', False) if session_info else False
    
    commands_message = """**📋 iFlow 企业微信机器人 - 可用命令**

**基础命令：**
• 直接发送消息：执行 iFlow 命令（自动恢复上次会话）
• `/run <命令>`：执行 iFlow 命令
• `/new`：开始新会话（清除上下文）

**查询命令：**
• `/status`：查看服务状态（tmux、iflow 运行状态）
• `/sessions`：查看历史会话列表
• `/lscmd`：列出所有可用命令（本命令）

**iflow 管理命令：**
• `/start-iflow`：启动 iflow CLI""" + ("" if iflow_running else "（推荐）") + """
• `/stop-iflow`：停止 iflow CLI
• `/restart-iflow`：重启 iflow CLI

**帮助命令：**
• `/help`：显示详细帮助信息

---
💡 提示：
• """ + ("iflow 已运行，可以直接发送命令使用" if iflow_running else "iflow 未运行，请先使用 `/start-iflow` 启动") + """
• 默认会自动恢复最近的会话，保持对话连续性
• 如需重新开始，请使用 `/new` 命令

示例：
```
""" + ("帮我写一个 Python 脚本" if iflow_running else "/start-iflow") + """
继续完善这个脚本
```
"""
    await self.wechat_channel.send(commands_message, chat_id, is_group=is_group)
```

**4. 智能提示**
系统会根据 iflow 状态智能调整提示信息：

**iflow 未运行时：**
- 提示使用 `/start-iflow` 启动
- 示例显示启动命令

**iflow 已运行时：**
- 提示可以直接使用命令
- 示例显示实际命令

**5. 错误处理优化**

**tmux 未启动时的错误提示：**
```
❌ iflow 未运行

请使用以下命令启动服务：
python manage.py start

或者只启动 iflow：
python manage.py start --no-wechat
```

**tmux 已启动但 iflow 未运行时的错误提示：**
```
❌ iflow 未运行

请使用以下命令启动服务：
python manage.py start

或者只启动 iflow：
python manage.py start --no-wechat
```

**6. 启动通知优化**

**tmux 未连接时的启动通知：**
```
🤖 iFlow 企业微信机器人已启动

📅 启动时间: 2026-03-10 15:28:02
💻 tmux 会话: 无连接
📁 工作目录: 无
🌐 回调端口: 8787

⚠️ iflow 未运行，无法处理消息

---
📋 快速开始：
• `/start-iflow`：启动 iflow CLI（推荐）
• `/lscmd`：查看所有可用命令

💡 提示：输入 `/lscmd` 查看完整的命令列表和功能说明。
```

**tmux 已连接时的启动通知：**
```
🤖 iFlow 企业微信机器人已启动

📅 启动时间: 2026-03-10 15:28:02
📁 工作目录: ~/.iflow
💻 tmux 会话: iflow ✓
🌐 回调端口: 8787

✅ 服务运行正常，可以开始使用！

---
📋 快速开始：
• 直接发送消息：执行 iFlow 命令
• `/lscmd`：查看所有可用命令

💡 提示：输入 `/lscmd` 查看完整的命令列表和功能说明。
```

**7. 关闭通知优化**

**tmux 未连接时的关闭通知：**
```
🛑 iFlow 企业微信机器人已停止

📅 关闭时间: 2026-03-10 15:30:00
💻 tmux 会话: 无连接
📁 工作目录: 无

---
如需重新启动，请执行:
```bash
python manage.py start
```
```

**tmux 已连接时的关闭通知：**
```
🛑 iFlow 企业微信机器人已停止

📅 关闭时间: 2026-03-10 15:30:00
📁 工作目录: ~/.iflow
💻 tmux 会话: iflow

---
如需重新启动，请执行:
```bash
python manage.py start
```
```

**优势：**
- ✅ 完整的 iflow 管理功能
- ✅ 智能的状态提示
- ✅ 简洁的启动/关闭通知
- ✅ 统一的命令列表查看方式
- ✅ 友好的错误提示
- ✅ 完全无需手动操作服务器

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

## 多机器人管理方案

### 1. 设计目标

- 支持配置多个企业微信机器人
- 每个机器人独立进程运行
- 支持多个 tmux 会话（多 iflow 实例）
- 灵活的资源管理（机器人、tmux 会话独立启停）
- 清晰的状态显示和管理命令

### 2. 配置文件结构

#### config.json（iflow 配置）

支持多个 tmux 会话配置：

```json
{
  "tmux_sessions": [
    {
      "name": "iflow1",
      "workspace": "~/.iflow1",
      "model": "kimi-k2.5"
    },
    {
      "name": "iflow2",
      "workspace": "~/.iflow2",
      "model": "kimi-k2.5"
    }
  ]
}
```

#### bots.json（机器人配置）

```json
{
  "bots": [
    {
      "name": "bot1",
      "enabled": true,
      "corp_id": "企业ID1",
      "agent_id": "应用ID1",
      "secret": "Secret1",
      "user_id": "用户1",
      "token": "Token1",
      "encoding_aes_key": "Key1",
      "callback_port": 8788,
      "tmux_session": "iflow1"
    },
    {
      "name": "bot2",
      "enabled": true,
      "corp_id": "企业ID2",
      "agent_id": "应用ID2",
      "secret": "Secret2",
      "user_id": "用户2",
      "token": "Token2",
      "encoding_aes_key": "Key2",
      "callback_port": 8789,
      "tmux_session": "iflow2"
    }
  ]
}
```

### 3. 命令设计

#### list 命令

列出所有机器人和 tmux 会话：

```bash
python manage.py list
```

输出：
```
============================================================
Ling-iflow 资源列表
============================================================

企业微信机器人 (共 2 个)
  
  1. bot1
    状态: 运行中 ✓
    回调端口: 8788
    tmux 会话: iflow1
    用户: 用户1
    
  2. bot2
    状态: 未运行
    回调端口: 8789
    tmux 会话: iflow2
    用户: 用户2

tmux 会话 (共 2 个)
  
  1. iflow1
    状态: 运行中 ✓
    工作目录: ~/.iflow1
    模型: kimi-k2.5
    
  2. iflow2
    状态: 未运行
    工作目录: ~/.iflow2
    模型: kimi-k2.5
```

#### start 命令

启动机器人或 tmux 会话：

```bash
# 启动机器人（使用序号）
python manage.py start -r 1

# 启动机器人（使用名称）
python manage.py start -r bot1

# 启动 tmux 会话（使用序号）
python manage.py start -t 1

# 启动 tmux 会话（使用名称）
python manage.py start -t iflow1

# 启动所有机器人
python manage.py start -r all

# 启动所有 tmux 会话
python manage.py start -t all
```

#### stop 命令

停止机器人或 tmux 会话：

```bash
# 停止机器人（使用序号）
python manage.py stop -r 1

# 停止机器人（使用名称）
python manage.py stop -r bot1

# 停止 tmux 会话（使用序号）
python manage.py stop -t 1

# 停止 tmux 会话（使用名称）
python manage.py stop -t iflow1

# 停止所有机器人
python manage.py stop -r all

# 停止所有 tmux 会话
python manage.py stop -t all
```

#### restart 命令

重启机器人或 tmux 会话：

```bash
# 重启机器人
python manage.py restart -r 1

# 重启 tmux 会话
python manage.py restart -t 1
```

#### status 命令

查看服务状态：

```bash
python manage.py status
```

输出：
```
============================================================
Ling-iflow 服务状态
============================================================

企业微信机器人 (共 2 个，运行中: 1)
  
  1. bot1 (PID: 12345)
    状态: 运行中 ✓
    回调端口: 8788
    tmux 会话: iflow1 ✓
    用户: 用户1
    
  2. bot2
    状态: 未运行
    回调端口: 8789
    tmux 会话: iflow2
    用户: 用户2

tmux 会话 (共 2 个，运行中: 1)
  
  1. iflow1
    状态: 运行中 ✓
    工作目录: ~/.iflow1
    模型: kimi-k2.5
    
  2. iflow2
    状态: 未运行
    工作目录: ~/.iflow2
    模型: kimi-k2.5
```

#### logs 命令

查看日志：

```bash
# 查看机器人日志
python manage.py logs -r 1
python manage.py logs -r bot1

# 查看所有机器人日志
python manage.py logs -r all

# 实时跟踪日志
python manage.py logs -r 1 --follow
```

### 4. 进程管理

#### PID 文件位置

- 机器人：`<项目根目录>/.pids/bot_<bot_name>.pid`
- 格式：`.pids/bot_bot1.pid`

#### 日志文件位置

- 机器人：`logs/wechat_bot_<bot_name>_<date>.log`

#### 进程标识

- 机器人进程：`wechat_bot.py --bot <bot_name>`

### 5. 实现步骤

1. **创建 bots.example.json**（示例配置文件）
2. **修改 config.json**（支持多个 tmux 配置）
3. **创建 config/bots_schema.py**（机器人配置 Schema）
4. **创建 config/bots_loader.py**（机器人配置加载器）
5. **修改 wechat_bot.py**（添加 --bot 参数）
6. **创建 utils/process_manager.py**（进程管理工具）
7. **修改 manage.py**（重构命令，添加 list、start、stop、restart、status、logs）

### 6. 核心优势

- **配置集中**：所有配置集中在项目根目录
- **操作灵活**：支持序号和名称两种方式
- **状态清晰**：list 和 status 命令显示详细状态
- **独立管理**：机器人、tmux 会话独立启停
- **扩展性强**：轻松添加多个机器人和 tmux 会话
- **故障隔离**：单个机器人故障不影响其他机器人

### 7. 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户层                                    │
│  ┌──────────────┐                  ┌──────────────┐             │
│  │  manage.py   │                  │  wechat_bot  │             │
│  │  (管理脚本)   │                  │  (机器人进程)  │             │
│  └──────┬───────┘                  └──────┬───────┘             │
└─────────┼──────────────────────────────────┼────────────────────┘
          │                                  │
          │                                  │
┌─────────┼──────────────────────────────────┼────────────────────┐
│         │        配置层                     │                    │
│  ┌──────▼──────┐                  ┌────────▼────────┐          │
│  │config.json  │                  │  bots.json     │          │
│  │(tmux配置)   │                  │  (机器人配置)   │          │
│  └─────────────┘                  └─────────────────┘          │
└──────────────────────────────────────────────────────────────┘
          │
┌─────────┼──────────────────────────────────────────────────────┐
│         │        进程管理层                 │                    │
│  ┌──────▼──────┐                  ┌─────────────────┐          │
│  │Process      │                  │  .pids/         │          │
│  │Manager      │◄────────────────►│  (PID文件)       │          │
│  └─────────────┘                  └─────────────────┘          │
└──────────────────────────────────────────────────────────────┘
          │
┌─────────┼──────────────────────────────────────────────────────┐
│         │        运行层                                          │
│  ┌──────▼──────┐                  ┌─────────────────┐          │
│  │  bot1 进程   │                  │  bot2 进程       │          │
│  │  (wechat_   │                  │  (wechat_       │          │
│  │  bot.py)    │                  │  bot.py)        │          │
│  └──────┬──────┘                  └──────┬──────────┘          │
│         │                                  │                     │
│  ┌──────▼──────┐                  ┌────────▼────────┐          │
│  │  iflow1     │                  │  iflow2         │          │
│  │  (tmux)     │                  │  (tmux)         │          │
│  └─────────────┘                  └─────────────────┘          │
└──────────────────────────────────────────────────────────────┘
```

### 8. 消息分发机制

#### 单机器人场景

```
企业微信消息 → bot1 进程 → iflow1 → AI 回复 → bot1 进程 → 企业微信
```

#### 多机器人场景

```
企业微信消息1 → bot1 进程 → iflow1 → AI 回复 → bot1 进程 → 企业微信
企业微信消息2 → bot2 进程 → iflow2 → AI 回复 → bot2 进程 → 企业微信
```

#### 共享 iflow 场景

```
企业微信消息1 → bot1 进程 ┐
                            ├──► iflow1 → AI 回复 ──┬─► bot1 进程 → 企业微信
企业微信消息2 → bot2 进程 ┘                      └─► bot2 进程 → 企业微信
```

### 9. 状态检查机制

#### 机器人状态检查

1. **PID 文件存在**：进程已启动
2. **进程运行中**：检查 `/proc/<pid>/status`
3. **端口监听**：检查回调端口是否监听
4. **tmux 连接**：检查关联的 tmux 会话是否存在

#### tmux 会话检查

1. **会话存在**：`tmux has-session -t <name>`
2. **iflow 运行**：检查进程是否运行
3. **工作目录**：验证工作目录是否存在

### 10. 错误处理

#### 启动失败

- 检查配置是否完整
- 检查端口是否被占用
- 检查 tmux 会话是否已存在
- 记录错误日志
- 提供详细的错误信息

#### 运行异常

- 定期检查进程状态
- 自动重启失败的进程
- 记录异常日志
- 通知用户（可选）

#### 端口冲突

- 自动检测端口占用
- 提供端口修改建议
- 支持动态端口分配

### 11. 安全考虑

#### 配置安全

- 敏感信息加密存储
- 配置文件权限控制
- 环境变量支持

#### 网络安全

- 回调 URL 验证
- 消息签名验证
- IP 白名单

#### 进程安全

- PID 文件权限控制
- 进程隔离
- 资源限制

### 12. 性能优化

#### 进程管理

- 异步进程检查
- 批量操作支持
- 进程池管理

#### 日志管理

- 日志轮转
- 日志压缩
- 日志清理策略

#### 资源监控

- 内存使用监控
- CPU 使用监控
- 网络连接监控

---

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