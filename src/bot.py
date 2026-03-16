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
    支持单进程多组管理，默认只启动组1，其他组按需实例化。
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
        
        # 组定义缓存
        self.group_definitions: Dict[str, Dict] = {}
        self.default_group = "g1"  # 默认组
        
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
            
            # 3. 加载组定义
            self._load_group_definitions()
            
            # 4. 创建组1的模块（但不启动）
            await self._setup_default_group()
            
            # 5. 设置组1的绑定关系
            self._setup_bindings_for_group(self.default_group)
            
            # 6. 定义组1
            await self._setup_group_definition(self.default_group)
            
            logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False
    
    def _load_group_definitions(self) -> None:
        """加载组定义"""
        groups_config = self.config.get("groups", {})
        self.group_definitions = groups_config.copy()
        logger.info(f"加载了 {len(groups_config)} 个组定义: {list(groups_config.keys())}")
    
    async def _setup_default_group(self) -> None:
        """创建默认组（组1）的模块（不启动）"""
        # 从配置中获取默认组
        groups_config = self.config.get("groups", {})
        
        # 找到标记为 default 的组
        for group_name, group_config in groups_config.items():
            if group_config.get("default", False):
                self.default_group = group_name
                logger.info(f"发现默认组: {group_name}")
                break
        
        # 如果没有找到默认组，使用 g1
        if self.default_group not in groups_config:
            self.default_group = "g1"
            logger.warning(f"未找到默认组，使用 g1")
        
        # 创建默认组的模块
        await self._setup_group_modules(self.default_group)
    
    async def _setup_group_modules(self, group_name: str) -> None:
        """创建指定组的模块（不启动）
        
        Args:
            group_name: 组名
        """
        group_config = self.group_definitions.get(group_name, {})
        module_ids = group_config.get("modules", [])
        
        logger.info(f"创建组 {group_name} 的模块: {module_ids}")
        
        # 按照类型创建模块
        for module_id in module_ids:
            if module_id.startswith("iflow_"):
                await self._create_iflow_module(module_id)
            elif module_id.startswith("wechat_"):
                await self._create_wechat_module(module_id)
            elif module_id.startswith("simulator_"):
                await self._create_simulator_module(module_id)
            else:
                logger.warning(f"未知的模块类型: {module_id}")
    
    async def _create_iflow_module(self, module_id: str) -> None:
        """创建 IFlow 模块
        
        Args:
            module_id: 模块 ID
        """
        # 从 tmux_sessions 配置中查找对应的配置
        tmux_sessions = self.config.get("tmux_sessions", [])
        session_name = module_id.replace("iflow_", "")
        
        session_config = None
        for session in tmux_sessions:
            if session.get("name") == session_name:
                session_config = session
                break
        
        if not session_config:
            logger.warning(f"未找到 {module_id} 的配置，使用默认配置")
            session_config = {
                "name": session_name,
                "workspace": self.config.get("workspace", "~/.iflow"),
                "model": self.config.get("model", "kimi-k2.5")
            }
        
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
    
    async def _create_wechat_module(self, module_id: str) -> None:
        """创建 WeChat 模块
        
        Args:
            module_id: 模块 ID
        """
        bot_name = module_id.replace("wechat_", "")
        
        # 从 bots 配置中查找对应的配置
        bots = self.config.get("bots", [])
        bot_config = None
        for bot in bots:
            if bot.get("name") == bot_name:
                bot_config = bot
                break
        
        if not bot_config:
            logger.warning(f"未找到 {module_id} 的配置")
            return
        
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
    
    async def _create_simulator_module(self, module_id: str) -> None:
        """创建 Simulator 模块
        
        Args:
            module_id: 模块 ID
        """
        simulator_name = module_id.replace("simulator_", "")
        
        # 从 simulator_channels 配置中查找对应的配置
        simulators = self.config.get("simulator_channels", [])
        sim_config = None
        for sim in simulators:
            if sim.get("name") == simulator_name:
                sim_config = sim
                break
        
        if not sim_config:
            logger.warning(f"未找到 {module_id} 的配置")
            return
        
        # 使用 ModuleManager 创建模块
        simulator = await self.manager.create_module(
            module_type="simulator",
            module_id=module_id,
            config=sim_config
        )
        
        # 注册到消息总线
        await self.manager.register_module(module_id)
        
        # 设置消息总线引用
        self.manager.set_message_bus_for_module(module_id)
        
        # 设置模块管理器引用
        if hasattr(simulator, 'set_manager'):
            simulator.set_manager(self.manager)
        
        # 存储引用
        self.simulator_modules[simulator_name] = simulator
        
        logger.info(f"SimulatorChannel {module_id} 创建和注册成功")
    
    def _setup_bindings_for_group(self, group_name: str) -> None:
        """设置指定组的绑定关系
        
        Args:
            group_name: 组名
        """
        group_config = self.group_definitions.get(group_name, {})
        module_ids = group_config.get("modules", [])
        
        logger.info(f"设置组 {group_name} 的绑定关系")
        
        # 简单的绑定策略：渠道 -> IFlow
        for i in range(len(module_ids)):
            for j in range(i + 1, len(module_ids)):
                module_id1 = module_ids[i]
                module_id2 = module_ids[j]
                
                # 判断是否需要绑定（渠道 -> IFlow）
                if (module_id1.startswith("wechat_") or module_id1.startswith("simulator_")) and module_id2.startswith("iflow_"):
                    self.bus.bind(module_id1, module_id2)
                    self.bus.bind(module_id2, module_id1)
                    logger.info(f"绑定: {module_id1} <-> {module_id2}")
    
    async def _setup_group_definition(self, group_name: str) -> None:
        """定义指定的组
        
        Args:
            group_name: 组名
        """
        group_config = self.group_definitions.get(group_name, {})
        module_ids = group_config.get("modules", [])
        
        self.manager.define_group(group_name, module_ids)
        logger.info(f"定义组 {group_name}: {module_ids}")


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
            
            # 设置模块管理器引用
            if hasattr(simulator, 'set_manager'):
                simulator.set_manager(self.manager)
            
            # 存储引用
            self.simulator_modules[simulator_name] = simulator
            
            logger.info(f"SimulatorChannel {module_id} 创建和注册成功")
    
    def _setup_bindings(self) -> None:
        """设置模块绑定关系（双向绑定）
        
        只为实际创建的模块设置绑定关系
        """
        # 企业微信渠道绑定
        for bot_name, wechat in self.wechat_modules.items():
            tmux_session = wechat.config.get("tmux_session", "iflow")
            
            wechat_id = f"wechat_{bot_name}"
            iflow_id = f"iflow_{tmux_session}"
            
            # 双向绑定：WeChat -> IFlow, IFlow -> WeChat
            self.bus.bind(wechat_id, iflow_id)
            self.bus.bind(iflow_id, wechat_id)
            logger.info(f"双向绑定: {wechat_id} <-> {iflow_id}")
        
        # 模拟器渠道绑定
        for simulator_name, simulator in self.simulator_modules.items():
            tmux_session = simulator.config.get("tmux_session", "iflow")
            
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
        
        # 默认只启动组1
        # 如果 active_group 为 all，仍然只启动默认组
        # 这样可以保持向后兼容，同时实现新的启动策略
        logger.info(f"启动默认组: {self.default_group}")
        results = await self.manager.start_group(self.default_group)
        
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

    
    # ==================== 组控制功能 ====================
    
    async def start_group(self, group_name: str) -> Dict[str, bool]:
        """启动指定的组
        
        Args:
            group_name: 组名
            
        Returns:
            每个模块的启动结果
        """
        logger.info(f"启动组: {group_name}")
        
        # 检查组是否存在
        if group_name not in self.group_definitions:
            logger.error(f"组不存在: {group_name}")
            return {}
        
        # 检查组的模块是否已创建
        group_config = self.group_definitions[group_name]
        module_ids = group_config.get("modules", [])
        
        # 检查是否需要创建模块
        for module_id in module_ids:
            if module_id not in self.manager.modules:
                logger.info(f"按需创建模块: {module_id}")
                await self._setup_group_modules(group_name)
                self._setup_bindings_for_group(group_name)
                await self._setup_group_definition(group_name)
                break
        
        # 启动组
        results = await self.manager.start_group(group_name)
        
        return results
    
    async def stop_group(self, group_name: str) -> Dict[str, bool]:
        """停止指定的组
        
        Args:
            group_name: 组名
            
        Returns:
            每个模块的停止结果
        """
        logger.info(f"停止组: {group_name}")
        return await self.manager.stop_group(group_name)
    
    async def restart_group(self, group_name: str) -> Dict[str, bool]:
        """重启指定的组
        
        Args:
            group_name: 组名
            
        Returns:
            每个模块的重启结果
        """
        logger.info(f"重启组: {group_name}")
        
        # 先停止
        await self.stop_group(group_name)
        
        # 等待一下
        await asyncio.sleep(1)
        
        # 再启动
        return await self.start_group(group_name)
    
    def get_group_status(self, group_name: str) -> Dict[str, Any]:
        """获取指定组的状态
        
        Args:
            group_name: 组名
            
        Returns:
            组状态信息
        """
        module_ids = self.manager.get_group_modules(group_name)
        
        group_status = {
            "group_name": group_name,
            "modules": {}
        }
        
        for module_id in module_ids:
            group_status["modules"][module_id] = self.manager.get_module_status(module_id)
        
        return group_status
    
    def get_all_groups_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有组的状态
        
        Returns:
            所有组的状态信息
        """
        all_status = {}
        for group_name in self.group_definitions.keys():
            all_status[group_name] = self.get_group_status(group_name)
        
        return all_status
    
    def list_groups(self) -> List[str]:
        """列出所有组
        
        Returns:
            组名列表
        """
        return list(self.group_definitions.keys())
    
    def get_group_info(self, group_name: str) -> Optional[Dict[str, Any]]:
        """获取组的信息
        
        Args:
            group_name: 组名
            
        Returns:
            组信息
        """
        return self.group_definitions.get(group_name)


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
