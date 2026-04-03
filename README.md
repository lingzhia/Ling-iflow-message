# Ling-iflow-message

## 项目简介

Ling-iflow-message 是一个基于 tmux 的 iflow CLI 交互模式管理工具，通过消息总线架构实现与多个聊天渠道的双向消息同步。

核心功能：
- **多渠道消息同步** — 聊天消息在渠道端和 iflow CLI 之间双向传递
- **消息总线架构** — 模块间完全解耦，易于扩展
- **tmux 会话管理** — 每个渠道对应一个独立的 tmux 会话
- **命令系统** — /help, /status, /new, /sessions 等
- **多实例支持** — 可同时管理多个机器人/iflow 实例

---

## ⚠️ 重要说明：聊天工具定位

### 飞书（Feishu）✅ 核心渠道

- **当前主要维护的渠道**，推荐使用
- 采用 WebSocket 长连接，**无需公网 IP**
- 完整支持双向消息同步
- 配置简单，稳定可靠

### 企业微信（WeChat Work）⚠️ 已废弃

> **警告：企业微信实现已不再维护，不建议在新项目中使用。**
>
> 如需使用，风险自负。保留仅为历史参考。

企业微信存在的问题：
- 依赖公网可达的回调接口
- 实现不完善，稳定性差
- 已无维护和更新

---

## 快速开始

### 1. 克隆并安装

```bash
git clone git@github.com:lingzhia/Ling-iflow-message.git
cd Ling-iflow-message
pip install -e ".[dev,feishu]"   # 飞书开发（推荐）
# 或
pip install -e ".[dev,wechat,feishu]"  # 包含企业微信（不推荐）
```

### 2. 配置

```bash
cp config.example.json config.json
# 编辑 config.json，填入渠道配置
```

**飞书配置示例：**

```json
{
  "feishu_channels": [
    {
      "name": "feishu1",
      "app_id": "cli_xxxxxxxxxxxxx",
      "app_secret": "xxxxxxxxxxxxxxxxxxxx",
      "verification_token": "xxxxxxxxxxxx",
      "allow_from": [],
      "notify_user_id": "ou_xxxxx",
      "tmux_session": "feishu1+iflow"
    }
  ]
}
```

### 3. 启动

```bash
./manage.py start
# 或前台运行（方便调试）
./manage.py start -f
```

### 4. 常用命令

```bash
./manage.py start          # 启动服务
./manage.py stop           # 停止服务
./manage.py status         # 查看状态
./manage.py logs -f        # 实时查看日志
./manage.py channel list   # 列出所有渠道
```

---

## 架构说明

```
Ling-iflow-message/
├── src/
│   ├── core/              # 核心基础类
│   │   ├── bus.py         # 消息总线（模块间通信中枢）
│   │   ├── manager.py     # 模块管理器
│   │   ├── message.py     # 消息模型
│   │   └── base.py        # 基础类和接口定义
│   └── modules/
│       ├── channel/       # 渠道模块
│       │   ├── feishu.py  # 飞书渠道 ⭐ 核心
│       │   ├── wechat.py  # 企业微信渠道 ⚠️ 已废弃
│       │   └── simulator.py
│       ├── iflow/         # iflow CLI 会话管理
│       ├── claudecode/    # Claude Code 会话管理
│       ├── command/       # 命令系统
│       └── common/        # 通用工具
├── design-v2/             # 设计文档
├── tests/                 # 测试文件
├── tools/                 # 测试工具
├── manage.py              # 管理脚本
└── config.json            # 配置文件
```

### 核心组件

| 组件 | 说明 |
|------|------|
| **消息总线（Bus）** | 所有模块通过总线发布/订阅消息，完全解耦 |
| **渠道模块（Channel）** | 对接各聊天平台，收发消息 |
| **iflow 模块** | 管理 tmux 会话中的 iflow CLI 进程 |
| **命令系统** | 处理 /help、/status 等命令 |

---

## 飞书渠道配置（推荐）

详见 [飞书渠道设计方案](design-v2/20-飞书渠道设计方案.md)，或查看 [INSTALL.md](INSTALL.md)。

### 配置步骤

1. 在 [飞书开放平台](https://open.feishu.cn/) 创建企业自建应用
2. 获取 `App ID` 和 `App Secret`
3. 配置应用权限（消息相关权限）
4. 配置事件订阅（使用 WebSocket 模式，无需公网回调）
5. 填写到 `config.json` 的 `feishu_channels` 中

---

## 项目文档

| 文档 | 说明 |
|------|------|
| [INSTALL.md](INSTALL.md) | 详细的安装、配置和使用说明 |
| [design-v2/README.md](design-v2/README.md) | 架构设计和模块设计 |
| [design-v2/20-飞书渠道设计方案.md](design-v2/20-飞书渠道设计方案.md) | 飞书渠道设计和配置 |
| [TODO.md](TODO.md) | 项目待办事项 |

---

## 许可证

MIT License
