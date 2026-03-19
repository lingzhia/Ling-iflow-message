# 进程 ID 目录

此目录用于存储进程 ID (PID) 文件。

## 文件说明

- `bot_*.pid` - 机器人进程 ID 文件
- `*.pid` - 其他进程 ID 文件

## 文件命名规则

PID 文件命名格式：`{channel_name}_bot.pid`

例如：
- `wechat_bot1_bot.pid` - 企业微信 bot1 的进程 ID
- `simulator1_bot.pid` - 模拟器1 的进程 ID

## 用途

- 记录正在运行的进程 ID
- 用于进程管理和监控
- 支持优雅停止服务

## 自动管理

PID 文件由系统自动生成和清理：
- 服务启动时自动创建
- 服务停止时自动删除
- 不要手动编辑或删除这些文件

## 查看进程状态

```bash
# 查看进程 ID
cat .pids/bot_bot1.pid

# 检查进程是否运行
ps -p $(cat .pids/bot_bot1.pid)

# 使用管理脚本查看状态
./manage.py status
```