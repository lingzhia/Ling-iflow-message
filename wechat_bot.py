#!/usr/bin/env python3
"""iFlow 企业微信机器人 - 统一入口脚本。

同时启动企业微信渠道和 iflow CLI 控制，实现消息双向流转。
"""

import asyncio
import signal
import sys
from pathlib import Path
from loguru import logger

from config.loader import ConfigLoader
from config.schema import WechatWorkConfig
from channels.wechat_work import WechatWorkChannel
from interactive.bot_integration import BotIntegration


# 颜色定义
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[36m"


class WechatBot:
    """企业微信机器人主类。"""
    
    def __init__(self, config_path: str = "config.json"):
        """初始化机器人。
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        
        # 初始化组件
        self.wechat_channel = None
        self.bot_integration = None
        self.running = False
        
        logger.info("[WechatBot] 初始化完成")
    
    async def start(self) -> None:
        """启动机器人。"""
        # 检查企业微信配置
        if not self.config.wechat_work or not self.config.wechat_work.enabled:
            logger.error("[WechatBot] 企业微信未启用，请在配置中设置 wechat_work.enabled=true")
            print(f"{COLOR_YELLOW}[错误] 企业微信未启用，请在配置中设置 wechat_work.enabled=true{COLOR_RESET}")
            return
        
        wechat_config: WechatWorkConfig = self.config.wechat_work
        
        # 验证必需配置
        if not wechat_config.corp_id or not wechat_config.agent_id or not wechat_config.secret:
            logger.error("[WechatBot] 企业微信配置不完整")
            print(f"{COLOR_YELLOW}[错误] 企业微信配置不完整，请检查以下配置：{COLOR_RESET}")
            print(f"  - corp_id: {wechat_config.corp_id}")
            print(f"  - agent_id: {wechat_config.agent_id}")
            print(f"  - secret: {wechat_config.secret}")
            return
        
        self.running = True
        
        # 创建企业微信渠道
        logger.info("[WechatBot] 正在初始化企业微信渠道...")
        print(f"{COLOR_BLUE}[启动] 正在初始化企业微信渠道...{COLOR_RESET}")
        
        self.wechat_channel = WechatWorkChannel(wechat_config)
        
        # 创建机器人集成
        logger.info("[WechatBot] 正在初始化机器人集成...")
        print(f"{COLOR_BLUE}[启动] 正在初始化机器人集成...{COLOR_RESET}")
        
        self.bot_integration = BotIntegration(
            wechat_channel=self.wechat_channel,
            tmux_session=self.config.tmux_session,
            workspace=self.config.workspace
        )
        
        # 设置消息处理器
        self.wechat_channel.set_message_handler(self.bot_integration.handle_message)
        
        # 启动企业微信渠道
        logger.info("[WechatBot] 正在启动企业微信渠道...")
        print(f"{COLOR_BLUE}[启动] 正在启动企业微信渠道...{COLOR_RESET}")
        
        await self.wechat_channel.start()
        
        # 显示启动信息
        self._print_startup_info(wechat_config)
        
        logger.info("[WechatBot] 启动完成，等待企业微信消息...")
        print(f"{COLOR_GREEN}[成功] iFlow 企业微信机器人已启动！{COLOR_RESET}")
        print(f"{COLOR_BLUE}[状态] 等待企业微信消息...{COLOR_RESET}")
        
        # 保持运行
        while self.running:
            await asyncio.sleep(1)
    
    def _print_startup_info(self, wechat_config: WechatWorkConfig) -> None:
        """打印启动信息。"""
        print()
        print("=" * 70)
        print(f"{COLOR_GREEN}iFlow 企业微信机器人 🤖{COLOR_RESET}")
        print("=" * 70)
        print()
        print(f"{COLOR_BLUE}[配置信息]{COLOR_RESET}")
        print(f"  企业 ID: {wechat_config.corp_id}")
        print(f"  应用 ID: {wechat_config.agent_id}")
        print(f"  tmux 会话: {self.config.tmux_session}")
        print(f"  工作目录: {self.config.workspace}")
        print()
        print(f"{COLOR_BLUE}[回调服务]{COLOR_RESET}")
        callback_url = f"http://{wechat_config.callback_host}:{wechat_config.callback_port}/wechat/callback"
        print(f"  回调 URL: {callback_url}")
        print()
        print(f"{COLOR_BLUE}[可用命令]{COLOR_RESET}")
        print(f"  直接发送消息：执行 iFlow 命令")
        print(f"  /run <命令>：执行 iFlow 命令")
        print(f"  /new：开始新会话")
        print(f"  /sessions：查看历史会话")
        print(f"  /status：查看服务状态")
        print(f"  /help：显示帮助")
        print()
        print("=" * 70)
        print()
    
    async def stop(self) -> None:
        """停止机器人。"""
        self.running = False
        
        if self.wechat_channel:
            await self.wechat_channel.stop()
        
        logger.info("[WechatBot] 已停止")
        print(f"{COLOR_YELLOW}[停止] iFlow 企业微信机器人已停止{COLOR_RESET}")
    
    async def _handle_shutdown(self) -> None:
        """处理关闭信号。"""
        logger.info("[WechatBot] 收到关闭信号，正在停止...")
        print(f"{COLOR_YELLOW}[停止] 收到关闭信号，正在停止...{COLOR_RESET}")
        await self.stop()


async def main():
    """主函数。"""
    import argparse
    
    parser = argparse.ArgumentParser(description="iFlow 企业微信机器人")
    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="配置文件路径（默认: config.json）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细日志模式"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    
    # 创建机器人实例
    bot = WechatBot(config_path=args.config)
    
    # 设置信号处理
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        asyncio.create_task(bot._handle_shutdown())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    # 启动机器人
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("[WechatBot] 用户中断")
        print(f"\n{COLOR_YELLOW}[中断] 收到用户中断，正在停止...{COLOR_RESET}")
        await bot.stop()
    except Exception as e:
        logger.error(f"[WechatBot] 启动失败: {e}", exc_info=True)
        print(f"{COLOR_YELLOW}[错误] 启动失败: {e}{COLOR_RESET}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}[中断] 程序已退出{COLOR_RESET}")
        sys.exit(0)
