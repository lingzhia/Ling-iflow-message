# 模块设计 - CLI 层

## 概述

CLI 层提供命令行接口，让用户可以通过命令行工具管理和操作 Ling-iflow 服务。

## 目录结构

```
cli/
├── __init__.py
└── commands.py    # CLI 命令接口
```

## 命令列表

### 1. start - 启动交互模式服务

**功能**：启动 Ling-iflow 交互模式服务

**用法**：
```bash
ling-iflow start [OPTIONS]
```

**选项**：
- `--workspace PATH`：iflow 工作目录（默认：~/.iflow）
- `--model TEXT`：iflow 模型名称（默认：kimi-k2.5）
- `--tmux-session TEXT`：tmux 会话名称（默认：iflow）
- `--no-auto-start`：不自动启动 iflow
- `--wechat`：启用企业微信同步
- `--config PATH`：配置文件路径

**示例**：
```bash
# 使用默认配置启动
ling-iflow start

# 指定工作目录和模型
ling-iflow start --workspace ~/.iflow --model kimi-k2.5

# 启用企业微信同步
ling-iflow start --wechat

# 不自动启动 iflow
ling-iflow start --no-auto-start
```

### 2. stop - 停止 iflow

**功能**：停止 iflow CLI

**用法**：
```bash
ling-iflow stop [OPTIONS]
```

**选项**：
- `--tmux-session TEXT`：tmux 会话名称（默认：iflow）

**示例**：
```bash
# 停止默认会话
ling-iflow stop

# 停止指定会话
ling-iflow stop --tmux-session iflow1
```

### 3. status - 查看状态

**功能**：查看服务状态

**用法**：
```bash
ling-iflow status [OPTIONS]
```

**选项**：
- `--tmux-session TEXT`：tmux 会话名称（默认：iflow）
- `--workspace PATH`：iflow 工作目录

**示例**：
```bash
# 查看默认状态
ling-iflow status
```

**输出示例**：
```
============================================================
Ling-iflow 状态
============================================================
tmux 会话: iflow
  存在: 是
  iflow 运行中: 是

会话文件: ~/.iflow/projects/
  会话数量: 1
  会话列表:
    1. session-abc123.jsonl
```

### 4. test - 运行测试程序

**功能**：运行测试程序

**用法**：
```bash
ling-iflow test [OPTIONS]
```

**选项**：
- `--simple`：运行简单测试

**示例**：
```bash
# 运行完整测试
ling-iflow test

# 运行简单测试
ling-iflow test --simple
```

### 5. init - 初始化配置

**功能**：初始化配置文件

**用法**：
```bash
ling-iflow init [OPTIONS]
```

**选项**：
- `--config PATH`：配置文件路径

**示例**：
```bash
# 初始化配置（使用默认路径）
ling-iflow init

# 指定配置文件路径
ling-iflow init --config /path/to/config.json
```

## 实现细节

### 命令注册

```python
import typer
from typing import Optional

app = typer.Typer(help="Ling-iflow 交互模式管理工具")

@app.command()
def start(
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        help="iflow 工作目录"
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        help="iflow 模型名称"
    ),
    tmux_session: Optional[str] = typer.Option(
        None,
        "--tmux-session",
        help="tmux 会话名称"
    ),
    no_auto_start: bool = typer.Option(
        False,
        "--no-auto-start",
        help="不自动启动 iflow"
    ),
    wechat: bool = typer.Option(
        False,
        "--wechat",
        help="启用企业微信同步"
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="配置文件路径"
    )
) -> None:
    """启动交互模式服务。"""
    # 实现启动逻辑
    pass

@app.command()
def stop(
    tmux_session: Optional[str] = typer.Option(
        None,
        "--tmux-session",
        help="tmux 会话名称"
    )
) -> None:
    """停止 iflow CLI。"""
    # 实现停止逻辑
    pass

@app.command()
def status(
    tmux_session: Optional[str] = typer.Option(
        None,
        "--tmux-session",
        help="tmux 会话名称"
    ),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        help="iflow 工作目录"
    )
) -> None:
    """查看服务状态。"""
    # 实现状态查询逻辑
    pass

@app.command()
def test(
    simple: bool = typer.Option(
        False,
        "--simple",
        help="运行简单测试"
    )
) -> None:
    """运行测试程序。"""
    # 实现测试逻辑
    pass

@app.command()
def init(
    config: Optional[str] = typer.Option(
        None,
        "--config",
        help="配置文件路径"
    )
) -> None:
    """初始化配置文件。"""
    # 实现初始化逻辑
    pass

if __name__ == "__main__":
    app()
```

### 配置加载

```python
from ..config.loader import ConfigLoader

def _load_config(config_path: Optional[str] = None) -> InteractiveConfig:
    """加载配置。"""
    loader = ConfigLoader(config_path)
    return loader.load_config()
```

### 启动逻辑实现

```python
import asyncio
from ..interactive.sync_manager import SyncManager

async def _start_service(
    workspace: str,
    model: str,
    tmux_session: str,
    auto_start_iflow: bool,
    wechat_config: Optional[WechatWorkConfig]
) -> None:
    """启动服务。"""
    # 创建同步管理器
    sync_manager = SyncManager(
        workspace=workspace,
        tmux_session=tmux_session,
        wechat_config=wechat_config
    )
    
    # 启动服务
    success = await sync_manager.start(auto_start_iflow=auto_start_iflow)
    
    if not success:
        typer.echo("❌ 启动失败", err=True)
        raise typer.Exit(1)
    
    typer.echo("✅ 服务启动成功")
    
    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\n正在停止服务...")
        await sync_manager.stop()
        typer.echo("✅ 服务已停止")

def start(
    workspace: Optional[str] = None,
    model: Optional[str] = None,
    tmux_session: Optional[str] = None,
    no_auto_start: bool = False,
    wechat: bool = False,
    config: Optional[str] = None
) -> None:
    """启动交互模式服务。"""
    # 加载配置
    config = _load_config(config)
    
    # 合并命令行参数
    if workspace:
        config.workspace = workspace
    if model:
        config.model = model
    if tmux_session:
        config.tmux_sessions[0].name = tmux_session
    
    # 检查是否启用企业微信
    wechat_config = None
    if wechat or config.wechat_work.enabled:
        wechat_config = config.wechat_work
    
    # 启动服务
    asyncio.run(_start_service(
        workspace=config.workspace,
        model=config.model,
        tmux_session=config.tmux_sessions[0].name,
        auto_start_iflow=not no_auto_start,
        wechat_config=wechat_config
    ))
```

### 停止逻辑实现

```python
from ..interactive.iflow_controller import IFlowController

def stop(
    tmux_session: Optional[str] = None
) -> None:
    """停止 iflow CLI。"""
    # 加载配置
    config = _load_config()
    
    # 获取会话名称
    session_name = tmux_session or config.tmux_sessions[0].name
    
    # 创建控制器
    controller = IFlowController(session_name)
    
    # 停止 iflow
    success = controller.stop_iflow()
    
    if success:
        typer.echo("✅ iflow 已停止")
    else:
        typer.echo("❌ 停止失败", err=True)
        raise typer.Exit(1)
```

### 状态查询实现

```python
from ..interactive.iflow_controller import IFlowController
from ..interactive.session_manager import SessionManager

def status(
    tmux_session: Optional[str] = None,
    workspace: Optional[str] = None
) -> None:
    """查看服务状态。"""
    # 加载配置
    config = _load_config()
    
    # 获取参数
    session_name = tmux_session or config.tmux_sessions[0].name
    workspace_path = workspace or config.workspace
    
    # 创建控制器和管理器
    controller = IFlowController(session_name)
    session_manager = SessionManager(workspace_path)
    
    # 检查 tmux 会话
    tmux_exists = controller.check_tmux_session()
    iflow_running = controller.check_iflow_running()
    
    # 获取会话信息
    latest_session = session_manager.get_latest_session()
    all_sessions = session_manager.get_all_sessions(limit=10)
    
    # 打印状态
    typer.echo("=" * 60)
    typer.echo("Ling-iflow 状态")
    typer.echo("=" * 60)
    typer.echo(f"")
    typer.echo(f"tmux 会话: {session_name}")
    typer.echo(f"  存在: {'是' if tmux_exists else '否'}")
    typer.echo(f"  iflow 运行中: {'是' if iflow_running else '否'}")
    typer.echo(f"")
    typer.echo(f"会话文件: {workspace_path}/projects/")
    typer.echo(f"  会话数量: {len(all_sessions)}")
    
    if latest_session:
        typer.echo(f"  最新会话: {latest_session['id']}")
        typer.echo(f"  修改时间: {latest_session['mtime']}")
    
    if all_sessions:
        typer.echo(f"  会话列表:")
        for i, session in enumerate(all_sessions, 1):
            typer.echo(f"    {i}. {session['id']} ({session['mtime']})")
```

### 初始化配置实现

```python
from ..config.loader import ConfigLoader

def init(
    config: Optional[str] = None
) -> None:
    """初始化配置文件。"""
    # 创建加载器
    loader = ConfigLoader(config)
    
    # 检查配置文件是否存在
    if loader.config_path.exists():
        typer.confirm(f"配置文件已存在：{loader.config_path}\n是否覆盖？", abort=True)
    
    # 创建默认配置
    default_config = loader._create_default_config()
    
    typer.echo(f"✅ 配置文件已创建：{loader.config_path}")
    typer.echo(f"")
    typer.echo(f"请编辑配置文件，填写必要信息：")
    typer.echo(f"  - 企业微信配置：corp_id, agent_id, secret, token, encoding_aes_key")
    typer.echo(f"  - 用户配置：user_id")
    typer.echo(f"")
    typer.echo(f"配置文件位置：{loader.config_path}")
```

## 多机器人管理命令

### 1. list - 列出资源

**功能**：列出所有机器人和 tmux 会话

**用法**：
```bash
python manage.py list
```

**输出示例**：
```
============================================================
Ling-iflow 资源列表
============================================================

企业微信机器人 (共 2 个)
  
  1. bot1
    状态: 运行中 ✓
    回调端口: 8788
    tmux 会话: iflow1
    用户: 用户1
    
  2. bot2
    状态: 未运行
    回调端口: 8789
    tmux 会话: iflow2
    用户: 用户2

tmux 会话 (共 2 个)
  
  1. iflow1
    状态: 运行中 ✓
    工作目录: ~/.iflow1
    模型: kimi-k2.5
    
  2. iflow2
    状态: 未运行
    工作目录: ~/.iflow2
    模型: kimi-k2.5
```

### 2. start - 启动资源

**功能**：启动机器人或 tmux 会话

**用法**：
```bash
python manage.py start [OPTIONS]
```

**选项**：
- `-r, --robot TEXT`：启动机器人（名称或序号）
- `-t, --tmux TEXT`：启动 tmux 会话（名称或序号）
- `--all`：启动所有资源

**示例**：
```bash
# 启动机器人（使用序号）
python manage.py start -r 1

# 启动机器人（使用名称）
python manage.py start -r bot1

# 启动 tmux 会话（使用序号）
python manage.py start -t 1

# 启动 tmux 会话（使用名称）
python manage.py start -t iflow1

# 启动所有机器人
python manage.py start -r --all

# 启动所有 tmux 会话
python manage.py start -t --all
```

### 3. stop - 停止资源

**功能**：停止机器人或 tmux 会话

**用法**：
```bash
python manage.py stop [OPTIONS]
```

**选项**：
- `-r, --robot TEXT`：停止机器人（名称或序号）
- `-t, --tmux TEXT`：停止 tmux 会话（名称或序号）
- `--all`：停止所有资源

**示例**：
```bash
# 停止机器人（使用序号）
python manage.py stop -r 1

# 停止机器人（使用名称）
python manage.py stop -r bot1

# 停止 tmux 会话（使用序号）
python manage.py stop -t 1

# 停止 tmux 会话（使用名称）
python manage.py stop -t iflow1

# 停止所有机器人
python manage.py stop -r --all

# 停止所有 tmux 会话
python manage.py stop -t --all
```

### 4. restart - 重启资源

**功能**：重启机器人或 tmux 会话

**用法**：
```bash
python manage.py restart [OPTIONS]
```

**选项**：
- `-r, --robot TEXT`：重启机器人（名称或序号）
- `-t, --tmux TEXT`：重启 tmux 会话（名称或序号）

**示例**：
```bash
# 重启机器人
python manage.py restart -r 1

# 重启 tmux 会话
python manage.py restart -t 1
```

### 5. status - 查看状态

**功能**：查看服务状态

**用法**：
```bash
python manage.py status
```

**输出示例**：
```
============================================================
Ling-iflow 服务状态
============================================================

企业微信机器人 (共 2 个，运行中: 1)
  
  1. bot1 (PID: 12345)
    状态: 运行中 ✓
    回调端口: 8788
    tmux 会话: iflow1 ✓
    用户: 用户1
    
  2. bot2
    状态: 未运行
    回调端口: 8789
    tmux 会话: iflow2
    用户: 用户2

tmux 会话 (共 2 个，运行中: 1)
  
  1. iflow1
    状态: 运行中 ✓
    工作目录: ~/.iflow1
    模型: kimi-k2.5
    
  2. iflow2
    状态: 未运行
    工作目录: ~/.iflow2
    模型: kimi-k2.5
```

### 6. logs - 查看日志

**功能**：查看日志

**用法**：
```bash
python manage.py logs [OPTIONS]
```

**选项**：
- `-r, --robot TEXT`：查看机器人日志（名称或序号）
- `--all`：查看所有机器人日志
- `--follow`：实时跟踪日志

**示例**：
```bash
# 查看机器人日志
python manage.py logs -r 1
python manage.py logs -r bot1

# 查看所有机器人日志
python manage.py logs -r --all

# 实时跟踪日志
python manage.py logs -r 1 --follow
```

## 相关文档

- [设计总览](./01-设计总览.md) - 项目概述、整体架构、核心目标
- [架构设计](./02-架构设计.md) - 详细的架构设计
- [模块设计-Channels层](./03-模块设计-Channels层.md) - 渠道层的详细设计
- [模块设计-Interactive层](./04-模块设计-Interactive层.md) - 交互层的详细设计
- [模块设计-Config层](./05-模块设计-Config层.md) - 配置层的详细设计
- [多机器人管理](./10-多机器人管理.md) - 多机器人管理方案