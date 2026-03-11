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


def load_config() -> Dict:
    """加载配置文件。
    
    Returns:
        配置字典
    """
    import json
    from pathlib import Path
    
    config_path = Path.home() / '.ling-iflow' / 'config.json'
    
    if not config_path.exists():
        config_path = Path.cwd() / 'config.json'
    
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print_error(f"加载配置文件失败: {e}")
        return {}


def get_bot_binding(config: Dict) -> Dict[str, Dict]:
    """获取机器人绑定关系。
    
    Args:
        config: 配置字典
        
    Returns:
        会话名称到机器人信息的映射
    """
    binding = {}
    
    # 从 bots 配置中获取绑定关系
    bots = config.get('bots', [])
    for bot in bots:
        if bot.get('enabled', False):
            tmux_session = bot.get('tmux_session', '')
            if tmux_session:
                binding[tmux_session] = {
                    'name': bot.get('name', ''),
                    'port': bot.get('callback_port', 0),
                    'workspace': bot.get('workspace', ''),
                }
    
    # 从 tmux_sessions 配置中获取额外信息
    tmux_sessions = config.get('tmux_sessions', [])
    for tmux_config in tmux_sessions:
        name = tmux_config.get('name', '')
        if name and name in binding:
            # 补充配置信息
            binding[name]['workspace'] = tmux_config.get('workspace', binding[name].get('workspace', ''))
            binding[name]['model'] = tmux_config.get('model', '')
    
    return binding


def get_tmux_sessions() -> List[Dict[str, str]]:
    """获取所有 tmux 会话。
    
    Returns:
        会话列表，每个会话包含 name, windows
    """
    try:
        # 使用更简单的格式获取会话信息
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}|#{session_windows}"],
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
            if len(parts) >= 2:
                sessions.append({
                    'name': parts[0],
                    'windows': parts[1],
                    'width': '80',
                    'height': '24',
                })
        
        return sessions
    
    except Exception as e:
        print_error(f"获取 tmux 会话失败: {e}")
        return []


def format_session_info(session: Dict[str, str], index: int, bot_binding: Dict[str, Dict] = None) -> str:
    """格式化会话信息。
    
    Args:
        session: 会话信息
        index: 索引
        bot_binding: 机器人绑定关系
        
    Returns:
        格式化的字符串
    """
    name = session['name']
    info = [
        f"{COLOR_CYAN}{index + 1}.{COLOR_RESET} ",
        f"{COLOR_BOLD}{COLOR_GREEN}{name}{COLOR_RESET} ",
        f"({session['windows']} 窗口, {session['width']}x{session['height']})"
    ]
    
    # 添加机器人绑定信息
    if bot_binding and name in bot_binding:
        bot = bot_binding[name]
        info.append(f"\n    {COLOR_BLUE}→ {COLOR_RESET}")
        info.append(f"{COLOR_YELLOW}{bot['name']}{COLOR_RESET} ")
        info.append(f"(端口: {bot['port']}, 工作目录: {bot.get('workspace', 'N/A')})")
        if 'model' in bot:
            info.append(f", 模型: {bot['model']}")
    
    return ''.join(info)


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


def kill_session(session_name: str, bot_binding: Dict[str, Dict] = None) -> bool:
    """删除 tmux 会话。
    
    Args:
        session_name: 会话名称
        bot_binding: 机器人绑定关系
        
    Returns:
        是否成功
    """
    # 检查是否被机器人使用
    if bot_binding and session_name in bot_binding:
        bot = bot_binding[session_name]
        print_warning(f"⚠️ 会话 '{session_name}' 正在被机器人 '{bot['name']}' 使用")
        print_warning(f"   端口: {bot['port']}, 工作目录: {bot.get('workspace', 'N/A')}")
        print_warning(f"   删除此会话将导致机器人中断！")
        
        confirm = input(f"确定要删除吗？(yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print_info("已取消删除")
            return False
    
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


def list_sessions(sessions: List[Dict[str, str]], bot_binding: Dict[str, Dict] = None) -> None:
    """列出所有会话。
    
    Args:
        sessions: 会话列表
        bot_binding: 机器人绑定关系
    """
    if not sessions:
        print_warning("没有找到正在运行的 tmux 会话")
        print()
        print_info("你可以创建一个新会话")
        return
    
    print(f"找到 {len(sessions)} 个正在运行的 tmux 会话：")
    print()
    
    for i, session in enumerate(sessions):
        print(format_session_info(session, i, bot_binding))
    
    print()


def show_bot_bindings(bot_binding: Dict[str, Dict]) -> None:
    """显示机器人绑定关系。
    
    Args:
        bot_binding: 机器人绑定关系
    """
    if not bot_binding:
        print_info("没有配置机器人绑定关系")
        return
    
    print_header("机器人绑定关系")
    
    for session_name, bot_info in bot_binding.items():
        print(f"{COLOR_GREEN}会话: {COLOR_RESET}{session_name}")
        print(f"  {COLOR_YELLOW}机器人: {COLOR_RESET}{bot_info['name']}")
        print(f"  {COLOR_YELLOW}端口: {COLOR_RESET}{bot_info['port']}")
        print(f"  {COLOR_YELLOW}工作目录: {COLOR_RESET}{bot_info.get('workspace', 'N/A')}")
        if 'model' in bot_info:
            print(f"  {COLOR_YELLOW}模型: {COLOR_RESET}{bot_info['model']}")
        print()


def main():
    """主函数。"""
    print_header("tmux 会话管理器")
    
    # 加载配置
    config = load_config()
    bot_binding = get_bot_binding(config)
    
    # 获取所有会话
    sessions = get_tmux_sessions()
    
    # 显示会话列表
    list_sessions(sessions, bot_binding)
    
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
    print(f"  {COLOR_CYAN}s{COLOR_RESET} - 显示机器人绑定关系")
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
                # 重新加载配置
                config = load_config()
                bot_binding = get_bot_binding(config)
                sessions = get_tmux_sessions()
                list_sessions(sessions, bot_binding)
                
                if not sessions:
                    print_info("没有正在运行的会话")
                    break
                
                continue
            
            elif choice == 's':
                print()
                show_bot_bindings(bot_binding)
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
                        # 重新加载配置，检查绑定关系
                        config = load_config()
                        bot_binding = get_bot_binding(config)
                        if kill_session(session_name, bot_binding):
                            print_success(f"已删除会话: {session_name}")
                            # 刷新列表
                            sessions = get_tmux_sessions()
                            bot_binding = get_bot_binding(config)
                            list_sessions(sessions, bot_binding)
                        else:
                            print_info("已取消删除")
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
