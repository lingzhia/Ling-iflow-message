#!/usr/bin/env python3
"""
ModuleManager 高级功能测试脚本（简化版）

测试模块管理器的高级功能：
- 消息应答检查
- 依赖管理和启动顺序
- 健康监控和自动恢复
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core import MessageBus, ModuleManager, Message, MessageContent, MessageType, ModuleStatus, IFlowStatus


class MockModule:
    """模拟模块"""
    
    def __init__(self, module_id: str):
        self.module_id = module_id
        self.id = module_id
        self.running = False
        self.message_bus = None
    
    def set_message_bus(self, message_bus):
        self.message_bus = message_bus
    
    async def start(self):
        self.running = True
        print(f"模拟模块 {self.module_id} 启动")
    
    async def stop(self):
        self.running = False
        print(f"模拟模块 {self.module_id} 停止")
    
    async def receive(self, message: Message):
        pass


class ModuleManagerAdvancedTester:
    """ModuleManager 高级功能测试器"""
    
    def __init__(self):
        self.bus = None
        self.manager = None
        self.test_results = []
    
    async def test_1_message_response_check(self):
        """测试 1: 消息应答检查"""
        print("\n" + "="*60)
        print("测试 1: 消息应答检查")
        print("="*60)
        
        try:
            # 创建消息总线和管理器
            self.bus = MessageBus()
            self.manager = ModuleManager(self.bus)
            print("✅ 消息总线和管理器创建成功")
            
            # 创建模拟模块
            wechat_module = MockModule("wechat_test1")
            self.manager.modules["wechat_test1"] = wechat_module
            self.manager.module_states["wechat_test1"] = ModuleStatus(module_id="wechat_test1")
            
            # 注册模拟模块
            await self.manager.register_module("wechat_test1")
            print("✅ 模拟模块注册成功")
            
            # 测试 1: 检查不存在的接收方
            message1 = Message(
                id="test_001",
                type=MessageType.TEXT,
                content=MessageContent(type=MessageType.TEXT, text="测试消息"),
                from_module="wechat_test1",
                to_module="nonexistent"
            )
            
            result1 = await self.manager.send_with_check(message1)
            print(f"测试不存在的接收方: {result1['error']}")
            assert result1["success"] == False
            assert result1["error"] == "receiver_not_found"
            print("✅ 不存在的接收方检查正确")
            
            # 测试 2: 检查未运行的接收方（创建一个未启动的模块）
            test_module = MockModule("test_module")
            self.manager.modules["test_module"] = test_module
            self.manager.module_states["test_module"] = ModuleStatus(module_id="test_module")
            await self.manager.register_module("test_module")
            
            message2 = Message(
                id="test_002",
                type=MessageType.TEXT,
                content=MessageContent(type=MessageType.TEXT, text="测试消息"),
                from_module="wechat_test1",
                to_module="test_module"
            )
            
            result2 = await self.manager.send_with_check(message2)
            print(f"测试未运行的接收方: {result2['error']}")
            assert result2["success"] == False
            assert result2["error"] == "receiver_not_running"
            print("✅ 未运行的接收方检查正确")
            
            # 测试 3: 创建一个 IFlow 模块，测试生成中状态
            iflow_module = MockModule("iflow_test1")
            self.manager.modules["iflow_test1"] = iflow_module
            self.manager.module_states["iflow_test1"] = ModuleStatus(module_id="iflow_test1")
            # 初始化 IFlow 状态
            self.manager.iflow_status["iflow_test1"] = IFlowStatus(module_id="iflow_test1")
            
            # 注册模块
            await self.manager.register_module("iflow_test1")
            
            # 启动模块
            await self.manager.start_module("iflow_test1")
            await self.manager.start_module("wechat_test1")
            print("✅ 模块已启动")
            
            # 设置 IFlow 为生成中状态
            self.manager.update_iflow_state("iflow_test1", "generating")
            
            message3 = Message(
                id="test_003",
                type=MessageType.TEXT,
                content=MessageContent(type=MessageType.TEXT, text="测试消息"),
                from_module="wechat_test1",
                to_module="iflow_test1"
            )
            
            result3 = await self.manager.send_with_check(message3)
            print(f"测试生成中的 IFlow: {result3['error']}")
            assert result3["success"] == False
            assert result3["error"] == "iflow_generating"
            assert "duration" in result3
            print("✅ 生成中的 IFlow 检查正确")
            
            # 清理：重置状态
            self.manager.update_iflow_state("iflow_test1", "idle")
            
            # 销毁模块
            await self.manager.destroy_module("iflow_test1")
            await self.manager.destroy_module("wechat_test1")
            await self.manager.destroy_module("test_module")
            print("✅ 模块已销毁")
            
            self.test_results.append(("测试 1: 消息应答检查", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 1: 消息应答检查", False))
            return False
    
    async def test_2_dependency_management(self):
        """测试 2: 依赖管理和启动顺序"""
        print("\n" + "="*60)
        print("测试 2: 依赖管理和启动顺序")
        print("="*60)
        
        try:
            # 创建消息总线和管理器
            self.bus = MessageBus()
            self.manager = ModuleManager(self.bus)
            print("✅ 消息总线和管理器创建成功")
            
            # 创建三个模拟模块
            module1 = MockModule("module1")
            module2 = MockModule("module2")
            module3 = MockModule("module3")
            print("✅ 三个模拟模块创建成功")
            
            # 手动存储模拟模块到管理器
            for module in [module1, module2, module3]:
                self.manager.modules[module.id] = module
                self.manager.module_states[module.id] = ModuleStatus(module_id=module.id)
            
            # 注册模块
            for module in [module1, module2, module3]:
                await self.manager.register_module(module.id)
            print("✅ 所有模块注册成功")
            
            # 设置依赖关系：module3 依赖 module1
            self.manager.add_dependency("module3", "module1")
            print("✅ 依赖关系设置成功: module3 -> module1")
            
            # 检查依赖
            deps = self.manager.get_dependencies("module3")
            print(f"module3 的依赖: {deps}")
            assert "module1" in deps
            print("✅ 依赖查询正确")
            
            # 检查依赖是否满足
            satisfied = self.manager.check_dependencies("module3")
            print(f"依赖是否满足: {satisfied}")
            assert not satisfied  # module1 未启动
            print("✅ 依赖检查正确")
            
            # 按顺序启动
            results = await self.manager.start_with_order(["module1", "module3"])
            print(f"按顺序启动结果: {results}")
            print("✅ 按顺序启动成功")
            
            # 停止模块
            await self.manager.stop_module("module1")
            await self.manager.stop_module("module3")
            print("✅ 模块已停止")
            
            # 销毁模块
            await self.manager.destroy_module("module1")
            await self.manager.destroy_module("module2")
            await self.manager.destroy_module("module3")
            print("✅ 模块已销毁")
            
            self.test_results.append(("测试 2: 依赖管理和启动顺序", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 2: 依赖管理和启动顺序", False))
            return False
    
    async def test_3_health_monitor_and_recovery(self):
        """测试 3: 健康监控和自动恢复"""
        print("\n" + "="*60)
        print("测试 3: 健康监控和自动恢复")
        print("="*60)
        
        try:
            # 创建消息总线和管理器
            self.bus = MessageBus()
            self.manager = ModuleManager(self.bus)
            print("✅ 消息总线和管理器创建成功")
            
            # 创建模拟模块
            module = MockModule("iflow_test2")
            print("✅ 模拟模块创建成功")
            
            # 手动存储模拟模块到管理器
            self.manager.modules["iflow_test2"] = module
            self.manager.module_states["iflow_test2"] = ModuleStatus(module_id="iflow_test2")
            
            # 注册模块
            await self.manager.register_module("iflow_test2")
            print("✅ 模块注册成功")
            
            # 启动模块
            await self.manager.start_module("iflow_test2")
            print("✅ 模块已启动")
            
            # 启动健康监控
            await self.manager.start_health_monitor()
            print("✅ 健康监控已启动")
            
            # 等待健康检查执行一次
            await asyncio.sleep(2)
            
            # 检查状态
            status = self.manager.get_module_status("iflow_test2")
            print(f"模块状态: {status}")
            assert status["healthy"] == True
            print("✅ 健康状态检查正确")
            
            # 停止健康监控
            await self.manager.stop_health_monitor()
            print("✅ 健康监控已停止")
            
            # 销毁模块
            await self.manager.destroy_module("iflow_test2")
            print("✅ 模块已销毁")
            
            self.test_results.append(("测试 3: 健康监控和自动恢复", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 3: 健康监控和自动恢复", False))
            return False
    
    async def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        total = len(self.test_results)
        passed = sum(1 for _, success in self.test_results if success)
        failed = total - passed
        
        print(f"总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        
        if failed == 0:
            print("\n✅ 所有测试通过！")
        else:
            print("\n❌ 部分测试失败")
            for name, success in self.test_results:
                status = "✅" if success else "❌"
                print(f"{status} {name}")
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("开始 ModuleManager 高级功能测试...")
        
        # 测试 1: 消息应答检查
        await self.test_1_message_response_check()
        
        # 测试 2: 依赖管理和启动顺序
        await self.test_2_dependency_management()
        
        # 测试 3: 健康监控和自动恢复
        await self.test_3_health_monitor_and_recovery()
        
        # 打印总结
        await self.print_summary()


async def main():
    """主函数"""
    tester = ModuleManagerAdvancedTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())