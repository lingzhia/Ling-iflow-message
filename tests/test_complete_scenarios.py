#!/usr/bin/env python3
"""
完整场景测试

对照设计方案，测试不同的对话场景，验证消息提取的正确性。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor


def test_scenario_1_single_message():
    """场景 1: 单条消息对话"""
    print("\n" + "=" * 60)
    print("场景 1: 单条消息对话")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
Hi～今天想做点什么
> 你好，请简单回复一下
✦ 你好！我是一个 AI 助手，很高兴为你服务。
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    assert len(messages) == 1, f"期望: 1 个消息, 实际: {len(messages)} 个"
    
    print(f"消息类型: {messages[0]['marker_type']}")
    assert messages[0]['marker_type'] == '✦', f"期望: ✦, 实际: {messages[0]['marker_type']}"
    
    print(f"消息内容: {messages[0]['content']}")
    assert "你好！我是一个 AI 助手" in messages[0]['content']
    
    print("✅ 场景 1 通过")


def test_scenario_2_multiple_messages():
    """场景 2: 多条消息对话"""
    print("\n" + "=" * 60)
    print("场景 2: 多条消息对话")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
> 请帮我写一个 Python 函数
✦ 好的，我来帮你写一个 Python 函数。
✦ 这里是一个示例函数：
  def hello():
      print("Hello, World!")
✦ 这个函数会打印一条消息。
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    assert len(messages) == 3, f"期望: 3 个消息, 实际: {len(messages)} 个"
    
    for i, msg in enumerate(messages):
        print(f"消息 {i+1}: {msg['marker_type']} - {msg['content'][:50]}...")
    
    assert messages[0]['marker_type'] == '✦'
    assert messages[1]['marker_type'] == '✦'
    assert messages[2]['marker_type'] == '✦'
    
    print("✅ 场景 2 通过")


def test_scenario_3_with_thinking():
    """场景 3: 带思考的对话"""
    print("\n" + "=" * 60)
    print("场景 3: 带思考的对话")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
> 帮我分析一下这个代码
✻ 让我先分析一下这段代码的逻辑
✻ 这段代码首先定义了一个变量
✻ 然后进行了一些计算
✦ 好的，我来分析这段代码。
✦ 这段代码的逻辑如下：
  1. 定义变量
  2. 进行计算
  3. 返回结果
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    assert len(messages) == 5, f"期望: 5 个消息, 实际: {len(messages)} 个"
    
    # 验证消息类型顺序
    assert messages[0]['marker_type'] == '✻', f"第1条应该是思考"
    assert messages[1]['marker_type'] == '✻', f"第2条应该是思考"
    assert messages[2]['marker_type'] == '✻', f"第3条应该是思考"
    assert messages[3]['marker_type'] == '✦', f"第4条应该是回复"
    assert messages[4]['marker_type'] == '✦', f"第5条应该是回复"
    
    print("✅ 场景 3 通过")


def test_scenario_4_long_message():
    """场景 4: 长消息对话"""
    print("\n" + "=" * 60)
    print("场景 4: 长消息对话")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
> 请写一篇关于 Python 的介绍
✦ Python 是一种高级编程语言，由 Guido van Rossum 于 1991 年创建。
✦ Python 的设计哲学强调代码的可读性和简洁的语法。
  相比于 C++ 或 Java，Python 让开发者能够用更少的代码表达概念。
✦ Python 的应用领域非常广泛：
  1. Web 开发
  2. 数据科学
  3. 人工智能
  4. 自动化
  5. 网络爬虫
✦ Python 有丰富的第三方库，如 NumPy、Pandas、Django 等。
✦ Python 的社区非常活跃，有大量的文档和教程可供学习。
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    assert len(messages) == 5, f"期望: 5 个消息, 实际: {len(messages)} 个"
    
    # 验证每条消息的内容
    for i, msg in enumerate(messages):
        print(f"消息 {i+1} 长度: {len(msg['content'])} 字符")
        assert len(msg['content']) > 0, f"消息 {i+1} 内容为空"
    
    print("✅ 场景 4 通过")


def test_scenario_5_with_tui():
    """场景 5: 包含 TUI 界面的对话"""
    print("\n" + "=" * 60)
    print("场景 5: 包含 TUI 界面的对话")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
> 你好
✦ 你好！
⠦ 生成中 2s ... (按esc取消)
思考: 开启
上下文剩余: 10000 tokens
---
✦ 我是一个 AI 助手。
✻ 思考中...
  我应该介绍我自己
✦ 我可以帮你回答问题、写作、编程等。
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    # 应该提取 4 个消息（3 个 ✦ + 1 个 ✻）
    assert len(messages) == 4, f"期望: 4 个消息, 实际: {len(messages)} 个"
    
    # 验证 TUI 被过滤掉了
    for msg in messages:
        content = msg['content']
        assert "生成中" not in content, f"消息中不应该包含 '生成中': {content}"
        assert "思考: 开启" not in content, f"消息中不应该包含 '思考: 开启': {content}"
        assert "上下文剩余" not in content, f"消息中不应该包含 '上下文剩余': {content}"
    
    print("✅ 场景 5 通过")


def test_scenario_6_edge_case_empty():
    """场景 6: 边界情况 - 空消息"""
    print("\n" + "=" * 60)
    print("场景 6: 边界情况 - 空消息")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
> 
✦ 你好！
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    # 应该提取 1 个消息
    assert len(messages) == 1, f"期望: 1 个消息, 实际: {len(messages)} 个"
    
    print("✅ 场景 6 通过")


def test_scenario_7_edge_case_only_tui():
    """场景 7: 边界情况 - 只有 TUI"""
    print("\n" + "=" * 60)
    print("场景 7: 边界情况 - 只有 TUI")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
⠦ 生成中 5s ... (按esc取消)
思考: 开启
上下文剩余: 8000 tokens
---
═══════════════════════════════════════════
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    # 应该提取 0 个消息
    assert len(messages) == 0, f"期望: 0 个消息, 实际: {len(messages)} 个"
    
    print("✅ 场景 7 通过")


def test_scenario_8_edge_case_only_markers():
    """场景 8: 边界情况 - 只有标记"""
    print("\n" + "=" * 60)
    print("场景 8: 边界情况 - 只有标记")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
✦ 消息1
✦ 消息2
✻ 思考
✦ 消息3
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    # 应该提取 4 个消息
    assert len(messages) == 4, f"期望: 4 个消息, 实际: {len(messages)} 个"
    
    print("✅ 场景 8 通过")


def test_scenario_9_message_filtering():
    """场景 9: 消息过滤测试 - 验证去掉发送消息前的内容"""
    print("\n" + "=" * 60)
    print("场景 9: 消息过滤测试")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
Hi～今天想做点什么
> 用户的问题
✦ 回答1
✦ 回答2
"""
    
    # 第一次提取
    messages_1 = monitor._extract_messages(test_output)
    
    print(f"第一次提取的消息数量: {len(messages_1)}")
    assert len(messages_1) == 2, f"期望: 2 个消息, 实际: {len(messages_1)} 个"
    
    # 验证消息内容不包含用户问题
    for msg in messages_1:
        content = msg['content']
        assert "用户的问题" not in content, f"消息中不应该包含用户问题: {content}"
        assert "Hi～今天想做点什么" not in content, f"消息中不应该包含欢迎语: {content}"
    
    print("✅ 场景 9 通过")


def test_scenario_10_message_order():
    """场景 10: 消息顺序测试"""
    print("\n" + "=" * 60)
    print("场景 10: 消息顺序测试")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
> 问题
✻ 思考1
✦ 回答1
✻ 思考2
✦ 回答2
✻ 思考3
✦ 回答3
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    assert len(messages) == 6, f"期望: 6 个消息, 实际: {len(messages)} 个"
    
    # 验证顺序
    expected_order = ['✻', '✦', '✻', '✦', '✻', '✦']
    actual_order = [msg['marker_type'] for msg in messages]
    
    print(f"期望顺序: {expected_order}")
    print(f"实际顺序: {actual_order}")
    
    assert actual_order == expected_order, f"消息顺序不正确"
    
    print("✅ 场景 10 通过")


def test_scenario_11_real_world_complex():
    """场景 11: 真实世界复杂对话"""
    print("\n" + "=" * 60)
    print("场景 11: 真实世界复杂对话")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
Hi～今天想做点什么
> 请帮我写一个快速排序算法的 Python 实现
✻ 我需要写一个快速排序算法
✻ 快速排序使用分治法
✻ 选择一个基准元素，将数组分成两部分
✻ 递归地对两部分进行排序
✦ 好的，我来帮你写一个快速排序算法的 Python 实现。
✦ 这里是代码：
  def quick_sort(arr):
      if len(arr) <= 1:
          return arr
      pivot = arr[len(arr) // 2]
      left = [x for x in arr if x < pivot]
      middle = [x for x in arr if x == pivot]
      right = [x for x in arr if x > pivot]
      return quick_sort(left) + middle + quick_sort(right)
✦ 这个实现的时间复杂度是 O(n log n)。
✦ 让我再给你一个使用示例：
  arr = [3, 6, 8, 10, 1, 2, 1]
  print(quick_sort(arr))
✦ 这会输出排序后的数组。
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    # 修正期望值：根据实际提取逻辑，应该是 9 个消息
    # 因为每个带缩进的行都会被当作独立的消息
    assert len(messages) == 9, f"期望: 9 个消息, 实际: {len(messages)} 个"
    
    # 验证消息类型
    type_counts = {'✦': 0, '✻': 0}
    for msg in messages:
        type_counts[msg['marker_type']] += 1
    
    print(f"✦ 消息数量: {type_counts['✦']}")
    print(f"✻ 消息数量: {type_counts['✻']}")
    
    assert type_counts['✻'] == 4, f"期望 4 条思考消息"
    assert type_counts['✦'] == 5, f"期望 5 条回复消息"
    
    # 验证代码内容
    code_found = False
    for msg in messages:
        if "def quick_sort" in msg['content']:
            code_found = True
            break
    
    assert code_found, "应该找到快速排序代码"
    
    print("✅ 场景 11 通过")


def test_scenario_12_mixed_content():
    """场景 12: 混合内容测试"""
    print("\n" + "=" * 60)
    print("场景 12: 混合内容测试")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
> 解释什么是递归
✦ 递归是指一个函数调用自身的过程。
✦ 递归通常包含两个部分：
  1. 基准情况（停止条件）
  2. 递归情况（调用自身）
✦ 举个简单的例子：
✦ 计算阶乘的函数：
  def factorial(n):
      if n <= 1:
          return 1
      return n * factorial(n - 1)
✦ 这个函数会一直调用自己，直到 n <= 1。
✻ 让我解释一下这个例子
✻ 当 n = 5 时，factorial(5) = 5 * factorial(4)
✻ factorial(4) = 4 * factorial(3)
✻ 依此类推，直到 factorial(1) = 1
✦ 递归的优点是代码简洁，但要注意避免无限递归。
"""
    
    messages = monitor._extract_messages(test_output)
    
    print(f"提取的消息数量: {len(messages)}")
    # 修正期望值：根据实际提取逻辑，应该是 10 个消息
    assert len(messages) == 10, f"期望: 10 个消息, 实际: {len(messages)} 个"
    
    # 验证缩进内容被正确收集
    has_indented = False
    for msg in messages:
        if "def factorial" in msg['content']:
            # 应该包含缩进的代码
            assert "if n <= 1:" in msg['content'], "应该包含完整的函数"
            has_indented = True
    
    assert has_indented, "应该找到包含缩进代码的消息"
    
    print("✅ 场景 12 通过")


def main():
    """运行所有场景测试"""
    print("\n" + "=" * 60)
    print("开始完整场景测试")
    print("=" * 60)
    
    scenarios = [
        ("场景 1: 单条消息对话", test_scenario_1_single_message),
        ("场景 2: 多条消息对话", test_scenario_2_multiple_messages),
        ("场景 3: 带思考的对话", test_scenario_3_with_thinking),
        ("场景 4: 长消息对话", test_scenario_4_long_message),
        ("场景 5: 包含 TUI 界面的对话", test_scenario_5_with_tui),
        ("场景 6: 边界情况 - 空消息", test_scenario_6_edge_case_empty),
        ("场景 7: 边界情况 - 只有 TUI", test_scenario_7_edge_case_only_tui),
        ("场景 8: 边界情况 - 只有标记", test_scenario_8_edge_case_only_markers),
        ("场景 9: 消息过滤测试", test_scenario_9_message_filtering),
        ("场景 10: 消息顺序测试", test_scenario_10_message_order),
        ("场景 11: 真实世界复杂对话", test_scenario_11_real_world_complex),
        ("场景 12: 混合内容测试", test_scenario_12_mixed_content),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in scenarios:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ {name} 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ {name} 出错: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    if failed == 0:
        print("✅ 所有场景测试通过！")
        return 0
    else:
        print("❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())