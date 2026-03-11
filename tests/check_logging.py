#!/usr/bin/env python3
"""日志系统健康检查脚本。

快速检查日志系统的健康状态。
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"


def check_log_directory():
    """检查日志目录。"""
    print("=" * 80)
    print("检查 1: 日志目录")
    print("=" * 80)
    
    if not LOG_DIR.exists():
        print("❌ 日志目录不存在")
        return False
    
    print(f"✅ 日志目录存在: {LOG_DIR}")
    
    # 检查权限
    if not os.access(LOG_DIR, os.W_OK):
        print("❌ 日志目录无写权限")
        return False
    
    print("✅ 日志目录有写权限")
    return True


def check_log_files():
    """检查日志文件。"""
    print()
    print("=" * 80)
    print("检查 2: 日志文件")
    print("=" * 80)
    
    if not LOG_DIR.exists():
        print("❌ 日志目录不存在")
        return False
    
    log_files = list(LOG_DIR.glob("*.log"))
    
    if not log_files:
        print("⚠️  没有找到日志文件")
        return True
    
    print(f"✅ 找到 {len(log_files)} 个日志文件")
    
    # 检查日志文件大小
    total_size = sum(f.stat().st_size for f in log_files)
    print(f"   总大小: {total_size:,} bytes")
    
    # 检查最近的日志文件
    latest = max(log_files, key=lambda f: f.stat().st_mtime)
    mtime = datetime.fromtimestamp(latest.stat().st_mtime)
    age = datetime.now() - mtime
    
    print(f"   最新日志: {latest.name}")
    print(f"   修改时间: {mtime} ({age} ago)")
    
    # 检查是否有过旧的日志文件
    old_threshold = datetime.now() - timedelta(days=8)
    old_files = [f for f in log_files if datetime.fromtimestamp(f.stat().st_mtime) < old_threshold]
    
    if old_files:
        print(f"⚠️  发现 {len(old_files)} 个超过 7 天的日志文件（应该被自动清理）")
    else:
        print("✅ 没有过旧的日志文件")
    
    return True


def check_log_content():
    """检查日志内容。"""
    print()
    print("=" * 80)
    print("检查 3: 日志内容")
    print("=" * 80)
    
    if not LOG_DIR.exists():
        print("❌ 日志目录不存在")
        return False
    
    log_files = list(LOG_DIR.glob("*.log"))
    
    if not log_files:
        print("⚠️  没有日志文件可以检查")
        return True
    
    latest = max(log_files, key=lambda f: f.stat().st_mtime)
    
    # 检查日志格式
    print(f"检查日志格式: {latest.name}")
    
    with open(latest, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    if not lines:
        print("⚠️  日志文件为空")
        return True
    
    # 检查日志行格式
    sample_lines = lines[:5]
    print(f"   前 5 行示例:")
    for line in sample_lines:
        print(f"   {line.rstrip()}")
    
    # 统计日志级别
    error_count = sum(1 for line in lines if ' ERROR ' in line)
    warning_count = sum(1 for line in lines if ' WARNING ' in line)
    info_count = sum(1 for line in lines if ' INFO ' in line)
    debug_count = sum(1 for line in lines if ' DEBUG ' in line)
    
    print()
    print(f"   日志统计:")
    print(f"     ERROR:   {error_count}")
    print(f"     WARNING: {warning_count}")
    print(f"     INFO:    {info_count}")
    print(f"     DEBUG:   {debug_count}")
    print(f"     总计:    {len(lines)} 行")
    
    # 检查是否有最近的错误
    if error_count > 0:
        print()
        print(f"   ⚠️  发现 {error_count} 个错误")
        print("   最近的错误:")
        for line in reversed(lines):
            if ' ERROR ' in line:
                print(f"     {line.rstrip()}")
                break
    
    return True


def check_log_rotation():
    """检查日志轮转。"""
    print()
    print("=" * 80)
    print("检查 4: 日志轮转")
    print("=" * 80)
    
    if not LOG_DIR.exists():
        print("❌ 日志目录不存在")
        return False
    
    # 检查是否按日期分割
    log_files = list(LOG_DIR.glob("*.log"))
    
    if not log_files:
        print("⚠️  没有日志文件可以检查")
        return True
    
    # 按文件名分组
    date_pattern = {}
    for log_file in log_files:
        if '_20' in log_file.name:
            parts = log_file.name.split('_')
            if len(parts) >= 2:
                base_name = '_'.join(parts[:-1])
                date_str = parts[-1].replace('.log', '')
                date_pattern.setdefault(base_name, []).append(date_str)
    
    print(f"✅ 按日期分割的日志文件:")
    for base_name, dates in sorted(date_pattern.items()):
        print(f"   {base_name}: {len(dates)} 个文件 ({', '.join(sorted(dates)[-3:])})")
    
    return True


def check_disk_space():
    """检查磁盘空间。"""
    print()
    print("=" * 80)
    print("检查 5: 磁盘空间")
    print("=" * 80)
    
    import shutil
    
    # 检查日志目录大小
    if LOG_DIR.exists():
        total_size = 0
        for log_file in LOG_DIR.rglob("*"):
            if log_file.is_file():
                total_size += log_file.stat().st_size
        
        print(f"✅ 日志目录总大小: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
    else:
        print("⚠️  日志目录不存在")
    
    # 检查磁盘可用空间
    disk_usage = shutil.disk_usage(PROJECT_ROOT)
    free_space = disk_usage.free
    total_space = disk_usage.total
    used_percent = (disk_usage.used / total_space) * 100
    
    print(f"   磁盘总空间: {total_space / 1024 / 1024 / 1024:.2f} GB")
    print(f"   可用空间:   {free_space / 1024 / 1024 / 1024:.2f} GB ({100 - used_percent:.1f}%)")
    print(f"   已使用:     {used_percent:.1f}%")
    
    if used_percent > 90:
        print("⚠️  磁盘空间不足（超过 90%）")
        return False
    elif used_percent > 75:
        print("⚠️  磁盘空间紧张（超过 75%）")
    else:
        print("✅ 磁盘空间充足")
    
    return True


def main():
    """主函数。"""
    print()
    print("=" * 80)
    print("日志系统健康检查")
    print("=" * 80)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 运行所有检查
    results = []
    
    results.append(("日志目录", check_log_directory()))
    results.append(("日志文件", check_log_files()))
    results.append(("日志内容", check_log_content()))
    results.append(("日志轮转", check_log_rotation()))
    results.append(("磁盘空间", check_disk_space()))
    
    # 总结
    print()
    print("=" * 80)
    print("检查总结")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"通过: {passed}/{total}")
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
    
    print()
    
    if passed == total:
        print("🎉 所有检查通过！日志系统状态良好。")
    else:
        print("⚠️  发现问题，请检查上述失败的检查项。")
    
    print()


if __name__ == "__main__":
    import os
    main()