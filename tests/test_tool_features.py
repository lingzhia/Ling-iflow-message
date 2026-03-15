#!/usr/bin/env python3
"""
测试工具的功能是否符合方案预期
"""

import subprocess
import sys
import time

def test_feature(name, command, checks, timeout=180):
    """测试功能"""
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
        
        # 检查所有预期结果
        all_passed = True
        for check_name, check_pattern in checks.items():
            if check_pattern in result.stdout:
                print(f"✅ {check_name}")
            else:
                print(f"❌ {check_name} - 未找到: {check_pattern}")
                all_passed = False
        
        if all_passed:
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
    print("测试工具的功能是否符合方案预期")
    print("=" * 60)
    
    # 清理残留会话
    print("\n清理残留的 tmux 会话...")
    subprocess.run("tmux kill-session -t iflow1 2>/dev/null", shell=True)
    subprocess.run("tmux kill-session -t iflow2 2>/dev/null", shell=True)
    time.sleep(1)
    
    tests = [
        {
            "name": "就绪检查功能",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --clean",
            "checks": {
                "等待 iflow 完全就绪": "等待 iflow 完全就绪",
                "iflow 已完全就绪": "iflow 已完全就绪",
                "可以发送消息": "可以发送消息"
            }
        },
        
        {
            "name": "消息发送功能",
            "command": "python tools/iflow_interactive_tool.py --message '收到请回答' --clean",
            "checks": {
                "发送消息": "发送消息:",
                "mock_bus.route()": "mock_bus.route()"
            }
        },
        
        {
            "name": "消息接收功能",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --clean",
            "checks": {
                "等待回复": "等待回复完成",
                "收到消息": "收到",
                "回复消息": "📤 [✦ 回复]"
            }
        },
        
        {
            "name": "scope 过滤功能 - all",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --scope all --clean",
            "checks": {
                "回复消息": "📤 [✦ 回复]"
            }
        },
        
        {
            "name": "scope 过滤功能 - reply_only",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --scope reply_only --clean",
            "checks": {
                "只显示回复": "📤 [✦ 回复]"
            }
        },
        
        {
            "name": "完成通知功能",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --clean",
            "checks": {
                "完成消息": "✅ [完成]",
                "回复结束": "回复结束",
                "生成完成": "✅ 生成完成"
            }
        },
        
        {
            "name": "消息历史功能",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --clean",
            "checks": {
                "显示历史": "📝 消息历史"
            }
        },
        
        {
            "name": "会话清理功能",
            "command": "python tools/iflow_interactive_tool.py --message '测试' --clean",
            "checks": {
                "清理残留会话": "已清理残留的 tmux 会话",
                "模块已停止": "模块已停止"
            }
        },
    ]
    
    results = []
    
    for i, test in enumerate(tests, 1):
        # 在测试之间等待一下
        if i > 1:
            time.sleep(5)
        
        passed = test_feature(
            test["name"],
            test["command"],
            test["checks"]
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
        print("\n🎉 所有功能测试通过！")
        print("\n工具功能完全符合方案预期：")
        print("✅ 就绪检查功能 - 等待 iflow 完全就绪")
        print("✅ 消息发送功能 - 正确发送消息到 iflow")
        print("✅ 消息接收功能 - 正确接收 iflow 回复")
        print("✅ scope 过滤功能 - 支持 all 和 reply_only 模式")
        print("✅ 完成通知功能 - 显示完成通知")
        print("✅ 消息历史功能 - 记录和显示消息历史")
        print("✅ 会话清理功能 - 清理残留的 tmux 会话")
        return 0
    else:
        print(f"\n⚠️ 有 {total_count - passed_count} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())