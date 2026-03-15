#!/usr/bin/env python3
"""
ModuleManager 基础功能测试脚本

测试模块管理器的核心功能：
- 模块创建和销毁
- 模块注册和注销
- 模块启动和停止
- 状态管理
- 组管理
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core import MessageBus, ModuleManager


class ModuleManagerTester:
    """ModuleManager 测试器"""
    
    def __init__(self):
        self.bus = None
        self.manager = None
        self.test_results = []
    
    async def test_1_create_and_register(self):
        """测试 1: 模块创建和注册"""
        print("\n" + "="*60)
        print("测试 1: 模块创建和注册")
        print("="*60)
        
        try:
            # 创建消息总线
            self.bus = MessageBus()
            print("✅ 消息总线创建成功")
            
            # 创建模块管理器
            self.manager = ModuleManager(self.bus)
            print("✅ 模块管理器创建成功")
            
            # 创建 iflow 模块
            iflow = await self.manager.create_module(
                module_type="iflow",
                module_id="iflow_test",
                config={
                    "tmux_session": "iflow_test",
                    "model": "kimi-k2.5",
                    "workspace": "~/.iflow"
                }
            )
            print(f"✅ IFlow 模块创建成功: {iflow}")
            
            # 注册模块
            await self.manager.register_module("iflow_test")
            print("✅ IFlow 模块注册成功")
            
            # 设置消息总线引用
            self.manager.set_message_bus_for_module("iflow_test")
            print("✅ 消息总线引用设置成功")
            
            # 检查模块是否在消息总线中
            if "iflow_test" in self.bus.modules:
                print("✅ 模块已在消息总线中")
            else:
                print("❌ 模块未在消息总线中")
                return False
            
            self.test_results.append(("测试 1: 模块创建和注册", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            self.test_results.append(("测试 1: 模块创建和注册", False))
            return False
    
    async def test_2_status_management(self):
        """测试 2: 状态管理"""
        print("\n" + "="*60)
        print("测试 2: 状态管理")
        print("="*60)
        
        try:
            # 检查模块状态
            status = self.manager.get_module_status("iflow_test")
            print(f"模块状态: {status}")
            
            # 检查是否运行
            running = self.manager.is_module_running("iflow_test")
            print(f"是否运行: {running}")
            
            # 检查是否健康
            healthy = self.manager.is_module_healthy("iflow_test")
            print(f"是否健康: {healthy}")
            
            # 获取所有状态
            all_status = self.manager.get_all_status()
            print(f"所有模块状态: {all_status}")
            
            self.test_results.append(("测试 2: 状态管理", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            self.test_results.append(("测试 2: 状态管理", False))
            return False
    
    async def test_3_group_management(self):
        """测试 3: 组管理"""
        print("\n" + "="*60)
        print("测试 3: 组管理")
        print("="*60)
        
        try:
            # 定义组
            self.manager.define_group("test_group", ["iflow_test"])
            print("✅ 组定义成功: test_group")
            
            # 获取组模块
            group_modules = self.manager.get_group_modules("test_group")
            print(f"组模块: {group_modules}")
            
            if "iflow_test" in group_modules:
                print("✅ 模块在组中")
            else:
                print("❌ 模块不在组中")
                return False
            
            self.test_results.append(("测试 3: 组管理", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            self.test_results.append(("测试 3: 组管理", False))
            return False
    
    async def test_4_iflow_status(self):
        """测试 4: IFlow 状态管理"""
        print("\n" + "="*60)
        print("测试 4: IFlow 状态管理")
        print("="*60)
        
        try:
            # 获取 IFlow 状态
            iflow_status = self.manager.get_iflow_status("iflow_test")
            print(f"IFlow 状态: {iflow_status}")
            
            # 检查是否可用
            available = self.manager.is_iflow_available("iflow_test")
            print(f"是否可用: {available}")
            
            # 更新状态
            self.manager.update_iflow_state("iflow_test", "idle")
            print("✅ 状态更新成功: idle")
            
            # 再次检查状态
            iflow_status = self.manager.get_iflow_status("iflow_test")
            print(f"更新后状态: {iflow_status}")
            
            self.test_results.append(("测试 4: IFlow 状态管理", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            self.test_results.append(("测试 4: IFlow 状态管理", False))
            return False
    
    async def test_5_destroy_module(self):
        """测试 5: 销毁模块"""
        print("\n" + "="*60)
        print("测试 5: 销毁模块")
        print("="*60)
        
        try:
            # 销毁模块
            success = await self.manager.destroy_module("iflow_test")
            print(f"销毁结果: {success}")
            
            if success:
                print("✅ 模块销毁成功")
            else:
                print("❌ 模块销毁失败")
                return False
            
            # 检查模块是否还存在
            if "iflow_test" not in self.manager.modules:
                print("✅ 模块已从管理器中移除")
            else:
                print("❌ 模块仍在管理器中")
                return False
            
            # 检查模块是否在消息总线中
            if "iflow_test" not in self.bus.modules:
                print("✅ 模块已从消息总线中移除")
            else:
                print("❌ 模块仍在消息总线中")
                return False
            
            self.test_results.append(("测试 5: 销毁模块", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            self.test_results.append(("测试 5: 销毁模块", False))
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
        print("开始 ModuleManager 基础功能测试...")
        
        # 测试 1: 模块创建和注册
        await self.test_1_create_and_register()
        
        # 测试 2: 状态管理
        await self.test_2_status_management()
        
        # 测试 3: 组管理
        await self.test_3_group_management()
        
        # 测试 4: IFlow 状态管理
        await self.test_4_iflow_status()
        
        # 测试 5: 销毁模块
        await self.test_5_destroy_module()
        
        # 打印总结
        await self.print_summary()


async def main():
    """主函数"""
    tester = ModuleManagerTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())