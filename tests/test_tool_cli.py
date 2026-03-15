#!/usr/bin/env python3
"""
测试工具的所有命令行选项
"""

import subprocess
import sys
import time
from pathlib import Path

# 设置项目根目录
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def run_test(name, command, timeout=120):
    """运行测试命令"""
    print(f"\n{'=' * 60}")
    print(f"测试: {name}")
    print(f"命令: {command}")
    print(f"{'=' * 60}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        print("输出:")
        print(result.stdout)
        
        if result.stderr:
            print("错误:")
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✅ 测试通过")
        else:
            print(f"❌ 测试失败，返回码: {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print(f"❌ 测试超时 ({timeout}秒)")
        return False
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("测试工具的所有命令行选项")
    print("=" * 60)
    
    tests = [
        # 测试 1: 交互模式（不带参数）
        {
            "name": "交互模式（不带参数）",
            "command": "timeout 10 python tools/iflow_interactive_tool.py",
            "timeout": 15,
            "description": "应该显示帮助并退出（timeout）"
        },
        
        # 测试 2: 命令行模式 - 发送简单消息
        {
            "name": "命令行模式 - 发送简单消息",
            "command": "python tools/iflow_interactive_tool.py --message '测试'",
            "timeout": 120,
            "description": "应该发送消息并收到回复"
        },
        
        # 测试 3: 命令行模式 - 发送带中文的消息
        {
            "name": "命令行模式 - 发送带中文的消息",
            "command": "python tools/iflow_interactive_tool.py --message '收到请回答'",
            "timeout": 120,
            "description": "应该发送消息并收到回复"
        },
        
        # 测试 4: 命令行模式 - 使用 --clean 选项
        {
            "name": "命令行模式 - 使用 --clean 选项",
            "command": "python tools/iflow_interactive_tool.py --message '测试clean' --clean",
            "timeout": 120,
            "description": "应该清理残留会话并发送消息"
        },
        
        # 测试 5: 命令行模式 - 使用 --scope all
        {
            "name": "命令行模式 - 使用 --scope all",
            "command": "python tools/iflow_interactive_tool.py --message '测试scope' --scope all --clean",
            "timeout": 120,
            "description": "应该接收所有类型的消息（包括思考）"
        },
        
        # 测试 6: 命令行模式 - 使用 --scope reply_only
        {
            "name": "命令行模式 - 使用 --scope reply_only",
            "command": "python tools/iflow_interactive_tool.py --message '测试reply' --scope reply_only --clean",
            "timeout": 120,
            "description": "应该只接收回复消息（不包括思考）"
        },
        
        # 测试 7: 命令行模式 - 使用自定义配置文件
        {
            "name": "命令行模式 - 使用自定义配置文件",
            "command": "python tools/iflow_interactive_tool.py --message '测试config' --config config.json --clean",
            "timeout": 120,
            "description": "应该使用指定配置文件"
        },
        
        # 测试 8: 命令行模式 - 组合选项
        {
            "name": "命令行模式 - 组合所有选项",
            "command": "python tools/iflow_interactive_tool.py --message '测试组合' --config config.json --scope all --clean",
            "timeout": 120,
            "description": "应该正常工作，所有选项都生效"
        },
        
        # 测试 9: 帮助信息
        {
            "name": "帮助信息",
            "command": "python tools/iflow_interactive_tool.py --help",
            "timeout": 10,
            "description": "应该显示帮助信息"
        },
    ]
    
    results = []
    
    for i, test in enumerate(tests, 1):
        # 在测试之间等待一下
        if i > 1:
            time.sleep(2)
        
        passed = run_test(
            test["name"],
            test["command"],
            test["timeout"]
        )
        
        results.append({
            "name": test["name"],
            "description": test["description"],
            "passed": passed
        })
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    
    for i, result in enumerate(results, 1):
        status = "✅ 通过" if result["passed"] else "❌ 失败"
        print(f"{i}. {result['name']}: {status}")
        print(f"   {result['description']}")
    
    print(f"\n总计: {passed_count}/{total_count} 通过")
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️ 有 {total_count - passed_count} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())