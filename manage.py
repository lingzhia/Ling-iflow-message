#!/usr/bin/env python3
"""Ling-iflow 项目管理脚本。

提供统一的项目管理功能，包括：
- 启动/停止 iflow CLI
- 启动/停止企业微信 Bot
- 查看服务状态
- 重启服务
- 多机器人管理
"""

import asyncio
import os
import subprocess
import sys
import signal
import time
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import load_config as load_project_config
from config.bots_loader import load_bots_config
from config.schema import WechatWorkConfig
from interactive.iflow_controller import IFlowController
from utils.process_manager import ProcessManager



# 配置日志

LOG_DIR = PROJECT_ROOT / "logs"

LOG_DIR.mkdir(exist_ok=True)



# 移除默认日志处理器

logger.remove()



# 添加控制台日志

logger.add(

    sys.stderr,

    level="INFO",

    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"

)



# 添加文件日志

logger.add(

    LOG_DIR / "manage_{time:YYYY-MM-DD}.log",

    level="DEBUG",

    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",

    rotation="00:00",

    retention="7 days",

    encoding="utf-8"

)





# 颜色定义
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_BLUE = "\033[36m"
COLOR_CYAN = "\033[96m"


def print_header(title: str):
    """打印标题。"""
    print()
    print("=" * 70)
    print(f"{COLOR_CYAN}{title}{COLOR_RESET}")
    print("=" * 70)
    print()


def print_success(message: str):
    """打印成功消息。"""
    print(f"{COLOR_GREEN}[成功] {message}{COLOR_RESET}")


def print_warning(message: str):
    """打印警告消息。"""
    print(f"{COLOR_YELLOW}[警告] {message}{COLOR_RESET}")


def print_error(message: str):
    """打印错误消息。"""
    print(f"{COLOR_RED}[错误] {message}{COLOR_RESET}")


def print_info(message: str):
    """打印信息消息。"""
    print(f"{COLOR_BLUE}[信息] {message}{COLOR_RESET}")


def check_tmux_session(session_name: str) -> bool:
    """检查 tmux 会话是否存在。"""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def kill_process_by_name(process_name: str) -> bool:
    """根据进程名杀死进程。"""
    try:
        result = subprocess.run(
            ["pkill", "-f", process_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Failed to kill process: {e}")
        return False


app = typer.Typer(
    name="manage",
    help="Ling-iflow 项目管理工具",
    add_completion=False,
)


def load_config() -> dict:
    """加载配置。"""
    config_path = PROJECT_ROOT / "config.json"
    if not config_path.exists():
        print_error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    
    return load_project_config(config_path)


@app.command()
def start(
    index: Optional[int] = typer.Argument(None, help="序号（默认为1），启动对应序号的机器人和 tmux 会话"),
    iflow: bool = typer.Option(True, "--iflow/--no-iflow", help="启动 iflow CLI"),
    wechat: bool = typer.Option(True, "--wechat/--no-wechat", help="启动企业微信 Bot"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台模式：直接显示 iflow 界面"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="iflow 模型名称"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="iflow 工作目录"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细日志"),
):
    """启动服务。
    
    后台模式（默认）：服务在后台运行，返回命令行
    前台模式（--foreground）：直接显示 iflow 界面
    
    序号模式：指定序号启动对应序号的机器人和 tmux 会话（默认为1）
    """
    print_header("启动 Ling-iflow 服务")
    
    # 默认序号为1
    if index is None:
        index = 1
    
    print_info(f"操作序号: {index}")
    print()
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 加载主配置
    try:
        main_config = load_config()
    except Exception as e:
        print_error(f"加载主配置失败: {e}")
        sys.exit(1)
    
    # 获取对应序号的机器人和 tmux 会话
    bot_config = _resolve_bot(bots_config, str(index))
    tmux_config = _resolve_tmux_session(main_config, str(index))
    
    if not bot_config:
        print_error(f"机器人不存在: 序号 {index}")
        sys.exit(1)
    
    if not tmux_config:
        print_error(f"tmux 会话不存在: 序号 {index}")
        sys.exit(1)
    
    bot_name = bot_config.name
    tmux_session = tmux_config.get("name", "iflow")
    tmux_workspace = tmux_config.get("workspace", "~/.iflow")
    tmux_model = tmux_config.get("model", "kimi-k2.5")
    
    print_info(f"机器人: {bot_name}")
    print_info(f"tmux 会话: {tmux_session}")
    print()
    
    if foreground:
        print_info("前台模式：将直接显示 iflow 界面")
        print_info("退出方式：按 Ctrl+B 然后按 D 分离会话")
        print()
    
    # 更新工作目录（如果指定）
    if workspace:
        print_info(f"更新工作目录: {workspace}")
        tmux_workspace = workspace
        tmux_config["workspace"] = workspace
        print_success(f"工作目录已更新: {workspace}")
        print()
    
    if verbose:
        print_info(f"使用工作目录: {tmux_workspace}")
        print_info(f"使用模型: {tmux_model}")
        print()
    
    # 启动 iflow
    if iflow:
        print_info(f"检查 iflow CLI (tmux 会话: {tmux_session})...")
        
        if check_tmux_session(tmux_session):
            print_warning(f"iflow CLI 已在 tmux 会话 '{tmux_session}' 中运行")
        else:
            print_info(f"启动 iflow CLI...")
            
            model_arg = model if model else tmux_model
            cmd = f"iflow --model {model_arg}"
            
            try:
                # 检查 iflow 命令是否存在
                check_result = subprocess.run(
                    ["which", "iflow"],
                    capture_output=True,
                    text=True
                )
                
                if check_result.returncode != 0:
                    print_warning("未找到 iflow 命令，跳过 iflow 启动")
                    print_info("请先安装 iflow CLI: https://github.com/your-org/iflow")
                else:
                    subprocess.run(
                        ["tmux", "new-session", "-d", "-s", tmux_session, cmd],
                        check=True
                    )
                    print_success(f"iflow CLI 已启动 (tmux 会话: {tmux_session})")
                    
                    # 等待 iflow 启动
                    time.sleep(2)
            except subprocess.CalledProcessError as e:
                print_error(f"启动 iflow CLI 失败: {e}")
                sys.exit(1)
    else:
        print_info("跳过 iflow CLI 启动")
    
    # 前台模式：连接到 tmux 会话
    if foreground and iflow and check_tmux_session(tmux_session):
        print()
        print_info(f"正在连接到 tmux 会话 '{tmux_session}'...")
        print_info("按 Ctrl+B 然后按 D 可以分离会话")
        print()
        
        try:
            # 连接到 tmux 会话
            subprocess.run(["tmux", "attach-session", "-t", tmux_session])
        except KeyboardInterrupt:
            print()
            print_info("已从 iflow 界面分离")
        except Exception as e:
            print_error(f"连接 tmux 会话失败: {e}")
        
        # 如果在前台模式连接后，通常不继续启动企业微信 Bot
        # 因为用户可能想在 iflow 中工作
        print()
        return
    
    # 启动企业微信 Bot
    if wechat:
        print_info(f"检查企业微信 Bot ({bot_name})...")
        
        # 检查机器人是否已运行
        process_manager = ProcessManager(PROJECT_ROOT)
        if process_manager.is_running(bot_name):
            print_warning(f"企业微信 Bot 已在运行: {bot_name}")
        else:
            print_info(f"启动企业微信 Bot ({bot_name})...")
            
            try:
                pid = process_manager.start_bot(
                    bot_name=bot_name,
                    config_path="config.json",
                    daemon=True,
                    verbose=verbose
                )
                
                print_success(f"企业微信 Bot 已启动: {bot_name} (PID: {pid})")
            except Exception as e:
                print_error(f"启动企业微信 Bot 失败: {e}")
                sys.exit(1)
    else:
        print_info("跳过企业微信 Bot 启动")
    
    print()
    print_success("服务启动完成！")
    print()
    print_info(f"使用以下命令查看状态:")
    print(f"  {COLOR_CYAN}python manage.py status{COLOR_RESET}")
    print()


@app.command()
def stop(
    index: Optional[int] = typer.Argument(None, help="序号（默认为1），停止对应序号的机器人和 tmux 会话"),
    iflow: bool = typer.Option(True, "--iflow/--no-iflow", help="停止 iflow CLI"),
    wechat: bool = typer.Option(True, "--wechat/--no-wechat", help="停止企业微信 Bot"),
):
    """停止服务。
    
    序号模式：指定序号停止对应序号的机器人和 tmux 会话（默认为1）
    """
    print_header("停止 Ling-iflow 服务")
    
    # 默认序号为1
    if index is None:
        index = 1
    
    print_info(f"操作序号: {index}")
    print()
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 加载主配置
    try:
        main_config = load_config()
    except Exception as e:
        print_error(f"加载主配置失败: {e}")
        sys.exit(1)
    
    # 获取对应序号的机器人和 tmux 会话
    bot_config = _resolve_bot(bots_config, str(index))
    tmux_config = _resolve_tmux_session(main_config, str(index))
    
    if not bot_config:
        print_error(f"机器人不存在: 序号 {index}")
        sys.exit(1)
    
    if not tmux_config:
        print_error(f"tmux 会话不存在: 序号 {index}")
        sys.exit(1)
    
    bot_name = bot_config.name
    tmux_session = tmux_config.get("name", "iflow")
    
    print_info(f"机器人: {bot_name}")
    print_info(f"tmux 会话: {tmux_session}")
    print()
    
    # 停止企业微信 Bot
    if wechat:
        print_info(f"停止企业微信 Bot ({bot_name})...")
        
        process_manager = ProcessManager(PROJECT_ROOT)
        if process_manager.is_running(bot_name):
            if process_manager.stop_bot(bot_name):
                print_success(f"企业微信 Bot 已停止: {bot_name}")
            else:
                print_error(f"停止企业微信 Bot 失败: {bot_name}")
        else:
            print_warning(f"企业微信 Bot 未运行: {bot_name}")
    
    # 停止 iflow
    if iflow:
        print_info(f"停止 iflow CLI (tmux 会话: {tmux_session})...")
        
        if check_tmux_session(tmux_session):
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", tmux_session],
                    check=True
                )
                print_success(f"iflow CLI 已停止: {tmux_session}")
            except subprocess.CalledProcessError as e:
                print_error(f"停止 iflow CLI 失败: {e}")
        else:
            print_warning(f"iflow CLI 未运行: {tmux_session}")
    
    print()
    print_success("服务停止完成！")
    print()


@app.command()
def restart(
    index: Optional[int] = typer.Argument(None, help="序号（默认为1），重启对应序号的机器人和 tmux 会话"),
    iflow: bool = typer.Option(True, "--iflow/--no-iflow", help="重启 iflow CLI"),
    wechat: bool = typer.Option(True, "--wechat/--no-wechat", help="重启企业微信 Bot"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="iflow 模型名称"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="iflow 工作目录"),
):
    """重启服务。
    
    序号模式：指定序号重启对应序号的机器人和 tmux 会话（默认为1）
    """
    print_header("重启 Ling-iflow 服务")
    
    # 先停止
    stop(index, iflow=iflow, wechat=wechat)
    
    # 等待一下
    time.sleep(2)
    
    # 再启动
    start(index, iflow=iflow, wechat=wechat, model=model, workspace=workspace)


@app.command()
def status():
    """查看服务状态。"""
    print_header("Ling-iflow 服务状态")
    
    config = load_config()
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        bots_config = None
    except Exception as e:
        print_warning(f"加载机器人配置失败: {e}")
        bots_config = None
    
    # 显示机器人状态
    if bots_config and bots_config.bots:
        process_manager = ProcessManager(PROJECT_ROOT)
        running_bots = process_manager.list_running_bots()
        
        print_info(f"企业微信机器人 (共 {len(bots_config.bots)} 个，运行中: {len(running_bots)})")
        print()
        
        for i, bot in enumerate(bots_config.bots, 1):
            is_running = process_manager.is_running(bot.name)
            status = "运行中 ✓" if is_running else "未运行"
            
            # 检查 tmux 连接状态
            tmux_running = check_tmux_session(bot.tmux_session)
            tmux_status = "✓" if tmux_running else "✗"
            
            print(f"  {i}. {bot.name}")
            if is_running:
                pid = process_manager.get_pid(bot.name)
                print(f"    状态: {status} (PID: {pid})")
            else:
                print(f"    状态: {status}")
            
            print(f"    回调端口: {bot.callback_port}")
            print(f"    tmux 会话: {bot.tmux_session} {tmux_status}")
            print(f"    用户: {bot.user_id}")
            print()
    else:
        print_warning("未找到机器人配置")
        print()
    
    # 显示连接关系
    if bots_config and bots_config.bots:
        print_info(f"机器人与 tmux 会话连接关系")
        print()
        
        # 收集连接信息
        connections = {}
        for bot in bots_config.bots:
            connections[bot.name] = bot.tmux_session
        
        # 检查是否有冲突（多个机器人连接到同一个 tmux）
        tmux_to_bots = {}
        for bot_name, tmux_session in connections.items():
            if tmux_session not in tmux_to_bots:
                tmux_to_bots[tmux_session] = []
            tmux_to_bots[tmux_session].append(bot_name)
        
        # 显示连接关系
        for tmux_session, bot_names in tmux_to_bots.items():
            if len(bot_names) > 1:
                print_warning(f"  ⚠️  {tmux_session}: {', '.join(bot_names)} (多个机器人连接)")
            else:
                print_success(f"  ✓ {tmux_session}: {bot_names[0]}")
        print()
    
    # 显示 tmux 会话状态
    try:
        tmux_sessions = config.tmux_sessions if hasattr(config, 'tmux_sessions') else []
        
        # 兼容旧配置格式
        if not tmux_sessions and hasattr(config, 'tmux_session'):
            tmux_sessions = [{
                "name": config.tmux_session,
                "workspace": config.workspace,
                "model": config.model if hasattr(config, 'model') else "kimi-k2.5"
            }]
    except Exception as e:
        print_warning(f"加载配置失败: {e}")
        tmux_sessions = []
    
    print_info(f"tmux 会话 (共 {len(tmux_sessions)} 个，运行中: {sum(1 for s in tmux_sessions if check_tmux_session(s.get('name', 'iflow')))})")
    print()
    
    if not tmux_sessions:
        print_warning("  没有配置 tmux 会话")
    else:
        for i, session in enumerate(tmux_sessions, 1):
            session_name = session.get("name", "iflow")
            is_running = check_tmux_session(session_name)
            status = "运行中 ✓" if is_running else "未运行"
            
            print(f"  {i}. {session_name}")
            print(f"    状态: {status}")
            print(f"    工作目录: {session.get('workspace', '~/.iflow')}")
            print(f"    模型: {session.get('model', 'kimi-k2.5')}")
            print()


@app.command()
def logs(
    iflow: bool = typer.Option(False, "--iflow", help="查看 iflow 日志"),
    wechat: bool = typer.Option(False, "--wechat", help="查看企业微信 Bot 日志"),
    follow: bool = typer.Option(False, "--follow", "-f", help="实时跟踪日志"),
):
    """查看日志。"""
    if not iflow and not wechat:
        print_warning("请指定要查看的日志：--iflow 或 --wechat")
        return
    
    if iflow:
        print_info(f"查看 iflow CLI 日志 (tmux 会话: {load_config().tmux_session})")
        if follow:
            subprocess.run(["tmux", "attach-session", "-t", load_config().tmux_session])
        else:
            subprocess.run(["tmux", "capture-pane", "-t", load_config().tmux_session, "-p"])
    
    if wechat:
        print_info("查看企业微信 Bot 日志")
        # 检查日志文件
        log_files = [
            PROJECT_ROOT / "tests" / "wechat_messages.log",
            PROJECT_ROOT / "wechat_messages.log",
        ]
        
        for log_file in log_files:
            if log_file.exists():
                if follow:
                    subprocess.run(["tail", "-f", str(log_file)])
                else:
                    subprocess.run(["tail", "-n", "50", str(log_file)])
                break
        else:
            print_warning("未找到日志文件")


@app.command()
def clean():
    """清理临时文件和日志。"""
    print_header("清理临时文件")
    
    # 清理 __pycache__
    print_info("清理 __pycache__ 目录...")
    for root, dirs, files in os.walk(PROJECT_ROOT):
        for d in dirs:
            if d == "__pycache__":
                cache_dir = Path(root) / d
                try:
                    import shutil
                    shutil.rmtree(cache_dir)
                    print_success(f"  已删除: {cache_dir}")
                except Exception as e:
                    print_error(f"  删除失败: {cache_dir} - {e}")
    
    # 清理日志文件
    print_info("清理日志文件...")
    log_dirs = [
        PROJECT_ROOT / "logs",
        PROJECT_ROOT / "tests",
    ]
    
    for log_dir in log_dirs:
        if log_dir.exists():
            for log_file in log_dir.glob("*.log"):
                try:
                    log_file.unlink()
                    print_success(f"  已删除: {log_file}")
                except Exception as e:
                    print_error(f"  删除失败: {log_file} - {e}")
    
    print()
    print_success("清理完成！")
    print()


@app.command()
def tmux():
    """管理 tmux 会话。"""
    tmux_script = PROJECT_ROOT / "tmux_manager.py"
    
    if not tmux_script.exists():
        print_error(f"tmux 管理脚本不存在: {tmux_script}")
        return
    
    try:
        subprocess.run([sys.executable, str(tmux_script)])
    except Exception as e:
        print_error(f"运行 tmux 管理器失败: {e}")


@app.command()
def test():
    """运行测试。"""
    print_header("运行测试")
    
    tests_dir = PROJECT_ROOT / "tests"
    
    if not tests_dir.exists():
        print_error("tests 目录不存在")
        return
    
    # 列出测试文件
    test_files = sorted(tests_dir.glob("test_*.py"))
    
    if not test_files:
        print_warning("未找到测试文件")
        return
    
    print_info(f"找到 {len(test_files)} 个测试文件:")
    for i, test_file in enumerate(test_files, 1):
        print(f"  {i}. {test_file.name}")
    
    print()
    print_info("运行测试...")
    print()
    
    # 运行测试
    for test_file in test_files:
        print(f"{COLOR_CYAN}运行: {test_file.name}{COLOR_RESET}")
        try:
            subprocess.run(
                [sys.executable, str(test_file)],
                cwd=PROJECT_ROOT
            )
        except Exception as e:
            print_error(f"测试失败: {e}")
        print()


# ==================== 多机器人管理命令 ====================

@app.command()
def list_resources():
    """列出所有资源（机器人和 tmux 会话）。"""
    print_header("Ling-iflow 资源列表")
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_warning("机器人配置文件不存在: bots.json")
        return
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        return
    
    # 列出机器人
    print_info(f"企业微信机器人 (共 {len(bots_config.bots)} 个)")
    print()
    
    if not bots_config.bots:
        print_warning("  没有配置机器人")
    else:
        process_manager = ProcessManager(PROJECT_ROOT)
        
        for i, bot in enumerate(bots_config.bots, 1):
            is_running = process_manager.is_running(bot.name)
            status = "运行中 ✓" if is_running else "未运行"
            
            print(f"  {i}. {bot.name}")
            print(f"    状态: {status}")
            print(f"    回调端口: {bot.callback_port}")
            print(f"    tmux 会话: {bot.tmux_session}")
            print(f"    用户: {bot.user_id}")
            
            if is_running:
                pid = process_manager.get_pid(bot.name)
                print(f"    PID: {pid}")
            
            print()
    
    # 列出 tmux 会话
    try:
        config = load_config()
        tmux_sessions = config.tmux_sessions if hasattr(config, 'tmux_sessions') else []
        
        # 兼容旧配置格式
        if not tmux_sessions and hasattr(config, 'tmux_session'):
            tmux_sessions = [{
                "name": config.tmux_session,
                "workspace": config.workspace,
                "model": config.model if hasattr(config, 'model') else "kimi-k2.5"
            }]
    except Exception as e:
        print_error(f"加载配置失败: {e}")
        return
    
    print_info(f"tmux 会话 (共 {len(tmux_sessions)} 个)")
    print()
    
    if not tmux_sessions:
        print_warning("  没有配置 tmux 会话")
    else:
        for i, session in enumerate(tmux_sessions, 1):
            session_name = session.get("name", "iflow")
            is_running = check_tmux_session(session_name)
            status = "运行中 ✓" if is_running else "未运行"
            
            print(f"  {i}. {session_name}")
            print(f"    状态: {status}")
            print(f"    工作目录: {session.get('workspace', '~/.iflow')}")
            print(f"    模型: {session.get('model', 'kimi-k2.5')}")
            print()


@app.command()
def bot_start(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
    daemon: bool = typer.Option(True, "--foreground", help="前台模式（默认后台运行）"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细日志"),
):
    """启动机器人。"""
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 解析机器人参数
    bot_config = _resolve_bot(bots_config, bot)
    if not bot_config:
        print_error(f"机器人不存在: {bot}")
        sys.exit(1)
    
    if not bot_config.enabled:
        print_error(f"机器人未启用: {bot}")
        sys.exit(1)
    
    # 创建进程管理器
    process_manager = ProcessManager(PROJECT_ROOT)
    
    # 检查是否已运行
    if process_manager.is_running(bot_config.name):
        print_warning(f"机器人已在运行: {bot_config.name}")
        sys.exit(0)
    
    # 启动机器人
    print_info(f"正在启动机器人: {bot_config.name}")
    
    try:
        pid = process_manager.start_bot(
            bot_name=bot_config.name,
            config_path="config.json",
            daemon=daemon,
            verbose=verbose
        )
        
        print_success(f"机器人已启动: {bot_config.name} (PID: {pid})")
        
        if daemon:
            print_info(f"使用以下命令查看日志:")
            print(f"  {COLOR_CYAN}python manage.py logs -r {bot_config.name}{COLOR_RESET}")
    except Exception as e:
        print_error(f"启动机器人失败: {e}")
        sys.exit(1)


@app.command()
def bot_stop(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
):
    """停止机器人。"""
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 解析机器人参数
    bot_config = _resolve_bot(bots_config, bot)
    if not bot_config:
        print_error(f"机器人不存在: {bot}")
        sys.exit(1)
    
    # 创建进程管理器
    process_manager = ProcessManager(PROJECT_ROOT)
    
    # 检查是否运行
    if not process_manager.is_running(bot_config.name):
        print_warning(f"机器人未运行: {bot_config.name}")
        sys.exit(0)
    
    # 停止机器人
    print_info(f"正在停止机器人: {bot_config.name}")
    
    if process_manager.stop_bot(bot_config.name):
        print_success(f"机器人已停止: {bot_config.name}")
    else:
        print_error(f"停止机器人失败: {bot_config.name}")
        sys.exit(1)


@app.command()
def bind(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
    tmux: str = typer.Argument(..., help="tmux 会话名称或序号"),
    force: bool = typer.Option(False, "--force", "-f", help="强制停止正在运行的机器人和 tmux 会话"),
):
    """绑定机器人与 tmux 会话。
    
    调整机器人与 tmux 的连接关系。如果机器人或 tmux 正在运行，
    会先停止它们，然后更新配置。
    """
    print_header("绑定机器人与 tmux 会话")
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 加载主配置
    try:
        main_config = load_config()
    except Exception as e:
        print_error(f"加载主配置失败: {e}")
        sys.exit(1)
    
    # 解析机器人参数
    bot_config = _resolve_bot(bots_config, bot)
    if not bot_config:
        print_error(f"机器人不存在: {bot}")
        sys.exit(1)
    
    # 解析 tmux 会话参数
    tmux_config = _resolve_tmux_session(main_config, tmux)
    if not tmux_config:
        print_error(f"tmux 会话不存在: {tmux}")
        sys.exit(1)
    
    tmux_session_name = tmux_config.get("name", "iflow")
    
    print_info(f"机器人: {bot_config.name}")
    print_info(f"tmux 会话: {tmux_session_name}")
    print()
    
    # 检查当前连接关系
    current_tmux = bot_config.tmux_session
    if current_tmux == tmux_session_name:
        print_warning(f"机器人已连接到此 tmux 会话: {tmux_session_name}")
        return
    
    print_info(f"当前连接: {bot_config.name} → {current_tmux}")
    print_info(f"目标连接: {bot_config.name} → {tmux_session_name}")
    print()
    
    # 检查目标 tmux 是否已有其他机器人连接
    existing_bot = None
    for b in bots_config.bots:
        if b.tmux_session == tmux_session_name and b.name != bot_config.name:
            existing_bot = b
            break
    
    if existing_bot:
        print_warning(f"检测到已有连接: {existing_bot.name} → {tmux_session_name}")
        print_info(f"将断开旧连接: {existing_bot.name} → {tmux_session_name}")
        
        # 检查旧连接的机器人是否在运行
        process_manager = ProcessManager(PROJECT_ROOT)
        if process_manager.is_running(existing_bot.name):
            print_info(f"  正在停止机器人: {existing_bot.name}")
            if not process_manager.stop_bot(existing_bot.name):
                print_error(f"停止机器人失败: {existing_bot.name}")
                sys.exit(1)
            time.sleep(1)
        
        # 断开旧连接（设置为空字符串）
        existing_bot.tmux_session = ""
        print_success(f"已断开连接: {existing_bot.name}")
        print()
    
    # 检查是否正在运行
    bot_running = process_manager.is_running(bot_config.name)
    tmux_running = check_tmux_session(tmux_session_name)
    
    if bot_running or tmux_running:
        if not force:
            print_warning("机器人或 tmux 会话正在运行")
            print_info("使用 --force 参数强制停止")
            print()
            print(f"  机器人运行中: {'是' if bot_running else '否'}")
            print(f"  tmux 会话运行中: {'是' if tmux_running else '否'}")
            sys.exit(1)
        
        print_info("正在停止运行中的服务...")
        
        # 停止机器人
        if bot_running:
            print_info(f"  停止机器人: {bot_config.name}")
            if not process_manager.stop_bot(bot_config.name):
                print_error(f"停止机器人失败: {bot_config.name}")
                sys.exit(1)
            time.sleep(1)
        
        # 停止 tmux 会话
        if tmux_running:
            print_info(f"  停止 tmux 会话: {tmux_session_name}")
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", tmux_session_name],
                    check=True,
                    capture_output=True
                )
            except subprocess.CalledProcessError as e:
                print_error(f"停止 tmux 会话失败: {e}")
                sys.exit(1)
            time.sleep(1)
        
        print_success("服务已停止")
        print()
    
    # 更新配置
    print_info("更新机器人配置...")
    
    # 更新机器人的 tmux_session
    bot_config.tmux_session = tmux_session_name
    
    # 保存配置
    try:
        from config.bots_loader import save_bots_config
        save_bots_config(bots_config)
        print_success("配置已保存")
    except Exception as e:
        print_error(f"保存配置失败: {e}")
        sys.exit(1)
    
    print()
    print_success(f"绑定完成: {bot_config.name} → {tmux_session_name}")
    print()
    print_info(f"使用以下命令启动机器人:")
    print(f"  {COLOR_CYAN}python manage.py bot-start {bot_config.name}{COLOR_RESET}")
    print()


@app.command()
def bot_restart(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
    daemon: bool = typer.Option(True, "--foreground", help="前台模式（默认后台运行）"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细日志"),
):
    """重启机器人。"""
    # 停止
    bot_stop(bot)
    
    # 等待一下
    time.sleep(2)
    
    # 启动
    bot_start(bot, daemon=daemon, verbose=verbose)


@app.command()
def bot_logs(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
    follow: bool = typer.Option(False, "--follow", "-f", help="实时跟踪日志"),
):
    """查看机器人日志。"""
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 解析机器人参数
    bot_config = _resolve_bot(bots_config, bot)
    if not bot_config:
        print_error(f"机器人不存在: {bot}")
        sys.exit(1)
    
    # 查找日志文件
    log_files = sorted((LOG_DIR / "logs").glob(f"wechat_bot_{bot_config.name}_*.log"), reverse=True)
    
    if not log_files:
        print_warning("未找到日志文件")
        return
    
    log_file = log_files[0]
    print_info(f"查看日志文件: {log_file.name}")
    
    if follow:
        subprocess.run(["tail", "-f", str(log_file)])
    else:
        subprocess.run(["tail", "-n", "50", str(log_file)])


# ==================== 机器人管理命令 ====================

@app.command()
def bot_add(
    name: str = typer.Option(..., "--name", "-n", help="机器人名称"),
    corp_id: str = typer.Option(..., "--corp-id", help="企业 ID"),
    agent_id: str = typer.Option(..., "--agent-id", help="应用 AgentId"),
    secret: str = typer.Option(..., "--secret", help="应用 Secret"),
    user_id: str = typer.Option(..., "--user-id", help="用户 ID"),
    token: str = typer.Option("", "--token", help="Token"),
    encoding_aes_key: str = typer.Option("", "--encoding-aes-key", help="EncodingAESKey"),
    callback_port: int = typer.Option(8788, "--callback-port", "-p", help="回调端口"),
    tmux_session: str = typer.Option("", "--tmux-session", "-t", help="tmux 会话名称"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="交互式添加"),
):
    """添加机器人。"""
    print_header("添加机器人")
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 检查机器人名称是否已存在
    if not interactive:
        if bots_config.get_bot_by_name(name):
            print_error(f"机器人名称已存在: {name}")
            sys.exit(1)
    else:
        # 交互式模式
        print_info("交互式添加机器人")
        print()
        
        if bots_config.get_bot_by_name(name):
            print_warning(f"机器人名称已存在: {name}")
            return
    
    # 如果是交互式模式，提示用户输入必需参数
    if interactive:
        print_info("请输入机器人配置：")
        print()
        
        if not name:
            name = input("机器人名称: ").strip()
            if not name:
                print_error("机器人名称不能为空")
                sys.exit(1)
        
        if not corp_id:
            corp_id = input("企业 ID: ").strip()
        
        if not agent_id:
            agent_id = input("应用 AgentId: ").strip()
        
        if not secret:
            secret = input("应用 Secret: ").strip()
        
        if not user_id:
            user_id = input("用户 ID: ").strip()
        
        token = input("Token (可选，留空跳过): ").strip()
        encoding_aes_key = input("EncodingAESKey (可选，留空跳过): ").strip()
        
        callback_port_str = input(f"回调端口 (默认 {callback_port}): ").strip()
        if callback_port_str:
            try:
                callback_port = int(callback_port_str)
            except ValueError:
                print_error("回调端口必须是数字")
                sys.exit(1)
        
        tmux_session = input(f"tmux 会话名称 (可选，留空跳过): ").strip()
        
        print()
    
    # 验证必需参数
    if not corp_id:
        print_error("企业 ID 不能为空")
        sys.exit(1)
    
    if not agent_id:
        print_error("应用 AgentId 不能为空")
        sys.exit(1)
    
    if not secret:
        print_error("应用 Secret 不能为空")
        sys.exit(1)
    
    if not user_id:
        print_error("用户 ID 不能为空")
        sys.exit(1)
    
    # 创建新机器人配置
    from config.bots_schema import BotConfig
    
    new_bot = BotConfig(
        name=name,
        enabled=True,
        corp_id=corp_id,
        agent_id=agent_id,
        secret=secret,
        user_id=user_id,
        token=token,
        encoding_aes_key=encoding_aes_key,
        callback_host="0.0.0.0",
        callback_port=callback_port,
        stream_mode=False,
        poll_interval=5,
        allow_from=[],
        group_policy="mention",
        group_allow_from=[],
        tmux_session=tmux_session or f"iflow{name[-1:]}"  # 如果未指定，使用 iflow + 序号
    )
    
    # 添加到配置
    bots_config.bots.append(new_bot)
    
    # 保存配置
    try:
        from config.bots_loader import save_bots_config
        save_bots_config(bots_config)
        print_success(f"机器人已添加: {name}")
        print()
        print_info(f"使用以下命令启动机器人:")
        print(f"  {COLOR_CYAN}python manage.py bot-start {name}{COLOR_RESET}")
    except Exception as e:
        print_error(f"保存配置失败: {e}")
        sys.exit(1)


@app.command()
def bot_remove(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除（不确认）"),
):
    """删除机器人。"""
    print_header("删除机器人")
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 解析机器人参数
    bot_config = _resolve_bot(bots_config, bot)
    if not bot_config:
        print_error(f"机器人不存在: {bot}")
        sys.exit(1)
    
    bot_name = bot_config.name
    
    # 检查机器人是否在运行
    process_manager = ProcessManager(PROJECT_ROOT)
    if process_manager.is_running(bot_name):
        print_warning(f"机器人正在运行: {bot_name}")
        print_info("请先停止机器人，或使用 --force 参数强制删除")
        sys.exit(1)
    
    # 确认删除
    if not force:
        print_warning(f"确认删除机器人: {bot_name}?")
        print_info(f"此操作将永久删除机器人配置，无法恢复")
        print_info(f"请输入 'yes' 确认删除，或按 Ctrl+C 取消")
        
        confirm = input(f"\n确认删除 [{bot_name}]: ").strip()
        if confirm.lower() != 'yes':
            print_info("已取消删除")
            return
    
    # 从配置中移除
    bots_config.bots.remove(bot_config)
    
    # 保存配置
    try:
        from config.bots_loader import save_bots_config
        save_bots_config(bots_config)
        print_success(f"机器人已删除: {bot_name}")
    except Exception as e:
        print_error(f"保存配置失败: {e}")
        sys.exit(1)


@app.command()
def bot_edit(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="新机器人名称"),
    corp_id: Optional[str] = typer.Option(None, "--corp-id", help="新企业 ID"),
    agent_id: Optional[str] = typer.Option(None, "--agent-id", help="新应用 AgentId"),
    secret: Optional[str] = typer.Option(None, "--secret", help="新应用 Secret"),
    user_id: Optional[str] = typer.Option(None, "--user-id", help="新用户 ID"),
    token: Optional[str] = typer.Option(None, "--token", help="新 Token"),
    encoding_aes_key: Optional[str] = typer.Option(None, "--encoding-aes-key", help="新 EncodingAESKey"),
    callback_port: Optional[int] = typer.Option(None, "--callback-port", "-p", help="新回调端口"),
    tmux_session: Optional[str] = typer.Option(None, "--tmux-session", "-t", help="新 tmux 会话"),
    enabled: Optional[bool] = typer.Option(None, "--enabled/--disabled", help="启用/禁用机器人"),
):
    """编辑机器人。"""
    print_header("编辑机器人")
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 解析机器人参数
    bot_config = _resolve_bot(bots_config, bot)
    if not bot_config:
        print_error(f"机器人不存在: {bot}")
        sys.exit(1)
    
    bot_name = bot_config.name
    
    # 显示当前配置
    print_info(f"机器人: {bot_name}")
    print()
    print(f"  名称: {bot_config.name}")
    print(f"  状态: {'启用' if bot_config.enabled else '禁用'}")
    print(f"  企业 ID: {bot_config.corp_id}")
    print(f"  应用 ID: {bot_config.agent_id}")
    print(f"  用户 ID: {bot_config.user_id}")
    print(f"  回调端口: {bot_config.callback_port}")
    print(f"  tmux 会话: {bot_config.tmux_session}")
    print()
    
    # 更新配置
    updated = False
    
    if name is not None and name != bot_config.name:
        # 检查新名称是否已存在
        if bots_config.get_bot_by_name(name) and name != bot_config.name:
            print_error(f"机器人名称已存在: {name}")
            sys.exit(1)
        bot_config.name = name
        updated = True
    
    if corp_id is not None:
        bot_config.corp_id = corp_id
        updated = True
    
    if agent_id is not None:
        bot_config.agent_id = agent_id
        updated = True
    
    if secret is not None:
        bot_config.secret = secret
        updated = True
    
    if user_id is not None:
        bot_config.user_id = user_id
        updated = True
    
    if token is not None:
        bot_config.token = token
        updated = True
    
    if encoding_aes_key is not None:
        bot_config.encoding_aes_key = encoding_aes_key
        updated = True
    
    if callback_port is not None:
        bot_config.callback_port = callback_port
        updated = True
    
    if tmux_session is not None:
        bot_config.tmux_session = tmux_session
        updated = True
    
    if enabled is not None:
        bot_config.enabled = enabled
        updated = True
    
    if not updated:
        print_warning("没有配置被更新")
        return
    
    # 保存配置
    try:
        from config.bots_loader import save_bots_config
        save_bots_config(bots_config)
        print_success(f"机器人配置已更新: {bot_name}")
    except Exception as e:
        print_error(f"保存配置失败: {e}")
        sys.exit(1)


@app.command()
def bot_show(
    bot: str = typer.Argument(..., help="机器人名称或序号"),
):
    """查看机器人详情。"""
    print_header("机器人详情")
    
    # 加载机器人配置
    try:
        bots_config = load_bots_config()
    except FileNotFoundError:
        print_error("机器人配置文件不存在: bots.json")
        sys.exit(1)
    except Exception as e:
        print_error(f"加载机器人配置失败: {e}")
        sys.exit(1)
    
    # 解析机器人参数
    bot_config = _resolve_bot(bots_config, bot)
    if not bot_config:
        print_error(f"机器人不存在: {bot}")
        sys.exit(1)
    
    # 显示机器人详情
    print_info(f"名称: {bot_config.name}")
    print(f"  状态: {'启用' if bot_config.enabled else '禁用'}")
    print()
    print(f"企业微信配置:")
    print(f"  企业 ID: {bot_config.corp_id}")
    print(f"  应用 ID: {bot_config.agent_id}")
    print(f"  用户 ID: {bot_config.user_id}")
    print()
    print(f"回调配置:")
    print(f"  回调端口: {bot_config.callback_port}")
    print(f"  回调地址: {bot_config.callback_host}")
    print(f"  Token: {'已配置' if bot_config.token else '未配置'}")
    print(f"  EncodingAESKey: {'已配置' if bot_config.encoding_aes_key else '未配置'}")
    print()
    print(f"其他配置:")
    print(f"  tmux 会话: {bot_config.tmux_session}")
    print(f"  流模式: {'启用' if bot_config.stream_mode else '禁用'}")
    print(f"  轮询间隔: {bot_config.poll_interval} 秒")
    print(f"  群聊策略: {bot_config.group_policy}")
    print()
    
    # 检查运行状态
    process_manager = ProcessManager(PROJECT_ROOT)
    is_running = process_manager.is_running(bot_config.name)
    
    print(f"运行状态:")
    if is_running:
        pid = process_manager.get_pid(bot_config.name)
        print(f"  状态: 运行中 ✓")
        print(f"  PID: {pid}")
    else:
        print(f"  状态: 未运行")
    print()


# ==================== tmux 会话管理命令 ====================

@app.command()
def tmux_add(
    name: str = typer.Option(..., "--name", "-n", help="会话名称"),
    workspace: str = typer.Option(..., "--workspace", "-w", help="工作目录"),
    model: str = typer.Option("kimi-k2.5", "--model", "-m", help="模型名称"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="交互式添加"),
):
    """添加 tmux 会话。"""
    print_header("添加 tmux 会话")
    
    # 加载主配置
    try:
        main_config = load_config()
    except Exception as e:
        print_error(f"加载主配置失败: {e}")
        sys.exit(1)
    
    # 确保有 tmux_sessions 属性
    if not hasattr(main_config, 'tmux_sessions'):
        main_config.tmux_sessions = []
    
    # 检查会话名称是否已存在
    if not interactive:
        for session in main_config.tmux_sessions:
            if session.get("name") == name:
                print_error(f"tmux 会话名称已存在: {name}")
                sys.exit(1)
    else:
        # 交互式模式
        print_info("交互式添加 tmux 会话")
        print()
        
        if not name:
            name = input("会话名称: ").strip()
            if not name:
                print_error("会话名称不能为空")
                sys.exit(1)
            
            # 检查名称是否已存在
            for session in main_config.tmux_sessions:
                if session.get("name") == name:
                    print_warning(f"会话名称已存在: {name}")
                    return
        
        if not workspace:
            workspace = input("工作目录 (例如 ~/.iflow): ").strip()
        
        model_input = input(f"模型名称 (默认 {model}): ").strip()
        if model_input:
            model = model_input
        
        print()
    
    # 验证必需参数
    if not name:
        print_error("会话名称不能为空")
        sys.exit(1)
    
    if not workspace:
        print_error("工作目录不能为空")
        sys.exit(1)
    
    # 创建新 tmux 会话配置
    new_session = {
        "name": name,
        "workspace": workspace,
        "model": model
    }
    
    # 添加到配置
    main_config.tmux_sessions.append(new_session)
    
    # 保存配置
    try:
        from config.loader import save_config
        save_config(main_config, PROJECT_ROOT / "config.json")
        print_success(f"tmux 会话已添加: {name}")
        print()
        print_info(f"使用以下命令启动:")
        print(f"  {COLOR_CYAN}python manage.py start 2{COLOR_RESET}")
    except Exception as e:
        print_error(f"保存配置失败: {e}")
        sys.exit(1)


@app.command()
def tmux_remove(
    session: str = typer.Argument(..., help="会话名称或序号"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除（不确认）"),
):
    """删除 tmux 会话。"""
    print_header("删除 tmux 会话")
    
    # 加载主配置
    try:
        main_config = load_config()
    except Exception as e:
        print_error(f"加载主配置失败: {e}")
        sys.exit(1)
    
    # 确保有 tmux_sessions 属性
    if not hasattr(main_config, 'tmux_sessions'):
        print_error("没有配置的 tmux 会话")
        sys.exit(1)
    
    # 解析会话参数
    session_config = _resolve_tmux_session(main_config, session)
    if not session_config:
        print_error(f"tmux 会话不存在: {session}")
        sys.exit(1)
    
    session_name = session_config.get("name", "iflow")
    
    # 检查会话是否在运行
    if check_tmux_session(session_name):
        print_warning(f"tmux 会话正在运行: {session_name}")
        print_info("请先停止会话，或使用 --force 参数强制删除")
        print_info(f"停止命令: tmux kill-session -t {session_name}")
        sys.exit(1)
    
    # 检查是否有机器人连接到此会话
    try:
        bots_config = load_bots_config()
        connected_bots = []
        for bot in bots_config.bots:
            if bot.tmux_session == session_name:
                connected_bots.append(bot.name)
        
        if connected_bots and not force:
            print_warning(f"以下机器人连接到此会话: {', '.join(connected_bots)}")
            print_info("请先断开连接，或使用 --force 参数强制删除")
            sys.exit(1)
        elif connected_bots and force:
            print_info(f"正在断开机器人连接: {', '.join(connected_bots)}")
            for bot in bots_config.bots:
                if bot.tmux_session == session_name:
                    bot.tmux_session = ""
            
            # 保存机器人配置
            try:
                from config.bots_loader import save_bots_config
                save_bots_config(bots_config)
                print_success("已断开机器人连接")
            except Exception as e:
                print_error(f"保存机器人配置失败: {e}")
                sys.exit(1)
    except FileNotFoundError:
        pass  # 忽略机器人配置不存在的情况
    
    # 确认删除
    if not force:
        print_warning(f"确认删除 tmux 会话: {session_name}?")
        print_info(f"此操作将永久删除会话配置，无法恢复")
        print_info(f"请输入 'yes' 确认删除，或按 Ctrl+C 取消")
        
        confirm = input(f"\n确认删除 [{session_name}]: ").strip()
        if confirm.lower() != 'yes':
            print_info("已取消删除")
            return
    
    # 从配置中移除
    main_config.tmux_sessions.remove(session_config)
    
    # 保存配置
    try:
        from config.loader import save_config
        save_config(main_config, PROJECT_ROOT / "config.json")
        print_success(f"tmux 会话已删除: {session_name}")
    except Exception as e:
        print_error(f"保存配置失败: {e}")
        sys.exit(1)


@app.command()
def tmux_edit(
    session: str = typer.Argument(..., help="会话名称或序号"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="新会话名称"),
    workspace: Optional[str] = typer.Option(None, "--workspace", "-w", help="新工作目录"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="新模型名称"),
):
    """编辑 tmux 会话。"""
    print_header("编辑 tmux 会话")
    
    # 加载主配置
    try:
        main_config = load_config()
    except Exception as e:
        print_error(f"加载主配置失败: {e}")
        sys.exit(1)
    
    # 确保有 tmux_sessions 属性
    if not hasattr(main_config, 'tmux_sessions'):
        print_error("没有配置的 tmux 会话")
        sys.exit(1)
    
    # 解析会话参数
    session_config = _resolve_tmux_session(main_config, session)
    if not session_config:
        print_error(f"tmux 会话不存在: {session}")
        sys.exit(1)
    
    session_name = session_config.get("name", "iflow")
    
    # 显示当前配置
    print_info(f"tmux 会话: {session_name}")
    print()
    print(f"  名称: {session_config.get('name', 'iflow')}")
    print(f"  工作目录: {session_config.get('workspace', '~/.iflow')}")
    print(f"  模型: {session_config.get('model', 'kimi-k2.5')}")
    print()
    
    # 更新配置
    updated = False
    
    if name is not None and name != session_config.get("name"):
        # 检查新名称是否已存在
        for s in main_config.tmux_sessions:
            if s.get("name") == name and s != session_config:
                print_error(f"会话名称已存在: {name}")
                sys.exit(1)
        session_config["name"] = name
        updated = True
    
    if workspace is not None:
        session_config["workspace"] = workspace
        updated = True
    
    if model is not None:
        session_config["model"] = model
        updated = True
    
    if not updated:
        print_warning("没有配置被更新")
        return
    
    # 保存配置
    try:
        from config.loader import save_config
        save_config(main_config, PROJECT_ROOT / "config.json")
        print_success(f"tmux 会话配置已更新: {session_name}")
    except Exception as e:
        print_error(f"保存配置失败: {e}")
        sys.exit(1)


@app.command()
def tmux_show(
    session: str = typer.Argument(..., help="会话名称或序号"),
):
    """查看 tmux 会话详情。"""
    print_header("tmux 会话详情")
    
    # 加载主配置
    try:
        main_config = load_config()
    except Exception as e:
        print_error(f"加载主配置失败: {e}")
        sys.exit(1)
    
    # 确保有 tmux_sessions 属性
    if not hasattr(main_config, 'tmux_sessions'):
        print_error("没有配置的 tmux 会话")
        sys.exit(1)
    
    # 解析会话参数
    session_config = _resolve_tmux_session(main_config, session)
    if not session_config:
        print_error(f"tmux 会话不存在: {session}")
        sys.exit(1)
    
    session_name = session_config.get("name", "iflow")
    
    # 显示会话详情
    print_info(f"名称: {session_name}")
    print(f"  工作目录: {session_config.get('workspace', '~/.iflow')}")
    print(f"  模型: {session_config.get('model', 'kimi-k2.5')}")
    print()
    
    # 检查运行状态
    is_running = check_tmux_session(session_name)
    
    print(f"运行状态:")
    if is_running:
        print(f"  状态: 运行中 ✓")
    else:
        print(f"  状态: 未运行")
    print()
    
    # 查找连接到此会话的机器人
    try:
        bots_config = load_bots_config()
        connected_bots = []
        for bot in bots_config.bots:
            if bot.tmux_session == session_name:
                connected_bots.append(bot.name)
        
        if connected_bots:
            print(f"连接的机器人:")
            for bot_name in connected_bots:
                process_manager = ProcessManager(PROJECT_ROOT)
                bot_running = process_manager.is_running(bot_name)
                status = "运行中 ✓" if bot_running else "未运行"
                print(f"  - {bot_name} ({status})")
        else:
            print(f"连接的机器人: 无")
    except FileNotFoundError:
        print(f"连接的机器人: 未知（配置文件不存在）")
    print()


# ==================== 辅助函数 ====================

def _resolve_bot(bots_config, bot: str):
    """解析机器人参数（序号或名称）。
    
    Args:
        bots_config: 机器人配置
        bot: 机器人序号或名称
        
    Returns:
        机器人配置，如果不存在返回 None
    """
    # 尝试按序号查找
    try:
        index = int(bot) - 1
        if 0 <= index < len(bots_config.bots):
            return bots_config.bots[index]
    except ValueError:
        pass
    
    # 尝试按名称查找
    return bots_config.get_bot_by_name(bot)


def _resolve_tmux_session(config, session: str):
    """解析 tmux 会话参数（序号或名称）。
    
    Args:
        config: 配置对象
        session: tmux 会话序号或名称
        
    Returns:
        tmux 会话配置，如果不存在返回 None
    """
    tmux_sessions = config.tmux_sessions if hasattr(config, 'tmux_sessions') else []
    
    # 兼容旧配置格式
    if not tmux_sessions and hasattr(config, 'tmux_session'):
        tmux_sessions = [{
            "name": config.tmux_session,
            "workspace": config.workspace,
            "model": config.model if hasattr(config, 'model') else "kimi-k2.5"
        }]
    
    # 尝试按序号查找
    try:
        index = int(session) - 1
        if 0 <= index < len(tmux_sessions):
            return tmux_sessions[index]
    except ValueError:
        pass
    
    # 尝试按名称查找
    for s in tmux_sessions:
        if s.get("name") == session:
            return s
    
    return None


def main():
    """主函数。"""
    try:
        app()
    except KeyboardInterrupt:
        print()
        print_warning("操作已取消")
        sys.exit(0)
    except Exception as e:
        print_error(f"发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()