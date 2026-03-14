#!/usr/bin/env python3
"""
测试消息提取功能

测试三个技术问题的解决方案：
1. 如何准确识别 iflow 接收消息？
2. 如何准确识别 TUI 界面？
3. 如何准确识别发送消息的分界线？
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor


def test_extract_received_message():
    """测试提取接收消息的功能"""
    print("\n" + "=" * 60)
    print("测试 1: 提取接收消息")
    print("=" * 60)
    
    # 创建一个 mock controller
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    # 测试用例 1: 正常的接收消息
    test_output_1 = """
> 用户的消息内容
✦ 回复内容
"""
    lines_1 = test_output_1.split('\n')
    received_msg, received_line = monitor._extract_received_message(lines_1)
    
    assert received_msg == "用户的消息内容", f"期望: '用户的消息内容', 实际: '{received_msg}'"
    assert received_line == 1, f"期望行号: 1, 实际: {received_line}"
    print("✅ 测试用例 1 通过: 正常的接收消息")
    
    # 测试用例 2: 多行中的接收消息
    test_output_2 = """
Hi～今天想做点什么
> 第二个消息
✦ 回复内容
"""
    lines_2 = test_output_2.split('\n')
    received_msg, received_line = monitor._extract_received_message(lines_2)
    
    assert received_msg == "第二个消息", f"期望: '第二个消息', 实际: '{received_msg}'"
    assert received_line == 2, f"期望行号: 2, 实际: {received_line}"
    print("✅ 测试用例 2 通过: 多行中的接收消息")
    
    # 测试用例 3: 没有接收消息
    test_output_3 = """
Hi～今天想做点什么
✦ 回复内容
"""
    lines_3 = test_output_3.split('\n')
    received_msg, received_line = monitor._extract_received_message(lines_3)
    
    assert received_msg is None, f"期望: None, 实际: '{received_msg}'"
    assert received_line is None, f"期望: None, 实际: {received_line}"
    print("✅ 测试用例 3 通过: 没有接收消息")
    
    print("\n✅ 所有提取接收消息测试通过")


def test_is_tui_line():
    """测试 TUI 界面识别功能"""
    print("\n" + "=" * 60)
    print("测试 2: TUI 界面识别")
    print("=" * 60)
    
    # 创建一个 mock controller
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    # 测试用例 1: 生成中行
    line_1 = "⠦ 生成中 6m 37s ... (按esc取消)"
    is_tui = monitor._is_tui_line(line_1)
    assert is_tui == True, f"期望: True, 实际: {is_tui}"
    print("✅ 测试用例 1 通过: 生成中行")
    
    # 测试用例 2: 思考行
    line_2 = "思考: 开启"
    is_tui = monitor._is_tui_line(line_2)
    assert is_tui == True, f"期望: True, 实际: {is_tui}"
    print("✅ 测试用例 2 通过: 思考行")
    
    # 测试用例 3: 上下文剩余行
    line_3 = "上下文剩余: 5000 tokens"
    is_tui = monitor._is_tui_line(line_3)
    assert is_tui == True, f"期望: True, 实际: {is_tui}"
    print("✅ 测试用例 3 通过: 上下文剩余行")
    
    # 测试用例 4: 分隔符行
    line_4 = "---"
    is_tui = monitor._is_tui_line(line_4)
    assert is_tui == True, f"期望: True, 实际: {is_tui}"
    print("✅ 测试用例 4 通过: 分隔符行")
    
    # 测试用例 5: 普通消息行
    line_5 = "这是一条普通的消息"
    is_tui = monitor._is_tui_line(line_5)
    assert is_tui == False, f"期望: False, 实际: {is_tui}"
    print("✅ 测试用例 5 通过: 普通消息行")
    
    # 测试用例 6: 标记行（应该不是 TUI）
    line_6 = "✦ 回复内容"
    is_tui = monitor._is_tui_line(line_6)
    assert is_tui == False, f"期望: False, 实际: {is_tui}"
    print("✅ 测试用例 6 通过: 标记行")
    
    print("\n✅ 所有 TUI 界面识别测试通过")


def test_extract_messages_with_filtering():
    """测试消息提取功能（带 TUI 过滤和消息定位）"""
    print("\n" + "=" * 60)
    print("测试 3: 消息提取（带过滤）")
    print("=" * 60)
    
    # 创建一个 mock controller
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    # 测试用例 1: 完整的 iflow 输出（包含 TUI 和接收消息）
    test_output = """
Hi～今天想做点什么
> 用户的消息内容
✦ 第一条回复
  这是第一条回复的扩展内容
✻ 思考中...
  这是思考内容
✦ 第二条回复
⠦ 生成中 6m 37s ... (按esc取消)
思考: 开启
上下文剩余: 5000 tokens
---
"""
    
    messages = monitor._extract_messages(test_output)
    
    # 验证提取的消息数量（2 个 ✦ + 1 个 ✻ = 3 个）
    assert len(messages) == 3, f"期望: 3 个消息, 实际: {len(messages)} 个"
    print(f"✅ 测试用例 1 通过: 提取了 {len(messages)} 个消息")
    
    # 验证消息类型
    assert messages[0]['marker_type'] == '✦', f"期望: ✦, 实际: {messages[0]['marker_type']}"
    assert messages[1]['marker_type'] == '✻', f"期望: ✻, 实际: {messages[1]['marker_type']}"
    assert messages[2]['marker_type'] == '✦', f"期望: ✦, 实际: {messages[2]['marker_type']}"
    print("✅ 测试用例 1 通过: 消息类型正确")
    
    # 验证消息内容
    assert "第一条回复" in messages[0]['content'], f"期望包含 '第一条回复', 实际: {messages[0]['content']}"
    assert "思考中" in messages[1]['content'], f"期望包含 '思考中', 实际: {messages[1]['content']}"
    assert "第二条回复" in messages[2]['content'], f"期望包含 '第二条回复', 实际: {messages[2]['content']}"
    print("✅ 测试用例 1 通过: 消息内容正确")
    
    # 测试用例 2: 没有 TUI 的输出
    test_output_2 = """
> 用户的消息
✦ 回复内容
  扩展内容
"""
    
    messages_2 = monitor._extract_messages(test_output_2)
    assert len(messages_2) == 1, f"期望: 1 个消息, 实际: {len(messages_2)} 个"
    print("✅ 测试用例 2 通过: 没有 TUI 的输出")
    
    # 测试用例 3: 只有 TUI 的输出
    test_output_3 = """
⠦ 生成中 6m 37s ... (按esc取消)
思考: 开启
上下文剩余: 5000 tokens
---
"""
    
    messages_3 = monitor._extract_messages(test_output_3)
    assert len(messages_3) == 0, f"期望: 0 个消息, 实际: {len(messages_3)} 个"
    print("✅ 测试用例 3 通过: 只有 TUI 的输出")
    
    print("\n✅ 所有消息提取测试通过")


def test_controller_last_sent_message():
    """测试 IFlowController 记录最后发送消息的功能"""
    print("\n" + "=" * 60)
    print("测试 4: IFlowController 记录最后发送消息")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    
    # 测试用例 1: 初始状态
    last_sent = controller.get_last_sent_message()
    assert last_sent is None, f"期望: None, 实际: '{last_sent}'"
    print("✅ 测试用例 1 通过: 初始状态为 None")
    
    # 测试用例 2: 模拟发送消息（由于没有实际 tmux 会话，我们直接测试记录逻辑）
    # 注意：这个测试假设 send_message 会成功，实际上在没有 tmux 会话时会失败
    # 但我们主要测试记录逻辑，所以可以手动设置
    controller._last_sent_message = "测试消息"
    last_sent = controller.get_last_sent_message()
    assert last_sent == "测试消息", f"期望: '测试消息', 实际: '{last_sent}'"
    print("✅ 测试用例 2 通过: 记录最后发送消息")
    
    # 测试用例 3: 更新最后发送消息
    controller._last_sent_message = "新的测试消息"
    last_sent = controller.get_last_sent_message()
    assert last_sent == "新的测试消息", f"期望: '新的测试消息', 实际: '{last_sent}'"
    print("✅ 测试用例 3 通过: 更新最后发送消息")
    
    print("\n✅ 所有 IFlowController 测试通过")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("开始测试消息提取功能")
    print("=" * 60)
    
    try:
        test_extract_received_message()
        test_is_tui_line()
        test_extract_messages_with_filtering()
        test_controller_last_sent_message()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
