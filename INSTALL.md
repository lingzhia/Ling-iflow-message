# Ling-iflow 安装和使用指南

## 目录

- [安装方法](#安装方法)
- [安装后使用](#安装后使用)
- [常用命令](#常用命令)
- [配置说明](#配置说明)
- [常见问题](#常见问题)

## 安装方法

### 前置要求

- Python 3.10 或更高版本
- pip 包管理器
- tmux (用于 iflow CLI 会话管理)
- iflow CLI 工具

### 1. 克隆项目

```bash
git clone git@github.com:lingzhia/Ling-iflow-message.git
cd Ling-iflow
```

### 2. 安装依赖

**基础安装（仅核心功能）：**
```bash
pip install -e .
```

**开发环境安装（包含测试工具）：**
```bash
pip install -e ".[dev]"
```

**企业微信功能安装（包含企业微信相关依赖）：**
```bash
pip install -e ".[wechat]"
```

**完整安装（包含开发和微信功能）：**
```bash
pip install -e ".[dev,wechat]"
```

### 3. 验证安装

```bash
# 检查命令是否可用
ling-iflow --help

# 应该看到帮助信息输出
```

## 安装后使用

### 1. 配置文件

复制示例配置文件并根据需要修改：

```bash
cp config.example.json config.json
vim config.json  # 使用你喜欢的编辑器
```

**主要配置项：**

```json
{
  "bots": [
    {
      "name": "bot1",
      "enabled": true,
      "corp_id": "企业ID",
      "agent_id": "应用AgentId",
      "secret": "应用Secret",
      "user_id": "用户账号",
      "token": "回调Token",
      "encoding_aes_key": "EncodingAESKey",
      "callback_port": 8787,
      "callback_host": "0.0.0.0",
      "tmux_session": "wechat_bot1+iflow"
    }
  ],
  "simulator_channels": [
    {
      "name": "simulator1",
      "enabled": false,
      "host": "localhost",
      "port": 19999,
      "tmux_session": "simulator1+iflow"
    }
  ],
  "log_level": "INFO",
  "filter_thinking": true
}
```

### 2. 基本使用

**查看可用渠道：**
```bash
ling-iflow start --channel ls
```

**启动默认渠道：**
```bash
ling-iflow start
```

**启动指定渠道：**
```bash
ling-iflow start --channel bot1
```

**启动所有渠道：**
```bash
ling-iflow start -a
```

**前台运行（方便调试）：**
```bash
ling-iflow start -f
```

**查看服务状态：**
```bash
ling-iflow status
```

**停止服务：**
```bash
ling-iflow stop
```

**重启服务：**
```bash
ling-iflow restart
```

### 3. 任意目录使用

安装完成后，可以在系统的任何目录使用 `ling-iflow` 命令：

```bash
# 在任意目录
cd /any/directory
ling-iflow start --channel bot1
ling-iflow status
```

## 常用命令

### 启动命令

```bash
# 启动默认渠道
ling-iflow start

# 启动指定渠道
ling-iflow start -c bot1

# 启动所有渠道
ling-iflow start -a

# 前台运行（调试用）
ling-iflow start -f

# 使用指定配置文件
ling-iflow start -c config.json
```

### 停止命令

```bash
# 停止默认渠道
ling-iflow stop

# 停止指定渠道
ling-iflow stop -c bot1

# 停止所有渠道
ling-iflow stop -a
```

### 重启命令

```bash
# 重启默认渠道
ling-iflow restart

# 重启指定渠道
ling-iflow restart -c bot1

# 重启所有渠道
ling-iflow restart -a
```

### 状态查看

```bash
# 查看服务状态
ling-iflow status

# 查看日志
ling-iflow logs

# 实时跟踪日志
ling-iflow logs -f

# 查看最近 N 行日志
ling-iflow logs -n 100
```

### 渠道管理

```bash
# 列出所有渠道
ling-iflow channel list

# 查看渠道状态
ling-iflow channel status bot1

# 启动指定渠道
ling-iflow channel start bot1

# 停止指定渠道
ling-iflow channel stop bot1

# 重启指定渠道
ling-iflow channel restart bot1
```

### 其他命令

```bash
# 清理日志和缓存
ling-iflow clean

# 查看完整帮助
ling-iflow help-all

# 查看特定命令帮助
ling-iflow start --help
```

## 配置说明

### 企业微信配置

```json
{
  "bots": [
    {
      "name": "bot1",              // 渠道名称（唯一）
      "enabled": true,             // 是否启用
      "corp_id": "企业ID",          // 企业微信企业ID
      "agent_id": "1000002",       // 应用AgentId
      "secret": "应用Secret",       // 应用Secret
      "user_id": "YuLingZhi",      // 用户账号（用于发送消息）
      "token": "回调Token",        // 回调配置的Token
      "encoding_aes_key": "EncodingAESKey",  // 回调配置的EncodingAESKey
      "callback_port": 8787,       // 回调服务端口
      "callback_host": "0.0.0.0",  // 回调服务监听地址
      "tmux_session": "wechat_bot1+iflow"  // tmux会话名称（格式：渠道名+iflow）
    }
  ]
}
```

### 模拟器配置

```json
{
  "simulator_channels": [
    {
      "name": "simulator1",       // 模拟器名称
      "enabled": false,           // 是否启用
      "host": "localhost",        // 模拟器主机
      "port": 19999,             // 模拟器端口
      "tmux_session": "simulator1+iflow"  // tmux会话名称
    }
  ]
}
```

### 全局配置

```json
{
  "log_level": "INFO",           // 日志级别（DEBUG, INFO, WARNING, ERROR）
  "filter_thinking": true        // 是否过滤思考过程
}
```

## 常见问题

### 1. 安装后找不到 `ling-iflow` 命令

**问题：** 安装后执行 `ling-iflow` 命令提示 "command not found"

**解决方案：**
- 确认使用 `pip install -e .` 安装
- 检查 Python 环境变量是否正确配置
- 尝试使用完整路径：`/path/to/python/bin/ling-iflow`
- 或者直接使用：`python3 -m src.bot`

### 2. 启动失败：配置文件不存在

**问题：** 启动时提示 "配置文件不存在"

**解决方案：**
```bash
# 复制示例配置文件
cp config.example.json config.json

# 或者指定配置文件路径
ling-iflow start -c /path/to/config.json
```

### 3. 企业微信消息没有回复

**问题：** 通过企业微信发送消息后没有收到回复

**解决方案：**
1. 检查服务状态：`ling-iflow status`
2. 查看日志：`ling-iflow logs -f`
3. 确认模块绑定关系：查看日志中是否有 "绑定成功" 的信息
4. 检查企业微信配置是否正确
5. 确认 iflow CLI 是否正常启动：`tmux ls`

### 4. 工作目录显示不正确

**问题：** 启动通知中显示的工作目录与实际不符

**解决方案：**
- 项目现在使用当前目录作为工作目录
- 确保在正确的目录启动服务
- 检查配置文件中的 workspace 配置（已弃用）

### 5. tmux 会话无法启动

**问题：** iflow CLI 无法在 tmux 会话中启动

**解决方案：**
1. 检查 tmux 是否安装：`tmux -V`
2. 手动测试 tmux：`tmux new-session -d -s test`
3. 检查 iflow CLI 是否可用：`iflow --help`
4. 查看日志获取详细错误信息

### 6. 端口被占用

**问题：** 启动时提示端口被占用

**解决方案：**
```bash
# 查看端口占用情况
netstat -tlnp | grep 8787

# 停止占用端口的进程
kill -9 <PID>

# 或者修改配置文件中的 callback_port
```

### 7. 权限问题

**问题：** 安装或运行时出现权限错误

**解决方案：**
```bash
# 使用虚拟环境安装
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 8. 依赖安装失败

**问题：** 安装依赖时出现错误

**解决方案：**
```bash
# 更新 pip
pip install --upgrade pip

# 使用国内镜像源
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 分步安装依赖
pip install pydantic pydantic-settings loguru typer
pip install -e .
```

## 高级使用

### 1. 使用不同的配置文件

```bash
# 使用开发环境配置
ling-iflow start -c config-dev.json

# 使用测试环境配置
ling-iflow start -c config-test.json
```

### 2. 后台运行和日志管理

```bash
# 后台启动服务
ling-iflow start

# 实时查看日志
ling-iflow logs -f

# 查看最近的日志
ling-iflow logs -n 50

# 清理日志
ling-iflow clean
```

### 3. tmux 会话管理

```bash
# 查看所有 tmux 会话
tmux ls

# 连接到 iflow 会话
tmux attach -t wechat_bot1+iflow

# 从 tmux 会话中分离（不关闭）
按 Ctrl+B，然后按 D

# 关闭 tmux 会话
tmux kill-session -t wechat_bot1+iflow
```

### 4. 多渠道管理

```bash
# 同时管理多个渠道
ling-iflow start -a

# 单独控制特定渠道
ling-iflow channel start bot2
ling-iflow channel stop bot1

# 查看所有渠道状态
ling-iflow channel status
```

## 卸载

```bash
# 卸载包
pip uninstall ling-iflow

# 删除项目目录（如果不再需要）
rm -rf /path/to/Ling-iflow

# 删除配置文件（如果需要）
rm -rf ~/.ling-iflow
```

## 技术支持

如遇到问题，请：

1. 查看日志文件：`logs/bot.log`
2. 检查服务状态：`ling-iflow status`
3. 查看详细帮助：`ling-iflow help-all`
4. 查看项目文档：`README.md` 和 `design-v2/` 目录

## 更新日志

### v0.1.0 (2026-03-17)
- ✅ 实现渠道架构简化方案
- ✅ 支持项目安装和全局命令
- ✅ 支持任意目录使用
- ✅ 简化配置结构
- ✅ 完善命令行工具