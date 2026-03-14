#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def add_numbers(a, b):
    """计算两个数之和"""
    return a + b

# 示例调用
if __name__ == "__main__":
    print("Hello, World!")

    # 计算两数之和
    result = add_numbers(3, 5)
    print(f"3 + 5 = {result}")

    result = add_numbers(10.5, 2.3)
    print(f"10.5 + 2.3 = {result}")