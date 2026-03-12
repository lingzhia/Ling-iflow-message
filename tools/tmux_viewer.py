#!/usr/bin/env python3
"""
tmux 会话观测工具

用于连接和观测 iflow 的 tmux 会话。
"""

import subprocess
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 颜色定义
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[36m"
COLOR_RED = "\033[31m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


def print_header(title: str):
    """打印标题"""
    print()
    print("=" * 70)
    print(f"{COLOR_BOLD}{COLOR_CYAN}{title}{COLOR_RESET}")
    print("=" * 70)
    print()


def print_success(message: str):
    """打印成功消息"""
    print(f"{COLOR_GREEN}✓{COLOR_RESET} {message}")


def print_warning(message: str):
    """打印警告消息"""
    print(f"{COLOR_YELLOW}⚠{COLOR_RESET} {message}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{COLOR_RED}✗{COLOR_RESET} {message}")


def print_info(message: str):
    """打印信息消息"""
    print(f"{COLOR_BLUE}ℹ{COLOR_RESET} {message}")


def get_tmux_sessions():
    """获取所有 tmux 会话
    
    Returns:
        会话列表
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return []
        
        sessions = []
        for line in result.stdout.strip().split('\n'):
            if line:
                # 格式: session_name: [windows_count] (created)
                parts = line.split(':')
                if parts:
                    name = parts[0]
                    sessions.append(name)
        
        return sessions
    except Exception as e:
        print_error(f"获取 tmux 会话失败: {e}")
        return []


def attach_to_session(session_name: str):
    """连接到 tmux 会话
    
    Args:
        session_name: 会话名称
    """
    print()
    print_info(f"正在连接到会话 '{session_name}'...")
    print_info(f"按 {COLOR_BOLD}Ctrl+B{COLOR_RESET} 然后 {COLOR_BOLD}D{COLOR_RESET} 可以分离会话")
    print()
    
    try:
        subprocess.run(["tmux", "attach-session", "-t", session_name])
    except KeyboardInterrupt:
        print()
        print_info("已从 tmux 会话分离")
    except Exception as e:
        print_error(f"连接会话失败: {e}")


def main():
    """主函数"""
    print_header("tmux 会话观测工具")
    
    # 获取所有会话
    sessions = get_tmux_sessions()
    
    if not sessions:
        print_warning("没有找到正在运行的 tmux 会话")
        print()
        print_info("请先启动服务: ./manage.py start")
        return
    
    # 显示会话列表
    print(f"找到 {len(sessions)} 个正在运行的 tmux 会话：")
    print()
    
    for i, session in enumerate(sessions):
        print(f"  {COLOR_CYAN}{i + 1}.{COLOR_RESET} {COLOR_GREEN}{session}{COLOR_RESET}")
    
    print()
    
    # 允许用户选择
    while True:
        try:
            choice = input(f"请选择要连接的会话 (1-{len(sessions)}) 或输入 'q' 退出: ").strip()
            
            if choice.lower() == 'q':
                print_info("退出")
                break
            
            num = int(choice)
            if 1 <= num <= len(sessions):
                session_name = sessions[num - 1]
                attach_to_session(session_name)
                break
            else:
                print_warning(f"请输入 1-{len(sessions)} 之间的数字")
        except ValueError:
            print_warning("请输入有效的数字")
        except KeyboardInterrupt:
            print()
            print_info("退出")
            break


if __name__ == "__main__":
    main()