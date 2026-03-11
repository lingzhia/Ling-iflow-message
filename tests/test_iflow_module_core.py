"""
IFlowModule 核心功能自动化测试

测试：
1. 消息发送到 iflow（通过 tmux send-keys）
2. 从 iflow 获取回复（通过 tmux capture-pane）
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor
from src.core.message import Message, MessageType


class IFlowModuleCoreTest:
    """IFlowModule 核心功能测试"""
    
    def __init__(self, tmux_session: str = "iflow"):
        self.tmux_session = tmux_session
        self.controller = None
        self.monitor = None
        self.results = []
    
    def record(self, name: str, passed: bool, detail: str = ""):
        """记录测试结果"""
        status = "✅ 通过" if passed else "❌ 失败"
        self.results.append({"name": name, "passed": passed, "detail": detail})
        print(f"  {status} {name}")
        if detail:
            print(f"         {detail}")
    
    async def test_tmux_session_exists(self):
        """测试 tmux 会话是否存在"""
        print("\n[测试 1] tmux 会话是否存在")
        
        self.controller = IFlowController(self.tmux_session)
        exists = await self.controller.check_tmux_session()
        
        if exists:
            self.record("tmux 会话存在", True, f"会话名: {self.tmux_session}")
        else:
            self.record("tmux 会话存在", False, f"会话 {self.tmux_session} 不存在，请先启动 iflow")
        
        return exists
    
    async def test_iflow_running(self):
        """测试 iflow 是否在运行"""
        print("\n[测试 2] iflow 是否在运行")
        
        running = await self.controller.check_iflow_running()
        
        if running:
            self.record("iflow 进程运行中", True)
        else:
            self.record("iflow 进程运行中", False, "iflow 未运行")
        
        return running
    
    async def test_send_message_to_iflow(self):
        """测试发送消息到 iflow"""
        print("\n[测试 3] 发送消息到 iflow")
        
        test_message = "你好，这是一条测试消息"
        success = await self.controller.send_message(test_message)
        
        self.record("send_message 执行成功", success, f"消息: {test_message}")
        
        return success
    
    async def test_capture_output_from_iflow(self):
        """测试从 iflow 捕获输出"""
        print("\n[测试 4] 从 iflow 捕获输出")
        
        output = await self.controller.capture_output(lines=50)
        
        if output:
            lines_count = len(output.split('\n'))
            self.record("capture_output 返回内容", True, f"获取 {lines_count} 行")
            # 显示前几行
            preview = output[:200].replace('\n', ' ')
            print(f"         预览: {preview}...")
        else:
            self.record("capture_output 返回内容", False, "无输出")
        
        return bool(output)
    
    async def test_monitor_extract_messages(self):
        """测试监控器提取消息"""
        print("\n[测试 5] 监控器提取消息")
        
        # 创建监控器
        self.monitor = IFlowMonitor(self.controller)
        
        # 捕获输出并提取消息
        output = await self.controller.capture_output(lines=100)
        
        if output:
            messages = self.monitor._extract_messages(output)
            self.record("_extract_messages 提取消息", True, f"提取到 {len(messages)} 条消息")
            
            # 显示提取的消息
            for i, msg in enumerate(messages[:3]):
                marker = msg.get('marker_id', 'unknown')[:20]
                content_preview = msg.get('content', '')[:50].replace('\n', ' ')
                print(f"         消息 {i+1}: [{marker}] {content_preview}...")
        else:
            self.record("_extract_messages 提取消息", False, "无输出可提取")
        
        return bool(output)
    
    async def test_message_content_cleaning(self):
        """测试消息内容清理"""
        print("\n[测试 6] 消息内容清理")
        
        # 测试分隔符清理
        test_cases = [
            ("有效内容\n---\n分隔符后", "有效内容", "--- 分隔符"),
            ("有效内容\n══════\n分隔符后", "有效内容", "══ 分隔符"),
            ("纯有效内容无分隔符", "纯有效内容无分隔符", "无分隔符"),
        ]
        
        for original, expected, desc in test_cases:
            cleaned = self.monitor._clean_message_content(original)
            passed = expected in cleaned
            self.record(f"清理 {desc}", passed, f"结果: {cleaned[:50]}")
    
    async def run_all(self):
        """运行所有测试"""
        print("=" * 60)
        print("IFlowModule 核心功能自动化测试")
        print("=" * 60)
        
        # 测试 1: tmux 会话
        session_exists = await self.test_tmux_session_exists()
        if not session_exists:
            print("\n⚠️  跳过后续测试：tmux 会话不存在")
            self.print_summary()
            return
        
        # 测试 2: iflow 运行
        iflow_running = await self.test_iflow_running()
        if not iflow_running:
            print("\n⚠️  跳过后续测试：iflow 未运行")
            self.print_summary()
            return
        
        # 测试 3: 发送消息
        await self.test_send_message_to_iflow()
        
        # 等待 iflow 处理
        print("\n等待 iflow 响应 (3秒)...")
        await asyncio.sleep(3)
        
        # 测试 4: 捕获输出
        await self.test_capture_output_from_iflow()
        
        # 测试 5: 提取消息
        await self.test_monitor_extract_messages()
        
        # 测试 6: 消息清理
        await self.test_message_content_cleaning()
        
        # 打印摘要
        self.print_summary()
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("测试摘要")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r["passed"])
        failed = len(self.results) - passed
        
        print(f"总计: {len(self.results)} 个测试")
        print(f"通过: {passed} 个")
        print(f"失败: {failed} 个")
        print("=" * 60)


async def main():
    """主函数"""
    # 使用默认 iflow 会话
    tmux_session = "iflow"
    
    # 支持命令行参数指定会话
    if len(sys.argv) > 1:
        tmux_session = sys.argv[1]
    
    print(f"测试 tmux 会话: {tmux_session}")
    
    tester = IFlowModuleCoreTest(tmux_session)
    await tester.run_all()


if __name__ == "__main__":
    asyncio.run(main())
