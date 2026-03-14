#!/usr/bin/env python3
"""
Ling-iflow 项目管理脚本

提供统一的项目管理功能，包括：
- 启动/停止服务
- 查看服务状态
- 重启服务
- 查看日志
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional
import typer

app = typer.Typer()

# 颜色定义
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_RED = "\033[31m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"


def print_header(title: str):
    """打印标题"""
    print()
    print("=" * 70)
    print(f"{COLOR_CYAN}{title}{COLOR_RESET}")
    print("=" * 70)


def print_success(message: str):
    """打印成功消息"""
    print(f"{COLOR_GREEN}✅ {message}{COLOR_RESET}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{COLOR_RED}❌ {message}{COLOR_RESET}")


def print_warning(message: str):
    """打印警告消息"""
    print(f"{COLOR_YELLOW}⚠️  {message}{COLOR_RESET}")


def print_info(message: str):
    """打印信息消息"""
    print(f"{COLOR_CYAN}ℹ️  {message}{COLOR_RESET}")


@app.command()
def start(
    config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="后台运行"),
    group: str = typer.Option("all", "--group", "-g", help="启动的机器人组 (all, g1, g2, ls)")
):
    """启动服务

    示例:
        ./manage.py start                    # 启动所有组
        ./manage.py start -g g1             # 只启动 g1 组
        ./manage.py start -g g2             # 只启动 g2 组
        ./manage.py start -g ls             # 列出所有组
        ./manage.py start -d                 # 后台运行
        ./manage.py start -c config-dev.json # 使用指定配置
    """
    print_header("启动服务")

    # 特殊处理：列出所有组
    if group == "ls":
        print_info("可用组:")
        print()
        print("  g1  - bot1 + iflow")
        print("  g2  - bot2 + iflow2")
        print("  all - 所有组")
        print()
        print_info("使用示例: ./manage.py start --group g1")
        return

    # 检查配置文件
    config_path = Path(config)
    if not config_path.exists():
        print_error(f"配置文件不存在: {config}")
        print_info("使用示例: ./manage.py start -c config.json")
        raise typer.Exit(1)

    # 验证组名
    if group not in ["all", "g1", "g2"]:
        print_error(f"无效的组名: {group}")
        print_info("可用组: all, g1, g2")
        print_info("使用 --group ls 查看详细信息")
        raise typer.Exit(1)

    print_info(f"配置文件: {config}")
    print_info(f"运行模式: {'后台' if daemon else '前台'}")
    print_info(f"启动组: {group}")

    # 构建启动命令
    cmd = ["python3", "-m", "src.bot", config, "--group", group]

    if daemon:
        # 后台运行
        log_file = Path("logs/bot.log")
        log_file.parent.mkdir(exist_ok=True)

        print_info("后台运行，日志输出到: logs/bot.log")

        full_cmd = f"nohup python3 -m src.bot {config} --group {group} > logs/bot.log 2>&1 &"
        subprocess.run(full_cmd, shell=True)

        print_success("服务已在后台启动")
        print_info("查看日志: ./manage.py logs")
        print_info("查看状态: ./manage.py status")
    else:
        # 前台运行
        print_info("前台运行，按 Ctrl+C 停止")
        print()
        subprocess.run(["python3", "-m", "src.bot", config, "--group", group])


@app.command()
def stop(
    group: str = typer.Option("all", "--group", "-g", help="停止的机器人组 (all, g1, g2, ls)")
):
    """停止服务

    示例:
        ./manage.py stop            # 停止所有组
        ./manage.py stop -g g1      # 只停止 g1 组
        ./manage.py stop -g g2      # 只停止 g2 组
        ./manage.py stop -g ls      # 列出所有组
    """
    print_header("停止服务")

    # 特殊处理：列出所有组
    if group == "ls":
        print_info("可用组:")
        print()
        print("  g1  - bot1 + iflow")
        print("  g2  - bot2 + iflow2")
        print("  all - 所有组")
        print()
        print_info("使用示例: ./manage.py stop --group g1")
        return

    # 验证组名
    if group not in ["all", "g1", "g2"]:
        print_error(f"无效的组名: {group}")
        print_info("可用组: all, g1, g2")
        print_info("使用 --group ls 查看详细信息")
        raise typer.Exit(1)

    # 根据组确定要停止的进程
    if group == "all":
        # 停止所有进程
        print_info("停止所有组...")
        subprocess.run("pkill -9 -f 'src.bot'", shell=True)
    else:
        # 停止指定组的进程
        print_info(f"停止组: {group}...")
        # 通过查找包含 --group 参数的进程来停止
        result = subprocess.run(
            f"ps aux | grep 'src.bot.*--group {group}' | grep -v grep | awk '{{print $2}}'",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                subprocess.run(f"kill -9 {pid}", shell=True)
                print_success(f"已停止进程: {pid}")
        else:
            print_warning(f"未找到运行中的 {group} 组进程")

    # 停止对应的 tmux 会话
    if group == "g1" or group == "all":
        print_info("停止 tmux 会话: iflow")
        subprocess.run("tmux kill-session -t iflow 2>/dev/null", shell=True)
    
    if group == "g2" or group == "all":
        print_info("停止 tmux 会话: iflow2")
        subprocess.run("tmux kill-session -t iflow2 2>/dev/null", shell=True)

    # 等待进程结束
    import time
    time.sleep(2)

    print_success("停止完成")


@app.command()
def restart(
    config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="后台运行"),
    group: str = typer.Option("all", "--group", "-g", help="重启的机器人组 (all, g1, g2, ls)")
):
    """重启服务

    示例:
        ./manage.py restart               # 重启所有组
        ./manage.py restart -g g1         # 只重启 g1 组
        ./manage.py restart -g g2         # 只重启 g2 组
        ./manage.py restart -g ls         # 列出所有组
        ./manage.py restart -d            # 后台运行
    """
    print_header("重启服务")

    # 特殊处理：列出所有组
    if group == "ls":
        print_info("可用组:")
        print()
        print("  g1  - bot1 + iflow")
        print("  g2  - bot2 + iflow2")
        print("  all - 所有组")
        print()
        print_info("使用示例: ./manage.py restart --group g1")
        return

    # 验证组名
    if group not in ["all", "g1", "g2"]:
        print_error(f"无效的组名: {group}")
        print_info("可用组: all, g1, g2")
        print_info("使用 --group ls 查看详细信息")
        raise typer.Exit(1)

    print_info(f"重启组: {group}")

    # 停止服务
    print_info("正在停止服务...")
    stop_group = group  # 传递给 stop 的 group 参数
    
    # 根据 group 停止进程
    if stop_group == "all":
        subprocess.run("pkill -9 -f 'src.bot'", shell=True)
    else:
        result = subprocess.run(
            f"ps aux | grep 'src.bot.*--group {stop_group}' | grep -v grep | awk '{{print $2}}'",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                subprocess.run(f"kill -9 {pid}", shell=True)
    
    # 停止 tmux 会话
    if stop_group == "g1" or stop_group == "all":
        subprocess.run("tmux kill-session -t iflow 2>/dev/null", shell=True)
    if stop_group == "g2" or stop_group == "all":
        subprocess.run("tmux kill-session -t iflow2 2>/dev/null", shell=True)

    import time
    time.sleep(2)

    # 启动服务
    print_info("正在启动服务...")
    
    # 构建 start 命令
    cmd = ["python3", "-m", "src.bot", config, "--group", group]

    if daemon:
        # 后台运行
        log_file = Path("logs/bot.log")
        log_file.parent.mkdir(exist_ok=True)

        full_cmd = f"nohup python3 -m src.bot {config} --group {group} > logs/bot.log 2>&1 &"
        subprocess.run(full_cmd, shell=True)

        print_success("服务已在后台重启")
        print_info("查看日志: ./manage.py logs")
        print_info("查看状态: ./manage.py status")
    else:
        # 前台运行
        print_info("前台运行，按 Ctrl+C 停止")
        print()
        subprocess.run(cmd)


@app.command()
def status():
    """查看服务状态"""
    print_header("服务状态")

    # 检查服务是否运行
    result = subprocess.run(
        "ps aux | grep 'src.bot' | grep -v grep",
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print_success("服务运行中")
        print()
        print("进程信息:")
        for line in result.stdout.strip().split('\n'):
            print(f"  {line}")

        # 检查端口占用
        ports = [8787, 8788]
        print()
        print("端口监听:")
        for port in ports:
            result_port = subprocess.run(
                f"netstat -tlnp 2>/dev/null | grep {port} || ss -tlnp | grep {port}",
                shell=True,
                capture_output=True,
                text=True
            )
            if result_port.returncode == 0:
                print(f"  {COLOR_GREEN}✓{COLOR_RESET} 端口 {port}: 监听中")
            else:
                print(f"  {COLOR_YELLOW}✗{COLOR_RESET} 端口 {port}: 未监听")

        # 检查 tmux 会话
        print()
        print("Tmux 会话:")
        sessions = ["iflow", "iflow2"]
        for session in sessions:
            result_tmux = subprocess.run(
                f"tmux has-session -t {session} 2>/dev/null",
                shell=True,
                capture_output=True
            )
            if result_tmux.returncode == 0:
                print(f"  {COLOR_GREEN}✓{COLOR_RESET} 会话 {session}: 存在")
            else:
                print(f"  {COLOR_YELLOW}✗{COLOR_RESET} 会话 {session}: 不存在")

    else:
        print_error("服务未运行")
        print()
        print_info("启动服务: ./manage.py start")


@app.command()
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="持续跟踪日志"),
    lines: int = typer.Option(100, "--lines", "-n", help="显示的行数")
):
    """查看服务日志

    示例:
        ./manage.py logs         # 查看最近100行
        ./manage.py logs -f      # 持续跟踪
        ./manage.py logs -n 50   # 查看最近50行
    """
    print_header("服务日志")

    log_file = Path("logs/bot.log")

    if not log_file.exists():
        print_warning("日志文件不存在")
        print_info("启动服务后会自动创建日志文件")
        raise typer.Exit(0)

    if follow:
        print_info("持续跟踪日志，按 Ctrl+C 退出")
        print()
        subprocess.run(["tail", "-f", str(log_file)])
    else:
        print_info(f"显示最近 {lines} 行日志")
        print()
        subprocess.run(["tail", f"-{lines}", str(log_file)])


@app.command()
def clean():
    """清理日志和缓存"""
    print_header("清理日志和缓存")

    logs_dir = Path("logs")

    if not logs_dir.exists():
        print_warning("日志目录不存在")
        raise typer.Exit(0)

    print_info("清理日志文件...")

    # 删除日志文件
    for log_file in logs_dir.glob("*.log"):
        log_file.unlink()
        print_success(f"已删除: {log_file.name}")

    # 清理 __pycache__
    print_info("清理 Python 缓存...")
    for cache_dir in Path(".").rglob("__pycache__"):
        import shutil
        shutil.rmtree(cache_dir)
        print_success(f"已删除: {cache_dir}")

    print_success("清理完成")


@app.command()
def help_all():
    """显示所有可用命令"""
    print_header("Ling-iflow 管理脚本")

    print()
    print("可用命令:")
    print()
    print("  start     启动服务")
    print("  stop      停止服务")
    print("  restart   重启服务")
    print("  status    查看服务状态")
    print("  logs      查看服务日志")
    print("  clean     清理日志和缓存")
    print()
    print("使用示例:")
    print()
    print("  ./manage.py start -d           # 后台启动")
    print("  ./manage.py logs -f            # 跟踪日志")
    print("  ./manage.py status             # 查看状态")
    print()
    print("获取命令帮助:")
    print()
    print("  ./manage.py start --help")
    print("  ./manage.py logs --help")


if __name__ == "__main__":
    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        help_all()
        sys.exit(0)

    app()
