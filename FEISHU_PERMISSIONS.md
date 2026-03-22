# 飞书应用权限配置清单

> 📋 按照以下清单在飞书开放平台手动配置权限

---

## 一、权限配置（4 个必选）

在「权限管理」页面，逐个添加以下权限：

### ✅ 必选权限

| 序号 | 权限名称 | 权限 Code | 用途 |
|:---:|---------|----------|------|
| 1 | 发送消息 | `im:message` | 向用户/群聊发送消息 |
| 2 | 获取用户信息 | `contact:contact:readonly` | 获取发送者信息 |
| 3 | 事件订阅 | `event:event:readonly` | 订阅消息接收事件 |
| 4 | 管理机器人 | `app:bot` | 启用机器人功能 |

### ⭕ 可选权限（高级功能）

| 序号 | 权限名称 | 权限 Code | 用途 |
|:---:|---------|----------|------|
| 5 | 上传图片/文件 | `im:resource` | 发送图片/文件消息 |
| 6 | 下载图片/文件 | `im:file` | 接收图片/文件消息 |

---

## 二、事件订阅配置

在「事件订阅」页面配置：

### Verification Token
```
f8a0EUHM6ilMxn7oZFs1reUwx1bSEaow
```

### ✅ 必选事件

| 序号 | 事件名称 | 事件 Code |
|:---:|---------|----------|
| 1 | 接收消息 v2.0 | `im.message.receive_v1` |

### ⭕ 可选事件

| 序号 | 事件名称 | 事件 Code |
|:---:|---------|----------|
| 2 | 消息已读 v2.0 | `im.message.message_read_v1` |
| 3 | 添加表情回应 v2.0 | `im.message.reaction_created_v1` |
| 4 | 删除表情回应 v2.0 | `im.message.reaction_deleted_v1` |

---

## 三、机器人配置

在「机器人」页面：

- [x] 启用机器人
- [x] 支持单聊
- [x] 支持群聊
- [x] 支持@机器人

---

## 四、配置信息

将以下信息复制到 `config.json`：

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

---

## 五、快速配置步骤

1. **打开飞书开放平台**
   - 访问：https://open.feishu.cn/
   - 登录企业账号

2. **创建应用**
   - 进入「应用开发」→「企业自建应用」
   - 点击「创建应用」
   - 填写应用名称：iFlow 机器人

3. **添加权限**
   - 进入「权限管理」
   - 点击「添加权限」
   - 搜索并添加上述 4 个必选权限

4. **配置事件订阅**
   - 进入「事件订阅」
   - 填写 Verification Token: `f8a0EUHM6ilMxn7oZFs1reUwx1bSEaow`
   - 添加事件：`im.message.receive_v1`
   - 点击「保存」

5. **配置机器人**
   - 进入「机器人」
   - 启用机器人
   - 配置机器人名称和头像
   - 开启单聊和群聊支持

6. **发布应用**
   - 进入「版本管理与发布」
   - 创建版本并发布
   - 等待审核通过

7. **启用应用**
   - 进入「应用信息」
   - 点击「启用应用」
   - 选择启用范围

---

## 六、验证配置

配置完成后，运行以下命令验证：

```bash
# 启动飞书渠道
./manage.py start --channel feishu1

# 查看状态
./manage.py status

# 查看日志
./manage.py logs -f
```

在飞书中向机器人发送消息测试。

---

## 七、常见问题

### Q: 权限申请失败？
A: 确保使用的是企业管理员账号，或联系管理员授权。

### Q: 事件订阅验证失败？
A: 检查 Verification Token 是否正确复制，确保没有多余空格。

### Q: 机器人无法发送消息？
A: 检查是否启用了「发送消息」权限，并确保应用已发布。

---

*创建时间：2026-03-22*
