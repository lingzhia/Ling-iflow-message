#!/usr/bin/env python3
"""
Ling-iflow CLI 入口点
"""
import sys
from pathlib import Path


def main():
    """命令行入口点"""
    # 获取 manage.py 的路径
    current_dir = Path(__file__).parent.parent
    manage_path = current_dir / "manage.py"
    
    # 如果 manage.py 不存在，尝试使用项目根目录
    if not manage_path.exists():
        manage_path = current_dir / "manage.py"
    
    # 将 manage.py 添加到参数列表中
    sys.argv = ["manage.py"] + sys.argv[1:]
    
    # 运行 manage.py
    import subprocess
    result = subprocess.run(
        [sys.executable, str(manage_path)] + sys.argv[1:],
        cwd=str(current_dir)
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()