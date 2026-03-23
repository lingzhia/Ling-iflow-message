#!/usr/bin/env python3
"""
Ling-iflow CLI 入口点

工作目录逻辑：
- 用户在哪个目录运行 ling-iflow 命令，哪个目录就是 iflow 的工作目录
- 不强制切换工作目录，保持用户当前的工作目录
"""
import sys
import os
from pathlib import Path


def main():
    """命令行入口点"""
    # 获取项目根目录（manage.py 所在目录）
    project_root = Path(__file__).parent.parent
    manage_path = project_root / "manage.py"
    
    # 设置环境变量，让 bot.py 知道用户的工作目录
    user_cwd = os.getcwd()
    os.environ["LING_IFLOW_WORKSPACE"] = user_cwd
    
    # 运行 manage.py，不改变工作目录
    # 用户当前目录会被保留，作为 iflow 的工作目录
    import subprocess
    result = subprocess.run(
        [sys.executable, str(manage_path)] + sys.argv[1:]
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()