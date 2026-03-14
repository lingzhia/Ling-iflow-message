#!/usr/bin/env python3
"""
调试场景 11
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor


def debug_scenario_11():
    """调试场景 11"""
    print("\n" + "=" * 60)
    print("调试场景 11")
    print("=" * 60)
    
    controller = IFlowController("test_session")
    monitor = IFlowMonitor(controller)
    
    test_output = """
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
    
    print(f"\n提取的消息数量: {len(messages)}")
    print(f"期望的消息数量: 7")
    
    print("\n提取的消息详情:")
    for i, msg in enumerate(messages):
        print(f"\n消息 {i+1}:")
        print(f"  类型: {msg['marker_type']}")
        print(f"  内容: {msg['content']}")
        print(f"  长度: {len(msg['content'])}")
    
    # 统计消息类型
    type_counts = {'✦': 0, '✻': 0}
    for msg in messages:
        type_counts[msg['marker_type']] += 1
    
    print(f"\n✦ 消息数量: {type_counts['✦']} (期望: 3)")
    print(f"✻ 消息数量: {type_counts['✻']} (期望: 4)")
    
    # 查看原始输出
    print("\n原始输出:")
    print(test_output)


if __name__ == "__main__":
    debug_scenario_11()