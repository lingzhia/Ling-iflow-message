#!/usr/bin/env python3
"""
测试组管理功能的脚本

测试 Unix Socket 控制接口和组管理命令
"""

import socket
import json
import sys


def send_control_command(command: str) -> dict:
    """通过 Unix Socket 发送控制命令
    
    Args:
        command: 控制命令
        
    Returns:
        返回结果字典
    """
    socket_path = "/tmp/ling-iflow.sock"
    
    try:
        # 创建 Unix Socket 客户端
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
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
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_list_groups():
    """测试列出所有组"""
    print("\n" + "="*50)
    print("测试 1: 列出所有组")
    print("="*50)
    
    result = send_control_command("list")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get("success"):
        print("✅ 测试通过")
        return True
    else:
        print(f"❌ 测试失败: {result.get('error')}")
        return False


def test_status_all():
    """测试查看所有组状态"""
    print("\n" + "="*50)
    print("测试 2: 查看所有组状态")
    print("="*50)
    
    result = send_control_command("status")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get("success"):
        print("✅ 测试通过")
        return True
    else:
        print(f"❌ 测试失败: {result.get('error')}")
        return False


def test_status_group():
    """测试查看指定组状态"""
    print("\n" + "="*50)
    print("测试 3: 查看 g1 组状态")
    print("="*50)
    
    result = send_control_command("status g1")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get("success"):
        print("✅ 测试通过")
        return True
    else:
        print(f"❌ 测试失败: {result.get('error')}")
        return False


def test_start_group():
    """测试启动组"""
    print("\n" + "="*50)
    print("测试 4: 启动 g2 组")
    print("="*50)
    
    result = send_control_command("start g2")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get("success"):
        print("✅ 测试通过")
        return True
    else:
        print(f"❌ 测试失败: {result.get('error')}")
        return False


def test_stop_group():
    """测试停止组"""
    print("\n" + "="*50)
    print("测试 5: 停止 g2 组")
    print("="*50)
    
    result = send_control_command("stop g2")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get("success"):
        print("✅ 测试通过")
        return True
    else:
        print(f"❌ 测试失败: {result.get('error')}")
        return False


def test_restart_group():
    """测试重启组"""
    print("\n" + "="*50)
    print("测试 6: 重启 g2 组")
    print("="*50)
    
    result = send_control_command("restart g2")
    print(f"结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    
    if result.get("success"):
        print("✅ 测试通过")
        return True
    else:
        print(f"❌ 测试失败: {result.get('error')}")
        return False


def main():
    """主函数"""
    print("\n" + "="*50)
    print("组管理功能测试")
    print("="*50)
    print("⚠️  请确保服务已启动（使用 ./manage.py start）")
    print()
    
    # 运行所有测试
    tests = [
        ("列出所有组", test_list_groups),
        ("查看所有组状态", test_status_all),
        ("查看 g1 组状态", test_status_group),
        ("启动 g2 组", test_start_group),
        ("停止 g2 组", test_stop_group),
        ("重启 g2 组", test_restart_group),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    print("\n" + "="*50)
    print("测试结果汇总")
    print("="*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())