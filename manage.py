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

app = typer.Typer(
    help="Ling-iflow 项目管理脚本 - 统一管理服务启动、停止、重启、状态查询和渠道管理"
)

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


def load_config(config_path: str) -> dict:
    """加载配置文件"""
    config_file = Path(config_path)
    if not config_file.exists():
        return {}
    
    import json
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def get_channel_info(config_path: str) -> dict:
    """从配置文件获取渠道信息"""
    config = load_config(config_path)
    channels = {}
    
    # 从 bots 中获取企业微信渠道
    bots = config.get('bots', [])
    for bot in bots:
        channels[bot['name']] = {
            'type': 'wechat',
            'name': bot['name'],
            'tmux_session': f"{bot['name']}+iflow"
        }

    # 从 simulator_channels 中获取模拟器渠道
    simulators = config.get('simulator_channels', [])
    for sim in simulators:
        channels[sim['name']] = {
            'type': 'simulator',
            'name': sim['name'],
            'tmux_session': f"{sim['name']}+iflow"
        }
    
    return channels


def get_available_channels(config_path: str) -> list:
    """获取可用的渠道列表"""
    channel_info = get_channel_info(config_path)
    return list(channel_info.keys())


def get_default_channel(config_path: str) -> str:
    """获取默认渠道名称（返回第一个渠道）"""
    channel_info = get_channel_info(config_path)
    # 直接返回第一个渠道
    if channel_info:
        return list(channel_info.keys())[0]
    return "wechat_bot1"


def get_tmux_session_by_channel(channel_name: str, config_path: str) -> Optional[str]:
    """根据渠道名获取对应的tmux会话

    根据 design-v2/17-渠道架构简化方案.md，tmux 会话名使用命名规则：渠道名+iflow
    """
    # 使用命名规则：渠道名+iflow
    return f"{channel_name}+iflow"


def get_all_tmux_sessions(config_path: str) -> list:
    """获取配置文件中所有的tmux会话

    根据 design-v2/17-渠道架构简化方案.md，tmux 会话名使用命名规则：渠道名+iflow
    """
    config = load_config(config_path)
    tmux_sessions = []

    # 从 bots 中获取
    bots = config.get('bots', [])
    for bot in bots:
        tmux_session = f"{bot['name']}+iflow"
        if tmux_session not in tmux_sessions:
            tmux_sessions.append(tmux_session)

    # 从 simulator_channels 中获取
    simulators = config.get('simulator_channels', [])
    for sim in simulators:
        tmux_session = f"{sim['name']}+iflow"
        if tmux_session not in tmux_sessions:
            tmux_sessions.append(tmux_session)

    return tmux_sessions


@app.command()
def start(
    config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径"),
    all_channels: bool = typer.Option(False, "--all", "-a", help="启动所有渠道"),
    channel: Optional[str] = typer.Option(None, "--channel", help="启动的特定渠道（使用 ls 列出所有渠道）"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台运行（默认后台运行）")
):
    """启动服务

    默认后台启动第一个启用的渠道，使用 -a 启动所有渠道

    示例：
      ./manage.py start              后台启动默认渠道（第一个启用的渠道）
      ./manage.py start -a           后台启动所有渠道
      ./manage.py start -f           前台启动默认渠道
      ./manage.py start --channel ls 列出所有可用渠道
      ./manage.py start --channel wechat_bot1  启动指定渠道
    """
    print_header("启动服务")

    # 特殊处理：列出所有渠道
    if channel == "ls":
        available_channels = get_available_channels(config)
        config_data = load_config(config)
        channel_info = get_channel_info(config)

        print_info("配置文件中的所有渠道:")
        print()
        print(f"  {'渠道名':<20} {'类型':<10} {'状态':<10} {'tmux会话':<25}")
        print(f"  {'-'*65}")

        # 显示企业微信渠道
        if config_data.get('bots'):
            for bot in config_data['bots']:
                channel_name = bot['name']
                tmux_session = f"{bot['name']}+iflow"
                type_icon = "📱企业微信"
                print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

        # 显示模拟器渠道
        if config_data.get('simulator_channels'):
            for sim in config_data['simulator_channels']:
                channel_name = sim['name']
                tmux_session = f"{sim['name']}+iflow"
                type_icon = "🔧模拟器"
                print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

        # 显示默认渠道
        default_channel = get_default_channel(config)
        print()
        print_info(f"默认渠道: {default_channel}（第一个渠道）")
        print()
        print_info("使用示例:")
        print("  ./manage.py start                      # 启动默认渠道")
        print(f"  ./manage.py start --channel {default_channel}  # 启动默认渠道")
        print("  ./manage.py start -a                   # 启动所有渠道")
        return

    # 检查配置文件
    config_path = Path(config)
    if not config_path.exists():
        print_error(f"配置文件不存在: {config}")
        print_info("使用示例: ./manage.py start -c config.json")
        raise typer.Exit(1)

    # 优先级：all_channels > channel > 默认渠道
    if all_channels and channel:
        print_error("--all 和 --channel 参数互斥")
        print_info("使用 --channel ls 查看所有可用渠道")
        raise typer.Exit(1)

    # 确定要启动的渠道
    if all_channels:
        # 启动所有渠道（不指定 channel 参数）
        print_info(f"配置文件: {config}")
        print_info(f"运行模式: {'前台' if foreground else '后台'}")
        print_info(f"启动: 所有渠道")
        cmd_args = [config]
    elif channel:
        # 验证渠道名
        available_channels = get_available_channels(config)
        if channel not in available_channels:
            print_error(f"渠道不存在: {channel}")
            print_info(f"可用渠道: {', '.join(available_channels)}")
            print_info("使用 --channel ls 查看所有可用渠道")
            raise typer.Exit(1)

        # 启动指定渠道
        print_info(f"配置文件: {config}")
        print_info(f"运行模式: {'前台' if foreground else '后台'}")
        print_info(f"启动渠道: {channel}")
        cmd_args = [config, "--channel", channel]
    else:
        # 使用默认渠道（第一个启用的渠道）
        default_channel = get_default_channel(config)
        print_info(f"配置文件: {config}")
        print_info(f"运行模式: {'前台' if foreground else '后台'}")
        print_success(f"默认渠道: {default_channel}（第一个启用的渠道）")
        print_info(f"启动渠道: {default_channel}")
        cmd_args = [config, "--channel", default_channel]

    # 构建启动命令
    cmd = ["python3", "-m", "src.bot"] + cmd_args

    if not foreground:
        # 后台运行（默认）
        log_file = Path("logs/bot.log")
        log_file.parent.mkdir(exist_ok=True)

        print_info("后台运行，日志输出到: logs/bot.log")

        full_cmd = f"nohup python3 -m src.bot {' '.join(cmd_args)} > logs/bot.log 2>&1 &"
        subprocess.run(full_cmd, shell=True)

        print_success("服务已在后台启动")
        print_info("查看日志: ./manage.py logs")
        print_info("查看状态: ./manage.py status")
    else:
        # 前台运行
        print_info("前台运行，按 Ctrl+C 停止")
        print()
        subprocess.run(["python3", "-m", "src.bot"] + cmd_args)


@app.command()
def stop(
    config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径"),
    all_channels: bool = typer.Option(False, "--all", "-a", help="停止所有渠道"),
    channel: Optional[str] = typer.Option(None, "--channel", help="停止的特定渠道（使用 ls 列出所有渠道）")
):
    """停止服务

    默认停止默认渠道，使用 -a 停止所有渠道

    示例：
      ./manage.py stop              停止默认渠道
      ./manage.py stop -a           停止所有渠道
      ./manage.py stop --channel ls 列出所有可用渠道
      ./manage.py stop --channel wechat_bot1  停止指定渠道
    """
    print_header("停止服务")

    # 处理渠道参数
    if all_channels and channel:
        print_error("--all 和 --channel 参数互斥")
        print_info("使用 --channel ls 查看所有可用渠道")
        raise typer.Exit(1)

    # 确定要停止的渠道
    if all_channels:
        target_channel = "all"
    elif channel:
        target_channel = channel
    else:
        # 使用默认渠道
        target_channel = get_default_channel(config)

    # 特殊处理：列出所有渠道
    if target_channel == "ls":
        available_channels = get_available_channels(config)
        config_data = load_config(config)
        channel_info = get_channel_info(config)

        print_info("可用渠道:")
        print()
        print(f"  {'渠道名':<20} {'类型':<10} {'状态':<10} {'tmux会话':<25}")
        print(f"  {'-'*65}")

        # 显示企业微信渠道
        if config_data.get('bots'):
            for bot in config_data['bots']:
                channel_name = bot['name']
                tmux_session = f"{bot['name']}+iflow"
                type_icon = "📱企业微信"
                print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

        # 显示模拟器渠道
        if config_data.get('simulator_channels'):
            for sim in config_data['simulator_channels']:
                channel_name = sim['name']
                tmux_session = f"{sim['name']}+iflow"
                type_icon = "🔧模拟器"
                print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

        print()
        print_info("使用示例:")
        print("  ./manage.py stop                      # 停止默认渠道")
        print(f"  ./manage.py stop --channel {get_default_channel(config)}  # 停止默认渠道")
        print("  ./manage.py stop -a                   # 停止所有渠道")
        return

    # 验证渠道名
    available_channels = get_available_channels(config)
    if target_channel != "all" and target_channel not in available_channels:
        print_error(f"渠道不存在: {target_channel}")
        print_info(f"可用渠道: all, {', '.join(available_channels)}")
        print_info("使用 --channel ls 查看详细信息")
        raise typer.Exit(1)

    # 根据渠道确定要停止的进程
    if target_channel == "all":
        # 停止所有进程
        print_info("停止所有渠道...")
        # 先尝试正常停止（SIGTERM）
        result = subprocess.run(
            "ps aux | grep 'src.bot' | grep -v grep | awk '{print $2}'",
            shell=True,
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                subprocess.run(f"kill -TERM {pid}", shell=True)
                print_info(f"发送停止信号到进程: {pid}")

            # 等待进程正常退出
            import time
            time.sleep(3)

            # 检查是否还有进程在运行，如果有则强制停止
            result = subprocess.run(
                "ps aux | grep 'src.bot' | grep -v grep | awk '{print $2}'",
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(f"kill -9 {pid}", shell=True)
                    print_warning(f"强制停止进程: {pid}")
        else:
            print_warning("没有运行中的服务进程")
    else:
        # 停止指定渠道的进程
        print_info(f"停止渠道: {target_channel}...")
        # 通过查找包含 --channel 参数的进程来停止
        result = subprocess.run(
            f"ps aux | grep 'src.bot.*--channel {target_channel}' | grep -v grep | awk '{{print $2}}'",
            shell=True,
            capture_output=True,
            text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                subprocess.run(f"kill -TERM {pid}", shell=True)
                print_info(f"发送停止信号到进程: {pid}")

            # 等待进程正常退出
            import time
            time.sleep(3)

            # 检查是否还有进程在运行，如果有则强制停止
            result = subprocess.run(
                f"ps aux | grep 'src.bot.*--channel {target_channel}' | grep -v grep | awk '{{print $2}}'",
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(f"kill -9 {pid}", shell=True)
                    print_warning(f"强制停止进程: {pid}")
        else:
            print_warning(f"未找到运行中的 {target_channel} 渠道进程")

    # 停止对应的 tmux 会话
    if target_channel == "all":
        # 停止所有tmux会话
        tmux_sessions = get_all_tmux_sessions(config)
        if tmux_sessions:
            print_info(f"停止所有 tmux 会话: {', '.join(tmux_sessions)}")
            for session in tmux_sessions:
                subprocess.run(f"tmux kill-session -t {session} 2>/dev/null", shell=True)
        else:
            print_warning("没有配置的 tmux 会话")
    else:
        # 停止指定渠道的tmux会话
        tmux_session = get_tmux_session_by_channel(target_channel, config)
        if tmux_session:
            print_info(f"停止 tmux 会话: {tmux_session}")
            subprocess.run(f"tmux kill-session -t {tmux_session} 2>/dev/null", shell=True)

    # 等待进程结束
    import time
    time.sleep(2)

    print_success("停止完成")


@app.command()
def restart(
    config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径"),
    all_channels: bool = typer.Option(False, "--all", "-a", help="重启所有渠道"),
    channel: Optional[str] = typer.Option(None, "--channel", help="重启的特定渠道（使用 ls 列出所有渠道）"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="前台运行（默认后台运行）")
):
    """重启服务

    默认后台重启默认渠道，使用 -f 前台运行

    示例：
      ./manage.py restart             后台重启默认渠道
      ./manage.py restart -a          后台重启所有渠道
      ./manage.py restart -f          前台重启默认渠道
      ./manage.py restart --channel ls 列出所有可用渠道
      ./manage.py restart --channel wechat_bot1  重启指定渠道
    """
    print_header("重启服务")

    # 处理渠道参数
    if all_channels and channel:
        print_error("--all 和 --channel 参数互斥")
        print_info("使用 --channel ls 查看所有可用渠道")
        raise typer.Exit(1)

    # 确定要重启的渠道
    if all_channels:
        target_channel = "all"
    elif channel:
        target_channel = channel
    else:
        # 使用默认渠道
        target_channel = get_default_channel(config)

    # 特殊处理：列出所有渠道
    if target_channel == "ls":
        available_channels = get_available_channels(config)
        config_data = load_config(config)
        channel_info = get_channel_info(config)

        print_info("可用渠道:")
        print()
        print(f"  {'渠道名':<20} {'类型':<10} {'状态':<10} {'tmux会话':<25}")
        print(f"  {'-'*65}")

        # 显示企业微信渠道
        if config_data.get('bots'):
            for bot in config_data['bots']:
                channel_name = bot['name']
                tmux_session = f"{bot['name']}+iflow"
                type_icon = "📱企业微信"
                print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

        # 显示模拟器渠道
        if config_data.get('simulator_channels'):
            for sim in config_data['simulator_channels']:
                channel_name = sim['name']
                tmux_session = f"{sim['name']}+iflow"
                type_icon = "🔧模拟器"
                print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

        print()
        print_info("使用示例:")
        print("  ./manage.py restart                      # 重启默认渠道")
        print(f"  ./manage.py restart --channel {get_default_channel(config)}  # 重启默认渠道")
        print("  ./manage.py restart -a                   # 重启所有渠道")
        return

    # 验证渠道名
    available_channels = get_available_channels(config)
    if target_channel != "all" and target_channel not in available_channels:
        print_error(f"渠道不存在: {target_channel}")
        print_info(f"可用渠道: all, {', '.join(available_channels)}")
        print_info("使用 --channel ls 查看详细信息")
        raise typer.Exit(1)

    print_info(f"重启渠道: {target_channel}")

    # 停止服务
    print_info("正在停止服务...")

    # 使用 Unix Socket 控制服务停止渠道
    if target_channel != "all":
        stop_command = f"stop {target_channel}"
        result = send_control_command(stop_command)

        if not result.get("success"):
            # 如果控制服务失败，回退到直接停止
            print_warning(f"控制服务停止失败，使用直接停止: {result.get('error')}")

            # 直接停止进程
            result = subprocess.run(
                f"ps aux | grep 'src.bot.*--channel {target_channel}' | grep -v grep | awk '{{print $2}}'",
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(f"kill -9 {pid}", shell=True)

            # 停止 tmux 会话
            tmux_session = get_tmux_session_by_channel(target_channel, config)
            if tmux_session:
                print_info(f"停止 tmux 会话: {tmux_session}")
                subprocess.run(f"tmux kill-session -t {tmux_session} 2>/dev/null", shell=True)
    else:
        # 停止所有渠道
        print_info("停止所有渠道...")
        channels = get_available_channels(config)
        for channel_name in channels:
            stop_command = f"stop {channel_name}"
            send_control_command(stop_command)

        # 停止所有 tmux 会话
        tmux_sessions = get_all_tmux_sessions(config)
        if tmux_sessions:
            print_info(f"停止所有 tmux 会话: {', '.join(tmux_sessions)}")
            for session in tmux_sessions:
                subprocess.run(f"tmux kill-session -t {session} 2>/dev/null", shell=True)

    import time
    time.sleep(2)

    # 启动服务
    print_info("正在启动服务...")

    # 构建 start 命令
    if target_channel == "all":
        cmd = ["python3", "-m", "src.bot", config]
    else:
        cmd = ["python3", "-m", "src.bot", config, "--channel", target_channel]

    if not foreground:
        # 后台运行（默认）
        log_file = Path("logs/bot.log")
        log_file.parent.mkdir(exist_ok=True)

        if target_channel == "all":
            full_cmd = f"nohup python3 -m src.bot {config} > logs/bot.log 2>&1 &"
        else:
            full_cmd = f"nohup python3 -m src.bot {config} --channel {target_channel} > logs/bot.log 2>&1 &"
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
def status(config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径")):
    """查看服务状态

    检查已启动渠道的进程、端口和 tmux 会话状态

    示例：./manage.py status
    """
    print_header("服务状态")

    # 加载配置
    config_data = load_config(config)
    channel_info = get_channel_info(config)

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

        # 尝试通过控制命令获取实际的渠道状态
        running_channels = []
        control_result = send_control_command('status')
        
        if control_result.get('success') and 'result' in control_result:
            # 从控制命令结果中提取已启动的渠道
            channels_status = control_result['result']
            for channel_name, channel_data in channels_status.items():
                if isinstance(channel_data, dict) and 'modules' in channel_data:
                    # 检查渠道的模块是否都在运行
                    modules = channel_data['modules']
                    all_running = all(
                        isinstance(m, dict) and m.get('running', False)
                        for m in modules.values()
                    )
                    if all_running:
                        running_channels.append(channel_name)
        else:
            # 回退到解析ps命令获取渠道
            for line in result.stdout.strip().split('\n'):
                if '--channel' in line:
                    parts = line.split('--channel')
                    if len(parts) > 1:
                        channel_part = parts[1].strip().split()[0]
                        running_channels.append(channel_part)

        print()
        print_success(f"已启动渠道: {len(running_channels)} 个")
        if running_channels:
            print(f"  {', '.join(running_channels)}")

        # 检查已启动渠道的端口占用
        if running_channels:
            print()
            print("端口监听:")
            # 从配置中获取已启动渠道的端口
            for channel_name in running_channels:
                if channel_name in channel_info:
                    channel_config = channel_info[channel_name]
                    if channel_config['type'] == 'wechat':
                        # 企业微信渠道查找端口
                        if config_data.get('bots'):
                            for bot in config_data['bots']:
                                if bot['name'] == channel_name:
                                    port = bot.get('callback_port', 8788)
                                    result_port = subprocess.run(
                                        f"netstat -tlnp 2>/dev/null | grep {port} || ss -tlnp | grep {port}",
                                        shell=True,
                                        capture_output=True,
                                        text=True
                                    )
                                    if result_port.returncode == 0:
                                        print(f"  {COLOR_GREEN}✓{COLOR_RESET} 端口 {port} ({channel_name}): 监听中")
                                    else:
                                        print(f"  {COLOR_YELLOW}✗{COLOR_RESET} 端口 {port} ({channel_name}): 未监听")
                                    break

        # 检查已启动渠道的 tmux 会话
        if running_channels:
            print()
            print("Tmux 会话:")
            for channel_name in running_channels:
                tmux_session = get_tmux_session_by_channel(channel_name, config)
                if tmux_session:
                    result_tmux = subprocess.run(
                        f"tmux has-session -t {tmux_session} 2>/dev/null",
                        shell=True,
                        capture_output=True
                    )
                    if result_tmux.returncode == 0:
                        print(f"  {COLOR_GREEN}✓{COLOR_RESET} 会话 {tmux_session} ({channel_name}): 存在")
                    else:
                        print(f"  {COLOR_YELLOW}✗{COLOR_RESET} 会话 {tmux_session} ({channel_name}): 不存在")

    else:
        print_error("服务未运行")
        print()
        print_info("启动服务: ./manage.py start")
        return

    # 显示可用渠道信息
    print()
    print("=" * 70)
    print(f"{COLOR_CYAN}可用渠道{COLOR_RESET}")
    print("=" * 70)

    all_channels = get_available_channels(config)
    print()
    print(f"  {'渠道名':<20} {'类型':<10} {'状态':<10} {'tmux会话':<25}")
    print(f"  {'-'*65}")

    # 显示企业微信渠道
    if config_data.get('bots'):
        for bot in config_data['bots']:
            channel_name = bot['name']
            tmux_session = f"{bot['name']}+iflow"
            is_running = channel_name in running_channels

            if is_running:
                status_icon = f"{COLOR_GREEN}已启动{COLOR_RESET}"
            else:
                status_icon = f"{COLOR_YELLOW}未启动{COLOR_RESET}"

            type_icon = "📱企业微信"
            print(f"  {channel_name:<20} {type_icon:<10} {status_icon:<10} {tmux_session:<25}")

    # 显示模拟器渠道
    if config_data.get('simulator_channels'):
        for sim in config_data['simulator_channels']:
            channel_name = sim['name']
            tmux_session = f"{sim['name']}+iflow"
            is_running = channel_name in running_channels

            if is_running:
                status_icon = f"{COLOR_GREEN}已启动{COLOR_RESET}"
            else:
                status_icon = f"{COLOR_YELLOW}未启动{COLOR_RESET}"

            type_icon = "🔧模拟器"
            print(f"  {channel_name:<20} {type_icon:<10} {status_icon:<10} {tmux_session:<25}")

    # 显示默认渠道
    default_channel = get_default_channel(config)
    print()
    print_info(f"默认渠道: {default_channel}（第一个渠道）")
    print()
    print_info("操作提示:")
    print("  ./manage.py start                      # 启动默认渠道")
    print("  ./manage.py start --channel ls         # 查看所有可用渠道")
    print("  ./manage.py start --channel <渠道名>    # 启动指定渠道")
    print("  ./manage.py start -a                   # 启动所有渠道")


@app.command()
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="持续跟踪日志"),
    lines: int = typer.Option(100, "--lines", "-n", help="显示的日志行数")
):
    """查看服务日志

    示例：
      ./manage.py logs              查看最近 100 行日志
      ./manage.py logs -f           实时跟踪日志
      ./manage.py logs -n 50        查看最近 50 行
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
    """清理日志和缓存

    删除日志文件和 Python 缓存

    示例：./manage.py clean
    """
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


def send_control_command(command: str) -> dict:
    """通过 Unix Socket 发送控制命令
    
    Args:
        command: 控制命令
        
    Returns:
        返回结果字典
    """
    import socket
    import json
    
    socket_path = "/tmp/ling-iflow.sock"
    
    try:
        # 创建 Unix Socket 客户端
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(socket_path)
        
        # 发送命令
        client.send(command.encode('utf-8'))
        
        # 接收响应
        response = client.recv(4096).decode('utf-8')
        
        # 关闭连接
        client.close()
        
        # 解析响应
        result = json.loads(response)
        return result
        
    except FileNotFoundError:
        print_error("控制服务未运行，请先启动服务")
        return {"success": False, "error": "控制服务未运行"}
    except ConnectionRefusedError:
        print_error("无法连接到控制服务")
        return {"success": False, "error": "连接被拒绝"}
    except Exception as e:
        print_error(f"发送控制命令失败: {e}")
        return {"success": False, "error": str(e)}


# 创建渠道管理子命令组
channel_app = typer.Typer(help="渠道管理命令")


@channel_app.command("list")
def list_channels(config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径")):
    """列出配置文件中的所有渠道（信息库）

    示例：./manage.py channel list
    """
    print_header("渠道列表（配置文件中的所有渠道）")

    # 加载配置
    config_data = load_config(config)
    channel_info = get_channel_info(config)

    if not config_data:
        print_error("无法加载配置文件")
        return

    print()
    print(f"  {'渠道名':<20} {'类型':<10} {'状态':<10} {'tmux会话':<25}")
    print(f"  {'-'*65}")

    # 显示企业微信渠道
    if config_data.get('bots'):
        for bot in config_data['bots']:
            channel_name = bot['name']
            tmux_session = f"{bot['name']}+iflow"

            type_icon = "📱企业微信"
            print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

    # 显示模拟器渠道
    if config_data.get('simulator_channels'):
        for sim in config_data['simulator_channels']:
            channel_name = sim['name']
            tmux_session = f"{sim['name']}+iflow"

            type_icon = "🔧模拟器"
            print(f"  {channel_name:<20} {type_icon:<10} 可用       {tmux_session:<25}")

    # 显示默认渠道
    default_channel = get_default_channel(config)
    print()
    print_success(f"默认渠道: {default_channel}（第一个渠道）")
    print()
    print_info("操作提示:")
    print("  ./manage.py start                      # 启动默认渠道")
    print("  ./manage.py channel status             # 查看已启动渠道的状态")
    print("  ./manage.py channel start <渠道名>      # 启动指定渠道")
    print("  ./manage.py channel stop <渠道名>       # 停止指定渠道")
    print("  ./manage.py channel restart <渠道名>    # 重启指定渠道")


@channel_app.command()
def status(
    channel_name: str = typer.Argument(None, help="渠道名，不指定则显示所有已启动渠道的状态"),
    config: str = typer.Option("config.json", "--config", "-c", help="配置文件路径")
):
    """查看渠道状态

    只显示已启动渠道的详细状态

    示例：
      ./manage.py channel status          查看所有已启动渠道的状态
      ./manage.py channel status wechat_bot1  查看 wechat_bot1 渠道状态
    """
    print_header("渠道状态")

    # 加载配置
    config_data = load_config(config)
    channel_info = get_channel_info(config)

    if not config_data:
        print_error("无法加载配置文件")
        return

    # 检查服务是否运行
    result = subprocess.run(
        "ps aux | grep 'src.bot' | grep -v grep",
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print_warning("服务未运行")
        print()
        print_info("启动服务: ./manage.py start")
        print()
        print_info("可用渠道:")
        print(f"  {'渠道名':<20} {'类型':<10} {'状态':<10} {'tmux会话':<25}")
        print(f"  {'-'*65}")

        # 显示企业微信渠道
        if config_data.get('bots'):
            for bot in config_data['bots']:
                channel_name_temp = bot['name']
                enabled = bot.get('enabled', False)
                tmux_session = f"{bot['name']}+iflow"

                if enabled:
                    status_icon = f"{COLOR_YELLOW}未启动{COLOR_RESET}"
                else:
                    status_icon = f"{COLOR_RED}未启用{COLOR_RESET}"

                type_icon = "📱企业微信"
                print(f"  {channel_name_temp:<20} {type_icon:<10} {status_icon:<10} {tmux_session:<25}")

        # 显示模拟器渠道
        if config_data.get('simulator_channels'):
            for sim in config_data['simulator_channels']:
                channel_name_temp = sim['name']
                enabled = sim.get('enabled', False)
                tmux_session = f"{sim['name']}+iflow"

                if enabled:
                    status_icon = f"{COLOR_YELLOW}未启动{COLOR_RESET}"
                else:
                    status_icon = f"{COLOR_RED}未启用{COLOR_RESET}"

                type_icon = "🔧模拟器"
                print(f"  {channel_name_temp:<20} {type_icon:<10} {status_icon:<10} {tmux_session:<25}")

        return

    # 解析进程获取已启动的渠道
    running_channels = []
    for line in result.stdout.strip().split('\n'):
        # 查找 --channel 参数
        if '--channel' in line:
            parts = line.split('--channel')
            if len(parts) > 1:
                channel_part = parts[1].strip().split()[0]
                running_channels.append(channel_part)

    if not running_channels:
        print_warning("没有已启动的渠道")
        print()
        print_info("使用以下命令启动渠道:")
        print("  ./manage.py start                      # 启动默认渠道")
        print("  ./manage.py start --channel ls         # 查看所有可用渠道")
        print("  ./manage.py start --channel <渠道名>    # 启动指定渠道")
        return

    print_success(f"已启动渠道: {len(running_channels)} 个")
    print()

    if channel_name:
        # 显示单个渠道的状态
        if channel_name not in running_channels:
            print_error(f"渠道未启动: {channel_name}")
            print()
            print_info(f"已启动的渠道: {', '.join(running_channels)}")
            print_info("使用 ./manage.py channel status 查看所有已启动渠道")
            return

        print(f"{COLOR_CYAN}渠道: {channel_name}{COLOR_RESET}")
        print()

        # 获取渠道信息
        if channel_name in channel_info:
            channel_config = channel_info[channel_name]
            type_icon = "📱企业微信" if channel_config['type'] == 'wechat' else "🔧模拟器"
            print(f"  类型: {type_icon}")
            print(f"  tmux会话: {channel_config['tmux_session']}")

            # 检查 tmux 会话状态
            tmux_session = channel_config['tmux_session']
            result_tmux = subprocess.run(
                f"tmux has-session -t {tmux_session} 2>/dev/null",
                shell=True,
                capture_output=True
            )
            if result_tmux.returncode == 0:
                print(f"  tmux状态: {COLOR_GREEN}存在{COLOR_RESET}")
            else:
                print(f"  tmux状态: {COLOR_YELLOW}不存在{COLOR_RESET}")

            # 检查端口状态（仅企业微信）
            if channel_config['type'] == 'wechat':
                if config_data.get('bots'):
                    for bot in config_data['bots']:
                        if bot['name'] == channel_name:
                            port = bot.get('callback_port', 8788)
                            result_port = subprocess.run(
                                f"netstat -tlnp 2>/dev/null | grep {port} || ss -tlnp | grep {port}",
                                shell=True,
                                capture_output=True,
                                text=True
                            )
                            if result_port.returncode == 0:
                                print(f"  端口 {port}: {COLOR_GREEN}监听中{COLOR_RESET}")
                            else:
                                print(f"  端口 {port}: {COLOR_YELLOW}未监听{COLOR_RESET}")
                            break

        print()
        print_info("使用控制服务查看详细信息:")
        print(f"  send_control_command('status {channel_name}')")

    else:
        # 显示所有已启动渠道的状态
        print(f"  {'渠道名':<20} {'类型':<10} {'tmux状态':<10} {'端口状态':<15}")
        print(f"  {'-'*55}")

        for ch_name in running_channels:
            if ch_name in channel_info:
                channel_config = channel_info[ch_name]
                type_icon = "📱企业微信" if channel_config['type'] == 'wechat' else "🔧模拟器"

                # 检查 tmux 会话状态
                tmux_session = channel_config['tmux_session']
                result_tmux = subprocess.run(
                    f"tmux has-session -t {tmux_session} 2>/dev/null",
                    shell=True,
                    capture_output=True
                )
                tmux_status = f"{COLOR_GREEN}存在{COLOR_RESET}" if result_tmux.returncode == 0 else f"{COLOR_YELLOW}不存在{COLOR_RESET}"

                # 检查端口状态（仅企业微信）
                port_status = "N/A"
                if channel_config['type'] == 'wechat':
                    if config_data.get('bots'):
                        for bot in config_data['bots']:
                            if bot['name'] == ch_name:
                                port = bot.get('callback_port', 8788)
                                result_port = subprocess.run(
                                    f"netstat -tlnp 2>/dev/null | grep {port} || ss -tlnp | grep {port}",
                                    shell=True,
                                    capture_output=True,
                                    text=True
                                )
                                if result_port.returncode == 0:
                                    port_status = f"{COLOR_GREEN}{port}:监听{COLOR_RESET}"
                                else:
                                    port_status = f"{COLOR_YELLOW}{port}:未监听{COLOR_RESET}"
                                break

                print(f"  {ch_name:<20} {type_icon:<10} {tmux_status:<10} {port_status:<15}")

        print()
        print_info("使用以下命令管理渠道:")
        print("  ./manage.py channel start <渠道名>      # 启动指定渠道")
        print("  ./manage.py channel stop <渠道名>       # 停止指定渠道")
        print("  ./manage.py channel restart <渠道名>    # 重启指定渠道")
        print("  ./manage.py channel status <渠道名>     # 查看指定渠道的详细状态")


@channel_app.command()
def start(channel_name: str = typer.Argument(..., help="渠道名")):
    """启动渠道

    示例：./manage.py channel start wechat_bot1
    """
    print_header(f"启动渠道: {channel_name}")
    
    command = f"start {channel_name}"
    result = send_control_command(command)
    
    if result.get("success"):
        module_results = result.get("result", {})
        
        success_count = 0
        fail_count = 0
        
        for module_id, success in module_results.items():
            if success:
                print_success(f"{module_id}: 启动成功")
                success_count += 1
            else:
                print_error(f"{module_id}: 启动失败")
                fail_count += 1
        
        print()
        print_info(f"总计: {success_count} 成功, {fail_count} 失败")
    else:
        print_error(result.get("error", "未知错误"))


@channel_app.command()
def stop(channel_name: str = typer.Argument(..., help="渠道名")):
    """停止渠道

    示例：./manage.py channel stop wechat_bot1
    """
    print_header(f"停止渠道: {channel_name}")
    
    command = f"stop {channel_name}"
    result = send_control_command(command)
    
    if result.get("success"):
        module_results = result.get("result", {})
        
        success_count = 0
        fail_count = 0
        
        for module_id, success in module_results.items():
            if success:
                print_success(f"{module_id}: 停止成功")
                success_count += 1
            else:
                print_error(f"{module_id}: 停止失败")
                fail_count += 1
        
        print()
        print_info(f"总计: {success_count} 成功, {fail_count} 失败")
    else:
        print_error(result.get("error", "未知错误"))


@channel_app.command()
def restart(channel_name: str = typer.Argument(..., help="渠道名")):
    """重启渠道

    示例：./manage.py channel restart wechat_bot1
    """
    print_header(f"重启渠道: {channel_name}")
    
    command = f"restart {channel_name}"
    result = send_control_command(command)
    
    if result.get("success"):
        module_results = result.get("result", {})
        
        success_count = 0
        fail_count = 0
        
        for module_id, success in module_results.items():
            if success:
                print_success(f"{module_id}: 重启成功")
                success_count += 1
            else:
                print_error(f"{module_id}: 重启失败")
                fail_count += 1
        
        print()
        print_info(f"总计: {success_count} 成功, {fail_count} 失败")
    else:
        print_error(result.get("error", "未知错误"))


@app.command()
def help_all():
    """显示所有可用命令

    Ling-iflow 管理脚本提供统一的服务管理功能，支持启动、停止、重启、
    状态查询、日志查看和渠道管理等操作。

    主命令:
      start     启动服务（默认启动默认渠道，-a 启动所有渠道）
      stop      停止服务（默认停止默认渠道，-a 停止所有渠道）
      restart   重启服务（默认重启默认渠道，-a 重启所有渠道）
      status    查看服务状态（进程、端口、tmux）
      logs      查看服务日志（支持静态和跟踪模式）
      clean     清理日志和缓存
      channel   渠道管理命令（动态管理服务渠道）

    渠道管理子命令:
      channel list      列出所有可用渠道
      channel status    查看渠道状态（所有渠道或指定渠道）
      channel start     启动指定渠道
      channel stop      停止指定渠道
      channel restart   重启指定渠道

    常用示例:
      服务管理:
        ./manage.py start                       # 启动默认渠道
        ./manage.py start -a                    # 启动所有渠道
        ./manage.py start -f                    # 前台启动默认渠道
        ./manage.py start -a -f                 # 前台启动所有渠道
        ./manage.py stop                        # 停止默认渠道
        ./manage.py stop -a                     # 停止所有渠道
        ./manage.py restart                     # 重启默认渠道
        ./manage.py restart -a                  # 重启所有渠道
      
      指定渠道:
        ./manage.py start -c wechat_bot1        # 启动 wechat_bot1 渠道
        ./manage.py stop -c wechat_bot1         # 停止 wechat_bot1 渠道
        ./manage.py restart -c wechat_bot1      # 重启 wechat_bot1 渠道
      
      日志管理:
        ./manage.py logs -f                     # 实时跟踪日志
        ./manage.py logs -n 200                 # 查看最近 200 行
        ./manage.py clean                       # 清理日志和缓存
      
      渠道管理:
        ./manage.py channel list                # 列出所有渠道
        ./manage.py channel status wechat_bot1  # 查看 wechat_bot1 渠道状态
        ./manage.py channel start wechat_bot1   # 启动 wechat_bot1 渠道
        ./manage.py channel stop wechat_bot1    # 停止 wechat_bot1 渠道
        ./manage.py channel restart wechat_bot1 # 重启 wechat_bot1 渠道

    获取详细帮助:
      主命令帮助:
        ./manage.py start --help                # 查看 start 命令帮助
        ./manage.py stop --help                 # 查看 stop 命令帮助
        ./manage.py restart --help              # 查看 restart 命令帮助
        ./manage.py logs --help                 # 查看 logs 命令帮助
      
      渠道管理帮助:
        ./manage.py channel --help              # 查看渠道管理命令帮助
        ./manage.py channel start --help        # 查看渠道启动帮助
        ./manage.py channel status --help       # 查看渠道状态帮助

    工作流程:
      1. 首次使用:
         ./manage.py start -c ls                # 查看可用渠道
         ./manage.py start                      # 后台启动默认渠道
         ./manage.py status                     # 确认服务正常
         ./manage.py logs -f                    # 实时监控日志

      2. 渠道管理:
         ./manage.py channel list               # 查看所有渠道
         ./manage.py channel status             # 查看渠道状态
         ./manage.py channel start wechat_bot1  # 启动 wechat_bot1 渠道
         ./manage.py channel restart wechat_bot1 # 重启 wechat_bot1 渠道
         ./manage.py channel stop wechat_bot1   # 停止 wechat_bot1 渠道

      3. 故障排查:
         ./manage.py status                     # 检查服务状态
         ./manage.py logs -n 200                # 查看详细日志
         ./manage.py channel status             # 检查各渠道状态
         ./manage.py channel restart wechat_bot1 # 重启有问题的渠道

    注意事项:
      1. 所有命令都需要在项目根目录执行
      2. 配置文件默认为 config.json
      3. 渠道管理命令需要先启动主服务
      4. 后台模式日志输出到 logs/bot.log
      5. 使用 --help 参数查看命令详细帮助
    """
    print_header("Ling-iflow 管理脚本")

    print()

    print("可用命令:")

    print()

    print("  start     启动服务（默认后台启动默认渠道，-a 启动所有渠道）")

    print("  stop      停止服务（默认停止默认渠道，-a 停止所有渠道）")

    print("  restart   重启服务（默认后台重启默认渠道，-a 重启所有渠道）")

    print("  status    查看服务状态（进程、端口、tmux）")

    print("  logs      查看服务日志（支持静态和跟踪模式）")

    print("  clean     清理日志和缓存")

    print("  channel   渠道管理命令（动态管理服务渠道）")

    print()

    print("常用示例:")

    print()

    print("  服务管理:")

    print("    ./manage.py start                   # 后台启动默认渠道")

    print("    ./manage.py start -a                # 后台启动所有渠道")

    print("    ./manage.py start -f                # 前台启动默认渠道")

    print("    ./manage.py stop                    # 停止默认渠道")

    print("    ./manage.py stop -a                 # 停止所有渠道")

    print("    ./manage.py restart                 # 后台重启默认渠道")

    print("    ./manage.py restart -a              # 后台重启所有渠道")

    print("    ./manage.py restart -f              # 前台重启默认渠道")

    print()

    print("  指定渠道:")

    print("    ./manage.py start -c wechat_bot1    # 启动 wechat_bot1 渠道")

    print("    ./manage.py stop -c wechat_bot1     # 停止 wechat_bot1 渠道")

    print("    ./manage.py restart -c wechat_bot1  # 重启 wechat_bot1 渠道")

    print()

    print("  日志管理:")

    print("    ./manage.py logs -f                 # 实时跟踪日志")

    print("    ./manage.py logs -n 200             # 查看最近 200 行")

    print("    ./manage.py clean                   # 清理日志和缓存")

    print()

    print("  渠道管理:")

    print("    ./manage.py channel list            # 列出所有渠道")

    print("    ./manage.py channel status wechat_bot1  # 查看 wechat_bot1 渠道状态")

    print("    ./manage.py channel start wechat_bot1   # 启动 wechat_bot1 渠道")

    print("    ./manage.py channel stop wechat_bot1    # 停止 wechat_bot1 渠道")

    print("    ./manage.py channel restart wechat_bot1 # 重启 wechat_bot1 渠道")

    print()

    print("获取详细帮助:")

    print()

    print("  ./manage.py start --help              # 查看 start 命令帮助")

    print("  ./manage.py stop --help               # 查看 stop 命令帮助")

    print("  ./manage.py restart --help            # 查看 restart 命令帮助")

    print("  ./manage.py logs --help               # 查看 logs 命令帮助")

    print("  ./manage.py channel --help            # 查看渠道管理命令帮助")

    print()
    print("更多信息:")
    print()
    print("  使用 --help 参数查看命令的详细说明和参数")
    print("  例如: ./manage.py start --help")


# 添加组管理子命令组
app.add_typer(channel_app, name="channel")


if __name__ == "__main__":
    # 如果没有参数，显示帮助
    if len(sys.argv) == 1:
        help_all()
        sys.exit(0)

    app()
