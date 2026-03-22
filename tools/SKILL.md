# IFlow CLI 控制工具

## 概述

这是一个用于控制 tmux 中 iflow CLI 的命令行工具。支持完整的 tmux 会话管理、消息交互和会话文件管理功能。

**设计目标**：作为 AI Skill 使用，让 AI 能够通过此工具控制 iflow 执行代码任务。

## 快速开始

```bash
# 进入项目目录
cd /opt/MyGitCode/Ling-iflow

# 运行工具
python3 tools/iflow_interactive_tool.py <command> [options]
```

## 命令格式

```bash
python3 tools/iflow_interactive_tool.py [全局选项] <命令> [命令选项]
```

### 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | JSON 格式输出（AI 调用必须使用） |
| `--tmux-session <name>` | 指定 tmux 会话名称（默认：iflow） |

### 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 参数错误 |
| 3 | iflow 未就绪 |
| 4 | 超时 |
| 5 | tmux 会话不存在 |

---

## 子命令详解

### 1. tmux - Tmux 会话管理

#### tmux create - 创建会话

```bash
python3 tools/iflow_interactive_tool.py --json tmux create <name> [options]
```

| 选项 | 说明 |
|------|------|
| `<name>` | 会话名称（必需） |
| `--workspace, -w <dir>` | 工作目录 |
| `--model, -m <name>` | 模型名称 |
| `--mode <smart\|yolo>` | 运行模式（默认：smart） |

**JSON 输出示例**：
```json
{
  "success": true,
  "command": "tmux create",
  "data": {
    "session": "my-iflow",
    "workspace": "/home/user/project",
    "model": "kimi-k2.5",
    "mode": "smart",
    "message": "会话 my-iflow 创建成功，iflow 已启动"
  }
}
```

#### tmux stop - 停止会话

```bash
python3 tools/iflow_interactive_tool.py --json tmux stop <name>
```

#### tmux restart - 重启会话中的 iflow

```bash
python3 tools/iflow_interactive_tool.py --json tmux restart <name> [--model <name>] [--mode <smart|yolo>]
```

#### tmux list - 列出所有会话

```bash
python3 tools/iflow_interactive_tool.py --json tmux list
```

**JSON 输出示例**：
```json
{
  "success": true,
  "command": "tmux list",
  "data": {
    "sessions": [
      {"name": "iflow", "created": 1234567890, "attached": false, "windows": 1}
    ],
    "count": 1
  }
}
```

#### tmux snapshot - 查看会话快照

```bash
python3 tools/iflow_interactive_tool.py --json tmux snapshot <name> [--lines 50]
```

**JSON 输出示例**：
```json
{
  "success": true,
  "command": "tmux snapshot",
  "data": {
    "session": "iflow",
    "lines": ["...", "..."],
    "total_lines": 100
  }
}
```

#### tmux switch - 切换会话

```bash
python3 tools/iflow_interactive_tool.py --json tmux switch <name>
```

---

### 2. send - 发送消息

```bash
python3 tools/iflow_interactive_tool.py --json --tmux-session <name> send <message> [options]
```

| 选项 | 说明 |
|------|------|
| `<message>` | 消息内容（必需） |
| `--scope <all\|reply_only>` | 消息范围（默认：reply_only） |
| `--source <name>` | 消息来源（默认：tool） |
| `--timeout <seconds>` | 超时时间（默认：300） |

**JSON 输出示例**：
```json
{
  "success": true,
  "command": "send",
  "data": {
    "success": true,
    "replies": [
      {"type": "reply", "content": "这是回复内容..."},
      {"type": "complete", "content": "【回复结束】本次交互共 1 条消息，处理耗时 10 秒"}
    ],
    "reply_count": 1,
    "duration": 10
  }
}
```

---

### 3. status - 查看状态

```bash
python3 tools/iflow_interactive_tool.py --json --tmux-session <name> status
```

**JSON 输出示例**：
```json
{
  "success": true,
  "command": "status",
  "data": {
    "tmux_session": "iflow",
    "connected": false,
    "tmux_exists": true,
    "iflow_running": true
  }
}
```

---

### 4. session - IFlow 会话文件管理

#### session list - 列出会话文件

```bash
python3 tools/iflow_interactive_tool.py --json session list [--workspace <dir>] [--limit 20]
```

#### session current - 显示当前会话

```bash
python3 tools/iflow_interactive_tool.py --json session current [--workspace <dir>]
```

#### session new - 创建新会话（清空上下文）

```bash
python3 tools/iflow_interactive_tool.py --json session new [--workspace <dir>]
```

#### session view - 查看会话内容

```bash
python3 tools/iflow_interactive_tool.py --json session view [name] [--workspace <dir>] [--lines 50]
```

---

### 5. interactive - 进入交互模式

```bash
python3 tools/iflow_interactive_tool.py --tmux-session <name> interactive
```

---

## AI 使用指南

### 典型工作流程

#### 1. 检查环境

```bash
# 检查是否有活动的 tmux 会话
python3 tools/iflow_interactive_tool.py --json tmux list

# 检查特定会话状态
python3 tools/iflow_interactive_tool.py --json --tmux-session <name> status
```

#### 2. 创建或使用会话

```bash
# 创建新会话
python3 tools/iflow_interactive_tool.py --json tmux create <name> --workspace <dir> --mode yolo

# 或使用现有会话
python3 tools/iflow_interactive_tool.py --json tmux switch <name>
```

#### 3. 发送任务

```bash
# 发送代码任务
python3 tools/iflow_interactive_tool.py --json --tmux-session <name> send "请帮我实现一个功能..." --timeout 600
```

#### 4. 查看结果

```bash
# 查看快照
python3 tools/iflow_interactive_tool.py --json tmux snapshot <name> --lines 100

# 检查状态
python3 tools/iflow_interactive_tool.py --json --tmux-session <name> status
```

#### 5. 清理

```bash
# 创建新会话清空上下文
python3 tools/iflow_interactive_tool.py --json session new

# 或停止会话
python3 tools/iflow_interactive_tool.py --json tmux stop <name>
```

### 错误处理

**检查 success 字段**：
```json
// 成功
{"success": true, "data": {...}}

// 失败
{"success": false, "error": {"code": "not_found", "message": "..."}}
```

**常见错误码**：
- `not_found`: 会话不存在
- `session_exists`: 会话已存在
- `connect_failed`: 连接失败
- `iflow_not_ready`: iflow 未就绪
- `timeout`: 等待超时

### 最佳实践

1. **始终使用 `--json` 参数**：便于解析输出
2. **检查退出码**：非零表示失败
3. **设置合理超时**：复杂任务需要更长时间
4. **使用 YOLO 模式**：执行代码任务时自动批准操作
5. **定期检查快照**：了解任务执行进度

---

## 示例场景

### 场景1：创建新项目会话并执行任务

```bash
# 1. 创建会话
python3 tools/iflow_interactive_tool.py --json tmux create myproject \
  --workspace /home/user/myproject --mode yolo

# 2. 发送任务
python3 tools/iflow_interactive_tool.py --json --tmux-session myproject send \
  "请帮我创建一个 FastAPI 项目，包含用户认证功能" --timeout 600

# 3. 查看结果
python3 tools/iflow_interactive_tool.py --json tmux snapshot myproject --lines 50

# 4. 检查状态
python3 tools/iflow_interactive_tool.py --json --tmux-session myproject status
```

### 场景2：使用现有会话继续工作

```bash
# 1. 列出会话
python3 tools/iflow_interactive_tool.py --json tmux list

# 2. 切换到会话
python3 tools/iflow_interactive_tool.py --json tmux switch existing-session

# 3. 发送任务
python3 tools/iflow_interactive_tool.py --json --tmux-session existing-session send \
  "继续完善这个功能，添加单元测试" --timeout 300
```

### 场景3：清空上下文开始新对话

```bash
# 方法1：使用 session new（推荐）
python3 tools/iflow_interactive_tool.py --json session new

# 方法2：重启 iflow
python3 tools/iflow_interactive_tool.py --json tmux restart <name>
```

---

## 技术细节

### iflow 运行模式

| 模式 | 说明 |
|------|------|
| `smart` | 智能模式，需要手动确认操作 |
| `yolo` | YOLO 模式，自动批准所有操作 |

### scope 模式

| 模式 | 说明 |
|------|------|
| `reply_only` | 只返回回复消息（默认） |
| `all` | 返回所有消息（包括思考过程） |

### 消息类型

| 类型 | 说明 |
|------|------|
| `reply` | AI 回复（✦ 标记） |
| `complete` | 交互完成通知 |
| `other` | 其他消息（✻ 思考过程） |

---

## 注意事项

1. **工作目录**：iflow 会话文件存储在 `~/.iflow/projects/<project-path>/` 目录下
2. **会话保持**：tmux 会话会保持 iflow 运行，工具断开连接不会影响
3. **超时设置**：复杂任务建议设置更长超时时间（如 600 秒）
4. **YOLO 模式**：执行代码修改任务时推荐使用，避免手动确认
5. **JSON 输出**：AI 调用时必须使用 `--json` 参数
