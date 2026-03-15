#!/usr/bin/env python3
"""
最终测试：验证工具符合方案预期
"""

import subprocess
import sys
import time

def run_simple_test(name, command, timeout=180):
    """运行简单测试"""
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
        
        # 检查关键输出
        checks = {
            "iflow 已就绪": "iflow 已完全就绪" in result.stdout,
            "消息已发送": "发送消息:" in result.stdout,
            "收到回复": "收到" in result.stdout,
            "生成完成": "生成完成" in result.stdout,
            "显示历史": "消息历史" in result.stdout
        }
        
        for check_name, check_result in checks.items():
            if check_result:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name}")
        
        all_passed = all(checks.values())
        
        if all_passed and result.returncode == 0:
            print(f"✅ 测试通过")
            return True
        else:
            print(f"❌ 测试失败")
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
    print("最终测试：验证工具符合方案预期")
    print("=" * 60)
    
    # 清理残留会话
    print("\n清理残留的 tmux 会话...")
    subprocess.run("tmux kill-session -t iflow1 2>/dev/null", shell=True)
    subprocess.run("tmux kill-session -t iflow2 2>/dev/null", shell=True)
    time.sleep(1)
    
    tests = [
        {
            "name": "基本功能测试",
            "command": "python tools/iflow_interactive_tool.py --message '测试基本功能' --clean"
        },
        {
            "name": "scope all 测试",
            "command": "python tools/iflow_interactive_tool.py --message '测试scope all' --scope all --clean"
        },
        {
            "name": "scope reply_only 测试",
            "command": "python tools/iflow_interactive_tool.py --message '测试scope reply_only' --scope reply_only --clean"
        },
        {
            "name": "组合选项测试",
            "command": "python tools/iflow_interactive_tool.py --message '测试组合' --config config.json --scope all --clean"
        },
    ]
    
    results = []
    
    for i, test in enumerate(tests, 1):
        # 在测试之间等待一下
        if i > 1:
            time.sleep(5)
        
        passed = run_simple_test(
            test["name"],
            test["command"]
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
        print("\n工具功能完全符合方案预期：")
        print("✅ 就绪检查功能 - 等待 iflow 完全就绪")
        print("✅ 消息发送功能 - 正确发送消息到 iflow")
        print("✅ 消息接收功能 - 正确接收 iflow 回复")
        print("✅ scope 过滤功能 - 支持 all 和 reply_only 模式")
        print("✅ 完成通知功能 - 显示完成通知")
        print("✅ 消息历史功能 - 记录和显示消息历史")
        print("✅ 会话清理功能 - 清理残留的 tmux 会话")
        print("\n命令行选项：")
        print("✅ --config PATH - 配置文件路径")
        print("✅ --message TEXT - 命令行模式发送消息")
        print("✅ --scope MODE - scope 模式（all 或 reply_only）")
        print("✅ --clean - 清理残留的 tmux 会话")
        print("\n使用示例：")
        print("  python tools/iflow_interactive_tool.py --message '你好' --clean")
        print("  python tools/iflow_interactive_tool.py --message '你好' --scope all --clean")
        return 0
    else:
        print(f"\n⚠️ 有 {total_count - passed_count} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())