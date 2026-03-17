#!/usr/bin/env python3
"""
简单的组管理功能测试

只测试基本功能，不测试需要长时间等待的操作
"""

import socket
import json
import sys


def send_control_command(command: str, timeout: int = 5) -> dict:
    """通过 Unix Socket 发送控制命令
    
    Args:
        command: 控制命令
        timeout: 超时时间（秒）
        
    Returns:
        返回结果字典
    """
    socket_path = "/tmp/ling-iflow.sock"
    
    try:
        # 创建 Unix Socket 客户端
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(timeout)
        client.connect(socket_path)
        
        # 发送命令
        client.send(command.encode('utf-8'))
        
        # 接收响应
        response = client.recv(4096).decode('utf-8')
        
        # 关闭连接
        client.close()
        
        # 解析响应
        result = json.loads(response)
        return result
        
    except FileNotFoundError:
        return {"success": False, "error": "控制服务未运行"}
    except ConnectionRefusedError:
        return {"success": False, "error": "无法连接到控制服务"}
    except socket.timeout:
        return {"success": False, "error": "请求超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    """主函数"""
    print("\n" + "="*50)
    print("组管理功能测试")
    print("="*50)
    print()
    
    # 测试 1: 列出所有组
    print("测试 1: 列出所有组")
    result = send_control_command("list")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    test1 = result.get("success", False)
    
    # 测试 2: 查看所有组状态
    print("\n测试 2: 查看所有组状态")
    result = send_control_command("status")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    test2 = result.get("success", False)
    
    # 测试 3: 查看 g1 组状态
    print("\n测试 3: 查看 g1 组状态")
    result = send_control_command("status g1")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    test3 = result.get("success", False)
    
    # 汇总结果
    print("\n" + "="*50)
    print("测试结果汇总")
    print("="*50)
    
    passed = sum([test1, test2, test3])
    total = 3
    
    print(f"{'✅ 通过' if test1 else '❌ 失败'} - 列出所有组")
    print(f"{'✅ 通过' if test2 else '❌ 失败'} - 查看所有组状态")
    print(f"{'✅ 通过' if test3 else '❌ 失败'} - 查看 g1 组状态")
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有基础测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())