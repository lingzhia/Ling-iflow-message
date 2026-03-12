#!/usr/bin/env python3
"""
IFlowModule 交互式体验工具

通过实例化 IFlowModule 来体验模块功能：
- 模块启动时自动创建 tmux 会话并启动 iflow
- 模块停止时自动销毁 tmux 会话
- 记录所有交互信息

使用方法：
    python tools/iflow_interactive_tool.py [选项]
    
选项：
    --session NAME   指定 tmux 会话名称（不指定则自动分配）
    --model MODEL    指定 iflow 模型
    --config PATH    指定配置文件路径
"""

import sys
import os
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.module import IFlowModule
from src.core.message import Message, MessageType, MessageContent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("iflow_tool")


class IFlowInteractiveTool:
    """IFlowModule 交互式体验工具
    
    通过模块实例化来体验功能，不直接操作 tmux。
    """
    
    def __init__(self, config_path: str = "config.json"):
        """初始化工具
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.module: Optional[IFlowModule] = None
        self.captured_messages: List[Message] = []
    
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            配置字典
        """
        config_file = Path(config_path)
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"已加载配置文件: {config_file}")
                return config
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}，使用默认配置")
        else:
            logger.info(f"配置文件不存在: {config_file}，使用默认配置")
        
        # 默认配置
        return {
            "iflow": {
                "model": "kimi-k2.5",
                "workspace": "~/.iflow",
                "auto_restart": True,
                "log_interactions": True,
                "log_dir": "logs/interactions"
            }
        }
    
    async def start(
        self,
        tmux_session: Optional[str] = None,
        model: Optional[str] = None
    ):
        """启动工具
        
        Args:
            tmux_session: 指定的 tmux 会话名称
            model: 指定的模型
        """
        print("=" * 60)
        print("IFlowModule 交互式体验工具")
        print("=" * 60)
        
        # 获取配置
        iflow_config = self.config.get("iflow", {})
        
        # 创建模块实例
        print("\n正在创建 IFlowModule 实例...")
        self.module = IFlowModule(
            tmux_session=tmux_session,
            model=model or iflow_config.get("model", "kimi-k2.5"),
            workspace=iflow_config.get("workspace", "~/.iflow"),
            auto_restart=iflow_config.get("auto_restart", True),
            log_interactions=iflow_config.get("log_interactions", True),
            log_dir=iflow_config.get("log_dir", "logs/interactions")
        )
        
        # 添加消息监听器
        self.module.monitor.add_listener(self._on_module_message)
        
        print(f"  模块 ID: {self.module.module_id}")
        print(f"  tmux 会话: {self.module.tmux_session or '(启动时分配)'}")
        
        # 启动模块（自动创建 tmux 会话并启动 iflow）
        print("\n正在启动模块...")
        try:
            await self.module.start()
            print(f"\n✅ 模块已启动")
            print(f"   module_id: {self.module.module_id}")
            print(f"   tmux_session: {self.module.tmux_session}")
        except Exception as e:
            print(f"\n❌ 启动失败: {e}")
            raise
        
        print("=" * 60)
    
    async def stop(self):
        """停止工具"""
        if self.module:
            print("\n正在停止模块...")
            await self.module.stop()
            print("✅ 模块已停止（tmux 会话已销毁）")
    
    async def _on_module_message(self, message: Message):
        """监听模块发出的消息"""
        self.captured_messages.append(message)
        content = message.content.text if message.content else ""
        
        # 显示回复
        print(f"\n📤 iflow 回复:")
        print("-" * 40)
        # 限制显示长度
        if len(content) > 500:
            print(content[:500])
            print("... (内容已截断)")
        else:
            print(content)
        print("-" * 40)
    
    async def send_message(self, content: str):
        """发送消息到模块
        
        Args:
            content: 消息内容
        """
        if not self.module:
            print("❌ 模块未启动")
            return
        
        print(f"\n📥 发送: {content}")
        
        # 创建消息
        message = Message(
            id=Message.generate_id(),
            type=MessageType.TEXT,
            content=MessageContent(type=MessageType.TEXT, text=content),
            from_module="tool",
            to_module=self.module.module_id
        )
        
        # 通过模块接收消息
        await self.module.receive(message)
    
    async def wait_for_reply(self, timeout: float = 120.0) -> bool:
        """等待回复
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否收到回复
        """
        print("⏳ 等待回复...")
        
        initial_count = len(self.captured_messages)
        elapsed = 0.0
        
        while elapsed < timeout:
            await asyncio.sleep(0.5)
            elapsed += 0.5
            
            # 检查是否有新消息
            if len(self.captured_messages) > initial_count:
                print(f"   ✅ 收到回复 (耗时 {elapsed:.1f}秒)")
                return True
            
            # 每 10 秒提示一次
            if int(elapsed) % 10 == 0 and elapsed > 0 and int(elapsed * 2) % 20 == 0:
                print(f"   等待中... {int(elapsed)}秒")
        
        print(f"   ⚠️ 超时 ({timeout}秒)")
        return False
    
    async def interactive_loop(self):
        """交互式循环"""
        print("\n" + "=" * 60)
        print("交互模式")
        print("  - 输入消息发送给 iflow")
        print("  - 输入 'quit' 或 'exit' 退出")
        print("  - 输入 '/status' 查看状态")
        print("  - 输入 '/log' 查看交互记录")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n👤 你: ").strip()
                
                if not user_input:
                    continue
                
                # 退出命令
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                # 状态命令
                if user_input == '/status':
                    await self._show_status()
                    continue
                
                # 日志命令
                if user_input == '/log':
                    self._show_interaction_log()
                    continue
                
                # 发送消息
                await self.send_message(user_input)
                await self.wait_for_reply()
                
            except KeyboardInterrupt:
                print("\n退出...")
                break
            except EOFError:
                break
    
    async def _show_status(self):
        """显示状态"""
        if not self.module:
            print("模块未启动")
            return
        
        status = await self.module.get_status()
        print(f"\n📊 模块状态:")
        print(f"   module_id: {status['module_id']}")
        print(f"   running: {status['running']}")
        print(f"   tmux_session: {status['tmux_session']}")
        print(f"   model: {status['model']}")
        print(f"   auto_restart: {status['auto_restart']}")
        
        logger_stats = status.get('logger_stats', {})
        print(f"   交互记录: {logger_stats.get('total_interactions', 0)} 条")
    
    def _show_interaction_log(self):
        """显示交互记录"""
        if not self.module:
            print("模块未启动")
            return
        
        logs = self.module.get_interaction_log()
        if not logs:
            print("\n📝 暂无交互记录")
            return
        
        print(f"\n📝 交互记录 ({len(logs)} 条):")
        print("-" * 40)
        for log in logs[-10:]:  # 只显示最近 10 条
            direction = "📤" if log['direction'] == 'sent' else "📥"
            content = log['content'][:50] + "..." if len(log['content']) > 50 else log['content']
            print(f"  {direction} {content}")
        print("-" * 40)


def print_usage():
    """打印使用说明"""
    print(__doc__)


async def main():
    """主函数"""
    tmux_session = None
    model = None
    config_path = "config.json"
    
    # 解析命令行参数
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ['-h', '--help']:
            print_usage()
            sys.exit(0)
        elif arg == '--session' and i + 1 < len(args):
            tmux_session = args[i + 1]
            i += 1
        elif arg == '--model' and i + 1 < len(args):
            model = args[i + 1]
            i += 1
        elif arg == '--config' and i + 1 < len(args):
            config_path = args[i + 1]
            i += 1
        i += 1
    
    # 创建并运行工具
    tool = IFlowInteractiveTool(config_path)
    
    try:
        await tool.start(tmux_session, model)
        await tool.interactive_loop()
    except Exception as e:
        logger.error(f"运行错误: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await tool.stop()


if __name__ == "__main__":
    asyncio.run(main())
