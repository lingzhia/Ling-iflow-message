#!/usr/bin/env python3
"""Ling-iflow 项目管理脚本。

提供统一的项目管理功能，包括：
- 启动/停止 iflow CLI
- 启动/停止企业微信 Bot
- 查看服务状态
- 重启服务
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

from config.schema import WechatWorkConfig

from interactive.iflow_controller import IFlowController



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
    """
    print_header("启动 Ling-iflow 服务")
    
    if foreground:
        print_info("前台模式：将直接显示 iflow 界面")
        print_info("退出方式：按 Ctrl+B 然后按 D 分离会话")
        print()
    
    config = load_config()
    tmux_session = config.tmux_session
    config_path = PROJECT_ROOT / "config.json"
    
    # 更新工作目录（如果指定）
    if workspace:
        print_info(f"更新工作目录: {workspace}")
        config.workspace = workspace
        
        # 保存配置（使用原子写入）
        try:
            from config.loader import save_config
            save_config(config, config_path)
            print_success(f"工作目录已保存到配置文件")
        except Exception as e:
            print_error(f"保存配置失败: {e}")
            sys.exit(1)
    
    workspace = config.workspace
    
    if verbose:
        print_info(f"使用工作目录: {workspace}")
        print()
    
    # 启动 iflow
    if iflow:
        print_info(f"检查 iflow CLI (tmux 会话: {tmux_session})...")
        
        if check_tmux_session(tmux_session):
            print_warning(f"iflow CLI 已在 tmux 会话 '{tmux_session}' 中运行")
        else:
            print_info(f"启动 iflow CLI...")
            
            model_arg = model if model else config.model
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
        print_info(f"检查企业微信 Bot...")
        
        if config.wechat_work and config.wechat_work.enabled:
            # 检查进程是否已运行
            result = subprocess.run(
                ["pgrep", "-f", "wechat_bot.py"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print_warning("企业微信 Bot 已在运行")
            else:
                print_info("启动企业微信 Bot...")
                
                bot_script = PROJECT_ROOT / "wechat_bot.py"
                if not bot_script.exists():
                    print_error(f"Bot 脚本不存在: {bot_script}")
                    sys.exit(1)
                
                # 启动 bot
                cmd = [sys.executable, str(bot_script), "--config", str(config_path)]
                if verbose:
                    cmd.append("--verbose")
                
                try:
                    # 在后台启动
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    
                    time.sleep(2)
                    
                    # 检查进程是否仍在运行
                    if process.poll() is None:
                        print_success("企业微信 Bot 已启动")
                    else:
                        print_error("企业微信 Bot 启动失败")
                        sys.exit(1)
                except Exception as e:
                    print_error(f"启动企业微信 Bot 失败: {e}")
                    sys.exit(1)
        else:
            print_warning("企业微信未启用")
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
    iflow: bool = typer.Option(True, "--iflow/--no-iflow", help="停止 iflow CLI"),
    wechat: bool = typer.Option(True, "--wechat/--no-wechat", help="停止企业微信 Bot"),
):
    """停止服务。"""
    print_header("停止 Ling-iflow 服务")
    
    config = load_config()
    tmux_session = config.tmux_session
    
    # 停止企业微信 Bot
    if wechat:
        print_info("停止企业微信 Bot...")
        
        if kill_process_by_name("wechat_bot.py"):
            print_success("企业微信 Bot 已停止")
        else:
            print_warning("企业微信 Bot 未运行或停止失败")
    
    # 停止 iflow
    if iflow:
        print_info(f"停止 iflow CLI (tmux 会话: {tmux_session})...")
        
        if check_tmux_session(tmux_session):
            try:
                subprocess.run(
                    ["tmux", "kill-session", "-t", tmux_session],
                    check=True
                )
                print_success(f"iflow CLI 已停止")
            except subprocess.CalledProcessError as e:
                print_error(f"停止 iflow CLI 失败: {e}")
        else:
            print_warning(f"iflow CLI 未运行")
    
    print()
    print_success("服务停止完成！")
    print()


@app.command()
def restart(
    iflow: bool = typer.Option(True, "--iflow/--no-iflow", help="重启 iflow CLI"),
    wechat: bool = typer.Option(True, "--wechat/--no-wechat", help="重启企业微信 Bot"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="iflow 模型名称"),
):
    """重启服务。"""
    print_header("重启 Ling-iflow 服务")
    
    # 先停止
    stop(iflow=iflow, wechat=wechat)
    
    # 等待一下
    time.sleep(2)
    
    # 再启动
    start(iflow=iflow, wechat=wechat, model=model)


@app.command()
def status():
    """查看服务状态。"""
    print_header("Ling-iflow 服务状态")
    
    config = load_config()
    tmux_session = config.tmux_session
    
    # 检查 iflow
    print_info(f"iflow CLI (tmux 会话: {tmux_session})")
    if check_tmux_session(tmux_session):
        print_success("  运行中")
        
        # 尝试获取更多信息
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", tmux_session, "-p"],
                capture_output=True,
                text=True
            )
            output = result.stdout
            
            # 检查是否有模型信息
            if "model" in output.lower():
                for line in output.split('\n'):
                    if 'model' in line.lower() and '--model' in line:
                        print(f"  {COLOR_CYAN}{line.strip()}{COLOR_RESET}")
                        break
        except Exception:
            pass
    else:
        print_warning("  未运行")
    
    # 检查企业微信 Bot
    print_info(f"企业微信 Bot")
    result = subprocess.run(
        ["pgrep", "-f", "wechat_bot.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print_success("  运行中")
        pids = result.stdout.strip().split('\n')
        for pid in pids:
            print(f"  {COLOR_CYAN}PID: {pid}{COLOR_RESET}")
    else:
        print_warning("  未运行")
    
    # 检查配置
    print_info(f"配置")
    print(f"  tmux 会话: {tmux_session}")
    print(f"  工作目录: {config.workspace}")
    if config.model:
        print(f"  模型: {config.model}")
    if config.wechat_work:
        print(f"  企业微信: {'启用' if config.wechat_work.enabled else '禁用'}")
        if config.wechat_work.enabled:
            print(f"  回调端口: {config.wechat_work.callback_port}")
    
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