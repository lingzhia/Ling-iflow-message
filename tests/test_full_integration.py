"""
完整集成测试

WeChatModule + IFlowModule + MessageBus 完整联动测试。
需要用户配合发送消息验证完整消息流转。
"""

import sys
import os
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import MessageBus, Message, MessageType, MessageContent
from src.modules import WeChatChannel, IFlowModule

# 配置日志
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "full_integration.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("full_integration")


class FullIntegrationTest:
    """完整集成测试"""

    def __init__(self):
        # 加载配置
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.bus = MessageBus()
        self.wechat_module = None
        self.iflow_module = None
        self.messages_received = []
        self.test_passed = False

    async def setup(self):
        """设置测试环境"""
        logger.info("=" * 60)
        logger.info("完整集成测试环境设置")
        logger.info("=" * 60)

        # 获取第一个启用的机器人配置
        bot_config = None
        for bot in self.config.get("bots", []):
            if bot.get("enabled", False):
                bot_config = bot
                break

        if not bot_config:
            raise ValueError("没有找到启用的机器人配置")

        # 获取对应的 iflow 配置
        tmux_session = bot_config.get("tmux_session", "iflow")
        session_config = None
        for session in self.config.get("tmux_sessions", []):
            if session.get("name") == tmux_session:
                session_config = session
                break

        if not session_config:
            session_config = {
                "name": tmux_session,
                "workspace": "~/.iflow",
                "model": "kimi-k2.5"
            }

        # 创建 WeChatModule
        logger.info(f"创建 WeChatModule: bot1")
        self.wechat_module = WeChatModule(
            module_id="wechat_test",
            config=bot_config
        )

        # 创建 IFlowModule
        logger.info(f"创建 IFlowModule: {tmux_session}")
        self.iflow_module = IFlowModule(
            module_id=f"iflow_{tmux_session}",
            tmux_session=tmux_session,
            model=session_config.get("model", "kimi-k2.5"),
            workspace=session_config.get("workspace", "~/.iflow")
        )

        # 注册模块
        self.bus.register_module(self.wechat_module)
        self.bus.register_module(self.iflow_module)

        # 设置双向绑定
        self.bus.bind("wechat_test", self.iflow_module.module_id)
        self.bus.bind(self.iflow_module.module_id, "wechat_test")
        logger.info(f"双向绑定: wechat_test <-> {self.iflow_module.module_id}")

        # 订阅 iflow 输出
        self.iflow_module.subscribe(self._on_iflow_message)

        logger.info("✅ 测试环境设置完成")
        logger.info("")

    async def _on_iflow_message(self, message):
        """处理 iflow 输出消息"""
        logger.info(f"📥 收到 iflow 消息:")
        logger.info(f"   类型: {message.type.value}")
        content_preview = message.content[:100] if len(message.content) > 100 else message.content
        logger.info(f"   内容: {content_preview}")
        self.messages_received.append(message)

        # 收到 complete 消息，测试通过
        if message.type.value == "complete":
            logger.info("")
            logger.info("=" * 60)
            logger.info(f"✅ 测试通过！")
            logger.info(f"   收到 {len(self.messages_received)} 条回复")
            logger.info(f"   完整消息流转: WeChat → IFlow → WeChat")
            logger.info("=" * 60)
            logger.info("")
            logger.info("现在可以按 Ctrl+C 停止测试")
            self.test_passed = True

    async def start_modules(self):
        """启动模块"""
        logger.info("=" * 60)
        logger.info("启动模块")
        logger.info("=" * 60)

        # 启动 IFlowModule
        logger.info("启动 IFlowModule...")
        await self.iflow_module.start()
        logger.info("✅ IFlowModule 启动成功")

        # 启动 WeChatModule
        logger.info("启动 WeChatModule...")
        await self.wechat_module.start()
        logger.info("✅ WeChatModule 启动成功")

        logger.info("")
        logger.info("=" * 60)
        logger.info("所有模块启动完成")
        logger.info("=" * 60)
        logger.info("")

    async def stop_modules(self):
        """停止模块"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("停止模块")
        logger.info("=" * 60)

        await self.wechat_module.stop()
        await self.iflow_module.stop()

        logger.info("✅ 所有模块已停止")

    async def run(self):
        """运行测试"""
        try:
            # 设置环境
            await self.setup()

            # 启动模块
            await self.start_modules()

            # 等待 iflow 启动完成
            logger.info("等待 iflow 完全启动...")
            await asyncio.sleep(15)

            logger.info("")
            logger.info("=" * 60)
            logger.info("测试说明")
            logger.info("=" * 60)
            logger.info("")
            logger.info("请发送消息到企业微信...")
            logger.info("")
            logger.info("消息流转流程：")
            logger.info("  1. 企业微信 → WeChatModule（回调接收）")
            logger.info("  2. WeChatModule → IFlowModule（消息路由）")
            logger.info("  3. IFlowModule 处理消息")
            logger.info("  4. IFlowModule → WeChatModule（消息路由）")
            logger.info("  5. WeChatModule → 企业微信（发送回复）")
            logger.info("")
            logger.info("按 Ctrl+C 停止测试")
            logger.info("")

            # 持续运行，直到收到消息或用户中断
            while not self.test_passed:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("")
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"测试失败: {e}", exc_info=True)
        finally:
            # 停止模块
            await self.stop_modules()

            if self.test_passed:
                logger.info("")
                logger.info("=" * 60)
                logger.info("✅ 完整集成测试通过")
                logger.info("=" * 60)
                return True
            else:
                logger.warning("")
                logger.warning("⚠️ 测试未完成（未收到消息）")
                return False


async def main():
    """主函数"""
    test = FullIntegrationTest()
    success = await test.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)