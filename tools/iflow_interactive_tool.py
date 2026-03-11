#!/usr/bin/env python3
"""
IFlowModule 交互式体验工具

直接测试 IFlowController 的核心功能：
- 发送消息到 iflow
- 接收 iflow 的回复

使用方法：
    python tools/iflow_interactive_tool.py [tmux_session] [--auto-start]
    
参数：
    tmux_session  - tmux 会话名称（默认: iflow）
    --auto-start  - 自动启动 tmux 和 iflow（如果不存在）
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("iflow_tool")


class IFlowInteractiveTool:
    """IFlow 交互式体验工具（直接测试组件）"""
    
    def __init__(self, tmux_session: str = "iflow", auto_start: bool = False, model: str = "kimi-k2.5"):
        self.tmux_session = tmux_session
        self.auto_start = auto_start
        self.model = model
        self.controller: Optional[IFlowController] = None
        self.monitor: Optional[IFlowMonitor] = None
    
    async def start(self):
        """启动工具"""
        print("=" * 60)
        print("IFlow 交互式体验工具")
        print("=" * 60)
        print(f"tmux 会话: {self.tmux_session}")
        
        # 创建 Controller
        self.controller = IFlowController(self.tmux_session)
        
        # 检查 tmux 会话
        tmux_exists = await self.controller.check_tmux_session()
        iflow_running = await self.controller.check_iflow_running() if tmux_exists else False
        
        if not tmux_exists:
            if self.auto_start:
                print(f"\n⏳ tmux 会话不存在，正在启动...")
                success = await self.controller.start_iflow(self.model)
                if success:
                    print(f"✅ 已启动 tmux 会话和 iflow")
                    iflow_running = True
                else:
                    print(f"❌ 启动失败")
                    sys.exit(1)
            else:
                print(f"\n❌ tmux 会话 '{self.tmux_session}' 不存在")
                print(f"   使用 --auto-start 自动启动")
                sys.exit(1)
        elif not iflow_running:
            if self.auto_start:
                print(f"\n⏳ iflow 未运行，正在启动...")
                success = await self.controller.start_iflow(self.model)
                if success:
                    print(f"✅ 已启动 iflow")
                else:
                    print(f"❌ 启动失败")
                    sys.exit(1)
            else:
                print(f"\n⚠️  iflow 未运行，使用 --auto-start 启动")
        else:
            print(f"✅ iflow 运行中")
        
        # 创建 Monitor（用于提取消息）
        self.monitor = IFlowMonitor(self.controller)
        
        print("=" * 60)
    
    async def stop(self):
        """停止工具"""
        print("\n已停止")
    
    async def send_message(self, content: str) -> bool:
        """发送消息到 iflow"""
        print(f"\n📥 发送: {content}")
        success = await self.controller.send_message(content)
        if success:
            print("   ✅ 已发送")
        else:
            print("   ❌ 发送失败")
        return success
    
    async def wait_for_reply(self, timeout: float = 60.0) -> Optional[str]:
        """等待 iflow 回复"""
        print(f"⏳ 等待回复 (超时 {timeout}秒)...")
        
        # 记录当前已处理的消息哈希
        initial_hashes = set(self.monitor._processed_hashes)
        
        elapsed = 0.0
        interval = 0.5
        
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval
            
            # 捕获输出
            output = await self.controller.capture_output(lines=100)
            if not output:
                continue
            
            # 提取消息
            messages = self.monitor._extract_messages(output)
            new_messages = self.monitor._filter_new_messages(messages)
            
            if new_messages:
                # 返回最新消息
                msg = new_messages[-1]
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                print(f"\n📤 回复: {content[:200]}{'...' if len(content) > 200 else ''}")
                print(f"   ✅ 收到回复 (耗时 {elapsed:.1f}秒)")
                return content
            
            # 显示等待进度
            if int(elapsed) % 10 == 0 and elapsed > 0:
                print(f"   等待中... {int(elapsed)}秒")
        
        print(f"   ⚠️ 超时，未收到回复")
        return None
    
    async def interactive_loop(self):
        """交互式循环"""
        print("\n" + "=" * 60)
        print("交互模式 - 输入消息发送，'quit' 退出")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n👤 你: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                await self.send_message(user_input)
                await self.wait_for_reply()
                
            except KeyboardInterrupt:
                print("\n退出...")
                break
            except EOFError:
                break


async def main():
    """主函数"""
    tmux_session = "iflow"
    auto_start = False
    model = "kimi-k2.5"
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--auto-start":
            auto_start = True
        elif arg == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 1
        elif not arg.startswith("--"):
            tmux_session = arg
        i += 1
    
    tool = IFlowInteractiveTool(tmux_session, auto_start, model)
    
    try:
        await tool.start()
        await tool.interactive_loop()
    finally:
        await tool.stop()


if __name__ == "__main__":
    asyncio.run(main())