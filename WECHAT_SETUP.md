# 企业微信配置说明

## 1. 获取企业微信配置信息

### 步骤 1：获取企业 ID
1. 登录企业微信管理后台：https://work.weixin.qq.com/wework_admin/frame
2. 点击「我的企业」
3. 查看「企业信息」中的「企业ID」

### 步骤 2：创建应用
1. 点击「应用管理」→「应用」→「创建应用」
2. 选择应用类型（推荐「自建应用」）
3. 填写应用信息并创建

### 步骤 3：获取应用配置
1. 进入刚创建的应用
2. 记录「AgentId」和「Secret」
3. 记录你的「企业微信App」账号（头像→账号）

## 2. 配置接收消息

### 步骤 1：配置回调 URL
1. 在应用设置中找到「接收消息」
2. 点击「设置API接收」
3. 填写回调URL（需要公网可访问）：`http://你的域名:8788/wechat/callback`
4. 点击「随机生成」获取 `EncodingAESKey`
5. 填写自定义的 `Token`（如：`mytoken123`）
6. 保存配置

### 步骤 2：验证回调 URL
1. 企业微信会发送验证请求到你的回调URL
2. 如果验证成功，回调配置就完成了

## 3. 配置项目

### 创建配置文件
```bash
cp config.example.json config.json
```

### 编辑 config.json
```json
{
  "tmux_session": "iflow",
  "workspace": "~/.iflow",
  "wechat_work": {
    "enabled": true,
    "corp_id": "你的企业ID",
    "agent_id": "你的应用AgentId",
    "secret": "你的应用Secret",
    "user_id": "你的用户账号",
    "token": "mytoken123",
    "encoding_aes_key": "你的EncodingAESKey",
    "callback_host": "0.0.0.0",
    "callback_port": 8788,
    "allow_from": [],
    "group_policy": "mention",
    "group_allow_from": []
  }
}
```

## 4. 启动服务

### 前置要求
- iflow 已启动
- 端口 8788 未被占用
- 公网 IP 或内网穿透（用于回调）

### 启动 iflow
```bash
tmux new-session -d -s iflow "iflow --model kimi-k2.5"
```

### 安装依赖
```bash
pip install -e ".[wechat]"
```

### 启动企业微信 Bot
```bash
python wechat_bot.py
```

## 5. 测试功能

### 测试配置
```bash
python test_wechat.py test
```

### 监听消息
```bash
python test_wechat.py listen
```

### 发送测试消息
```bash
python test_wechat.py send "测试消息"
```

### 查看帮助
```bash
python test_wechat.py --help
```

## 6. 使用企业微信

### 可用命令
- **直接发送消息**：执行 iflow 命令（自动恢复上次会话）
- **`/run <命令>`**：执行 iflow 命令
- **`/new`**：开始新会话（清除上下文）
- **`/sessions`**：查看历史会话
- **`/status`**：查看服务状态
- **`/help`**：显示帮助

### 示例对话
```
你: 帮我写一个 Python 脚本
bot: ⏳ 正在执行: 帮我写一个 Python 脚本
bot: ✅ [脚本内容]

你: 再帮我添加一个函数
bot: ⏳ 正在执行: 再帮我添加一个函数
bot: ✅ [更新后的脚本]

你: /new
bot: ✅ 已开始新会话

你: /status
bot: [状态信息]
```

## 7. 故障排查

### 问题 1：无法接收消息
- 检查回调 URL 是否可访问
- 检查端口 8788 是否开放
- 查看日志确认企业微信是否发送了请求

### 问题 2：消息发送失败
- 检查 AgentId 和 Secret 是否正确
- 检查用户 ID 是否正确
- 查看日志获取详细错误信息

### 问题 3：iflow 未运行
```bash
tmux new-session -d -s iflow "iflow --model kimi-k2.5"
```

### 问题 4：端口被占用
修改 `config.json` 中的 `callback_port`

## 8. 高级配置

### 权限控制
在 `config.json` 中设置白名单：
```json
{
  "wechat_work": {
    "allow_from": ["user1", "user2"],
    "group_policy": "mention",
    "group_allow_from": ["group1"]
  }
}
```

### 内网穿透
如果没有公网 IP，可以使用内网穿透工具：
- ngrok
- frp
- cpolar

示例（ngrok）：
```bash
ngrok http 8788
```
然后将 ngrok 提供的 URL 配置到企业微信回调 URL。