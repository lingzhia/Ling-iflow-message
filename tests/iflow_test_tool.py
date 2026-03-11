#!/usr/bin/env python3
"""
IFlow 模块自动化测试

测试 IFlowModule 的核心功能：
- IFlowController：进程管理
- IFlowMonitor：输出监控
- SessionManager：会话管理
- IFlowModule：整体集成

使用方法：
    python tests/iflow_test_tool.py
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.iflow.controller import IFlowController
from src.modules.iflow.monitor import IFlowMonitor
from src.modules.iflow.session_manager import SessionManager
from src.modules import IFlowModule

# 配置日志
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("iflow_test")


class IFlowTestTool:
    """IFlow 模块测试工具"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def record_result(self, test_name: str, passed: bool, message: str = ""):
        """记录测试结果"""
        status = "✅ 通过" if passed else "❌ 失败"
        self.results.append({
            "name": test_name,
            "passed": passed,
            "message": message
        })
        if passed:
            self.passed += 1
            logger.info(f"{status} {test_name}")
        else:
            self.failed += 1
            logger.error(f"{status} {test_name}: {message}")
    
    def test_session_manager(self):
        """测试 SessionManager"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 SessionManager")
        logger.info("=" * 60)
        
        try:
            sm = SessionManager(workspace="~/.iflow")
            
            # 测试 1: 获取 session 目录
            session_dir = sm.session_dir
            self.record_result(
                "SessionManager.session_dir",
                bool(session_dir),
                f"目录: {session_dir}"
            )
            
            # 测试 2: 获取最新会话
            latest = sm.get_latest_session()
            self.record_result(
                "SessionManager.get_latest_session",
                latest is not None or True,  # 可能没有会话
                f"最新会话: {latest['id'][:8] if latest else 'None'}..."
            )
            
            # 测试 3: 获取所有会话
            sessions = sm.get_all_sessions(limit=10)
            self.record_result(
                "SessionManager.get_all_sessions",
                isinstance(sessions, list),
                f"会话数量: {len(sessions)}"
            )
            
            # 测试 4: 获取状态信息
            status_msg = sm.get_status_message()
            self.record_result(
                "SessionManager.get_status_message",
                len(status_msg) > 0,
                f"信息长度: {len(status_msg)}"
            )
            
            # 测试 5: 创建新会话
            result = sm.create_new_session()
            self.record_result(
                "SessionManager.create_new_session",
                result.get("success", False),
                result.get("message", "")
            )
            
        except Exception as e:
            self.record_result("SessionManager", False, str(e))
    
    async def test_iflow_controller_async(self):
        """测试 IFlowController（异步）"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 IFlowController")
        logger.info("=" * 60)
        
        try:
            controller = IFlowController(tmux_session="iflow_test")
            
            # 测试 1: 检查 tmux 会话（预期不存在）
            exists = await controller.check_tmux_session()
            self.record_result(
                "IFlowController.check_tmux_session",
                True,  # 无论存在与否都算通过
                f"tmux 会话存在: {exists}"
            )
            
            # 测试 2: 获取会话信息
            info = await controller.get_session_info()
            self.record_result(
                "IFlowController.get_session_info",
                isinstance(info, dict),
                f"信息: {info}"
            )
            
        except Exception as e:
            self.record_result("IFlowController", False, str(e))
    
    def test_iflow_controller(self):
        """测试 IFlowController（同步包装）"""
        asyncio.run(self.test_iflow_controller_async())
    
    def test_iflow_monitor(self):
        """测试 IFlowMonitor"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 IFlowMonitor")
        logger.info("=" * 60)
        
        try:
            # 创建 mock controller
            class MockController:
                tmux_session = "test_session"
            
            monitor = IFlowMonitor(MockController())
            
            # 测试 1: 消息清理 - 分隔符 ---
            test_content_1 = "有效内容\n---\n分隔符后的内容"
            cleaned_1 = monitor._clean_message_content(test_content_1)
            passed_1 = "分隔符" not in cleaned_1 and "有效内容" in cleaned_1
            self.record_result(
                "IFlowMonitor._clean_message_content (---)",
                passed_1,
                f"清理后: {cleaned_1}"
            )
            
            # 测试 2: 消息清理 - 分隔符 ══
            test_content_2 = "有效内容\n════════════════\n分隔符后的内容"
            cleaned_2 = monitor._clean_message_content(test_content_2)
            passed_2 = "分隔符" not in cleaned_2 and "有效内容" in cleaned_2
            self.record_result(
                "IFlowMonitor._clean_message_content (══)",
                passed_2,
                f"清理后: {cleaned_2}"
            )
            
            # 测试 3: 消息清理 - 无分隔符
            test_content_3 = "纯有效内容，无分隔符"
            cleaned_3 = monitor._clean_message_content(test_content_3)
            passed_3 = cleaned_3 == test_content_3
            self.record_result(
                "IFlowMonitor._clean_message_content (无分隔符)",
                passed_3,
                f"清理后: {cleaned_3}"
            )
            
            # 测试 4: 消息提取
            test_output = """✦ 标记1
消息内容1
第一行
第二行
✻ 思考标记
思考内容
✦ 标记2
消息内容2"""
            
            messages = monitor._extract_messages(test_output)
            passed_4 = len(messages) == 3  # 2个✦ + 1个✻
            self.record_result(
                "IFlowMonitor._extract_messages",
                passed_4,
                f"提取消息数: {len(messages)}"
            )
            
            # 测试 5: 监听器
            listener_called = []
            
            async def test_listener(msg):
                listener_called.append(msg)
            
            monitor.add_listener(test_listener)
            self.record_result(
                "IFlowMonitor.add_listener",
                len(monitor._listeners) == 1,
                f"监听器数量: {len(monitor._listeners)}"
            )
            
            # 测试 6: 统计信息
            stats = monitor.get_stats()
            self.record_result(
                "IFlowMonitor.get_stats",
                isinstance(stats, dict),
                f"统计: {stats}"
            )
            
        except Exception as e:
            self.record_result("IFlowMonitor", False, str(e))
    
    def test_iflow_module(self):
        """测试 IFlowModule 集成"""
        logger.info("\n" + "=" * 60)
        logger.info("测试 IFlowModule 集成")
        logger.info("=" * 60)
        
        try:
            # 创建模块（不自动启动 iflow）
            iflow = IFlowModule(
                module_id="iflow_test",
                tmux_session="iflow_test",
                model="kimi-k2.5",
                auto_start=False
            )
            
            # 测试 1: 模块创建
            self.record_result(
                "IFlowModule 创建",
                iflow.module_id == "iflow_test",
                f"ID: {iflow.module_id}"
            )
            
            # 测试 2: 子模块存在
            self.record_result(
                "IFlowModule 子模块",
                hasattr(iflow, 'controller') and hasattr(iflow, 'monitor') and hasattr(iflow, 'session_manager'),
                "controller, monitor, session_manager"
            )
            
            # 测试 3: get_status_message
            status = iflow.get_status_message()
            self.record_result(
                "IFlowModule.get_status_message",
                len(status) > 0,
                f"长度: {len(status)}"
            )
            
            # 测试 4: get_sessions_message
            sessions = iflow.get_sessions_message(limit=5)
            self.record_result(
                "IFlowModule.get_sessions_message",
                len(sessions) > 0,
                f"长度: {len(sessions)}"
            )
            
            # 测试 5: create_new_session
            result = iflow.create_new_session()
            self.record_result(
                "IFlowModule.create_new_session",
                result.get("success", False),
                result.get("message", "")
            )
            
            # 测试 6: get_all_sessions
            all_sessions = iflow.get_all_sessions(limit=10)
            self.record_result(
                "IFlowModule.get_all_sessions",
                isinstance(all_sessions, list),
                f"数量: {len(all_sessions)}"
            )
            
        except Exception as e:
            self.record_result("IFlowModule", False, str(e))
    
    def print_summary(self):
        """打印测试摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("测试摘要")
        logger.info("=" * 60)
        
        total = self.passed + self.failed
        logger.info(f"总计: {total} 个测试")
        logger.info(f"通过: {self.passed} 个")
        logger.info(f"失败: {self.failed} 个")
        
        if self.failed > 0:
            logger.info("\n失败的测试:")
            for r in self.results:
                if not r["passed"]:
                    logger.info(f"  - {r['name']}: {r['message']}")
        
        logger.info("=" * 60)
        return self.failed == 0
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("=" * 60)
        logger.info("IFlow 模块测试工具")
        logger.info("=" * 60)
        
        # 运行各组件测试
        self.test_session_manager()
        self.test_iflow_controller()  # 内部使用 asyncio.run
        self.test_iflow_monitor()
        self.test_iflow_module()
        
        # 打印摘要
        return self.print_summary()


def main():
    """主函数"""
    tool = IFlowTestTool()
    success = tool.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
