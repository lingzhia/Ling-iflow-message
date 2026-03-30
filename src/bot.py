#!/usr/bin/env python3
"""
Ling-iflow 主程序入口

启动消息总线、企业微信模块和 iflow 模块，实现消息双向流转。
"""

import asyncio
import json
import os
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Dict, List, Optional, Any

# 前向声明，避免循环导入
if False:
    from .modules.channel import WeChatChannel, FeishuChannel, SimulatorChannel
    from .modules.iflow import IFlowModule

from .core import MessageBus, Message, ModuleManager


logger = logging.getLogger(__name__)


class LingIflowBot:
    """Ling-iflow 机器人主类
    
    使用 ModuleManager 管理消息总线和所有模块的生命周期。
    支持单进程多组管理，默认只启动组1，其他组按需实例化。
    """
    
    def __init__(self, config_path: str = "config.json", active_channel: Optional[str] = None):
        """初始化机器人
        
        Args:
            config_path: 配置文件路径
            active_channel: 要启动的特定渠道 (wechat_bot1, wechat_bot2, simulator1)，None 表示启动所有渠道
        """
        self.config_path = config_path
        self.config: Dict = {}
        self.active_channel = active_channel
        
        # 工作目录：优先级：配置文件 > 环境变量 > 当前工作目录
        # 默认使用当前工作目录，会在 load_config 后更新
        self.workspace = os.environ.get("LING_IFLOW_WORKSPACE", os.getcwd())
        
        # 核心组件
        self.bus: Optional[MessageBus] = None
        self.manager: Optional[ModuleManager] = None
        self.wechat_modules: Dict[str, WeChatChannel] = {}
        self.feishu_modules: Dict[str, FeishuChannel] = {}
        self.simulator_modules: Dict[str, SimulatorChannel] = {}
        self.iflow_modules: Dict[str, IFlowModule] = {}
        
        # Unix Socket 控制接口
        self.control_socket_path = "/tmp/ling-iflow.sock"
        self.control_server_task: Optional[asyncio.Task] = None
        
        self._running = False
        self._shutdown_event = asyncio.Event()
        
        # Unix Socket 控制接口
        self.control_socket_path = "/tmp/ling-iflow.sock"
        self.control_server_task: Optional[asyncio.Task] = None
    
    def _resolve_config_path(self) -> Path:
        """解析配置文件路径
        
        优先级：
        1. 用户指定的绝对路径
        2. 用户指定的相对路径（相对于当前工作目录）
        3. 项目根目录下的 config.json
        """
        path = Path(self.config_path)
        
        # 绝对路径直接返回
        if path.is_absolute():
            return path
        
        # 相对路径：先检查当前工作目录
        cwd_path = Path.cwd() / self.config_path
        if cwd_path.exists():
            return cwd_path
        
        # 再检查项目根目录（src/bot.py 的上级目录）
        project_path = Path(__file__).parent.parent / self.config_path
        if project_path.exists():
            return project_path
        
        # 都不存在，返回当前工作目录下的路径（用于错误提示）
        return cwd_path

    def load_config(self) -> bool:
        """加载配置文件
        
        Returns:
            是否加载成功
        """
        try:
            config_file = self._resolve_config_path()
            if not config_file.exists():
                logger.error(f"配置文件不存在: {self.config_path}")
                logger.error(f"查找路径: {config_file}")
                logger.error(f"当前工作目录: {Path.cwd()}")
                return False
            
            # 更新配置文件路径为解析后的绝对路径
            self.config_path = str(config_file)
            
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # 更新 workspace（配置文件优先级最高，但需要非空）
            config_workspace = self.config.get("workspace", "")
            if config_workspace:
                self.workspace = config_workspace
                logger.info(f"从配置文件设置工作目录: {self.workspace}")
            
            logger.info(f"配置加载成功: {self.config_path}")
            logger.info(f"iflow 工作目录: {self.workspace}")
            return True
            
        except Exception as e:
            logger.error(f"加载配置失败: {e}", exc_info=True)
            return False
    
    def setup_logging(self) -> None:
        """设置日志"""
        log_level = self.config.get("log_level", "INFO")
        
        # 获取 logger 等级
        level = getattr(logging, log_level, logging.INFO)
        
        # 设置根 logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # 清除现有 handlers
        root_logger.handlers.clear()
        
        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
        ))
        root_logger.addHandler(console_handler)
        
        # 文件 handler - 按大小轮转，保留 5 个备份，单文件最大 10MB
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "bot.log"
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
        ))
        root_logger.addHandler(file_handler)
        
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
            
            # 3. 将 ModuleManager 设置到 MessageBus（用于状态检查）
            logger.info("设置 MessageBus 的 ModuleManager 引用...")
            self.bus.module_manager = self.manager
            
            # 4. 根据配置创建模块
            # 检查是否有飞书配置
            has_feishu = len(self.config.get("feishu_channels", [])) > 0
            has_wechat = len(self.config.get("bots", [])) > 0
            has_simulator = len(self.config.get("simulator_channels", [])) > 0
            
            # 如果没有任何配置，默认创建企业微信模块
            if not has_feishu and not has_wechat and not has_simulator:
                has_wechat = True
            
            if has_wechat:
                await self._create_wechat_modules()
            
            if has_feishu:
                await self._create_feishu_modules()
            
            if has_simulator:
                await self._create_simulator_modules()
            
            # 7. 为每个渠道创建对应的 iflow 模块和绑定关系
            await self._setup_channels()
            
            logger.info("所有组件初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False
    
    async def _create_wechat_modules(self) -> None:
        """创建所有企业微信渠道模块"""
        bots_config = self.config.get("bots", [])
        logger.info(f"创建 {len(bots_config)} 个企业微信模块...")
        
        for bot_config in bots_config:
            bot_name = bot_config.get("name")
            
            try:
                module_id = f"wechat_{bot_name}"
                wechat = await self.manager.create_module(
                    module_type="wechat",
                    module_id=module_id,
                    config=bot_config
                )
                # 设置 manager 和 bot 引用
                wechat.set_manager(self.manager)
                wechat.set_bot(self)
                self.wechat_modules[bot_name] = wechat
                await self.manager.register_module(module_id)
                logger.info(f"创建企业微信模块: {module_id}")
            except Exception as e:
                logger.error(f"创建企业微信模块失败 {bot_name}: {e}")
    

    async def _create_feishu_modules(self) -> None:
        """创建所有飞书渠道模块"""
        feishu_config = self.config.get("feishu_channels", [])
        logger.info(f"创建 {len(feishu_config)} 个飞书模块...")
        
        for fs_config in feishu_config:
            if not fs_config.get("enabled", True):
                continue
            
            fs_name = fs_config.get("name")
            
            try:
                module_id = f"feishu_{fs_name}"
                feishu = await self.manager.create_module(
                    module_type="feishu",
                    module_id=module_id,
                    config=fs_config
                )
                feishu.set_manager(self.manager)
                feishu.set_bot(self)
                self.feishu_modules[fs_name] = feishu
                await self.manager.register_module(module_id)
                logger.info(f"创建飞书模块：{module_id}")
            except Exception as e:
                logger.error(f"创建飞书模块失败 {fs_name}: {e}")

    async def _create_simulator_modules(self) -> None:
        """创建所有模拟器渠道模块"""
        simulator_config = self.config.get("simulator_channels", [])
        logger.info(f"创建 {len(simulator_config)} 个模拟器模块...")
        
        for sim_config in simulator_config:
            sim_name = sim_config.get("name")
            
            try:
                module_id = f"simulator_{sim_name}"
                simulator = await self.manager.create_module(
                    module_type="simulator",
                    module_id=module_id,
                    config=sim_config
                )
                self.simulator_modules[sim_name] = simulator
                simulator.set_manager(self.manager)
                simulator.set_bot(self)
                await self.manager.register_module(module_id)
                logger.info(f"创建模拟器模块: {module_id}")
            except Exception as e:
                logger.error(f"创建模拟器模块失败 {sim_name}: {e}")
    
    async def _setup_channels(self) -> None:
        """为每个渠道创建对应的 iflow 模块和绑定关系"""
        # 设置企业微信渠道的 iflow 模块
        for bot_config in self.config.get("bots", []):
            if isinstance(bot_config, dict):
                bot_name = bot_config.get("name")
                await self._setup_channel_iflow(bot_name, bot_config)
        
        # 设置飞书渠道的 iflow 模块
        for fs_config in self.config.get("feishu_channels", []):
            if isinstance(fs_config, dict) and fs_config.get("enabled", True):
                fs_name = fs_config.get("name")
                await self._setup_channel_iflow(fs_name, fs_config)
        
        # 设置模拟器渠道的 iflow 模块
        for sim_config in self.config.get("simulator_channels", []):
            sim_name = sim_config.get("name")
            await self._setup_channel_iflow(sim_name, sim_config)
    
    async def _setup_channel_iflow(self, channel_name: str, channel_config: Dict) -> None:
        """为特定渠道设置 iflow 模块和绑定关系
        
        Args:
            channel_name: 渠道名称
            channel_config: 渠道配置
        """
        try:
            # 创建 iflow 模块
            iflow_module_id = f"iflow_{channel_name}"
            tmux_session = channel_config.get("tmux_session", f"{channel_name}+iflow")
            
            iflow = await self.manager.create_module(
                module_type="iflow",
                module_id=iflow_module_id,
                config={
                    "tmux_session": tmux_session,
                    "model": "glm-4.7",  # 默认模型
                    "workspace": self.workspace  # 使用工作目录
                }
            )
            # 设置 manager 引用
            iflow.manager = self.manager
            self.iflow_modules[channel_name] = iflow
            await self.manager.register_module(iflow_module_id)
            logger.info(f"创建 iflow 模块: {iflow_module_id}, tmux会话: {tmux_session}")
            
            # 设置绑定关系
            if channel_name in self.wechat_modules:
                wechat_module_id = f"wechat_{channel_name}"
                self.bus.bind(wechat_module_id, iflow_module_id)
                self.bus.bind(iflow_module_id, wechat_module_id)
                logger.info(f"绑定: {wechat_module_id} <-> {iflow_module_id}")
            elif channel_name in self.feishu_modules:
                feishu_module_id = f"feishu_{channel_name}"
                self.bus.bind(feishu_module_id, iflow_module_id)
                self.bus.bind(iflow_module_id, feishu_module_id)
                logger.info(f"绑定: {feishu_module_id} <-> {iflow_module_id}")
            elif channel_name in self.simulator_modules:
                simulator_module_id = f"simulator_{channel_name}"
                self.bus.bind(simulator_module_id, iflow_module_id)
                self.bus.bind(iflow_module_id, simulator_module_id)
                logger.info(f"绑定: {simulator_module_id} <-> {iflow_module_id}")
        
        except Exception as e:
            logger.error(f"设置渠道 iflow 失败 {channel_name}: {e}")
    
    async def start(self) -> None:
        """启动所有模块（使用 ModuleManager）"""
        logger.info("启动所有模块...")
        
        # 根据 active_channel 参数启动相应的渠道
        if self.active_channel:
            # 启动指定的渠道
            logger.info(f"启动指定渠道: {self.active_channel}")
            if self.active_channel in self.wechat_modules:
                # 启动企业微信模块
                wechat_module_id = f"wechat_{self.active_channel}"
                await self.manager.start_module(wechat_module_id)
            elif self.active_channel in self.feishu_modules:
                # 启动飞书模块
                feishu_module_id = f"feishu_{self.active_channel}"
                await self.manager.start_module(feishu_module_id)
            elif self.active_channel in self.simulator_modules:
                # 启动模拟器模块
                simulator_module_id = f"simulator_{self.active_channel}"
                await self.manager.start_module(simulator_module_id)
            
            # 启动对应的 iflow 模块
            iflow_module_id = f"iflow_{self.active_channel}"
            await self.manager.start_module(iflow_module_id)
        else:
            # 启动所有模块
            logger.info("启动所有模块...")
            
            # 启动所有企业微信模块
            for bot_name in self.wechat_modules.keys():
                wechat_module_id = f"wechat_{bot_name}"
                await self.manager.start_module(wechat_module_id)
            
            # 启动所有飞书模块
            for fs_name in self.feishu_modules.keys():
                feishu_module_id = f"feishu_{fs_name}"
                await self.manager.start_module(feishu_module_id)
            
            # 启动所有模拟器模块
            for sim_name in self.simulator_modules.keys():
                simulator_module_id = f"simulator_{sim_name}"
                await self.manager.start_module(simulator_module_id)
            
            # 启动所有 iflow 模块
            for channel_name in self.iflow_modules.keys():
                iflow_module_id = f"iflow_{channel_name}"
                await self.manager.start_module(iflow_module_id)
        
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
        
        # 启动Unix Socket控制服务器
        control_socket_task = asyncio.create_task(self._start_control_socket())
        
        # 等待退出信号
        logger.info("机器人运行中，按 Ctrl+C 退出")
        await self._shutdown_event.wait()
        
        # 停止Unix Socket控制服务器
        await self._stop_control_socket()
        
        # 停止
        await self.stop()
    
    async def _handle_signal(self) -> None:
        """处理退出信号"""
        logger.info("收到退出信号")
        self._shutdown_event.set()

    
    # ==================== 渠道控制功能 ====================
    
    async def start_channel(self, channel_name: str) -> Dict[str, bool]:
        """启动指定的渠道
        
        Args:
            channel_name: 渠道名称 (wechat_bot1, feishu1, simulator1)
            
        Returns:
            每个模块的启动结果
        """
        logger.info(f"启动渠道: {channel_name}")
        results = {}
        
        try:
            # 检查并创建企业微信模块（如果不存在）
            if channel_name not in self.wechat_modules:
                # 尝试从配置中查找企业微信配置
                for bot_config in self.config.get("bots", []):
                    if bot_config.get("name") == channel_name:
                        module_id = f"wechat_{channel_name}"
                        logger.info(f"动态创建企业微信模块: {module_id}")
                        wechat = await self.manager.create_module(
                            module_type="wechat",
                            module_id=module_id,
                            config=bot_config
                        )
                        wechat.set_manager(self.manager)
                        wechat.set_bot(self)
                        self.wechat_modules[channel_name] = wechat
                        await self.manager.register_module(module_id)
                        break
            
            # 检查并创建飞书模块（如果不存在）
            if channel_name not in self.feishu_modules:
                # 尝试从配置中查找飞书配置
                for fs_config in self.config.get("feishu_channels", []):
                    if fs_config.get("name") == channel_name and fs_config.get("enabled", True):
                        module_id = f"feishu_{channel_name}"
                        logger.info(f"动态创建飞书模块: {module_id}")
                        feishu = await self.manager.create_module(
                            module_type="feishu",
                            module_id=module_id,
                            config=fs_config
                        )
                        feishu.set_manager(self.manager)
                        feishu.set_bot(self)
                        self.feishu_modules[channel_name] = feishu
                        await self.manager.register_module(module_id)
                        break
            
            # 检查并创建模拟器模块（如果不存在）
            if channel_name not in self.simulator_modules:
                # 尝试从配置中查找模拟器配置
                for sim_config in self.config.get("simulator_channels", []):
                    if sim_config.get("name") == channel_name:
                        module_id = f"simulator_{channel_name}"
                        logger.info(f"动态创建模拟器模块: {module_id}")
                        simulator = await self.manager.create_module(
                            module_type="simulator",
                            module_id=module_id,
                            config=sim_config
                        )
                        simulator.set_manager(self.manager)
                        simulator.set_bot(self)
                        self.simulator_modules[channel_name] = simulator
                        await self.manager.register_module(module_id)
                        break
            
            # 启动企业微信模块
            if channel_name in self.wechat_modules:
                wechat_module_id = f"wechat_{channel_name}"
                result = await self.manager.start_module(wechat_module_id)
                results[wechat_module_id] = result.success
            
            # 启动飞书模块
            elif channel_name in self.feishu_modules:
                feishu_module_id = f"feishu_{channel_name}"
                result = await self.manager.start_module(feishu_module_id)
                results[feishu_module_id] = result.success
            
            # 启动模拟器模块
            elif channel_name in self.simulator_modules:
                simulator_module_id = f"simulator_{channel_name}"
                result = await self.manager.start_module(simulator_module_id)
                results[simulator_module_id] = result.success
            
            # 检查并创建 iflow 模块（如果不存在）
            iflow_module_id = f"iflow_{channel_name}"
            if iflow_module_id not in self.manager.modules:
                logger.info(f"动态创建 iflow 模块: {iflow_module_id}")
                # 查找渠道配置
                channel_config = None
                for bot_config in self.config.get("bots", []):
                    if bot_config.get("name") == channel_name:
                        channel_config = bot_config
                        break
                if not channel_config:
                    for fs_config in self.config.get("feishu_channels", []):
                        if fs_config.get("name") == channel_name:
                            channel_config = fs_config
                            break
                if not channel_config:
                    for sim_config in self.config.get("simulator_channels", []):
                        if sim_config.get("name") == channel_name:
                            channel_config = sim_config
                            break
                
                if channel_config:
                    await self._setup_channel_iflow(channel_name, channel_config)
            
            # 启动对应的 iflow 模块
            result = await self.manager.start_module(iflow_module_id)
            results[iflow_module_id] = result.success
            
            # 启动健康监控
            await self.manager.start_health_monitor()
            
        except Exception as e:
            logger.error(f"启动渠道失败 {channel_name}: {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    async def stop_channel(self, channel_name: str) -> Dict[str, bool]:
        """停止指定的渠道
        
        Args:
            channel_name: 渠道名称
            
        Returns:
            每个模块的停止结果
        """
        logger.info(f"停止渠道: {channel_name}")
        results = {}
        
        try:
            # 停止健康监控
            await self.manager.stop_health_monitor()
            
            # 停止企业微信模块
            if channel_name in self.wechat_modules:
                wechat_module_id = f"wechat_{channel_name}"
                result = await self.manager.stop_module(wechat_module_id)
                results[wechat_module_id] = result.success
            
            # 停止飞书模块
            elif channel_name in self.feishu_modules:
                feishu_module_id = f"feishu_{channel_name}"
                result = await self.manager.stop_module(feishu_module_id)
                results[feishu_module_id] = result.success
            
            # 停止模拟器模块
            elif channel_name in self.simulator_modules:
                simulator_module_id = f"simulator_{channel_name}"
                result = await self.manager.stop_module(simulator_module_id)
                results[simulator_module_id] = result.success
            
            # 停止对应的 iflow 模块
            iflow_module_id = f"iflow_{channel_name}"
            result = await self.manager.stop_module(iflow_module_id)
            results[iflow_module_id] = result.success
            
        except Exception as e:
            logger.error(f"停止渠道失败 {channel_name}: {e}")
        
        return results
    
    async def restart_channel(self, channel_name: str) -> Dict[str, bool]:
        """重启指定的渠道
        
        Args:
            channel_name: 渠道名称
            
        Returns:
            每个模块的重启结果
        """
        logger.info(f"重启渠道: {channel_name}")
        
        # 先停止
        await self.stop_channel(channel_name)
        
        # 等待一下
        await asyncio.sleep(1)
        
        # 再启动
        return await self.start_channel(channel_name)
    
    def get_channel_status(self, channel_name: str) -> Dict[str, Any]:
        """获取指定渠道的状态
        
        Args:
            channel_name: 渠道名称
            
        Returns:
            渠道状态信息
        """
        channel_status = {
            "channel_name": channel_name,
            "modules": {}
        }
        
        # 获取企业微信模块状态
        if channel_name in self.wechat_modules:
            wechat_module_id = f"wechat_{channel_name}"
            channel_status["modules"][wechat_module_id] = self.manager.get_module_status(wechat_module_id)
        
        # 获取飞书模块状态
        elif channel_name in self.feishu_modules:
            feishu_module_id = f"feishu_{channel_name}"
            channel_status["modules"][feishu_module_id] = self.manager.get_module_status(feishu_module_id)
        
        # 获取模拟器模块状态
        elif channel_name in self.simulator_modules:
            simulator_module_id = f"simulator_{channel_name}"
            channel_status["modules"][simulator_module_id] = self.manager.get_module_status(simulator_module_id)
        
        # 获取 iflow 模块状态
        iflow_module_id = f"iflow_{channel_name}"
        if iflow_module_id in self.manager.modules:
            channel_status["modules"][iflow_module_id] = self.manager.get_module_status(iflow_module_id)
        
        return channel_status
    
    def get_all_channels_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有渠道的状态
        
        Returns:
            所有渠道的状态信息
        """
        all_status = {}
        
        # 获取所有企业微信渠道状态
        for channel_name in self.wechat_modules.keys():
            all_status[channel_name] = self.get_channel_status(channel_name)
        
        # 获取所有飞书渠道状态
        for channel_name in self.feishu_modules.keys():
            all_status[channel_name] = self.get_channel_status(channel_name)
        
        # 获取所有模拟器渠道状态
        for channel_name in self.simulator_modules.keys():
            all_status[channel_name] = self.get_channel_status(channel_name)
        
        return all_status
    
    def list_channels(self) -> List[str]:
        """列出所有渠道
        
        Returns:
            渠道名列表
        """
        channels = list(self.wechat_modules.keys()) + list(self.feishu_modules.keys()) + list(self.simulator_modules.keys())
        return channels
    
    def get_channel_info(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """获取渠道的信息
        
        Args:
            channel_name: 渠道名称
            
        Returns:
            渠道信息
        """
        # 从 bots 配置中查找
        bots = self.config.get("bots", [])
        for bot in bots:
            if bot.get("name") == channel_name:
                return bot
        
        # 从 feishu_channels 配置中查找
        feishu_channels = self.config.get("feishu_channels", [])
        for fs in feishu_channels:
            if fs.get("name") == channel_name:
                return fs
        
        # 从 simulator_channels 配置中查找
        simulators = self.config.get("simulator_channels", [])
        for sim in simulators:
            if sim.get("name") == channel_name:
                return sim
        
        return None
    
    async def _start_control_socket(self) -> None:
        """启动Unix Socket控制服务器"""
        try:
            # 删除旧的socket文件
            import os
            if os.path.exists(self.control_socket_path):
                os.unlink(self.control_socket_path)
            
            # 创建Unix Socket服务器
            server = await asyncio.start_unix_server(
                self._handle_control_connection,
                path=self.control_socket_path
            )
            
            # 设置权限
            os.chmod(self.control_socket_path, 0o777)
            
            logger.info(f"Unix Socket控制服务器已启动: {self.control_socket_path}")
            
            # 启动服务器（不阻塞）
            self.control_server_task = asyncio.create_task(server.serve_forever())
        except Exception as e:
            logger.error(f"启动Unix Socket控制服务器失败: {e}")
    
    async def _stop_control_socket(self) -> None:
        """停止Unix Socket控制服务器"""
        if self.control_server_task and not self.control_server_task.done():
            self.control_server_task.cancel()
            try:
                await self.control_server_task
            except asyncio.CancelledError:
                pass
        
        # 删除socket文件
        import os
        if os.path.exists(self.control_socket_path):
            os.unlink(self.control_socket_path)
        
        logger.info("Unix Socket控制服务器已停止")
    
    async def _handle_control_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """处理控制连接"""
        try:
            # 读取命令
            data = await reader.read(1024)
            if not data:
                return
            
            command = data.decode('utf-8').strip()
            logger.info(f"收到控制命令: {command}")
            
            # 执行命令
            result = await self._execute_control_command(command)
            
            # 返回结果
            response = json.dumps(result, ensure_ascii=False) + '\n'
            writer.write(response.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            logger.error(f"处理控制连接时出错: {e}")
            error_result = {"success": False, "error": str(e)}
            response = json.dumps(error_result, ensure_ascii=False) + '\n'
            writer.write(response.encode('utf-8'))
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _execute_control_command(self, command: str) -> Dict[str, Any]:
        """执行控制命令
        
        Args:
            command: 控制命令 (格式: action channel_name)
            
        Returns:
            执行结果
        """
        try:
            parts = command.split()
            if len(parts) < 1:
                return {"success": False, "error": "命令格式错误"}
            
            action = parts[0]
            channel_name = parts[1] if len(parts) > 1 else None
            
            if action == "start":
                if not channel_name:
                    return {"success": False, "error": "请指定渠道名"}
                result = await self.start_channel(channel_name)
                return {"success": True, "action": "start", "channel": channel_name, "result": result}
            
            elif action == "stop":
                if not channel_name:
                    return {"success": False, "error": "请指定渠道名"}
                result = await self.stop_channel(channel_name)
                return {"success": True, "action": "stop", "channel": channel_name, "result": result}
            
            elif action == "restart":
                if not channel_name:
                    return {"success": False, "error": "请指定渠道名"}
                result = await self.restart_channel(channel_name)
                return {"success": True, "action": "restart", "channel": channel_name, "result": result}
            
            elif action == "status":
                if channel_name:
                    result = self.get_channel_status(channel_name)
                    return {"success": True, "action": "status", "channel": channel_name, "result": result}
                else:
                    result = self.get_all_channels_status()
                    return {"success": True, "action": "status_all", "result": result}
            
            elif action == "list":
                channels = self.list_channels()
                channel_info = {name: self.get_channel_info(name) for name in channels}
                return {"success": True, "action": "list", "result": channel_info}
            
            else:
                return {"success": False, "error": f"未知命令: {action}"}
            
        except Exception as e:
            logger.error(f"执行控制命令时出错: {e}")
            return {"success": False, "error": str(e)}



async def main():
    """主函数"""
    # 支持命令行参数指定配置文件
    config_path = "config.json"
    active_channel = None
    
    if len(sys.argv) > 1:
        # 解析命令行参数
        i = 1
        while i < len(sys.argv):
            if sys.argv[i] == "--channel" or sys.argv[i] == "-c":
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
    
    bot = LingIflowBot(config_path, active_channel)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
