#!/usr/bin/env python3
"""综合测试前准备检查脚本。

确保所有必要的配置和准备工作都已完成。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def check_file_exists(filepath, description):
    """检查文件是否存在。"""
    if filepath.exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath}")
        return False


def check_dir_exists(dirpath, description):
    """检查目录是否存在。"""
    if dirpath.exists() and dirpath.is_dir():
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ {description}: {dirpath}")
        return False


def check_module_import(module_name, description):
    """检查模块是否可以导入。"""
    try:
        __import__(module_name)
        print(f"✅ {description}")
        return True
    except ImportError as e:
        print(f"❌ {description}: {e}")
        return False


def main():
    """主函数。"""
    print()
    print("=" * 80)
    print("综合测试前准备检查")
    print("=" * 80)
    print()
    
    # 检查项目结构
    print("1. 项目结构检查")
    print("-" * 80)
    
    structure_checks = [
        (PROJECT_ROOT / "channels", "channels 目录"),
        (PROJECT_ROOT / "cli", "cli 目录"),
        (PROJECT_ROOT / "config", "config 目录"),
        (PROJECT_ROOT / "interactive", "interactive 目录"),
        (PROJECT_ROOT / "utils", "utils 目录"),
        (PROJECT_ROOT / "tests", "tests 目录"),
        (PROJECT_ROOT / "logs", "logs 目录"),
        (PROJECT_ROOT / "config.json", "配置文件"),
        (PROJECT_ROOT / "config.example.json", "配置示例文件"),
        (PROJECT_ROOT / "manage.py", "管理脚本"),
        (PROJECT_ROOT / "wechat_bot.py", "企业微信 Bot"),
        (PROJECT_ROOT / "logs_view.py", "日志查看工具"),
        (PROJECT_ROOT / ".gitignore", "Git 忽略文件"),
    ]
    
    structure_passed = 0
    for filepath, description in structure_checks:
        if check_file_exists(filepath, description) if not description.endswith("目录") else check_dir_exists(filepath, description):
            structure_passed += 1
    
    print(f"   通过: {structure_passed}/{len(structure_checks)}")
    print()
    
    # 检查依赖模块
    print("2. 依赖模块检查")
    print("-" * 80)
    
    dependency_checks = [
        ("typer", "typer (CLI 框架)"),
        ("loguru", "loguru (日志库)"),
        ("pydantic", "pydantic (数据验证)"),
        ("pydantic_settings", "pydantic-settings (配置加载)"),
    ]
    
    dependency_passed = 0
    for module, description in dependency_checks:
        if check_module_import(module, description):
            dependency_passed += 1
    
    print(f"   通过: {dependency_passed}/{len(dependency_checks)}")
    print()
    
    # 检查可选依赖
    print("3. 可选依赖检查")
    print("-" * 80)
    
    optional_checks = [
        ("httpx", "httpx (HTTP 客户端)"),
        ("aiohttp", "aiohttp (异步 HTTP)"),
        ("cryptography", "cryptography (加密库)"),
    ]
    
    optional_passed = 0
    for module, description in optional_checks:
        if check_module_import(module, description):
            optional_passed += 1
    
    print(f"   通过: {optional_passed}/{len(optional_checks)} (企业微信功能)")
    print()
    
    # 检查测试文件
    print("4. 测试文件检查")
    print("-" * 80)
    
    test_files = [
        (PROJECT_ROOT / "tests" / "test_logging.py", "日志功能测试"),
        (PROJECT_ROOT / "tests" / "check_logging.py", "日志健康检查"),
        (PROJECT_ROOT / "tests" / "LOGGING_CHECKLIST.md", "日志检查清单"),
        (PROJECT_ROOT / "tests" / "LOGGING_QUICK_REF.md", "日志快速参考"),
    ]
    
    test_passed = 0
    for filepath, description in test_files:
        if check_file_exists(filepath, description):
            test_passed += 1
    
    print(f"   通过: {test_passed}/{len(test_files)}")
    print()
    
    # 检查日志系统
    print("5. 日志系统检查")
    print("-" * 80)
    
    log_dir = PROJECT_ROOT / "logs"
    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        if log_files:
            print(f"✅ 找到 {len(log_files)} 个日志文件")
            log_passed = 1
        else:
            print("⚠️  日志目录存在但没有日志文件")
            log_passed = 1
    else:
        print("❌ 日志目录不存在")
        log_passed = 0
    
    print()
    
    # 检查配置
    print("6. 配置检查")
    print("-" * 80)
    
    config_file = PROJECT_ROOT / "config.json"
    if config_file.exists():
        try:
            import json
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            print(f"✅ 配置文件格式正确")
            print(f"   tmux_session: {config.get('tmux_session', 'N/A')}")
            print(f"   workspace: {config.get('workspace', 'N/A')}")
            print(f"   model: {config.get('model', 'N/A')}")
            
            wechat_config = config.get('wechat_work', {})
            print(f"   wechat_work.enabled: {wechat_config.get('enabled', False)}")
            
            config_passed = 1
        except Exception as e:
            print(f"❌ 配置文件格式错误: {e}")
            config_passed = 0
    else:
        print("❌ 配置文件不存在")
        config_passed = 0
    
    print()
    
    # 总结
    print("=" * 80)
    print("检查总结")
    print("=" * 80)
    
    total_passed = structure_passed + dependency_passed + optional_passed + test_passed + log_passed + config_passed
    total_checks = len(structure_checks) + len(dependency_checks) + len(optional_checks) + len(test_files) + 1 + 1
    
    print(f"总通过: {total_passed}/{total_checks}")
    print()
    
    if total_passed == total_checks:
        print("🎉 所有检查通过！可以进行综合测试。")
        print()
        print("下一步:")
        print("  1. 启动服务: python manage.py start")
        print("  2. 查看状态: python manage.py status")
        print("  3. 查看日志: python logs_view.py list")
        print("  4. 运行测试: python manage.py test")
        return 0
    else:
        print("⚠️  发现问题，请检查上述失败的检查项。")
        print()
        print("常见解决方案:")
        print("  - 依赖缺失: pip install -e \".[wechat]\"")
        print("  - 配置缺失: cp config.example.json config.json")
        print("  - 日志问题: python tests/check_logging.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
