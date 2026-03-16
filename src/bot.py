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

from .core import MessageBus, Message, ModuleManager
from .modules import WeChatChannel, SimulatorChannel, IFlowModule


logger = logging.getLogger(__name__)


class LingIflowBot:
    """Ling-iflow 机器人主类
    
    使用 ModuleManager 管理消息总线和所有模块的生命周期。
    """
    
    def __init__(self, config_path: str = "config.json", active_group: str = "all", active_channel: Optional[str] = None):
        """初始化机器人
        
        Args:
            config_path: 配置文件路径
            active_group: 要启动的组 (all, g1, g2, g_simulator)
            active_channel: 要启动的特定渠道 (wechat_bot1, simulator1)
        """
        self.config_path = config_path
        self.config: Dict = {}
        self.active_group = active_group
        self.active_channel = active_channel
        
        # 核心组件
        self.bus: Optional[MessageBus] = None
        self.manager: Optional[ModuleManager] = None
        self.wechat_modules: Dict[str, WeChatChannel] = {}
        self.simulator_modules: Dict[str, SimulatorChannel] = {}
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
            
            # 2. 创建模块管理器
            logger.info("创建模块管理器...")
            self.manager = ModuleManager(self.bus)
            
            # 3. 创建并注册 IFlowModule
            await self._setup_iflow_modules()
            
            # 4. 创建并注册 WeChatChannel
            await self._setup_wechat_modules()
            
            # 5. 创建并注册 SimulatorChannel
            await self._setup_simulator_channels()
            
            # 6. 设置绑定关系
            self._setup_bindings()
            
            # 7. 定义模块组
            await self._setup_groups()
            
            logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False
    
    async def _setup_iflow_modules(self) -> None:
        """创建并注册 IFlowModule（使用 ModuleManager）"""
        # 组名映射：g1 -> bot1, g2 -> bot2
        group_mapping = {
            "g1": "bot1",
            "g2": "bot2"
        }
        
        # 创建反向映射：bot名 -> tmux_session名
        bot_to_session = {}
        bots = self.config.get("bots", [])
        for bot_config in bots:
            if bot_config.get("enabled", False):
                bot_name = bot_config.get("name")
                tmux_session = bot_config.get("tmux_session", "iflow")
                bot_to_session[bot_name] = tmux_session
        
        # 收集需要启动的 tmux_session
        active_sessions = set()
        if self.active_group != "all":
            # 将组名转换为 bot 名，然后获取对应的 tmux_session
            target_bot_name = group_mapping.get(self.active_group, self.active_group)
            if target_bot_name in bot_to_session:
                active_sessions.add(bot_to_session[target_bot_name])
        else:
            # 收集所有启用的 bot 的 tmux_session
            active_sessions.update(bot_to_session.values())
        
        # 如果没有找到任何 session，使用默认的
        if not active_sessions:
            active_sessions.add(self.config.get("tmux_session", "iflow"))
        
        # 获取所有 tmux_sessions 配置
        tmux_sessions_config = self.config.get("tmux_sessions", [])
        
        # 如果没有配置 tmux_sessions，使用默认配置
        if not tmux_sessions_config:
            tmux_sessions_config = [{
                "name": self.config.get("tmux_session", "iflow"),
                "workspace": self.config.get("workspace", "~/.iflow"),
                "model": self.config.get("model", "kimi-k2.5")
            }]
        
        for session_config in tmux_sessions_config:
            session_name = session_config.get("name", "iflow")
            
            # 组过滤
            if session_name not in active_sessions:
                logger.info(f"会话 {session_name} 不在启动组 {self.active_group} 中，跳过")
                continue
            
            module_id = f"iflow_{session_name}"
            
            logger.info(f"创建 IFlowModule: {module_id}")
            
            # 使用 ModuleManager 创建模块
            iflow = await self.manager.create_module(
                module_type="iflow",
                module_id=module_id,
                config={
                    "tmux_session": session_name,
                    "model": session_config.get("model", "kimi-k2.5"),
                    "workspace": session_config.get("workspace", "~/.iflow")
                }
            )
            
            # 注册到消息总线
            await self.manager.register_module(module_id)
            
            # 设置消息总线引用
            self.manager.set_message_bus_for_module(module_id)
            
            # 存储引用
            self.iflow_modules[session_name] = iflow
            
            logger.info(f"IFlowModule {module_id} 创建和注册成功")
    
    async def _setup_wechat_modules(self) -> None:
        """创建并注册 WeChatChannel（使用 ModuleManager）"""
        # 组名映射：g1 -> bot1, g2 -> bot2
        group_mapping = {
            "g1": "bot1",
            "g2": "bot2"
        }
        
        bots = self.config.get("bots", [])
        
        for bot_config in bots:
            if not bot_config.get("enabled", False):
                logger.info(f"机器人 {bot_config.get('name')} 未启用，跳过")
                continue
            
            bot_name = bot_config.get("name", "default")
            
            # 组过滤
            if self.active_group != "all":
                # 将组名转换为 bot 名
                target_bot_name = group_mapping.get(self.active_group, self.active_group)
                if bot_name != target_bot_name:
                    logger.info(f"机器人 {bot_name} 不在启动组 {self.active_group} 中，跳过")
                    continue
            
            module_id = f"wechat_{bot_name}"
            
            logger.info(f"创建 WeChatChannel: {module_id}")
            
            # 使用 ModuleManager 创建模块
            wechat = await self.manager.create_module(
                module_type="wechat",
                module_id=module_id,
                config=bot_config
            )
            
            # 注册到消息总线
            await self.manager.register_module(module_id)
            
            # 设置消息总线引用
            self.manager.set_message_bus_for_module(module_id)
            
            # 设置模块管理器引用
            if hasattr(wechat, 'set_manager'):
                wechat.set_manager(self.manager)
            
            # 存储引用
            self.wechat_modules[bot_name] = wechat
            
            logger.info(f"WeChatChannel {module_id} 创建和注册成功")
    
    async def _setup_simulator_channels(self) -> None:
        """创建并注册 SimulatorChannel（使用 ModuleManager）"""
        # 收集需要启动的 tmux_session（从 iflow 模块中获取）
        active_sessions = set(self.iflow_modules.keys())
        
        # 如果没有找到任何 session，使用默认的
        if not active_sessions:
            active_sessions.add(self.config.get("tmux_session", "iflow"))
        
        simulator_channels = self.config.get("simulator_channels", [])
        
        for simulator_config in simulator_channels:
            if not simulator_config.get("enabled", False):
                logger.info(f"模拟器渠道 {simulator_config.get('name')} 未启用，跳过")
                continue
            
            simulator_name = simulator_config.get("name", "default")
            tmux_session = simulator_config.get("tmux_session", "iflow")
            
            # 会话过滤
            if tmux_session not in active_sessions:
                logger.info(f"模拟器渠道 {simulator_name} 的会话 {tmux_session} 未启动，跳过")
                continue
            
            module_id = f"simulator_{simulator_name}"
            
            logger.info(f"创建 SimulatorChannel: {module_id}")
            
            # 使用 ModuleManager 创建模块
            simulator = await self.manager.create_module(
                module_type="simulator",
                module_id=module_id,
                config=simulator_config
            )
            
            # 注册到消息总线
            await self.manager.register_module(module_id)
            
            # 设置消息总线引用
            self.manager.set_message_bus_for_module(module_id)
            
            # 存储引用
            self.simulator_modules[simulator_name] = simulator
            
            logger.info(f"SimulatorChannel {module_id} 创建和注册成功")
    
    def _setup_bindings(self) -> None:
        """设置模块绑定关系（双向绑定）"""
        # 企业微信渠道绑定
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
        
        # 模拟器渠道绑定
        simulator_channels = self.config.get("simulator_channels", [])
        
        for simulator_config in simulator_channels:
            if not simulator_config.get("enabled", False):
                continue
            
            simulator_name = simulator_config.get("name", "default")
            tmux_session = simulator_config.get("tmux_session", "iflow")
            
            simulator_id = f"simulator_{simulator_name}"
            iflow_id = f"iflow_{tmux_session}"
            
            # 双向绑定：Simulator -> IFlow, IFlow -> Simulator
            self.bus.bind(simulator_id, iflow_id)
            self.bus.bind(iflow_id, simulator_id)
            logger.info(f"双向绑定: {simulator_id} <-> {iflow_id}")
    
    async def _setup_groups(self) -> None:
        """定义模块组"""
        # 优先级：active_channel > active_group > all
        if self.active_channel:
            # 如果指定了渠道，不定义组
            logger.info(f"使用指定渠道: {self.active_channel}")
            return
        
        # 检查配置中是否定义了 groups
        groups_config = self.config.get("groups", {})
        
        if groups_config and self.active_group in groups_config:
            # 使用配置中的组定义
            group_modules = groups_config[self.active_group]
            self.manager.define_group(self.active_group, group_modules)
            logger.info(f"定义组 '{self.active_group}' (从配置): {group_modules}")
            return
        
        # 根据 active_group 定义组（向后兼容）
        if self.active_group == "all":
            # 创建包含所有模块的组
            all_modules = list(self.iflow_modules.keys()) + list(self.wechat_modules.keys()) + list(self.simulator_modules.keys())
            # 转换为 module_id
            all_module_ids = [f"iflow_{name}" for name in self.iflow_modules.keys()] + \
                              [f"wechat_{name}" for name in self.wechat_modules.keys()] + \
                              [f"simulator_{name}" for name in self.simulator_modules.keys()]
            self.manager.define_group("all", all_module_ids)
            logger.info(f"定义组 'all': {len(all_module_ids)} 个模块")
        else:
            # 根据 active_group 定义特定的组
            group_mapping = {
                "g1": "bot1",
                "g2": "bot2"
            }
            target_bot = group_mapping.get(self.active_group, self.active_group)
            
            # 查找对应的 tmux_session
            target_session = None
            bots = self.config.get("bots", [])
            for bot_config in bots:
                if bot_config.get("name") == target_bot:
                    target_session = bot_config.get("tmux_session", "iflow")
                    break
            
            if target_session:
                # 定义特定组的模块
                group_modules = [f"iflow_{target_session}", f"wechat_{target_bot}"]
                self.manager.define_group(self.active_group, group_modules)
                logger.info(f"定义组 '{self.active_group}': {group_modules}")
            else:
                logger.warning(f"无法找到组 '{self.active_group}' 对应的配置")
    
    async def start(self) -> None:
        """启动所有模块（使用 ModuleManager）"""
        logger.info("启动所有模块...")
        
        # 优先级：active_channel > active_group > all
        if self.active_channel:
            # 启动指定的渠道
            module_id = self.active_channel
            success = await self.manager.start_module(module_id)
            if success:
                logger.info(f"模块 {module_id} 启动成功")
            else:
                logger.warning(f"模块 {module_id} 启动失败")
        elif self.active_group == "all":
            # 启动所有模块
            for module_id in self.manager.modules.keys():
                success = await self.manager.start_module(module_id)
                if success:
                    logger.info(f"模块 {module_id} 启动成功")
                else:
                    logger.warning(f"模块 {module_id} 启动失败")
        else:
            # 启动指定组的模块
            results = await self.manager.start_group(self.active_group)
            for module_id, success in results.items():
                if success:
                    logger.info(f"模块 {module_id} 启动成功")
                else:
                    logger.warning(f"模块 {module_id} 启动失败")
        
        # 启动健康监控
        await self.manager.start_health_monitor()
        
        self._running = True
        logger.info("所有模块启动完成")
    
    async def stop(self) -> None:
        """停止所有模块（使用 ModuleManager）"""
        if not self._running:
            return
        
        logger.info("停止所有模块...")
        
        # 停止健康监控
        await self.manager.stop_health_monitor()
        
        # 使用 ModuleManager 停止模块
        for module_id in self.manager.modules.keys():
            await self.manager.stop_module(module_id)
        
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
    active_group = "all"
    active_channel = None
    
    if len(sys.argv) > 1:
        # 解析命令行参数
        i = 1
        while i < len(sys.argv):
            if sys.argv[i] == "--group" or sys.argv[i] == "-g":
                if i + 1 < len(sys.argv):
                    active_group = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            elif sys.argv[i] == "--channel":
                if i + 1 < len(sys.argv):
                    active_channel = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                # 第一个非参数的参数是配置文件
                if not sys.argv[i].startswith("-"):
                    config_path = sys.argv[i]
                i += 1
    
    bot = LingIflowBot(config_path, active_group, active_channel)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
