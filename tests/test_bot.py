#!/usr/bin/env python3
"""
LingIflowBot 简化单元测试

只测试基本功能，避免创建实际模块
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.bot import LingIflowBot
from src.core import MessageBus, ModuleManager


class LingIflowBotSimpleTester:
    """LingIflowBot 简化测试器"""
    
    def __init__(self):
        self.test_results = []
    
    async def test_1_initialization(self):
        """测试 1: Bot 初始化"""
        print("\n" + "="*60)
        print("测试 1: Bot 初始化")
        print("="*60)
        
        try:
            # 创建 bot 实例
            bot = LingIflowBot(config_path="config.json", active_group="all")
            
            # 检查初始化
            assert bot.config_path == "config.json"
            assert bot.active_group == "all"
            assert bot.bus is None
            assert bot.manager is None
            assert bot._running is False
            
            print("✅ Bot 初始化成功")
            self.test_results.append(("测试 1: Bot 初始化", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 1: Bot 初始化", False))
            return False
    
    async def test_2_load_config(self):
        """测试 2: 配置加载"""
        print("\n" + "="*60)
        print("测试 2: 配置加载")
        print("="*60)
        
        try:
            # 创建临时配置文件
            config_data = {
                "log_level": "DEBUG",
                "tmux_sessions": [
                    {"name": "iflow1", "workspace": "~/.iflow", "model": "kimi-k2.5"}
                ],
                "bots": [
                    {
                        "name": "bot1",
                        "enabled": True,
                        "tmux_session": "iflow1",
                        "corp_id": "test_corp",
                        "agent_id": "1",
                        "secret": "test_secret",
                        "user_id": "test_user",
                        "token": "test_token",
                        "encoding_aes_key": "test_key"
                    }
                ]
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(config_data, f)
                temp_config = f.name
            
            try:
                # 创建 bot 实例
                bot = LingIflowBot(config_path=temp_config, active_group="all")
                
                # 加载配置
                result = bot.load_config()
                assert result is True
                assert bot.config == config_data
                assert bot.config["log_level"] == "DEBUG"
                
                print("✅ 配置加载成功")
                self.test_results.append(("测试 2: 配置加载", True))
                return True
                
            finally:
                Path(temp_config).unlink()
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 2: 配置加载", False))
            return False
    
    async def test_3_load_config_not_found(self):
        """测试 3: 配置文件不存在"""
        print("\n" + "="*60)
        print("测试 3: 配置文件不存在")
        print("="*60)
        
        try:
            # 创建 bot 实例，使用不存在的配置文件
            bot = LingIflowBot(config_path="nonexistent.json", active_group="all")
            
            # 加载配置
            result = bot.load_config()
            assert result is False
            assert bot.config == {}
            
            print("✅ 配置文件不存在处理正确")
            self.test_results.append(("测试 3: 配置文件不存在", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 3: 配置文件不存在", False))
            return False
    
    async def test_4_setup_logging(self):
        """测试 4: 日志设置"""
        print("\n" + "="*60)
        print("测试 4: 日志设置")
        print("="*60)
        
        try:
            # 创建 bot 实例
            bot = LingIflowBot(config_path="config.json", active_group="all")
            
            # 设置配置
            bot.config = {"log_level": "DEBUG"}
            
            # 设置日志
            bot.setup_logging()
            
            print("✅ 日志设置成功")
            self.test_results.append(("测试 4: 日志设置", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 4: 日志设置", False))
            return False
    
    async def test_5_message_bus_creation(self):
        """测试 5: 消息总线创建"""
        print("\n" + "="*60)
        print("测试 5: 消息总线创建")
        print("="*60)
        
        try:
            # 创建 bot 实例
            bot = LingIflowBot(config_path="config.json", active_group="all")
            
            # 手动创建消息总线
            bot.bus = MessageBus()
            
            # 检查消息总线
            assert bot.bus is not None
            assert isinstance(bot.bus, MessageBus)
            
            print("✅ 消息总线创建成功")
            self.test_results.append(("测试 5: 消息总线创建", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 5: 消息总线创建", False))
            return False
    
    async def test_6_module_manager_creation(self):
        """测试 6: 模块管理器创建"""
        print("\n" + "="*60)
        print("测试 6: 模块管理器创建")
        print("="*60)
        
        try:
            # 创建 bot 实例
            bot = LingIflowBot(config_path="config.json", active_group="all")
            
            # 手动创建消息总线和模块管理器
            bot.bus = MessageBus()
            bot.manager = ModuleManager(bot.bus)
            
            # 检查模块管理器
            assert bot.manager is not None
            assert isinstance(bot.manager, ModuleManager)
            
            print("✅ 模块管理器创建成功")
            self.test_results.append(("测试 6: 模块管理器创建", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 6: 模块管理器创建", False))
            return False
    
    async def test_7_binding_setup(self):
        """测试 7: 绑定关系设置"""
        print("\n" + "="*60)
        print("测试 7: 绑定关系设置")
        print("="*60)
        
        try:
            # 创建 bot 实例
            bot = LingIflowBot(config_path="config.json", active_group="all")
            
            # 创建消息总线
            bot.bus = MessageBus()
            
            # 设置配置
            bot.config = {
                "bots": [
                    {
                        "name": "bot1",
                        "enabled": True,
                        "tmux_session": "iflow1"
                    }
                ]
            }
            
            # 模拟模块（只设置 ID，不实际创建）
            class MockModule:
                def __init__(self, module_id):
                    self.module_id = module_id
                def set_message_bus(self, bus):
                    pass
            
            iflow_module = MockModule("iflow_iflow1")
            wechat_module = MockModule("wechat_bot1")
            
            bot.iflow_modules = {"iflow1": iflow_module}
            bot.wechat_modules = {"bot1": wechat_module}
            
            # 注册模块到消息总线
            bot.bus.register_module(iflow_module)
            bot.bus.register_module(wechat_module)
            
            # 设置绑定
            bot._setup_bindings()
            
            # 检查绑定关系
            binding_to_iflow = bot.bus.get_binding("wechat_bot1")
            binding_to_wechat = bot.bus.get_binding("iflow_iflow1")
            
            # 应该有双向绑定
            assert binding_to_iflow == "iflow_iflow1"
            assert binding_to_wechat == "wechat_bot1"
            
            print("✅ 绑定关系设置成功")
            self.test_results.append(("测试 7: 绑定关系设置", True))
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append(("测试 7: 绑定关系设置", False))
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
        print("开始 LingIflowBot 简化单元测试...")
        
        # 测试 1: Bot 初始化
        await self.test_1_initialization()
        
        # 测试 2: 配置加载
        await self.test_2_load_config()
        
        # 测试 3: 配置文件不存在
        await self.test_3_load_config_not_found()
        
        # 测试 4: 日志设置
        await self.test_4_setup_logging()
        
        # 测试 5: 消息总线创建
        await self.test_5_message_bus_creation()
        
        # 测试 6: 模块管理器创建
        await self.test_6_module_manager_creation()
        
        # 测试 7: 绑定关系设置
        await self.test_7_binding_setup()
        
        # 打印总结
        await self.print_summary()


async def main():
    """主函数"""
    tester = LingIflowBotSimpleTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
