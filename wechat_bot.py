#!/usr/bin/env python3
"""iFlow 企业微信机器人 - 统一入口脚本。

同时启动企业微信渠道和 iflow CLI 控制，实现消息双向流转。
"""

import asyncio
import signal
import sys
import os
from pathlib import Path
from typing import Optional
from loguru import logger

from config.loader import load_config as load_project_config
from config.schema import WechatWorkConfig
from channels.wechat_work import WechatWorkChannel
from interactive.bot_integration import BotIntegration
from interactive.message_dispatcher import MessageDispatcher


# 颜色定义
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[36m"


class WechatBot:
    """企业微信机器人主类。"""
    
    def __init__(self, config_path: str = "config.json", bot_name: Optional[str] = None, test_mode: bool = False):
        """初始化机器人。
        
        Args:
            config_path: 配置文件路径
            bot_name: 机器人名称（从 bots.json 加载）
            test_mode: 测试模式（不启动 HTTP 服务器，提供测试接口）
        """
        # 加载配置
        self.config = load_project_config(Path(config_path))
        self.bot_name = bot_name
        self.test_mode = test_mode
        
        # 如果指定了机器人名称，从 bots.json 加载配置
        if bot_name:
            self.config = self._load_bot_config(bot_name)
        
        # 初始化组件
        self.wechat_channel = None
        self.bot_integration = None
        self.running = False
        self.dispatcher = None
        
        # 测试模式专用变量
        self.test_callback = None
        self.test_listener_id = "test_listener"
        
        mode_str = "测试模式" if test_mode else "生产模式"
        logger.info(f"[WechatBot] 初始化完成 (bot_name={bot_name}, mode={mode_str})")
    
    def _load_bot_config(self, bot_name: str):
        """从 bots.json 加载机器人配置。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            合并后的配置对象
        """
        from config.bots_loader import load_bots_config
        from config.schema import WechatWorkConfig
        
        # 加载机器人配置
        bots_config = load_bots_config()
        bot_config = bots_config.get_bot_by_name(bot_name)
        
        if not bot_config:
            raise ValueError(f"机器人配置不存在: {bot_name}")
        
        if not bot_config.enabled:
            raise ValueError(f"机器人未启用: {bot_name}")
        
        logger.info(f"[WechatBot] 已加载机器人配置: {bot_name}")
        
        # 创建企业微信配置对象
        wechat_config = WechatWorkConfig(
            enabled=bot_config.enabled,
            corp_id=bot_config.corp_id,
            agent_id=bot_config.agent_id,
            secret=bot_config.secret,
            user_id=bot_config.user_id,
            token=bot_config.token,
            encoding_aes_key=bot_config.encoding_aes_key,
            callback_port=bot_config.callback_port,
            callback_host=bot_config.callback_host,
            stream_mode=bot_config.stream_mode,
            poll_interval=bot_config.poll_interval,
            allow_from=bot_config.allow_from,
            group_policy=bot_config.group_policy,
            group_allow_from=bot_config.group_allow_from
        )
        
        # 更新主配置
        self.config.wechat_work = wechat_config
        self.config.tmux_session = bot_config.tmux_session
        
        # 更新工作目录（如果机器人配置中指定了）
        # 注意：机器人配置中通常不包含工作目录，使用主配置的工作目录
        
        return self.config
    
    async def start(self) -> None:
        """启动机器人。"""
        if self.test_mode:
            await self._start_test_mode()
        else:
            await self._start_production_mode()
    
    async def _start_test_mode(self) -> None:
        """启动测试模式（启动 HTTP 服务器 + 提供测试接口）。
        
        测试模式现在同时支持：
        - HTTP 服务器（企业微信回调）
        - 测试接口（send_message, listen 等）
        """
        logger.info("[WechatBot] 启动测试模式")
        print(f"{COLOR_BLUE}[测试模式] 正在初始化组件...{COLOR_RESET}")
        
        self.running = True
        
        # 检查企业微信配置
        if not self.config.wechat_work or not self.config.wechat_work.enabled:
            logger.error("[WechatBot] 企业微信未启用，请在配置中设置 wechat_work.enabled=true")
            print(f"{COLOR_YELLOW}[错误] 企业微信未启用，请在配置中设置 wechat_work.enabled=true{COLOR_RESET}")
            return
        
        wechat_config: WechatWorkConfig = self.config.wechat_work
        
        # 创建企业微信渠道（启动）
        logger.info("[WechatBot] 正在初始化企业微信渠道...")
        self.wechat_channel = WechatWorkChannel(wechat_config)
        
        # 创建机器人集成
        logger.info("[WechatBot] 正在初始化机器人集成...")
        print(f"{COLOR_BLUE}[测试模式] 正在初始化机器人集成...{COLOR_RESET}")
        
        self.bot_integration = BotIntegration(
            wechat_channel=self.wechat_channel,
            tmux_session=self.config.tmux_session,
            workspace=self.config.workspace,
            filter_thinking=self.config.filter_thinking
        )
        
        # 设置消息处理器
        logger.info("[WechatBot] 设置消息处理器...")
        self.wechat_channel.set_message_handler(self.bot_integration.handle_message)
        
        # 启动企业微信渠道
        logger.info("[WechatBot] 启动企业微信渠道...")
        await self.wechat_channel.start()
        
        # 启动后台监控（检测 iflow 交互界面的消息）
        logger.info("[WechatBot] 正在启动后台监控...")
        print(f"{COLOR_BLUE}[测试模式] 正在启动后台监控...{COLOR_RESET}")
        
        asyncio.create_task(self.bot_integration.start_background_monitor())
        
        # 注册到消息分发器
        logger.info("[WechatBot] 正在注册到消息分发器...")
        print(f"{COLOR_BLUE}[测试模式] 正在注册到消息分发器...{COLOR_RESET}")
        
        self.dispatcher = MessageDispatcher()
        
        # 定义测试模式回调（打印到控制台 + 发送到企业微信）
        async def test_callback(message: str, metadata: dict) -> None:
            """测试模式回调：打印消息到控制台 + 发送到企业微信"""
            try:
                # 检查消息来源（多 iflow 场景下过滤消息）
                source = metadata.get("source", "")
                tmux_session = metadata.get("tmux_session", "")
                workspace = metadata.get("workspace", "")
                
                # 只处理来自当前 iflow 的消息
                if source == "iflow_interactive":
                    if tmux_session != self.config.tmux_session:
                        logger.warning(
                            f"[WechatBot] 忽略来自其他 iflow 的消息: "
                            f"来源 tmux={tmux_session}, 当前 tmux={self.config.tmux_session}"
                        )
                        return
                    logger.info(
                        f"[WechatBot] 收到来自 iflow 的消息: "
                        f"tmux={tmux_session}, workspace={workspace}"
                    )
                
                # 打印消息到控制台
                print(f"{COLOR_GREEN}[iflow 回复]{COLOR_RESET}")
                print(f"{message}")
                print()
                logger.info(f"[WechatBot] 测试模式收到消息: {message[:50]}")
                
                # 发送到企业微信
                if wechat_config.user_id:
                    await self.wechat_channel.send(message, wechat_config.user_id, is_group=False)
                    logger.info(f"[WechatBot] 已发送消息到企业微信: {message[:50]}")
            except Exception as e:
                logger.error(f"[WechatBot] 测试模式回调失败: {e}")
        
        # 注册回调
        self.test_callback = test_callback
        self.dispatcher.subscribe(self.test_listener_id, test_callback)
        logger.info("[WechatBot] 已注册到消息分发器（测试模式）")
        print(f"{COLOR_GREEN}[测试模式] 已注册到消息分发器{COLOR_RESET}")
        
        # 显示启动信息
        self._print_test_startup_info()
        
        logger.info("[WechatBot] 测试模式启动完成")
        print(f"{COLOR_GREEN}[测试模式] 测试模式已启动！{COLOR_RESET}")
        print(f"{COLOR_BLUE}[功能特性]{COLOR_RESET}")
        print(f"  ✓ HTTP 服务器：已启动（支持企业微信回调）")
        print(f"  ✓ 测试接口：send_message(), listen() 等")
        print(f"{COLOR_BLUE}[提示] 使用 send_message() 发送消息{COLOR_RESET}")
        print(f"{COLOR_BLUE}[提示] 使用 listen() 监听回复{COLOR_RESET}")
        print()
        
        # 启动 HTTP 服务器（企业微信回调）
        logger.info("[WechatBot] 正在启动 HTTP 服务器...")
        print(f"{COLOR_BLUE}[测试模式] 正在启动 HTTP 服务器...{COLOR_RESET}")
        
        try:
            # 启动 HTTP 服务器
            await self.wechat_channel.start()
            
            logger.info("[WechatBot] HTTP 服务器已启动")
            print(f"{COLOR_GREEN}[成功] HTTP 服务器已启动{COLOR_RESET}")
            print(f"{COLOR_BLUE}[回调 URL]{COLOR_RESET}")
            callback_url = f"http://{wechat_config.callback_host}:{wechat_config.callback_port}/wechat/callback"
            print(f"  {callback_url}")
            print()
            
        except Exception as e:
            logger.error(f"[WechatBot] 启动 HTTP 服务器失败: {e}")
            print(f"{COLOR_YELLOW}[错误] 启动 HTTP 服务器失败: {e}{COLOR_RESET}")
            # HTTP 服务器启动失败，但继续运行测试模式
            print(f"{COLOR_YELLOW}[警告] HTTP 服务器启动失败，仅提供测试接口{COLOR_RESET}")
        
        # 发送启动通知
        await self._send_startup_notification(wechat_config)
    
    async def _start_production_mode(self) -> None:
        """启动生产模式（完整功能，包括 HTTP 服务器）。"""
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
            workspace=self.config.workspace,
            filter_thinking=self.config.filter_thinking
        )
        
        # 设置消息处理器
        self.wechat_channel.set_message_handler(self.bot_integration.handle_message)
        
        # 启动企业微信渠道
        logger.info("[WechatBot] 正在启动企业微信渠道...")
        print(f"{COLOR_BLUE}[启动] 正在启动企业微信渠道...{COLOR_RESET}")
        
        await self.wechat_channel.start()
        
        # 启动后台监控（检测 iflow 交互界面的消息）
        logger.info("[WechatBot] 正在启动后台监控...")
        print(f"{COLOR_BLUE}[启动] 正在启动后台监控...{COLOR_RESET}")
        
        asyncio.create_task(self.bot_integration.start_background_monitor())
        
        # 注册到消息分发器
        logger.info("[WechatBot] 正在注册到消息分发器...")
        print(f"{COLOR_BLUE}[启动] 正在注册到消息分发器...{COLOR_RESET}")
        
        self.dispatcher = MessageDispatcher()
        
        # 定义回调函数
        async def wechat_callback(message: str, metadata: dict) -> None:
            """分发器回调：发送消息到企业微信"""
            try:
                # 检查消息来源（多 iflow 场景下过滤消息）
                source = metadata.get("source", "")
                tmux_session = metadata.get("tmux_session", "")
                workspace = metadata.get("workspace", "")
                
                # 只处理来自当前 iflow 的消息
                if source == "iflow_interactive":
                    if tmux_session != self.config.tmux_session:
                        logger.warning(
                            f"[WechatBot] 忽略来自其他 iflow 的消息: "
                            f"来源 tmux={tmux_session}, 当前 tmux={self.config.tmux_session}"
                        )
                        return
                    logger.info(
                        f"[WechatBot] 收到来自 iflow 的消息: "
                        f"tmux={tmux_session}, workspace={workspace}"
                    )
                
                user_id = wechat_config.user_id
                is_group = metadata.get("is_group", False)
                
                await self.wechat_channel.send(message, user_id, is_group=is_group)
                logger.info(f"[WechatBot] 通过分发器发送消息到企业微信: {message[:50]}")
            except Exception as e:
                logger.error(f"[WechatBot] 分发器回调失败: {e}")
        
        # 注册回调
        self.dispatcher.subscribe("wechat_bot", wechat_callback)
        logger.info("[WechatBot] 已注册到消息分发器")
        print(f"{COLOR_GREEN}[启动] 已注册到消息分发器{COLOR_RESET}")
        
        # 显示启动信息
        self._print_startup_info(wechat_config)
        
        # 发送启动通知
        await self._send_startup_notification(wechat_config)
        
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
    
    async def _send_startup_notification(self, wechat_config: WechatWorkConfig) -> None:
        """发送启动通知。"""
        from datetime import datetime
        
        try:
            if self.wechat_channel and wechat_config.user_id:
                startup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 检查 tmux 会话状态
                session_info = self.bot_integration.iflow_controller.get_session_info()
                tmux_connected = session_info.get('tmux_exists', False) if session_info else False
                
                if tmux_connected:
                    # tmux 连接正常
                    notification = f"""**🤖 iFlow 企业微信机器人已启动**

📅 启动时间: {startup_time}
📁 工作目录: {self.config.workspace}
💻 tmux 会话: {self.config.tmux_session} ✓
🌐 回调端口: {wechat_config.callback_port}

✅ 服务运行正常，可以开始使用！

---
📋 快速开始：
• 直接发送消息：执行 iFlow 命令
• `/lscmd`：查看所有可用命令

💡 提示：输入 `/lscmd` 查看完整的命令列表和功能说明。
"""
                else:
                    # tmux 未连接
                    notification = f"""**🤖 iFlow 企业微信机器人已启动**

📅 启动时间: {startup_time}
💻 tmux 会话: 无连接
📁 工作目录: 无
🌐 回调端口: {wechat_config.callback_port}

⚠️ iflow 未运行，无法处理消息

---
📋 快速开始：
• `/start-iflow`：启动 iflow CLI（推荐）
• `/lscmd`：查看所有可用命令

💡 提示：输入 `/lscmd` 查看完整的命令列表和功能说明。
"""
                
                await self.wechat_channel.send(notification, wechat_config.user_id, is_group=False)
                logger.info("[WechatBot] 启动通知已发送")
        except Exception as e:
            logger.error(f"[WechatBot] 发送启动通知失败: {e}")
    
    async def stop(self) -> None:
        """停止机器人。"""
        if self.test_mode:
            # 测试模式：不发送关闭通知，不停止 HTTP 服务器
            # 取消分发器注册
            if self.dispatcher and self.test_listener_id in self.dispatcher.get_subscribers():
                logger.info("[WechatBot] 正在取消测试模式消息分发器注册...")
                self.dispatcher.unsubscribe(self.test_listener_id)
                logger.info("[WechatBot] 已取消测试模式消息分发器注册")
            
            self.running = False
            
            logger.info("[WechatBot] 测试模式已停止")
            print(f"{COLOR_YELLOW}[测试模式] 测试模式已停止{COLOR_RESET}")
        else:
            # 生产模式：完整停止流程
            # 发送关闭通知
            await self._send_shutdown_notification()
            
            # 取消分发器注册
            if self.dispatcher:
                logger.info("[WechatBot] 正在取消消息分发器注册...")
                self.dispatcher.unsubscribe("wechat_bot")
                logger.info("[WechatBot] 已取消消息分发器注册")
            
            self.running = False
            
            if self.wechat_channel:
                await self.wechat_channel.stop()
            
            logger.info("[WechatBot] 已停止")
            print(f"{COLOR_YELLOW}[停止] iFlow 企业微信机器人已停止{COLOR_RESET}")
    
    async def _send_shutdown_notification(self) -> None:
        """发送关闭通知。"""
        from datetime import datetime
        
        try:
            if self.wechat_channel and self.config.wechat_work and self.config.wechat_work.user_id:
                shutdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 检查关闭前的状态
                session_info = self.bot_integration.iflow_controller.get_session_info()
                tmux_was_connected = session_info.get('tmux_exists', False) if session_info else False
                
                if tmux_was_connected:
                    # tmux 之前是连接的
                    notification = f"""**🛑 iFlow 企业微信机器人已停止**

📅 关闭时间: {shutdown_time}
📁 工作目录: {self.config.workspace}
💻 tmux 会话: {self.config.tmux_session}

---
如需重新启动，请执行:
```bash
python manage.py start
```
"""
                else:
                    # tmux 之前就是未连接的
                    notification = f"""**🛑 iFlow 企业微信机器人已停止**

📅 关闭时间: {shutdown_time}
💻 tmux 会话: 无连接
📁 工作目录: 无

---
如需重新启动，请执行:
```bash
python manage.py start
```
"""
                
                await self.wechat_channel.send(notification, self.config.wechat_work.user_id, is_group=False)
                logger.info("[WechatBot] 关闭通知已发送")
        except Exception as e:
            logger.error(f"[WechatBot] 发送关闭通知失败: {e}")
    
    async def _handle_shutdown(self) -> None:
        """处理关闭信号。"""
        logger.info("[WechatBot] 收到关闭信号，正在停止...")
        print(f"{COLOR_YELLOW}[停止] 收到关闭信号，正在停止...{COLOR_RESET}")
        await self.stop()
    
    def _print_test_startup_info(self) -> None:
        """打印测试模式启动信息。"""
        print()
        print("=" * 70)
        print(f"{COLOR_GREEN}iFlow 企业微信机器人 - 测试模式 🧪{COLOR_RESET}")
        print("=" * 70)
        print()
        print(f"{COLOR_BLUE}[配置信息]{COLOR_RESET}")
        print(f"  机器人名称: {self.bot_name}")
        print(f"  tmux 会话: {self.config.tmux_session}")
        print(f"  工作目录: {self.config.workspace}")
        print()
        print(f"{COLOR_BLUE}[测试模式特性]{COLOR_RESET}")
        print(f"  启动 HTTP 服务器（支持企业微信回调）")
        print(f"  接收企业微信消息")
        print(f"  发送消息到企业微信")
        print(f"  提供测试接口（send_message, listen 等）")
        print(f"  工具和企业微信都能接收 iflow 回复")
        print()
        print(f"{COLOR_BLUE}[可用接口]{COLOR_RESET}")
        print(f"  await bot.send_message('消息')")
        print(f"  await bot.listen()")
        print(f"  await bot.listen(callback)")
        print(f"  await bot.stop_test_mode()")
        print()
        print("=" * 70)
        print()
    
    async def send_message(self, content: str, sender_id: str = None) -> None:
        """发送消息（测试模式接口）。
        
        Args:
            content: 消息内容
            sender_id: 发送者 ID（默认使用配置的 user_id）
        
        Raises:
            RuntimeError: 如果不在测试模式下
        """
        if not self.test_mode:
            raise RuntimeError("此方法只能在测试模式下使用")
        
        sender_id = sender_id or self.config.wechat_work.user_id
        chat_id = sender_id
        
        logger.info(f"[WechatBot] 测试模式发送消息: {content[:50]}...")
        
        await self.bot_integration.handle_message(
            content=content,
            sender_id=sender_id,
            chat_id=chat_id,
            is_group=False,
            metadata={},
            source="wechat"
        )
    
    async def listen(self, callback=None) -> None:
        """监听 iflow 回复（测试模式接口）。
        
        Args:
            callback: 自定义回调函数（可选），格式：async def callback(message: str, metadata: dict)
        
        Raises:
            RuntimeError: 如果不在测试模式下
        """
        if not self.test_mode:
            raise RuntimeError("此方法只能在测试模式下使用")
        
        # 如果提供了自定义回调，替换默认回调
        if callback:
            async def wrapper(message: str, metadata: dict):
                try:
                    await callback(message, metadata)
                except Exception as e:
                    logger.error(f"[WechatBot] 自定义回调失败: {e}")
            
            # 取消旧的回调
            if self.test_listener_id in self.dispatcher.get_subscribers():
                self.dispatcher.unsubscribe(self.test_listener_id)
            
            # 注册新的回调
            self.dispatcher.subscribe(self.test_listener_id, wrapper)
            logger.info("[WechatBot] 测试模式已使用自定义回调")
        
        # 保持运行
        logger.info("[WechatBot] 测试模式正在监听回复...")
        print(f"{COLOR_BLUE}[测试模式] 正在监听 iflow 回复...{COLOR_RESET}")
        print(f"{COLOR_BLUE}[提示] 按 Ctrl+C 停止{COLOR_RESET}")
        print()
        
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("[WechatBot] 测试模式监听已停止")
            print()
            print(f"{COLOR_YELLOW}[测试模式] 监听已停止{COLOR_RESET}")
    
    async def stop_test_mode(self) -> None:
        """停止测试模式。
        
        Raises:
            RuntimeError: 如果不在测试模式下
        """
        if not self.test_mode:
            raise RuntimeError("此方法只能在测试模式下使用")
        
        # 取消分发器注册
        if self.dispatcher and self.test_listener_id in self.dispatcher.get_subscribers():
            logger.info("[WechatBot] 正在取消测试模式消息分发器注册...")
            self.dispatcher.unsubscribe(self.test_listener_id)
            logger.info("[WechatBot] 已取消测试模式消息分发器注册")
        
        self.running = False
        
        logger.info("[WechatBot] 测试模式已停止")
        print(f"{COLOR_YELLOW}[测试模式] 测试模式已停止{COLOR_RESET}")


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
        "--bot", "-b",
        help="机器人名称（从 bots.json 加载）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细日志模式"
    )
    parser.add_argument(
        "--test-mode", "-t",
        action="store_true",
        help="测试模式（不启动 HTTP 服务器，提供测试接口）"
    )
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    
    # 配置 logging 模块，将其输出到 loguru（WechatWorkChannel 使用 logging）
    import logging
    from loguru import logger as loguru_logger
    
    class InterceptHandler(logging.Handler):
        """将 logging 的日志输出到 loguru 的 handler"""
        def emit(self, record):
            # 获取对应的 loguru level
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            
            # 查找调用者
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            
            loguru_logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )
    
    # 配置 logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    
    # 添加文件日志
    from pathlib import Path
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # 日志文件名包含机器人名称（如果指定）
    log_suffix = f"_{args.bot}" if args.bot else ""
    logger.add(
        log_dir / f"wechat_bot{log_suffix}_{{time:YYYY-MM-DD}}.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="00:00",
        retention="7 days",
        encoding="utf-8"
    )
    
    # 创建 PID 文件（如果指定了机器人名称）
    pid_file = None
    if args.bot:
        pids_dir = Path(__file__).parent / ".pids"
        pids_dir.mkdir(exist_ok=True)
        pid_file = pids_dir / f"bot_{args.bot}.pid"
        
        # 写入 PID
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
        
        logger.info(f"[WechatBot] 已创建 PID 文件: {pid_file}")
    
    # 创建机器人实例
    bot = WechatBot(
        config_path=args.config,
        bot_name=args.bot,
        test_mode=args.test_mode
    )
    
    # 设置信号处理
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        asyncio.create_task(bot._handle_shutdown())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    # 启动机器人
    try:
        await bot.start()
        
        # 测试模式下，保持运行
        if bot.test_mode:
            logger.info("[WechatBot] 测试模式运行中，等待消息...")
            while bot.running:
                await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("[WechatBot] 用户中断")
        print(f"\n{COLOR_YELLOW}[中断] 收到用户中断，正在停止...{COLOR_RESET}")
        await bot.stop()
    except Exception as e:
        logger.error(f"[WechatBot] 启动失败: {e}", exc_info=True)
        print(f"{COLOR_YELLOW}[错误] 启动失败: {e}{COLOR_RESET}")
        sys.exit(1)
    finally:
        # 只有在程序真正退出时才删除 PID 文件
        if pid_file and pid_file.exists() and not bot.running:
            pid_file.unlink()
            logger.info(f"[WechatBot] 已删除 PID 文件: {pid_file}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}[中断] 程序已退出{COLOR_RESET}")
        sys.exit(0)
