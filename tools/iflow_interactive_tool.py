#!/usr/bin/env python3
"""
IFlowModule 交互式体验工具

模拟消息来源方与 IFlowModule 交互：
- 直接调用模块的 send() 方法发送消息
- 通过 subscribe() 订阅模块输出
- 支持切换身份和过滤模式

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

from src.modules.iflow import IFlowModule, IFlowState, OutboundMessage, MessageType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("iflow_tool")


class IFlowInteractiveTool:
    """IFlowModule 交互式体验工具
    
    模拟消息来源方与 IFlowModule 交互。
    """
    
    def __init__(self, config_path: str = "config.json"):
        """初始化工具
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.module: Optional[IFlowModule] = None
        
        # 当前身份和模式
        self.current_source: str = "tool_user"
        self.current_scope: str = "reply_only"
        
        # 消息历史
        self.message_history: List[dict] = []
    
    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
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
        """启动工具"""
        print("=" * 60)
        print("IFlowModule 交互式体验工具")
        print("=" * 60)
        
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
        
        # 订阅模块输出
        self.module.subscribe(self._on_module_message)
        
        print(f"  模块 ID: {self.module.module_id}")
        print(f"  tmux 会话: {self.module.tmux_session or '(启动时分配)'}")
        
        # 启动模块
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
    
    async def _on_module_message(self, message: OutboundMessage):
        """订阅回调：接收模块输出，直接打印"""
        # 记录历史
        self.message_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": message.type.value,
            "content": message.content,
            "receiver": message.receiver,
            "scope": message.scope
        })
        
        # 根据类型显示
        if message.type == MessageType.REPLY:
            print(f"\n📤 [reply] {message.content}")
        
        elif message.type == MessageType.OTHER:
            # 思考消息，根据 scope 决定是否显示
            if self.current_scope == "all":
                print(f"\n💭 [thinking] {message.content[:100]}{'...' if len(message.content) > 100 else ''}")
        
        elif message.type == MessageType.COMPLETE:
            # 完成消息，显示统计
            reply_count = message.metadata.get("reply_count", 0)
            duration = message.metadata.get("duration", 0)
            print(f"\n✅ [complete] 共 {reply_count} 条消息，耗时 {duration} 秒")
    
    async def send_message(self, content: str):
        """发送消息到模块"""
        if not self.module:
            print("❌ 模块未启动")
            return
        
        print(f"\n📥 发送: {content}")
        print(f"   source={self.current_source}, scope={self.current_scope}")
        
        # 调用模块的 send 方法
        response = await self.module.send(
            content=content,
            source=self.current_source,
            scope=self.current_scope
        )
        
        if response.success:
            print(f"   ✅ 已发送 (id={response.message_id})")
        else:
            print(f"   ❌ 发送失败: {response.error} - {response.message}")
    
    async def wait_for_complete(self, timeout: float = 120.0) -> bool:
        """等待回复完成"""
        if not self.module:
            return False
        
        # 轮询状态
        elapsed = 0.0
        last_state = self.module.state
        
        while elapsed < timeout:
            await asyncio.sleep(0.5)
            elapsed += 0.5
            
            current_state = self.module.state
            
            # 状态变化提示
            if current_state != last_state:
                if current_state == IFlowState.GENERATING:
                    print(f"   ⏳ 开始生成...")
                elif current_state == IFlowState.IDLE:
                    print(f"   ✅ 生成完成")
                    return True
                last_state = current_state
            
            # 每 10 秒提示
            if int(elapsed) % 10 == 0 and elapsed > 0 and int(elapsed * 2) % 20 == 0:
                duration = self.module.generating_duration
                print(f"   等待中... {int(elapsed)}秒 (生成中 {duration}秒)")
        
        print(f"   ⚠️ 超时 ({timeout}秒)")
        return False
    
    async def interactive_loop(self):
        """交互式循环"""
        print("\n" + "=" * 60)
        print("交互模式")
        print("=" * 60)
        self._print_help()
        
        while True:
            try:
                prompt = f"\n[{self.current_source}] 你: "
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                # 命令处理
                if user_input.startswith('/'):
                    await self._handle_command(user_input)
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                # 发送消息
                await self.send_message(user_input)
                await self.wait_for_complete()
                
            except KeyboardInterrupt:
                print("\n退出...")
                break
            except EOFError:
                break
    
    async def _handle_command(self, command: str):
        """处理命令"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None
        
        if cmd == '/help':
            self._print_help()
        
        elif cmd == '/source':
            if arg:
                self.current_source = arg
                print(f"✅ 已切换身份: {arg}")
            else:
                print(f"当前身份: {self.current_source}")
        
        elif cmd == '/scope':
            if arg in ['all', 'reply_only']:
                self.current_scope = arg
                print(f"✅ 已切换模式: {arg}")
            else:
                print(f"当前模式: {self.current_scope}")
                print("可用: all, reply_only")
        
        elif cmd == '/status':
            await self._show_status()
        
        elif cmd == '/history':
            self._show_history()
        
        elif cmd == '/spam':
            await self._spam_test(int(arg) if arg else 3)
        
        else:
            print(f"未知命令: {cmd}")
    
    def _print_help(self):
        """打印帮助"""
        print("命令:")
        print("  直接输入文字     - 发送消息")
        print("  /source <name>   - 切换身份（模拟不同来源）")
        print("  /scope <mode>    - 切换模式: all(全部) / reply_only(仅回复)")
        print("  /status          - 查看状态")
        print("  /history         - 查看消息历史")
        print("  /spam [n]        - 连续发送 n 条消息测试拒绝机制")
        print("  /help            - 显示帮助")
        print("  quit/exit        - 退出")
        print("-" * 40)
        print(f"当前: source={self.current_source}, scope={self.current_scope}")
    
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
        print(f"   iflow_state: {status['iflow_state']}")
        print(f"   generating_duration: {status['generating_duration']}秒")
        
        monitor = status.get('monitor_stats', {})
        print(f"   监控统计:")
        print(f"     - 检查次数: {monitor.get('check_count', 0)}")
        print(f"     - 提取消息: {monitor.get('messages_extracted', 0)}")
        print(f"     - 状态变化: {monitor.get('state_changes', 0)}")
        
        store = status.get('message_store', {})
        print(f"   消息库:")
        print(f"     - 总计: {store.get('total', 0)}")
        print(f"     - 处理中: {store.get('processing', 0)}")
        
        logger_stats = status.get('logger_stats', {})
        print(f"   交互记录: {logger_stats.get('total_interactions', 0)} 条")
    
    def _show_history(self):
        """显示消息历史"""
        if not self.message_history:
            print("\n📝 暂无消息历史")
            return
        
        print(f"\n📝 消息历史 ({len(self.message_history)} 条):")
        print("-" * 40)
        
        for msg in self.message_history[-20:]:
            timestamp = msg['timestamp'][11:19]  # 只取时间部分
            msg_type = msg['type']
            content = msg['content'][:40] + '...' if len(msg['content']) > 40 else msg['content']
            print(f"  [{timestamp}] [{msg_type}] {content}")
        
        print("-" * 40)
    
    async def _spam_test(self, count: int):
        """连续发送测试拒绝机制"""
        print(f"\n🧪 连续发送 {count} 条消息测试拒绝机制...")
        print("   说明: 第一条消息成功后，后续消息应被拒绝（生成中状态）")
        
        results = []
        
        # 第一条消息
        print(f"\n  发送第 1 条消息...")
        response = await self.module.send(
            content=f"请帮我数到 {count * 10}",
            source=self.current_source,
            scope=self.current_scope
        )
        results.append(response)
        status = "✅" if response.success else f"❌({response.error})"
        print(f"    结果: {status}")
        
        if response.success:
            # 等待进入生成状态
            await asyncio.sleep(1)
            
            # 快速发送后续消息（应该被拒绝）
            for i in range(1, count):
                print(f"  发送第 {i+1} 条消息...")
                response = await self.module.send(
                    content=f"测试消息 {i+1}",
                    source=self.current_source,
                    scope=self.current_scope
                )
                results.append(response)
                
                current_state = self.module.state.value
                status = "✅" if response.success else f"❌({response.error})"
                print(f"    结果: {status} (状态: {current_state})")
                
                await asyncio.sleep(0.3)
            
            # 等待生成完成
            print("\n  等待生成完成...")
            await self.wait_for_complete(timeout=60)
        
        success_count = sum(1 for r in results if r.success)
        rejected_count = sum(1 for r in results if r.error == "iflow_generating")
        
        print(f"\n📊 测试结果:")
        print(f"   总计: {count} 条")
        print(f"   成功: {success_count} 条")
        print(f"   被拒: {rejected_count} 条")
        
        if rejected_count > 0:
            print("✅ 拒绝机制正常工作！")
        elif success_count == 1:
            print("⚠️ 其他消息发送失败（非拒绝原因）")


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
            print(__doc__)
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