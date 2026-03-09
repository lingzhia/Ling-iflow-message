#!/usr/bin/env python3
"""日志查看工具。

提供方便的日志查看和分析功能。
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / "logs"


def list_logs():
    """列出所有日志文件。"""
    if not LOG_DIR.exists():
        print(f"日志目录不存在: {LOG_DIR}")
        return
    
    log_files = sorted(LOG_DIR.glob("*.log"), reverse=True)
    
    if not log_files:
        print("没有找到日志文件")
        return
    
    print("日志文件列表：")
    print("-" * 80)
    for i, log_file in enumerate(log_files, 1):
        size = log_file.stat().st_size
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        print(f"{i}. {log_file.name}")
        print(f"   大小: {size:,} bytes | 修改时间: {mtime}")
        print()


def view_log(log_name: str, tail: int = 50):
    """查看日志文件。
    
    Args:
        log_name: 日志文件名
        tail: 显示最后多少行
    """
    log_path = LOG_DIR / log_name
    
    if not log_path.exists():
        print(f"日志文件不存在: {log_path}")
        return
    
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if tail:
        lines = lines[-tail:]
    
    print(f"查看日志: {log_name}")
    print("=" * 80)
    for line in lines:
        print(line.rstrip())
    print("=" * 80)


def search_logs(keyword: str, log_type: str = "all"):
    """搜索日志内容。
    
    Args:
        keyword: 搜索关键词
        log_type: 日志类型 (all, manage, wechat_bot)
    """
    if not LOG_DIR.exists():
        print(f"日志目录不存在: {LOG_DIR}")
        return
    
    log_files = []
    if log_type == "all":
        log_files = list(LOG_DIR.glob("*.log"))
    elif log_type == "manage":
        log_files = list(LOG_DIR.glob("manage_*.log"))
    elif log_type == "wechat_bot":
        log_files = list(LOG_DIR.glob("wechat_bot_*.log"))
    
    if not log_files:
        print("没有找到日志文件")
        return
    
    print(f"在 {len(log_files)} 个日志文件中搜索: {keyword}")
    print("=" * 80)
    
    found = False
    for log_file in log_files:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if keyword.lower() in line.lower():
                    print(f"\n{log_file.name}:{line_num}")
                    print(line.rstrip())
                    found = True
    
    if not found:
        print(f"未找到包含 '{keyword}' 的日志")
    
    print("=" * 80)


def tail_log(log_name: str, follow: bool = False):
    """实时查看日志。
    
    Args:
        log_name: 日志文件名
        follow: 是否持续跟踪
    """
    import subprocess
    
    log_path = LOG_DIR / log_name
    
    if not log_path.exists():
        print(f"日志文件不存在: {log_path}")
        return
    
    if follow:
        print(f"实时跟踪日志: {log_name} (按 Ctrl+C 退出)")
        print("=" * 80)
        subprocess.run(["tail", "-f", str(log_path)])
    else:
        print(f"查看最后 50 行: {log_name}")
        print("=" * 80)
        subprocess.run(["tail", "-n", "50", str(log_path)])
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="日志查看工具")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 列出日志
    subparsers.add_parser('list', help='列出所有日志文件')
    
    # 查看日志
    view_parser = subparsers.add_parser('view', help='查看日志文件')
    view_parser.add_argument('log_name', help='日志文件名')
    view_parser.add_argument('--tail', '-n', type=int, default=50, help='显示最后多少行')
    
    # 搜索日志
    search_parser = subparsers.add_parser('search', help='搜索日志内容')
    search_parser.add_argument('keyword', help='搜索关键词')
    search_parser.add_argument('--type', '-t', choices=['all', 'manage', 'wechat_bot'], 
                              default='all', help='日志类型')
    
    # 实时查看
    tail_parser = subparsers.add_parser('tail', help='实时查看日志')
    tail_parser.add_argument('log_name', help='日志文件名')
    tail_parser.add_argument('--follow', '-f', action='store_true', help='持续跟踪')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'list':
        list_logs()
    elif args.command == 'view':
        view_log(args.log_name, args.tail)
    elif args.command == 'search':
        search_logs(args.keyword, args.type)
    elif args.command == 'tail':
        tail_log(args.log_name, args.follow)


if __name__ == "__main__":
    main()