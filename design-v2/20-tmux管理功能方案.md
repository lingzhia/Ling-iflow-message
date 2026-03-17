# tmux 管理功能方案

## 一、方案概述

### 1.1 背景和目标

在 Ling-iflow 项目中，tmux 是管理 iflow CLI 会话的核心工具。每个渠道（企业微信、模拟器等）都会创建对应的 tmux 会话（格式：`channel_name+iflow`）来运行 iflow CLI。

当前项目缺乏对 tmux 会话的统一管理功能，用户无法方便地：
- 查看所有正在运行的 tmux 会话
- 创建新的 tmux 会话（用于调试或临时用途）
- 删除不再需要的 tmux 会话

**核心目标：**
- 提供统一的 tmux 会话管理接口
- 通过命令行命令实现对 tmux 会话的管理
- 支持会话列表查询、创建、删除功能
- 提供友好的用户界面和错误提示

### 1.2 设计原则

**安全性优先**
- tmux 会话删除是危险操作，需要明确的用户确认
- 提供详细的警告信息
- 记录所有管理操作的日志

**易用性**
- 提供简单的命令接口
- 清晰的错误提示和帮助信息
- 自动检测会话状态

**功能完整**
- 支持基本的 CRUD 操作（创建、读取、删除）
- 验证操作可行性（如删除前检查会话是否存在）
- 返回操作结果和状态信息

**松耦合**
- tmux 管理功能独立于业务逻辑
- 通过 subprocess 调用 tmux 命令
- 不依赖项目特定的 tmux 会话命名约定

## 二、系统架构

### 2.1 组件关系

```
┌─────────────────────────────────────────────────────────────┐
│                         用户渠道                              │
│  (企业微信 / 模拟器 / 其他渠道)                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   CommandHandler                             │
│                  (命令解析和执行)                              │
│  - parse_command() - 解析命令                                  │
│  - execute() - 执行命令                                        │
│  - _cmd_tmux() - tmux 管理命令                                │
└────────────┬────────────────────────────┬────────────────────┘
             │                            │
             ▼                            ▼
┌─────────────────────┐      ┌─────────────────────────┐
│   _cmd_tmux()       │      │  subprocess             │
│  (命令路由)          │      │  (tmux 命令执行)         │
└──────────┬──────────┘      └────────────┬────────────┘
           │                                  │
           └────────────┬─────────────────────┘
                        │
                        ▼
           ┌─────────────────────────┐
           │      tmux               │
           │  (会话管理)              │
           └────────────┬────────────┘
                        │
                        ▼
           ┌─────────────────────────┐
           │      CommandHandler     │
           │      (返回结果)          │
           └────────────┬────────────┘
                        │
                        ▼
           ┌─────────────────────────┐
           │         用户渠道         │
           │      (显示结果)          │
           └─────────────────────────┘
```

### 2.2 核心组件

**CommandHandler._cmd_tmux()**
- 位置：`src/modules/command/handler.py`
- 职责：处理 tmux 管理命令
- 依赖：subprocess（调用 tmux 命令）

**主要方法：**
- `_cmd_tmux(args: str, chat_id: str) -> str`: tmux 管理命令入口
- 支持的子命令：
  - `list` - 列出所有 tmux 会话
  - `create <name>` - 创建新的 tmux 会话
  - `kill <name>` - 杀死指定的 tmux 会话
  - 无参数 - 等同于 `list`

## 三、命令详解

### 3.1 `/tmux list` - 列出所有 tmux 会话

**功能：**
- 列出所有正在运行的 tmux 会话
- 显示会话名称、窗口数量、创建时间等信息
- 如果没有会话，返回友好的提示信息

**使用方法：**
```
/tmux list
/tmux          # 简写形式
```

**实现逻辑：**
```python
async def _cmd_tmux(self, args: str, chat_id: str) -> str:
    """tmux 管理命令"""
    parts = args.strip().split()
    
    if not parts:
        action = "list"
    else:
        action = parts[0].lower()
        args_str = ' '.join(parts[1:]) if len(parts) > 1 else ""
    
    if action == "list":
        # 列出所有 tmux 会话
        import subprocess
        
        try:
            result = subprocess.run(
                ["tmux", "list-sessions"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                sessions = result.stdout.strip()
                if not sessions:
                    return "✅ 当前没有运行的 tmux 会话"
                
                lines = ["**tmux 会话列表** 📋\n"]
                lines.append(sessions)
                return "\n".join(lines)
            else:
                return f"❌ 获取 tmux 会话列表失败: {result.stderr}"
        except Exception as e:
            return f"❌ 执行 tmux 命令失败: {e}"
```

**返回结果：**
```
**tmux 会话列表** 📋

bot1+iflow: 1 windows (created Tue Mar 17 10:30:15 2026)
bot2+iflow: 1 windows (created Tue Mar 17 11:00:00 2026)
simulator1+iflow: 1 windows (created Tue Mar 17 18:36:54 2026)
```

### 3.2 `/tmux create <name>` - 创建新的 tmux 会话

**功能：**
- 创建新的 tmux 会话
- 检查会话是否已存在
- 返回创建结果

**使用方法：**
```
/tmux create test_session
```

**实现逻辑：**
```python
elif action == "create":
    # 创建新的 tmux 会话
    session_name = args_str.strip()
    if not session_name:
        return "❌ 请指定会话名称\n用法: /tmux create <会话名>"
    
    import subprocess
    
    try:
        # 检查会话是否已存在
        check_result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )
        
        if check_result.returncode == 0:
            return f"❌ 会话 '{session_name}' 已存在"
        
        # 创建新会话
        create_result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name],
            capture_output=True,
            text=True
        )
        
        if create_result.returncode == 0:
            return f"✅ 已创建 tmux 会话: {session_name}"
        else:
            return f"❌ 创建会话失败: {create_result.stderr}"
    except Exception as e:
        return f"❌ 创建会话失败: {e}"
```

**返回结果：**
```
✅ 已创建 tmux 会话: test_session
```

**错误情况：**
```
❌ 会话 'test_session' 已存在
❌ 请指定会话名称
用法: /tmux create <会话名>
```

### 3.3 `/tmux kill <name>` - 杀死指定的 tmux 会话

**功能：**
- 杀死指定的 tmux 会话
- 检查会话是否存在
- 提供警告信息
- 返回删除结果

**使用方法：**
```
/tmux kill test_session
```

**实现逻辑：**
```python
elif action == "kill":
    # 杀死 tmux 会话
    session_name = args_str.strip()
    if not session_name:
        return "❌ 请指定会话名称\n用法: /tmux kill <会话名>"
    
    import subprocess
    
    try:
        # 检查会话是否存在
        check_result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )
        
        if check_result.returncode != 0:
            return f"❌ 会话 '{session_name}' 不存在"
        
        # 杀死会话
        kill_result = subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
            text=True
        )
        
        if kill_result.returncode == 0:
            return f"✅ 已杀死的 tmux 会话: {session_name}"
        else:
            return f"❌ 杀死会话失败: {kill_result.stderr}"
    except Exception as e:
        return f"❌ 杀死会话失败: {e}"
```

**返回结果：**
```
✅ 已杀死的 tmux 会话: test_session
```

**错误情况：**
```
❌ 会话 'test_session' 不存在
❌ 请指定会话名称
用法: /tmux kill <会话名>
```

### 3.4 `/tmux help` - 显示帮助信息

**功能：**
- 显示 tmux 管理命令的帮助信息
- 提供使用示例和注意事项

**使用方法：**
```
/tmux help
```

**返回结果：**
```
**tmux 管理命令** 🔧

用法:
- `/tmux list` - 列出所有 tmux 会话
- `/tmux create <会话名>` - 创建新的 tmux 会话
- `/tmux kill <会话名>` - 杀死指定的 tmux 会话
- `/tmux` - 列出所有 tmux 会话（简写）

示例:
- `/tmux` - 查看所有 tmux 会话
- `/tmux create test` - 创建名为 test 的会话
- `/tmux kill test` - 杀死名为 test 的会话

注意:
- 创建的 tmux 会话需要手动启动 iflow
- 杀死会话会同时停止该会话中的所有进程
- 请谨慎使用 kill 命令
```

## 四、实现细节

### 4.1 技术实现

**使用 subprocess 调用 tmux 命令：**
```python
import subprocess

# 列出会话
result = subprocess.run(
    ["tmux", "list-sessions"],
    capture_output=True,
    text=True
)

# 检查会话是否存在
result = subprocess.run(
    ["tmux", "has-session", "-t", session_name],
    capture_output=True
)

# 创建会话
result = subprocess.run(
    ["tmux", "new-session", "-d", "-s", session_name],
    capture_output=True,
    text=True
)

# 杀死会话
result = subprocess.run(
    ["tmux", "kill-session", "-t", session_name],
    capture_output=True,
    text=True
)
```

**参数说明：**
- `capture_output=True` - 捕获命令输出
- `text=True` - 返回字符串格式输出
- `-d` - 后台创建会话（不立即附加）
- `-s` - 指定会话名称
- `-t` - 指定目标会话

### 4.2 错误处理

**subprocess 错误处理：**
```python
try:
    result = subprocess.run(
        ["tmux", "list-sessions"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        # 成功处理
        ...
    else:
        # 命令执行失败
        return f"❌ 获取 tmux 会话列表失败: {result.stderr}"
        
except Exception as e:
    # 系统异常（如 tmux 未安装）
    return f"❌ 执行 tmux 命令失败: {e}"
```

**参数验证：**
```python
session_name = args_str.strip()
if not session_name:
    return "❌ 请指定会话名称\n用法: /tmux create <会话名>"
```

**会话存在性检查：**
```python
# 检查会话是否已存在
check_result = subprocess.run(
    ["tmux", "has-session", "-t", session_name],
    capture_output=True
)

if check_result.returncode == 0:
    return f"❌ 会话 '{session_name}' 已存在"
```

### 4.3 安全考虑

**会话名称验证：**
- 当前实现：tmux 命令本身会验证会话名称
- 未来改进：可以添加正则表达式验证，防止特殊字符注入

**操作确认：**
- 当前实现：kill 命令立即执行，无二次确认
- 未来改进：可以添加交互式确认机制

**日志记录：**
```python
logger.info(f"[{self.module_id}] tmux 操作: {action} {session_name}")
logger.info(f"[{self.module_id}] tmux 操作结果: {result}")
```

### 4.4 性能考虑

**subprocess 调用开销：**
- 每次 tmux 命令都会创建新的子进程
- 对于频繁操作，可以考虑缓存会话列表

**超时处理：**
```python
# 未来改进：添加超时控制
result = subprocess.run(
    ["tmux", "list-sessions"],
    capture_output=True,
    text=True,
    timeout=10  # 10秒超时
)
```

## 五、集成方式

### 5.1 在 CommandHandler 中集成

**命令注册：**
```python
def _register_builtin_commands(self) -> None:
    """注册内置命令"""
    self._commands = {
        # ... 其他命令
        "/tmux": self._cmd_tmux,
    }
```

**命令处理：**
```python
async def _cmd_tmux(self, args: str, chat_id: str) -> str:
    """tmux 管理命令"""
    parts = args.strip().split()
    
    if not parts:
        action = "list"
    else:
        action = parts[0].lower()
        args_str = ' '.join(parts[1:]) if len(parts) > 1 else ""
    
    # 根据动作执行相应操作
    if action == "list":
        return await self._tmux_list()
    elif action == "create":
        return await self._tmux_create(args_str)
    elif action == "kill":
        return await self._tmux_kill(args_str)
    else:
        return self._tmux_help()
```

### 5.2 在帮助文档中集成

**/help 命令：**
```python
async def _cmd_help(self, args: str, chat_id: str) -> str:
    """帮助命令"""
    return """**iFlow 企业微信助手** 🤖

*支持连续对话，自动保持上下文*

**可用命令：**
- 直接发送消息：执行 iFlow 命令（自动恢复上次会话）
- `/new`：开始新会话（清除上下文）
- `/sessions`：查看历史会话
- `/status`：查看服务状态
- `/history [模块ID]`：查看模块状态历史（最近 10 条）
- `/metrics [模块ID]`：查看模块性能指标
- `/snapshot [channel_name]`：查看 tmux 界面快照
- `/tmux [list|create|kill]`：tmux 会话管理
- `/help`：显示此帮助
- `/lscmd`：列出所有可用命令

**iFlow 命令支持：**
- 未知的斜杠命令会自动透传给 iflow 处理
- 例如：`/run`、`/config`、`/exit`、`/clear` 等会直接传递给 iflow"""
```

**/lscmd 命令：**
```python
async def _cmd_lscmd(self, args: str, chat_id: str) -> str:
    """列出所有命令"""
    return """**可用命令列表** 📋

**会话管理：**
- `/new` - 开始新会话（清除上下文）
- `/sessions` - 查看历史会话

**状态查询：**
- `/status` - 查看服务状态
- `/history [模块ID]` - 查看模块状态历史（最近 10 条）
- `/metrics [模块ID]` - 查看模块性能指标
- `/help` - 显示帮助信息
- `/lscmd` - 列出所有可用命令

**故障排查：**
- `/snapshot [channel_name]` - 查看 tmux 界面快照

**tmux 管理：**
- `/tmux list` - 列出所有 tmux 会话
- `/tmux create <会话名>` - 创建新的 tmux 会话
- `/tmux kill <会话名>` - 杀死指定的 tmux 会话
- `/tmux help` - 显示 tmux 命令帮助

**渠道管理：**
- `/channel list` - 列出所有渠道
- `/channel status [channel_name]` - 查看渠道状态
- `/channel start <channel_name>` - 启动渠道
- `/channel stop <channel_name>` - 停止渠道
- `/channel restart <channel_name>` - 重启渠道

**使用提示：**
- 直接发送消息即可与 iflow 对话
- 命令不区分大小写
- 模块 ID 可省略，将显示所有模块的信息
- 未知的斜杠命令会自动透传给 iflow 处理（如 `/run`、`/config`、`/clear` 等）"""
```

## 六、使用场景

### 6.1 调试场景

**场景：需要查看当前运行的 tmux 会话**
```
用户: /tmux list
系统: 
**tmux 会话列表** 📋

bot1+iflow: 1 windows (created Tue Mar 17 10:30:15 2026)
bot2+iflow: 1 windows (created Tue Mar 17 11:00:00 2026)
```

### 6.2 测试场景

**场景：创建测试会话用于调试**
```
用户: /tmux create test_debug
系统: ✅ 已创建 tmux 会话: test_debug

# 用户可以手动附加到会话进行调试
tmux attach -t test_debug

# 完成后删除会话
用户: /tmux kill test_debug
系统: ✅ 已杀死的 tmux 会话: test_debug
```

### 6.3 维护场景

**场景：清理不再使用的会话**
```
用户: /tmux list
系统: 
**tmux 会话列表** 📋

bot1+iflow: 1 windows (created Tue Mar 17 10:30:15 2026)
old_session: 2 windows (created Mon Mar 16 15:00:00 2026)

# 删除旧会话
用户: /tmux kill old_session
系统: ✅ 已杀死的 tmux 会话: old_session
```

## 七、测试和验证

### 7.1 单元测试

**命令解析测试：**
```python
def test_tmux_command_parsing():
    """测试 tmux 命令解析"""
    handler = CommandHandler()
    
    # 测试 list 命令
    parsed = handler.parse_command("/tmux list")
    assert parsed["is_command"] == True
    assert parsed["cmd_name"] == "/tmux"
    assert parsed["cmd_args"] == "list"
    
    # 测试 create 命令
    parsed = handler.parse_command("/tmux create test")
    assert parsed["is_command"] == True
    assert parsed["cmd_args"] == "create test"
    
    # 测试 kill 命令
    parsed = handler.parse_command("/tmux kill test")
    assert parsed["is_command"] == True
    assert parsed["cmd_args"] == "kill test"
```

### 7.2 集成测试

**完整流程测试：**
```python
async def test_tmux_management():
    """测试完整的 tmux 管理流程"""
    # 创建会话
    result = await handler._cmd_tmux("create test_session", "test_chat")
    assert "✅ 已创建 tmux 会话: test_session" in result
    
    # 列出会话
    result = await handler._cmd_tmux("list", "test_chat")
    assert "test_session" in result
    
    # 删除会话
    result = await handler._cmd_tmux("kill test_session", "test_chat")
    assert "✅ 已杀死的 tmux 会话: test_session" in result
    
    # 验证已删除
    result = await handler._cmd_tmux("list", "test_chat")
    assert "test_session" not in result
```

### 7.3 端到端测试

**通过企业微信测试：**
```python
async def test_via_wechat():
    """通过企业微信测试 tmux 管理命令"""
    # 启动服务
    bot = LingIflowBot("config.json")
    await bot.setup()
    await bot.start_all()
    
    # 模拟企业微信消息
    wechat_message = {
        "type": "text",
        "content": "/tmux list",
        "from": "test_user",
        "chat_id": "test_chat"
    }
    
    # 发送消息
    await bot.handle_wechat_message(wechat_message)
    
    # 等待回复
    await asyncio.sleep(2)
    
    # 验证回复
    # (需要检查企业微信收到的消息)
```

## 八、最佳实践

### 8.1 使用建议

**会话命名规范：**
- 使用小写字母和下划线
- 避免使用特殊字符
- 使用有意义的名称
- 遵循项目命名约定（如 `channel_name+iflow`）

**定期清理：**
- 定期检查不再使用的会话
- 及时删除测试会话
- 避免会话堆积

**谨慎删除：**
- 删除前确认会话内容
- 确保没有重要的进程在运行
- 备份重要数据后再删除

### 8.2 故障排查

**tmux 命令不可用：**
```bash
# 检查 tmux 是否安装
which tmux

# 安装 tmux
sudo apt-get install tmux  # Ubuntu/Debian
sudo yum install tmux      # CentOS/RHEL
```

**会话无法删除：**
```bash
# 强制删除会话
tmux kill-session -t session_name

# 或直接杀死进程
ps aux | grep tmux
kill -9 <pid>
```

**权限问题：**
```bash
# 检查 tmux socket 权限
ls -l /tmp/tmux-*

# 清理旧的 socket 文件
rm -f /tmp/tmux-*
```

## 九、未来扩展

### 9.1 会话重命名

**支持会话重命名：**
```python
async def _tmux_rename(self, old_name: str, new_name: str) -> str:
    """重命名 tmux 会话"""
    result = subprocess.run(
        ["tmux", "rename-session", "-t", old_name, new_name],
        capture_output=True,
        text=True
    )
    ...
```

### 9.2 会话附加

**支持附加到会话：**
```python
async def _tmux_attach(self, session_name: str) -> str:
    """附加到 tmux 会话（仅限本地使用）"""
    result = subprocess.run(
        ["tmux", "attach", "-t", session_name],
        capture_output=True,
        text=True
    )
    ...
```

### 9.3 会话信息查询

**支持查询会话详细信息：**
```python
async def _tmux_info(self, session_name: str) -> str:
    """查询 tmux 会话详细信息"""
    result = subprocess.run(
        ["tmux", "show-options", "-t", session_name],
        capture_output=True,
        text=True
    )
    ...
```

### 9.4 批量操作

**支持批量删除：**
```python
async def _tmux_kill_multiple(self, session_names: List[str]) -> str:
    """批量删除多个 tmux 会话"""
    results = []
    for session_name in session_names:
        result = await self._tmux_kill(session_name)
        results.append(result)
    return "\n".join(results)
```

## 十、总结

### 10.1 核心特性

✅ **统一管理接口**
- 通过命令行命令管理 tmux 会话
- 支持基本的 CRUD 操作
- 友好的用户界面

✅ **安全可靠**
- 操作前检查会话状态
- 详细的错误提示
- 完整的日志记录

✅ **易于使用**
- 简单的命令格式
- 清晰的帮助信息
- 自动验证操作可行性

### 10.2 设计优势

**松耦合**
- tmux 管理功能独立于业务逻辑
- 通过 subprocess 调用 tmux 命令
- 不依赖项目特定的命名约定

**可扩展**
- 易于添加新的 tmux 操作
- 支持自定义命令
- 预留扩展接口

**用户友好**
- 提供完整的帮助信息
- 友好的错误提示
- 清晰的操作结果

### 10.3 实施状态

- ✅ CommandHandler 集成完成
- ✅ 所有子命令已实现
- ✅ 错误处理和日志已实现
- ✅ 帮助文档已完善
- ⏳ 会话重命名（未来扩展）
- ⏳ 会话附加（未来扩展）
- ⏳ 会话信息查询（未来扩展）
- ⏳ 批量操作（未来扩展）

## 十一、参考文档

- **19-命令系统设计方案.md** - 命令系统设计基础
- **04-IFlow模块设计方案.md** - IFlow 模块设计
- **17-渠道架构简化方案.md** - 渠道架构设计

## 十二、相关文件

- **src/modules/command/handler.py** - CommandHandler 类实现
- **src/bot.py** - Bot 集成 CommandHandler
- **src/modules/channel/wechat.py** - 企业微信渠道集成
- **tests/test_command_handler.py** - 命令处理器测试

---

**文档版本：** 1.0  
**创建日期：** 2026-03-17  
**最后更新：** 2026-03-17