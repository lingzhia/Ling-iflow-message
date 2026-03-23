# Ling-iflow

Ling-iflow 是一个 iflow CLI 交互模式管理工具，通过 tmux 管理和监控 iflow CLI 会话，实现与企业微信、飞书等渠道的双向消息同步。

## 核心特性

- **多渠道支持** - 企业微信、飞书、模拟器
- **消息总线架构** - 模块间完全解耦，易于扩展
- **命令系统** - /help, /status, /new, /sessions 等
- **多实例管理** - 支持多机器人、多 iflow 实例

## 快速开始

```bash
# 1. 克隆并安装
git clone git@github.com:lingzhia/Ling-iflow-message.git
cd Ling-iflow
pip install -e ".[dev,wechat,feishu]"

# 2. 配置
cp config.example.json config.json
# 编辑 config.json，填入企业微信或飞书配置

# 3. 启动
./manage.py start
```

## 目录结构

```
Ling-iflow/
├── src/                    # 源代码
│   ├── core/              # 核心基础类（消息总线、模块管理器）
│   └── modules/           # 模块实现（渠道、iflow、命令）
├── design-v2/             # 设计文档
├── tests/                 # 测试文件
├── tools/                 # 测试工具
├── manage.py              # 管理脚本
└── config.json            # 配置文件
```

## 常用命令

```bash
./manage.py start          # 启动服务
./manage.py stop           # 停止服务
./manage.py status         # 查看状态
./manage.py logs -f        # 查看日志
./manage.py channel list   # 列出渠道
```

## 文档

- [安装和使用指南](INSTALL.md) - 详细的安装、配置和使用说明
- [设计文档](design-v2/README.md) - 架构设计和模块设计
- [飞书渠道配置](design-v2/20-飞书渠道设计方案.md) - 飞书渠道设计和配置

## 许可证

MIT License
