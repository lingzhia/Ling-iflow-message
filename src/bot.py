#!/usr/bin/env python3
"""
Ling-iflow 主程序入口

启动消息总线、企业微信模块和 iflow 模块，实现消息双向流转。
"""

import asyncio
import json
import signal
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .core import MessageBus, Message
from .modules import WeChatModule, IFlowModule


logger = logging.getLogger(__name__)


class LingIflowBot:
    """Ling-iflow 机器人主类
    
    管理消息总线和所有模块的生命周期。
    """
    
    def __init__(self, config_path: str = "config.json"):
        """初始化机器人
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config: Dict = {}
        
        # 核心组件
        self.bus: Optional[MessageBus] = None
        self.wechat_modules: Dict[str, WeChatModule] = {}
        self.iflow_modules: Dict[str, IFlowModule] = {}
        
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    def load_config(self) -> bool:
        """加载配置文件
        
        Returns:
            是否加载成功
        """
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                logger.error(f"配置文件不存在: {self.config_path}")
                return False
            
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            logger.info(f"配置加载成功: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            return False
    
    def setup_logging(self) -> None:
        """设置日志"""
        log_level = self.config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # 设置第三方库日志级别
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    async def setup(self) -> bool:
        """初始化所有组件
        
        Returns:
            是否初始化成功
        """
        try:
            # 1. 创建消息总线
            logger.info("创建消息总线...")
            self.bus = MessageBus()
            
            # 2. 创建并注册 IFlowModule
            await self._setup_iflow_modules()
            
            # 3. 创建并注册 WeChatModule
            await self._setup_wechat_modules()
            
            # 4. 设置绑定关系
            self._setup_bindings()
            
            logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False
    
    async def _setup_iflow_modules(self) -> None:
        """创建并注册 IFlowModule"""
        tmux_sessions = self.config.get("tmux_sessions", [])
        
        # 如果没有配置 tmux_sessions，使用默认配置
        if not tmux_sessions:
            tmux_sessions = [{
                "name": self.config.get("tmux_session", "iflow"),
                "workspace": self.config.get("workspace", "~/.iflow"),
                "model": self.config.get("model", "kimi-k2.5")
            }]
        
        for session_config in tmux_sessions:
            session_name = session_config.get("name", "iflow")
            module_id = f"iflow_{session_name}"
            
            logger.info(f"创建 IFlowModule: {module_id}")
            
            iflow = IFlowModule(
                module_id=module_id,
                tmux_session=session_name,
                model=session_config.get("model", "kimi-k2.5"),
                workspace=session_config.get("workspace", "~/.iflow"),
                auto_start=False  # 主程序控制启动时机
            )
            
            # 注册到消息总线
            self.bus.register_module(iflow)
            self.iflow_modules[session_name] = iflow
            
            logger.info(f"IFlowModule {module_id} 注册成功")
    
    async def _setup_wechat_modules(self) -> None:
        """创建并注册 WeChatModule"""
        bots = self.config.get("bots", [])
        
        for bot_config in bots:
            if not bot_config.get("enabled", False):
                logger.info(f"机器人 {bot_config.get('name')} 未启用，跳过")
                continue
            
            bot_name = bot_config.get("name", "default")
            module_id = f"wechat_{bot_name}"
            
            logger.info(f"创建 WeChatModule: {module_id}")
            
            wechat = WeChatModule(
                module_id=module_id,
                config=bot_config
            )
            
            # 注册到消息总线
            self.bus.register_module(wechat)
            self.wechat_modules[bot_name] = wechat
            
            logger.info(f"WeChatModule {module_id} 注册成功")
    
    def _setup_bindings(self) -> None:
        """设置模块绑定关系（双向绑定）"""
        bots = self.config.get("bots", [])
        
        for bot_config in bots:
            if not bot_config.get("enabled", False):
                continue
            
            bot_name = bot_config.get("name", "default")
            tmux_session = bot_config.get("tmux_session", "iflow")
            
            wechat_id = f"wechat_{bot_name}"
            iflow_id = f"iflow_{tmux_session}"
            
            # 双向绑定：WeChat -> IFlow, IFlow -> WeChat
            self.bus.bind(wechat_id, iflow_id)
            self.bus.bind(iflow_id, wechat_id)
            logger.info(f"双向绑定: {wechat_id} <-> {iflow_id}")
    
    async def start(self) -> None:
        """启动所有模块"""
        logger.info("启动所有模块...")
        
        # 启动 IFlowModule
        for session_name, iflow in self.iflow_modules.items():
            try:
                logger.info(f"启动 IFlowModule: {session_name}")
                await iflow.start()
                logger.info(f"IFlowModule {session_name} 启动成功")
            except Exception as e:
                logger.error(f"启动 IFlowModule {session_name} 失败: {e}", exc_info=True)
        
        # 启动 WeChatModule
        for bot_name, wechat in self.wechat_modules.items():
            try:
                logger.info(f"启动 WeChatModule: {bot_name}")
                await wechat.start()
                logger.info(f"WeChatModule {bot_name} 启动成功")
            except Exception as e:
                logger.error(f"启动 WeChatModule {bot_name} 失败: {e}", exc_info=True)
        
        self._running = True
        logger.info("所有模块启动完成")
    
    async def stop(self) -> None:
        """停止所有模块"""
        if not self._running:
            return
        
        logger.info("停止所有模块...")
        
        # 停止 WeChatModule
        for bot_name, wechat in self.wechat_modules.items():
            try:
                logger.info(f"停止 WeChatModule: {bot_name}")
                await wechat.stop()
            except Exception as e:
                logger.error(f"停止 WeChatModule {bot_name} 失败: {e}")
        
        # 停止 IFlowModule
        for session_name, iflow in self.iflow_modules.items():
            try:
                logger.info(f"停止 IFlowModule: {session_name}")
                await iflow.stop()
            except Exception as e:
                logger.error(f"停止 IFlowModule {session_name} 失败: {e}")
        
        self._running = False
        logger.info("所有模块已停止")
    
    async def run(self) -> None:
        """运行主循环"""
        # 加载配置
        if not self.load_config():
            return
        
        self.setup_logging()
        
        # 初始化
        if not await self.setup():
            return
        
        # 启动
        await self.start()
        
        # 注册信号处理
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self._handle_signal())
            )
        
        # 等待退出信号
        logger.info("机器人运行中，按 Ctrl+C 退出")
        await self._shutdown_event.wait()
        
        # 停止
        await self.stop()
    
    async def _handle_signal(self) -> None:
        """处理退出信号"""
        logger.info("收到退出信号")
        self._shutdown_event.set()


async def main():
    """主函数"""
    # 支持命令行参数指定配置文件
    config_path = "config.json"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    bot = LingIflowBot(config_path)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
