#!/usr/bin/env python3
"""
简单测试工具的关键命令行选项
"""

import subprocess
import sys
import time

def run_test(name, command, timeout=60):
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
        
        # 只输出关键信息
        if "iflow 已完全就绪" in result.stdout:
            print("✅ iflow 已完全就绪")
        if "发送消息:" in result.stdout:
            print("✅ 消息已发送")
        if "✅ 生成完成" in result.stdout:
            print("✅ 生成完成")
        if "消息历史" in result.stdout:
            print("✅ 显示了消息历史")
        
        if result.returncode == 0:
            print(f"✅ 测试通过")
            return True
        else:
            print(f"❌ 测试失败，返回码: {result.returncode}")
            print(f"输出: {result.stdout[:200]}")
            return False
        
    except subprocess.TimeoutExpired:
        print(f"❌ 测试超时 ({timeout}秒)")
        return False
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("测试工具的关键命令行选项")
    print("=" * 60)
    
    # 清理残留会话
    print("\n清理残留的 tmux 会话...")
    subprocess.run("tmux kill-session -t iflow1 2>/dev/null", shell=True)
    subprocess.run("tmux kill-session -t iflow2 2>/dev/null", shell=True)
    time.sleep(1)
    
    tests = [
        # 测试 1: 帮助信息
        {
            "name": "帮助信息",
            "command": "python tools/iflow_interactive_tool.py --help",
            "timeout": 10
        },
        
        # 测试 2: 命令行模式 - 简单消息（带 --clean）
        {
            "name": "命令行模式 - 简单消息",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --clean",
            "timeout": 180  # 增加超时时间
        },
        
        # 测试 3: 命令行模式 - scope all
        {
            "name": "命令行模式 - scope all",
            "command": "python tools/iflow_interactive_tool.py --message '测试scope' --scope all --clean",
            "timeout": 180
        },
        
        # 测试 4: 命令行模式 - scope reply_only
        {
            "name": "命令行模式 - scope reply_only",
            "command": "python tools/iflow_interactive_tool.py --message '测试reply' --scope reply_only --clean",
            "timeout": 180
        },
        
        # 测试 5: 命令行模式 - 组合选项
        {
            "name": "命令行模式 - 组合选项",
            "command": "python tools/iflow_interactive_tool.py --message '测试组合' --config config.json --scope all --clean",
            "timeout": 180
        },
    ]
    
    results = []
    
    for i, test in enumerate(tests, 1):
        # 在测试之间等待一下
        if i > 1:
            time.sleep(3)
        
        passed = run_test(
            test["name"],
            test["command"],
            test["timeout"]
        )
        
        results.append({
            "name": test["name"],
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
    
    print(f"\n总计: {passed_count}/{total_count} 通过")
    
    if passed_count == total_count:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️ 有 {total_count - passed_count} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())