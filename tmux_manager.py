#!/usr/bin/env python3
"""tmux 会话管理脚本。

功能：
- 列出所有正在运行的 tmux 会话
- 显示会话详细信息
- 让用户选择进入哪个会话
- 支持创建新会话
- 支持删除会话
"""

import subprocess
import sys
from typing import List, Dict, Optional
from pathlib import Path


# 颜色定义
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[36m"
COLOR_RED = "\033[31m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


def print_header(title: str) -> None:
    """打印标题。"""
    print()
    print("=" * 70)
    print(f"{COLOR_BOLD}{COLOR_CYAN}{title}{COLOR_RESET}")
    print("=" * 70)
    print()


def print_success(message: str) -> None:
    """打印成功消息。"""
    print(f"{COLOR_GREEN}✓{COLOR_RESET} {message}")


def print_warning(message: str) -> None:
    """打印警告消息。"""
    print(f"{COLOR_YELLOW}⚠{COLOR_RESET} {message}")


def print_error(message: str) -> None:
    """打印错误消息。"""
    print(f"{COLOR_RED}✗{COLOR_RESET} {message}")


def print_info(message: str) -> None:
    """打印信息消息。"""
    print(f"{COLOR_BLUE}ℹ{COLOR_RESET} {message}")


def get_tmux_sessions() -> List[Dict[str, str]]:
    """获取所有 tmux 会话。
    
    Returns:
        会话列表，每个会话包含 name, created, windows, width, height
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}|#{session_created}|#{session_windows}|#{session_width}|#{session_height}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return []
        
        sessions = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('|')
            if len(parts) >= 5:
                sessions.append({
                    'name': parts[0],
                    'created': parts[1],
                    'windows': parts[2],
                    'width': parts[3],
                    'height': parts[4],
                })
        
        return sessions
    
    except Exception as e:
        print_error(f"获取 tmux 会话失败: {e}")
        return []


def format_session_info(session: Dict[str, str], index: int) -> str:
    """格式化会话信息。
    
    Args:
        session: 会话信息
        index: 索引
        
    Returns:
        格式化的字符串
    """
    return (
        f"{COLOR_CYAN}{index + 1}.{COLOR_RESET} "
        f"{COLOR_BOLD}{COLOR_GREEN}{session['name']}{COLOR_RESET} "
        f"({session['windows']} 窗口, {session['width']}x{session['height']})"
    )


def attach_to_session(session_name: str) -> None:
    """连接到 tmux 会话。
    
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


def kill_session(session_name: str) -> bool:
    """删除 tmux 会话。
    
    Args:
        session_name: 会话名称
        
    Returns:
        是否成功
    """
    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print_error(f"删除会话失败: {e}")
        return False


def create_new_session(session_name: str = None) -> bool:
    """创建新的 tmux 会话。
    
    Args:
        session_name: 会话名称（可选）
        
    Returns:
        是否成功
    """
    if not session_name:
        import time
        session_name = f"session_{int(time.time())}"
    
    try:
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print_success(f"已创建新会话: {session_name}")
            return True
        else:
            print_error(f"创建会话失败: {result.stderr}")
            return False
    
    except Exception as e:
        print_error(f"创建会话失败: {e}")
        return False


def list_sessions(sessions: List[Dict[str, str]]) -> None:
    """列出所有会话。
    
    Args:
        sessions: 会话列表
    """
    if not sessions:
        print_warning("没有找到正在运行的 tmux 会话")
        print()
        print_info("你可以创建一个新会话")
        return
    
    print(f"找到 {len(sessions)} 个正在运行的 tmux 会话：")
    print()
    
    for i, session in enumerate(sessions):
        print(format_session_info(session, i))
    
    print()


def main():
    """主函数。"""
    print_header("tmux 会话管理器")
    
    # 获取所有会话
    sessions = get_tmux_sessions()
    
    # 显示会话列表
    list_sessions(sessions)
    
    if not sessions:
        # 没有会话，提示创建
        choice = input("是否创建一个新会话？(y/n): ").strip().lower()
        if choice == 'y' or choice == 'yes':
            name = input("输入会话名称（留空使用默认名称）: ").strip()
            if not name:
                import time
                name = f"session_{int(time.time())}"
            
            if create_new_session(name):
                print()
                print_info(f"会话 '{name}' 已创建")
                print_info(f"现在可以连接到这个会话了")
        
        return
    
    # 显示选项
    print("可用操作：")
    print(f"  {COLOR_CYAN}1-{len(sessions)}{COLOR_RESET} - 连接到对应的会话")
    print(f"  {COLOR_CYAN}n{COLOR_RESET} - 创建新会话")
    print(f"  {COLOR_CYAN}k{COLOR_RESET} - 删除会话")
    print(f"  {COLOR_CYAN}r{COLOR_RESET} - 刷新会话列表")
    print(f"  {COLOR_CYAN}q{COLOR_RESET} - 退出")
    print()
    
    while True:
        try:
            choice = input("请选择操作: ").strip().lower()
            
            if choice == 'q':
                print_info("退出 tmux 会话管理器")
                break
            
            elif choice == 'r':
                print()
                sessions = get_tmux_sessions()
                list_sessions(sessions)
                
                if not sessions:
                    print_info("没有正在运行的会话")
                    break
                
                continue
            
            elif choice == 'n':
                name = input("输入会话名称（留空使用默认名称）: ").strip()
                if not name:
                    import time
                    name = f"session_{int(time.time())}"
                
                if create_new_session(name):
                    print()
                    print_info(f"会话 '{name}' 已创建")
                    print_info(f"刷新列表查看新会话")
                
                continue
            
            elif choice == 'k':
                if not sessions:
                    print_warning("没有可删除的会话")
                    continue
                
                print()
                print("选择要删除的会话：")
                for i, session in enumerate(sessions):
                    print(f"  {i + 1}. {session['name']}")
                
                try:
                    num = int(input("输入会话编号: ").strip())
                    if 1 <= num <= len(sessions):
                        session_name = sessions[num - 1]['name']
                        confirm = input(f"确定要删除会话 '{session_name}'？(y/n): ").strip().lower()
                        if confirm == 'y' or confirm == 'yes':
                            if kill_session(session_name):
                                print_success(f"已删除会话: {session_name}")
                                # 刷新列表
                                sessions = get_tmux_sessions()
                                list_sessions(sessions)
                            else:
                                print_error(f"删除会话失败: {session_name}")
                    else:
                        print_warning("无效的编号")
                except ValueError:
                    print_warning("请输入有效的编号")
                
                continue
            
            # 尝试连接到会话
            try:
                num = int(choice)
                if 1 <= num <= len(sessions):
                    session_name = sessions[num - 1]['name']
                    attach_to_session(session_name)
                    # 连接后退出
                    break
                else:
                    print_warning(f"请输入 1-{len(sessions)} 之间的数字")
            except ValueError:
                print_warning("无效的选择，请重新输入")
        
        except KeyboardInterrupt:
            print()
            print_info("退出 tmux 会话管理器")
            break


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"程序运行出错: {e}")
        sys.exit(1)
