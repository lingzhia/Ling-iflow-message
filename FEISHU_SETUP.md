# 飞书渠道配置指南

## 一、依赖安装

已安装飞书依赖：

```bash
pip install -e ".[feishu]"
```

**包含依赖：**
- `lark-oapi>=1.0.0` - 飞书官方 SDK
- `httpx>=0.24.0` - HTTP 客户端

---

## 二、飞书开放平台配置

### 2.1 创建应用

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入「应用开发」→「企业自建应用」
3. 点击「创建应用」
4. 填写应用信息：
   - **应用名称**：iFlow 机器人（或自定义）
   - **应用图标**：可选
   - **应用描述**：iFlow CLI 交互模式管理工具

---

### 2.2 配置权限（重要）⭐

在「权限管理」页面，添加以下权限：

#### 必选权限

| 权限名称 | 权限标识 | 用途 | 申请方式 |
|---------|---------|------|---------|
| **发送消息** | `im:message` | 向用户/群聊发送消息 | 自动开通 |
| **获取用户信息** | `contact:contact:readonly` | 获取发送者信息 | 自动开通 |
| **事件订阅** | `event:event:readonly` | 订阅消息接收事件 | 自动开通 |
| **管理机器人** | `app:bot` | 启用机器人功能 | 自动开通 |

#### 可选权限（高级功能）

| 权限名称 | 权限标识 | 用途 |
|---------|---------|------|
| **上传图片/文件** | `im:resource` | 发送图片/文件消息 |
| **下载图片/文件** | `im:file` | 接收图片/文件消息 |

---

### 2.3 配置事件订阅

1. 进入「事件订阅」功能

2. **配置验证 Token**
   - 复制 Verification Token：`f8a0EUHM6ilMxn7oZFs1reUwx1bSEaow`
   - 粘贴到「Verification Token」输入框
   - 点击「保存」

3. **订阅事件**
   
   点击「订阅事件」→「添加事件」，搜索并添加以下事件：
   
   | 事件名称 | 事件标识 | 用途 |
   |---------|---------|------|
   | **接收消息 v2.0** | `im.message.receive_v1` | 接收用户发送的消息 |
   | **消息已读 v2.0** | `im.message.message_read_v1` | 监听消息已读状态（可选） |
   | **添加表情回应 v2.0** | `im.message.reaction_created_v1` | 监听表情回应（可选） |
   | **删除表情回应 v2.0** | `im.message.reaction_deleted_v1` | 监听表情回应删除（可选） |

4. **发布应用**
   - 点击「发布」按钮
   - 等待审核通过（通常几分钟）

---

### 2.4 配置机器人

1. 进入「机器人」功能

2. **启用机器人**
   - 开启「启用机器人」开关

3. **配置机器人信息**
   - **机器人名称**：iFlow 助手（或自定义）
   - **机器人图标**：上传图标（可选）
   - **机器人描述**：iFlow CLI 交互模式管理工具

4. **机器人能力**
   - ✅ 支持单聊
   - ✅ 支持群聊
   - ✅ 支持@机器人

5. **保存配置**

---

### 2.5 应用发布

1. 进入「版本管理与发布」

2. **创建版本**
   - 点击「创建版本」
   - 填写版本号：`1.0.0`
   - 填写更新说明：初始版本

3. **提交审核**
   - 点击「提交审核」
   - 等待审核通过

4. **发布应用**
   - 审核通过后，点击「发布」

---

## 三、启用应用

### 3.1 启用应用

1. 进入「应用信息」页面

2. 点击「启用应用」

3. **启用范围**
   - 选择「部分员工」或「全员」
   - 添加需要使用的用户

---

### 3.2 添加到群聊

1. 在飞书中打开目标群聊

2. 点击右上角「设置」

3. 选择「添加群机器人」

4. 选择「iFlow 助手」机器人

5. 点击「添加」

---

## 四、配置文件

配置文件位置：`config.json`

```json
{
  "feishu_channels": [
    {
      "name": "feishu1",
      "enabled": true,
      "app_id": "cli_a935de9dab799bcb",
      "app_secret": "pcXWuk0m26w4aqXa5W4NyeHxtDeuMiX2",
      "verification_token": "f8a0EUHM6ilMxn7oZFs1reUwx1bSEaow",
      "encrypt_key": "",
      "allow_from": [],
      "tmux_session": "feishu1+iflow"
    }
  ]
}
```

**配置项说明：**

| 配置项 | 说明 | 是否必填 |
|-------|------|---------|
| name | 渠道名称（唯一标识） | ✅ |
| enabled | 是否启用 | ✅ |
| app_id | 飞书应用 ID | ✅ |
| app_secret | 飞书应用密钥 | ✅ |
| verification_token | 事件订阅验证 Token | ✅ |
| encrypt_key | 消息加密密钥（未启用加密则为空） | ❌ |
| allow_from | 用户白名单（空表示允许所有） | ❌ |
| tmux_session | 关联的 iflow 会话名 | ✅ |

---

## 五、启动测试

### 5.1 启动服务

```bash
# 启动所有渠道
./manage.py start

# 只启动飞书渠道
./manage.py start --channel feishu1

# 查看状态
./manage.py status

# 查看日志
./manage.py logs -f
```

### 5.2 测试消息

1. **在飞书中发送消息**
   - 向机器人发送：`你好`
   - 或发送命令：`/help`

2. **预期响应**
   - 机器人应回复消息确认
   - 消息会被转发到 iflow 处理
   - iflow 的回复会发送回飞书

3. **查看日志**
   ```bash
   ./manage.py logs -f
   ```

---

## 六、常见问题

### Q1: 消息发送失败

**可能原因：**
- 应用未启用
- 权限配置不完整
- 用户不在启用范围内

**解决方案：**
1. 检查应用是否已启用
2. 检查权限配置是否完整
3. 确认用户在启用范围内

---

### Q2: 收不到消息回调

**可能原因：**
- 事件订阅未配置
- 事件未发布
- Verification Token 配置错误

**解决方案：**
1. 检查事件订阅配置
2. 确认事件已发布
3. 重新验证 Verification Token

---

### Q3: WebSocket 连接失败

**可能原因：**
- App ID 或 App Secret 错误
- 网络连接问题
- 应用权限不足

**解决方案：**
1. 检查 App ID 和 App Secret 配置
2. 检查网络连接
3. 确认应用权限配置完整

---

## 七、安全建议

### 7.1 密钥保护

- ❌ 不要将 `app_secret` 提交到代码仓库
- ✅ 使用环境变量或加密存储
- ✅ 定期轮换密钥

### 7.2 白名单控制

建议配置用户白名单：

```json
{
  "feishu_channels": [
    {
      "name": "feishu1",
      "allow_from": ["user_id_1", "user_id_2"]
    }
  ]
}
```

### 7.3 权限最小化

只申请必要的权限，避免过度授权。

---

## 八、参考文档

- [飞书开放平台](https://open.feishu.cn/)
- [事件订阅文档](https://open.feishu.cn/document/server-docs/event-subscription/event-subscription)
- [发送消息 API](https://open.feishu.cn/document/server-docs/im-v1/message/create)
- [lark-oapi SDK](https://github.com/larksuite/lark-oapi)

---

*文档创建时间：2026-03-22*
