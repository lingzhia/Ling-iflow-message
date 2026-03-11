#!/usr/bin/env python3
"""日志功能测试脚本。

测试各个模块的日志记录是否正常。
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger
from config.loader import load_config as load_project_config
from interactive.iflow_controller import IFlowController
from interactive.session_manager import SessionManager


def test_logger_config():
    """测试日志配置。"""
    print("=" * 80)
    print("测试 1: 日志配置")
    print("=" * 80)
    
    # 配置日志
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        log_dir / "test_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="00:00",
        retention="7 days",
        encoding="utf-8"
    )
    
    # 测试不同级别的日志
    logger.debug("这是 DEBUG 级别日志")
    logger.info("这是 INFO 级别日志")
    logger.warning("这是 WARNING 级别日志")
    logger.error("这是 ERROR 级别日志")
    
    print("✅ 日志配置测试完成")
    print()


def test_config_loading():
    """测试配置加载日志。"""
    print("=" * 80)
    print("测试 2: 配置加载日志")
    print("=" * 80)
    
    try:
        config_path = PROJECT_ROOT / "config.json"
        config = load_project_config(config_path)
        logger.info(f"配置加载成功: tmux_session={config.tmux_session}, workspace={config.workspace}")
        print("✅ 配置加载测试完成")
    except Exception as e:
        logger.error(f"配置加载失败: {e}", exc_info=True)
        print("❌ 配置加载测试失败")
    print()


def test_iflow_controller():
    """测试 iflow 控制器日志。"""
    print("=" * 80)
    print("测试 3: iflow 控制器日志")
    print("=" * 80)
    
    try:
        config = load_project_config(PROJECT_ROOT / "config.json")
        controller = IFlowController(config.tmux_session)
        
        # 测试检查 tmux 会话
        logger.info(f"检查 tmux 会话: {config.tmux_session}")
        session_info = controller.get_session_info()
        logger.info(f"会话信息: {session_info}")
        
        print("✅ iflow 控制器测试完成")
    except Exception as e:
        logger.error(f"iflow 控制器测试失败: {e}", exc_info=True)
        print("❌ iflow 控制器测试失败")
    print()


def test_session_manager():
    """测试会话管理器日志。"""
    print("=" * 80)
    print("测试 4: 会话管理器日志")
    print("=" * 80)
    
    try:
        config = load_project_config(PROJECT_ROOT / "config.json")
        manager = SessionManager(config.workspace)
        
        # 测试获取最新会话
        logger.info("获取最新会话")
        latest = manager.get_latest_session()
        if latest:
            logger.info(f"最新会话: {latest['id']}")
        else:
            logger.warning("未找到会话")
        
        # 测试获取所有会话
        logger.info("获取所有会话")
        sessions = manager.get_all_sessions()
        logger.info(f"会话数量: {len(sessions)}")
        
        print("✅ 会话管理器测试完成")
    except Exception as e:
        logger.error(f"会话管理器测试失败: {e}", exc_info=True)
        print("❌ 会话管理器测试失败")
    print()


async def test_bot_integration():
    """测试机器人集成日志。"""
    print("=" * 80)
    print("测试 5: 机器人集成日志")
    print("=" * 80)
    
    try:
        from interactive.bot_integration import BotIntegration
        
        # 创建模拟的微信渠道
        class MockWeChatChannel:
            async def send(self, content, chat_id, **kwargs):
                logger.info(f"[MockWeChat] 发送消息: chat_id={chat_id}, content={content[:50]}")
                return True
        
        config = load_project_config(PROJECT_ROOT / "config.json")
        mock_channel = MockWeChatChannel()
        
        # 创建机器人集成
        logger.info("初始化机器人集成")
        bot = BotIntegration(
            wechat_channel=mock_channel,
            tmux_session=config.tmux_session,
            workspace=config.workspace
        )
        
        # 测试命令解析
        logger.info("测试命令解析")
        test_commands = [
            "帮我写一个脚本",
            "/run 分析代码",
            "/new",
            "/sessions",
            "/status",
            "/help"
        ]
        
        for cmd in test_commands:
            parsed = bot._parse_command(cmd)
            logger.info(f"解析命令: '{cmd}' -> type={parsed['type']}, valid={parsed['valid']}")
        
        print("✅ 机器人集成测试完成")
    except Exception as e:
        logger.error(f"机器人集成测试失败: {e}", exc_info=True)
        print("❌ 机器人集成测试失败")
    print()


def main():
    """主函数。"""
    print()
    print("=" * 80)
    print("Ling-iflow 日志功能测试")
    print("=" * 80)
    print()
    
    # 测试日志配置
    test_logger_config()
    
    # 测试配置加载
    test_config_loading()
    
    # 测试 iflow 控制器
    test_iflow_controller()
    
    # 测试会话管理器
    test_session_manager()
    
    # 测试机器人集成
    asyncio.run(test_bot_integration())
    
    print("=" * 80)
    print("所有测试完成！")
    print("=" * 80)
    print()
    print("日志文件位置:")
    print(f"  {PROJECT_ROOT / 'logs'}")
    print()
    print("查看日志:")
    print(f"  python {PROJECT_ROOT / 'logs_view.py'} list")
    print(f"  python {PROJECT_ROOT / 'logs_view.py'} view test_*.log")
    print()


if __name__ == "__main__":
    main()