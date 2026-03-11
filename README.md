# Ling-iflow

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信的双向消息同步。

## 项目状态

🚧 **正在重构中**

当前项目正在进行架构重构，从紧耦合的架构升级到基于消息总线的松耦合架构：

| 版本 | 状态 | 说明 |
|------|------|------|
| `src/` | ✅ 稳定 | 旧版本代码，功能完整 |
| `src-v2/` | 🚧 开发中 | 新版本代码，重构架构 |

## 新架构概述

基于**发布-订阅模式**和**消息总线**设计，实现模块解耦：

### 三大核心模块

1. **企业微信消息模块** - 纯粹的企业微信 API 封装
2. **消息分发模块（消息总线）** - 模块间消息路由和分发
3. **iflow 消息模块** - iflow CLI 的完整管理

### 核心优势

- ✅ **解耦清晰** - 模块间通过消息总线通信
- ✅ **扩展性强** - 添加新功能无需修改现有代码
- ✅ **灵活度高** - 支持多对多绑定和动态绑定
- ✅ **易于维护** - 模块独立开发测试，故障隔离

## 目录结构

```
Ling-iflow/
├── src/                # 旧版本（稳定）
│   ├── channels/       # 渠道模块
│   ├── interactive/    # 交互模式核心模块
│   ├── config/         # 配置管理模块
│   ├── cli/            # CLI 命令模块
│   ├── utils/          # 工具函数模块
│   ├── tool/           # 测试工具模块
│   ├── design/         # 旧版本设计文档
│   ├── manage.py       # 项目管理脚本
│   ├── wechat_bot.py   # 企业微信 Bot 主程序
│   ├── tmux_manager.py # tmux 管理工具
│   └── README-old.md   # 旧版本 README 备份
├── src-v2/             # 新版本（开发中）
│   ├── core/           # 核心基础类
│   │   └── bus/        # 消息总线
│   └── modules/        # 模块实现
│       ├── wechat/     # 企业微信模块
│       └── iflow/      # iflow 模块
├── design-v2/          # 重构设计方案
│   ├── 01-模块重构方案.md
│   └── README.md
├── tests/              # 测试文件
├── logs/               # 日志目录
├── config.json         # 配置文件
├── config.example.json # 配置示例
├── pyproject.toml      # 项目依赖配置
└── README.md           # 本文档
```

## 文档

### 重构设计文档
- [design-v2/01-模块重构方案.md](design-v2/01-模块重构方案.md) - 详细的模块拆分方案
- [design-v2/README.md](design-v2/README.md) - 重构进度和说明

### 旧版本文档
- [src/design/](src/design/) - 旧版本完整设计文档
- [src/README-old.md](src/README-old.md) - 旧版本 README
- [src/AGENTS.md](src/AGENTS.md) - Agent 上下文文档
- [src/TOOLS.md](src/TOOLS.md) - 工具说明文档
- [src/WECHAT_SETUP.md](src/WECHAT_SETUP.md) - 企业微信配置说明文档

## 快速开始

### 安装依赖

```bash
# 安装基础依赖
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

### 启动旧版本（稳定）

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

### 启动新版本（开发中）

新版本正在开发中，暂不提供启动方式。

## 重构进度

- [x] 方案设计
- [x] 项目结构调整
- [ ] 核心基础类实现
- [ ] 消息总线实现
- [ ] 企业微信模块实现
- [ ] iflow 模块实现
- [ ] 集成测试
- [ ] 代码清理

## 许可证

MIT License