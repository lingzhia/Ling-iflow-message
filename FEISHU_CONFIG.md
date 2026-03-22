# 飞书渠道配置说明

## 📋 配置位置

飞书渠道配置在 `config.json` 的 `feishu_channels` 数组中。

## 🔧 配置项说明

```json
{
  "feishu_channels": [
    {
      "name": "feishu1",
      "enabled": true,
      "app_id": "cli_xxxxxxxxxxxxx",
      "app_secret": "your_app_secret",
      "verification_token": "your_verification_token",
      "encrypt_key": "",
      "allow_from": [],
      "tmux_session": "feishu1+iflow",
      "open_id": ""
    }
  ]
}
```

### 必填配置

| 配置项 | 说明 | 示例 |
|-------|------|------|
| name | 渠道名称（唯一标识） | feishu1 |
| enabled | 是否启用 | true |
| app_id | 飞书应用 ID | cli_xxxxxxxxxxxxx |
| app_secret | 飞书应用密钥 | your_app_secret |
| verification_token | 事件订阅验证 Token | your_verification_token |
| tmux_session | 关联的 iflow 会话 | feishu1+iflow |

### 可选配置

| 配置项 | 说明 | 默认值 |
|-------|------|--------|
| encrypt_key | 消息加密密钥 | "" |
| allow_from | 用户白名单（空表示允许所有） | [] |
| **open_id** | **接收通知的用户 ID** | "" |

---

## 🔍 如何获取 open_id

**open_id 是飞书用户的唯一标识**，用于发送启动/停止通知。

### 方法 1：通过飞书开放平台获取

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入「应用开发」→ 选择你的应用
3. 进入「用户信息」或「权限管理」
4. 找到您的用户 ID（open_id 格式如：`ou_xxxxxxxxxxxxx`）

### 方法 2：通过 API 获取

使用飞书 API 查询用户信息：

```bash
curl -X GET "https://open.feishu.cn/open-apis/contact/v3/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 方法 3：通过日志获取（推荐）

1. 启动服务后，在飞书中向机器人发送一条消息
2. 查看日志：`tail -f logs/bot.log`
3. 日志中会显示发送者的 open_id

示例日志：
```
[INFO] [feishu_feishu1] 收到飞书消息：message_id=xxx sender=ou_xxxxxxxxxxxxx
```

复制 `ou_xxxxxxxxxxxxx` 填入配置的 `open_id` 字段。

---

## ✅ 配置示例

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
      "tmux_session": "feishu1+iflow",
      "open_id": "ou_xxxxxxxxxxxxx"
    }
  ]
}
```

---

## 🚀 启动服务

配置完成后，启动服务：

```bash
# 启动所有渠道（包括飞书）
python3 -m src.bot config.json

# 或使用管理脚本
./manage.py start
```

---

## 📝 日志说明

### 启动成功日志

```
[INFO] [feishu_feishu1] 启动飞书通道
[INFO] [feishu_feishu1] WebSocket 线程已启动
[INFO] [feishu_feishu1] 飞书通道启动完成（WebSocket 长连接）
[INFO] [feishu_feishu1] 启动通知已发送
[INFO] [feishu_feishu1] 模块启动成功
```

### 未配置 open_id 日志

```
[INFO] [feishu_feishu1] 飞书通道启动完成（WebSocket 长连接）
[WARNING] [feishu_feishu1] 未配置 open_id，跳过启动通知发送
[INFO] [feishu_feishu1] 模块启动成功
```

**注意**：未配置 open_id 不影响消息功能，只是不会收到启动/停止通知。

---

## 🔧 测试工具

使用飞书测试工具测试消息交互：

```bash
# 监听消息
python3 tools/feishu_test_tool.py listen

# 发送消息
python3 tools/feishu_test_tool.py send "你好"

# 交互模式
python3 tools/feishu_test_tool.py interactive
```

---

*更新时间：2026-03-22*
