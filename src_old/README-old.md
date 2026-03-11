# Ling-iflow

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信的双向消息同步。

## 项目状态

⚠️ **项目正在重构中**

当前项目正在进行架构重构，采用了基于消息总线的全新设计：

- `src/` - 旧版本代码（稳定）
- `src-v2/` - 新版本代码（开发中）
- `design-v2/` - 重构设计方案

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/lingzhia/Ling-iflow-message.git
cd Ling-iflow-message

# 安装依赖
pip install -e .

# 安装企业微信依赖
pip install -e ".[wechat]"
```

### 配置

```bash
# 复制配置文件
cp config.example.json config.json

# 编辑配置文件
vim config.json
```

### 启动（旧版本）

```bash
# 启动服务（iflow + 企业微信）
python src/manage.py start

# 启动指定序号
python src/manage.py start 2

# 仅启动 iflow
python src/manage.py start --no-wechat

# 前台模式
python src/manage.py start --foreground
```

## 功能特性

- **tmux 集成**：通过 tmux 启动和管理 iflow CLI 会话
- **消息同步**：支持企业微信消息与 iflow CLI 的双向同步
- **会话管理**：提供会话查询、创建、删除等功能
- **命令系统**：支持 `/run`, `/new`, `/sessions`, `/status`, `/help` 等命令
- **多机器人管理**：支持配置多个企业微信机器人
- **测试工具**：提供 iflow 交互式测试工具和企业微信调试工具

## 目录结构

```
Ling-iflow/
├── src/                # 旧版本代码（稳定）
│   ├── channels/       # 渠道模块
│   ├── interactive/    # 交互模式核心模块
│   ├── config/         # 配置管理模块
│   ├── cli/            # CLI 命令模块
│   ├── utils/          # 工具函数模块
│   ├── tool/           # 测试工具模块
│   ├── manage.py       # 项目管理脚本
│   ├── wechat_bot.py   # 企业微信 Bot 主程序
│   └── tmux_manager.py # tmux 管理工具
├── src-v2/             # 新版本代码（开发中）
│   ├── core/           # 核心基础类
│   └── modules/        # 模块实现
│       ├── wechat/     # 企业微信模块
│       └── iflow/      # iflow 模块
├── design/             # 旧版本设计文档
├── design-v2/          # 重构设计方案
│   ├── 01-模块重构方案.md
│   └── README.md
├── tests/              # 测试文件
├── logs/               # 日志目录
├── config.json         # 配置文件
├── config.example.json # 配置示例
├── pyproject.toml      # 项目依赖配置
└── README.md           # 项目说明文档
```

## 文档

### 设计文档
- [design-v2/01-模块重构方案.md](design-v2/01-模块重构方案.md) - 重构设计方案
- [design/](design/) - 旧版本设计文档

### 旧版本文档
- [src/AGENTS.md](src/AGENTS.md) - Agent 上下文文档
- [src/TOOLS.md](src/TOOLS.md) - 工具说明文档
- [src/WECHAT_SETUP.md](src/WECHAT_SETUP.md) - 企业微信配置说明文档

## 许可证

MIT License