"""
Feishu Channel

飞书消息通道，使用 lark-oapi SDK 和 WebSocket 长连接。
无需公网 IP 或 webhook 配置。
"""

import asyncio
import contextlib
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ...core.base import BaseModule
from ...core.message import Message, MessageType, MessageContent
from ...core.logger_adapter import log_feishu_message, log_system_event

logger = logging.getLogger(__name__)
from ...core.message import Message, MessageType, MessageContent
from ...core.logger_adapter import log_feishu_message, log_system_event

try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import (
        CreateFileRequest,
        CreateFileRequestBody,
        CreateImageRequest,
        CreateImageRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
        CreateMessageReactionRequest,
        CreateMessageReactionRequestBody,
        DeleteMessageReactionRequest,
        Emoji,
        GetMessageResourceRequest,
        PatchMessageRequest,
        PatchMessageRequestBody,
        P2ImMessageReceiveV1,
        P2ImMessageReactionCreatedV1,
        P2ImMessageReactionDeletedV1,
        P2ImMessageMessageReadV1,
        P2ImChatAccessEventBotP2pChatEnteredV1,
    )
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None
    Emoji = None
    # 定义类型别名，避免类型注解错误
    P2ImMessageReceiveV1 = Any
    P2ImMessageReactionCreatedV1 = Any
    P2ImMessageReactionDeletedV1 = Any
    P2ImMessageMessageReadV1 = Any
    P2ImChatAccessEventBotP2pChatEnteredV1 = Any


from ...core.logger_adapter import log_feishu_message, log_system_event, MessageType

# 消息类型显示映射
MSG_TYPE_MAP = {
    "image": "[图片]",
    "audio": "[音频]",
    "file": "[文件]",
    "sticker": "[表情]",
}


class FeishuChannel(BaseModule):
    """飞书消息通道
    
    使用 WebSocket 长连接接收消息，无需公网 IP。
    支持文本、图片、文件、流式输出等功能。
    """

    def __init__(self, module_id: str, config: Dict[str, Any]):
        """初始化飞书通道
        
        Args:
            module_id: 模块唯一标识符
            config: 飞书配置
        """
        super().__init__(module_id)
        
        self.config = config
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self.verification_token = config.get("verification_token", "")
        self.encrypt_key = config.get("encrypt_key", "")
        self.allow_from = config.get("allow_from", [])
        # 用于发送启动/停止通知的用户ID（飞书 open_id）
        self.notify_user_id = config.get("notify_user_id", "")
        
        # SDK 客户端
        self._client: Optional[Any] = None
        self._ws_client: Optional[Any] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # 消息去重缓存
        self._processed_message_ids: OrderedDict[str, float] = OrderedDict()
        self._max_cache_size = 1000
        
        # 流式消息缓存
        self._streaming_message_ids: Dict[str, str] = {}
        self._streaming_last_content: Dict[str, str] = {}
        self._typing_reaction_ids: Dict[str, str] = {}
        
        # 命令处理器
        from ..command import CommandHandler
        self.command_handler = CommandHandler()
        
        # 通用组件
        from ..common.converter import MessageConverter
        from ..common.notifications import NotificationManager
        self.converter = MessageConverter()
        self.notification_manager = NotificationManager()
        
        # 注册通知处理器
        self.notification_manager.register_notification_handler(
            "startup", self._handle_startup_notification
        )
        self.notification_manager.register_notification_handler(
            "shutdown", self._handle_shutdown_notification
        )
        

        # 模块管理器引用
        self.manager: Optional[Any] = None
        
        # 缓存最近联系人 ID（用于发送通知）
        self._last_sender_id: Optional[str] = None
        self._last_chat_id: Optional[str] = None

    def set_manager(self, manager) -> None:
        """设置模块管理器"""
        self.manager = manager
        self.command_handler.set_manager(manager)

    def set_bot(self, bot) -> None:
        """设置 bot 实例"""
        self._bot = bot
        self.command_handler.set_bot(bot)

    def set_message_bus(self, bus) -> None:
        """设置消息总线"""
        # 调用父类方法设置 message_bus
        super().set_message_bus(bus)
        # 同时传递给 CommandHandler
        self.command_handler.set_message_bus(bus)

    async def _on_start(self) -> None:
        """启动时的钩子方法"""
        logger.info(f"[{self.module_id}] 启动飞书通道")
        
        # 必须先设置 _running=True，否则 WebSocket 线程会立即退出
        self._running = True
        
        # 设置主事件循环（用于 WebSocket 回调）
        self._loop = asyncio.get_running_loop()
        
        if not FEISHU_AVAILABLE:
            logger.error(f"[{self.module_id}] lark-oapi 未安装，请运行：pip install lark-oapi")
            raise RuntimeError("lark-oapi 未安装")
        
        if not self.app_id or not self.app_secret:
            logger.error(f"[{self.module_id}] 未配置 app_id 或 app_secret")
            raise RuntimeError("飞书应用配置缺失")
        
        # 降噪：屏蔽 Lark SDK 错误日志
        for logger_name in ("lark_oapi", "lark_oapi.ws", "lark_oapi.ws.client"):
            logging.getLogger(logger_name).setLevel(logging.CRITICAL)
        
        # 创建 SDK 客户端（用于发送消息）
        self._client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.ERROR) \
            .build()
        
        # 创建事件处理器
        event_handler = lark.EventDispatcherHandler.builder(
            self.encrypt_key or "",
            self.verification_token or "",
        ).register_p2_im_message_receive_v1(
            self._on_message_sync
        ).register_p2_im_message_reaction_created_v1(
            self._on_reaction_created_sync
        ).register_p2_im_message_reaction_deleted_v1(
            self._on_reaction_deleted_sync
        ).register_p2_im_message_message_read_v1(
            self._on_message_read_sync
        ).register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(
            self._on_bot_p2p_chat_entered_sync
        ).build()
        
        # 创建 WebSocket 客户端
        self._ws_client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.ERROR
        )
        
        # 启动 WebSocket 线程
        self._start_websocket_thread()
        
        # 等待连接建立
        await asyncio.sleep(2)
        
        logger.info(f"[{self.module_id}] 飞书通道启动完成（WebSocket 长连接）")
        
        # 发送启动通知
        await self._send_startup_notification()
        
        # 注意：不要在这里使用 while 循环阻塞
        # WebSocket 线程已独立运行，_on_start 应该返回让启动流程继续

    def _start_websocket_thread(self) -> None:
        """启动 WebSocket 线程"""
        def run_ws():
            """WebSocket 运行函数"""
            import time
            while self._running:
                new_loop = None
                try:
                    # 关键修复：lark_oapi/ws/client.py 在模块级别调用 asyncio.get_event_loop()
                    # 并保存在模块变量中。我们需要替换这个变量为新线程的事件循环
                    import lark_oapi.ws.client as ws_client_module
                    
                    # 创建新的事件循环并替换模块变量
                    new_loop = asyncio.new_event_loop()
                    self._ws_loop = new_loop
                    asyncio.set_event_loop(new_loop)
                    ws_client_module.loop = new_loop
                    
                    # 现在可以安全地调用 start()
                    self._ws_client.start()
                    
                except RuntimeError as e:
                    if not self._running and "Event loop stopped before Future completed" in str(e):
                        logger.debug(f"[{self.module_id}] WebSocket 循环停止")
                    else:
                        logger.warning(f"[{self.module_id}] WebSocket 错误：{e}")
                except Exception as e:
                    logger.warning(f"[{self.module_id}] WebSocket 异常：{e}")
                finally:
                    # 清理事件循环
                    if self._ws_loop:
                        try:
                            pending = [t for t in asyncio.all_tasks(self._ws_loop) if not t.done()]
                            for task in pending:
                                task.cancel()
                            if pending:
                                with contextlib.suppress(Exception):
                                    self._ws_loop.run_until_complete(
                                        asyncio.gather(*pending, return_exceptions=True)
                                    )
                            with contextlib.suppress(Exception):
                                self._ws_loop.run_until_complete(self._ws_loop.shutdown_asyncgens())
                            with contextlib.suppress(Exception):
                                self._ws_loop.close()
                        except Exception:
                            pass
                        self._ws_loop = None
                
                # 如果仍在运行，等待 5 秒后重试
                if self._running:
                    time.sleep(5)
        
        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()
        logger.info(f"[{self.module_id}] WebSocket 线程已启动")
        logger.info(f"[{self.module_id}] WebSocket 配置：app_id={self.app_id[:10]}...")
        logger.info(f"[{self.module_id}] 等待飞书事件推送...")

    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        logger.info(f"[{self.module_id}] 停止飞书通道")
        
        self._running = False
        
        # 停止 WebSocket 客户端
        if self._ws_client:
            self._stop_websocket_client()
        
        # 关闭 SDK 客户端
        if self._client:
            with contextlib.suppress(Exception):
                self._client.close()
        
        # 发送停止通知
        await self._send_shutdown_notification()
        
        logger.info(f"[{self.module_id}] 飞书通道已停止")

    def _stop_websocket_client(self) -> None:
        """停止 WebSocket 客户端"""
        if self._ws_loop and self._ws_client:
            def _shutdown_ws():
                async def _close():
                    with contextlib.suppress(Exception):
                        await self._ws_client._disconnect()
                    current = asyncio.current_task()
                    for task in asyncio.all_tasks():
                        if task is not current:
                            task.cancel()
                    asyncio.get_running_loop().stop()
                
                asyncio.create_task(_close())
            
            with contextlib.suppress(Exception):
                self._ws_loop.call_soon_threadsafe(_shutdown_ws)
        
        if self._ws_thread and self._ws_thread.is_alive():
            with contextlib.suppress(Exception):
                self._ws_thread.join(5)
        
        self._ws_thread = None

    def _on_message_sync(self, event: P2ImMessageReceiveV1) -> None:
        """同步处理消息接收事件"""
        try:
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._handle_message_event(event),
                    self._loop
                )
            else:
                logger.warning(f"[{self.module_id}] 事件循环未运行: loop={self._loop}")
        except Exception as e:
            logger.error(f"[{self.module_id}] _on_message_sync 异常: {e}", exc_info=True)

    def _on_reaction_created_sync(self, event: P2ImMessageReactionCreatedV1) -> None:
        """处理表情回应创建事件"""
        pass  # 暂不处理

    def _on_reaction_deleted_sync(self, event: P2ImMessageReactionDeletedV1) -> None:
        """处理表情回应删除事件"""
        pass  # 暂不处理

    def _on_message_read_sync(self, event: P2ImMessageMessageReadV1) -> None:
        """处理消息已读事件"""
        pass  # 暂不处理

    def _on_bot_p2p_chat_entered_sync(self, event: P2ImChatAccessEventBotP2pChatEnteredV1) -> None:
        """处理用户进入私聊事件"""
        pass  # 暂不处理

    async def _handle_message_event(self, event: P2ImMessageReceiveV1) -> None:
        """处理消息接收事件"""
        try:
            logger.info(f"[{self.module_id}] 收到飞书事件推送！")
            message = event.event.message
            sender = event.event.sender
            
            logger.info(f"[{self.module_id}] 消息 ID: {message.message_id}")
            message_id = message.message_id
            chat_id = message.chat_id
            # sender_id 是对象，需要获取 open_id
            sender_id = sender.sender_id.open_id if sender and sender.sender_id else ""
            msg_type = message.message_type
            content = message.content
            
            # 消息去重
            if await self._is_duplicate_message(message_id):
                logger.info(f"[{self.module_id}] 忽略重复消息：{message_id}")
                return
            
            # 解析消息内容
            content_parts = []
            media_paths = []
            
            try:
                content_json = json.loads(content) if content else {}
            except json.JSONDecodeError:
                content_json = {}
            
            if msg_type == "text":
                text = content_json.get("text", "")
                if text:
                    content_parts.append(text)
            
            elif msg_type == "post":
                # 解析富文本消息
                text_parts, resources = self._extract_post_parts(content_json)
                content_parts.extend(text_parts)
                # 下载媒体文件
                for resource in resources:
                    resource_type = resource.get("type")
                    if resource_type == "image":
                        file_path, content_text = await self._download_and_save_media(
                            "image", resource, message_id
                        )
                    elif resource_type in ("file", "media", "audio"):
                        file_path, content_text = await self._download_and_save_media(
                            resource_type, resource, message_id
                        )
                    else:
                        file_path, content_text = None, f"[{resource_type}]"
                    
                    if file_path:
                        media_paths.append(file_path)
                    if content_text:
                        content_parts.append(content_text)
            
            elif msg_type in ("image", "audio", "file", "media"):
                # 下载媒体文件
                file_path, content_text = await self._download_and_save_media(
                    msg_type, content_json, message_id
                )
                if file_path:
                    media_paths.append(file_path)
                content_parts.append(content_text)
            
            elif msg_type in ("share_chat", "share_user", "interactive",
                            "share_calendar_event", "system", "merge_forward"):
                text = self._extract_share_card_content(content_json, msg_type)
                if text:
                    content_parts.append(text)
            
            else:
                content_parts.append(MSG_TYPE_MAP.get(msg_type, f"[{msg_type}]"))
            
            # 合并内容
            content = "\n".join(content_parts) if content_parts else ""
            
            if not content and not media_paths:
                return
            
            # 确定回复目标并缓存联系人 ID
            chat_type = "group" if chat_id.startswith("oc_") else "private"
            reply_to = chat_id if chat_type == "group" else sender_id
            
            # 缓存最近联系人 ID（用于发送通知）
            self._last_sender_id = sender_id
            self._last_chat_id = chat_id
            
            # 检查白名单
            if not self._is_allowed(sender_id):
                logger.debug(f"[{self.module_id}] 消息来自未授权用户：{sender_id}")
                return
            
            logger.info(
                f"[{self.module_id}] 收到飞书消息：message_id={message_id} "
                f"chat_type={chat_type} msg_type={msg_type} sender={sender_id} "
                f"content_len={len(content)} media={len(media_paths)}"
            )
            
            # 解析命令
            parsed = self.command_handler.parse_command(content)
            
            # 执行命令
            if parsed.get("is_command"):
                result = await self.command_handler.execute(parsed, reply_to)
                if result:
                    await self.send_message(result, reply_to, "open_id" if reply_to == sender_id else "chat_id")
                    return  # 已知命令，不发送给 iflow
            
            # 创建标准消息
            message_obj = self.converter.create_wechat_inbound_message({
                "content": content,
                "sender_id": sender_id,
                "chat_id": reply_to,
                "msg_type": msg_type
            }, self.module_id)
            
            # 添加表情反应，表示已收到正在处理
            await self.add_reaction(message_id, "THUMBSUP")
            
            # 添加到消息总线
            if self.message_bus:
                await self.send_to_bus(message_obj)
                logger.info(f"[{self.module_id}] 飞书消息已发送到消息总线")
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理消息失败：{e}", exc_info=True)

    def _extract_post_parts(self, content_json: dict) -> Tuple[List[str], List[dict]]:
        """提取富文本消息的文本部分和资源引用"""
        def walk_element(element: Any, text_parts: list, resources: list) -> None:
            if not isinstance(element, dict):
                return
            
            tag = element.get("tag")
            if tag == "text":
                text = element.get("text", "")
                if text:
                    text_parts.append(text)
            elif tag == "a":
                text = element.get("text", "")
                href = element.get("href", "")
                if text:
                    text_parts.append(text)
                if href:
                    text_parts.append(f"链接：{href}")
            elif tag == "at":
                text_parts.append(f"@{element.get('user_name', '用户')}")
            elif tag == "img":
                image_key = element.get("image_key") or element.get("file_key")
                alt = element.get("alt", "") or "[图片]"
                text_parts.append(str(alt))
                if image_key:
                    resources.append({"type": "image", "image_key": image_key})
            elif tag in ("file", "media", "audio"):
                file_key = element.get("file_key")
                name = element.get("file_name") or element.get("name") or f"[{tag}]"
                text_parts.append(str(name))
                if file_key:
                    resources.append({"type": tag, "file_key": file_key})
            else:
                for key in ("elements", "content", "children"):
                    value = element.get(key)
                    if isinstance(value, list):
                        for item in value:
                            walk_element(item, text_parts, resources)
        
        def extract_from_lang(lang_content: dict):
            if not isinstance(lang_content, dict):
                return [], []
            title = lang_content.get("title", "")
            content_blocks = lang_content.get("content", [])
            if not isinstance(content_blocks, list):
                return [], []
            
            text_parts = []
            resources = []
            if title:
                text_parts.append(title)
            for block in content_blocks:
                if isinstance(block, list):
                    for element in block:
                        walk_element(element, text_parts, resources)
            return text_parts, resources
        
        if "content" in content_json:
            text_parts, resources = extract_from_lang(content_json)
            if text_parts or resources:
                return text_parts, resources
        
        for lang_key in ("zh_cn", "en_us", "ja_jp"):
            lang_content = content_json.get(lang_key)
            text_parts, resources = extract_from_lang(lang_content)
            if text_parts or resources:
                return text_parts, resources
        
        return [], []

    def _extract_share_card_content(self, content_json: dict, msg_type: str) -> str:
        """提取分享卡片消息的文本表示"""
        parts = []
        
        if msg_type == "share_chat":
            parts.append(f"[分享会话：{content_json.get('chat_id', '')}]")
        elif msg_type == "share_user":
            parts.append(f"[分享用户：{content_json.get('user_id', '')}]")
        elif msg_type == "interactive":
            parts.extend(self._extract_interactive_content(content_json))
        elif msg_type == "share_calendar_event":
            parts.append(f"[分享日历事件：{content_json.get('event_key', '')}]")
        elif msg_type == "system":
            parts.append("[系统消息]")
        elif msg_type == "merge_forward":
            parts.append("[合并转发的消息]")
        
        return "\n".join(parts) if parts else f"[{msg_type}]"

    def _extract_interactive_content(self, content: dict) -> list:
        """递归提取交互卡片的文本内容"""
        parts = []
        
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                return [content] if content.strip() else []
        
        if not isinstance(content, dict):
            return parts
        
        if "title" in content:
            title = content["title"]
            if isinstance(title, dict):
                title_content = title.get("content", "") or title.get("text", "")
                if title_content:
                    parts.append(f"标题：{title_content}")
            elif isinstance(title, str):
                parts.append(f"标题：{title}")
        
        elements = content.get("elements")
        if isinstance(elements, list):
            for element in elements:
                parts.extend(self._extract_element_content(element))
        
        return parts

    def _extract_element_content(self, element: dict) -> list:
        """提取卡片元素的文本内容"""
        parts = []
        
        if not isinstance(element, dict):
            return parts
        
        tag = element.get("tag")
        
        if tag in ("markdown", "lark_md"):
            content = element.get("content", "")
            if content:
                parts.append(content)
        elif tag == "div":
            text = element.get("text", {})
            if isinstance(text, dict):
                text_content = text.get("content", "") or text.get("text", "")
                if text_content:
                    parts.append(text_content)
            elif isinstance(text, str):
                parts.append(text)
        elif tag == "a":
            href = element.get("href", "")
            text = element.get("text", "")
            if href and text:
                parts.append(f"{text}: {href}")
            elif text:
                parts.append(text)
        
        return parts

    async def _download_and_save_media(
        self,
        msg_type: str,
        content_json: dict,
        message_id: Optional[str]
    ) -> Tuple[Optional[str], str]:
        """下载媒体文件并保存到本地"""
        loop = asyncio.get_running_loop()
        
        # 获取工作目录
        workspace = Path.cwd() / "images"
        workspace.mkdir(parents=True, exist_ok=True)
        
        data = None
        filename = None
        
        if msg_type == "image":
            image_key = content_json.get("image_key")
            if image_key and message_id:
                data, filename = await loop.run_in_executor(
                    None, self._download_image_sync, message_id, image_key
                )
                if not filename:
                    filename = f"{image_key[:16]}.jpg"
        
        elif msg_type in ("audio", "file", "media"):
            file_key = content_json.get("file_key")
            if file_key and message_id:
                data, filename = await loop.run_in_executor(
                    None, self._download_file_sync, message_id, file_key, msg_type
                )
                if not filename:
                    ext = {"audio": ".opus", "media": ".mp4"}.get(msg_type, "")
                    filename = f"{file_key[:16]}{ext}"
        
        if data and filename:
            file_path = workspace / filename
            file_path.write_bytes(data)
            logger.debug(f"[{self.module_id}] 已下载 {msg_type} 到 {file_path}")
            return str(file_path), f"[{msg_type}: {filename}]"
        
        return None, f"[{msg_type}: 下载失败]"

    def _download_image_sync(self, message_id: str, image_key: str) -> Tuple[Optional[bytes], Optional[str]]:
        """同步下载图片"""
        try:
            request = GetMessageResourceRequest.builder() \
                .message_id(message_id) \
                .file_key(image_key) \
                .type("image") \
                .build()
            response = self._client.im.v1.message_resource.get(request)
            if response.success():
                file_data = response.file
                if hasattr(file_data, 'read'):
                    file_data = file_data.read()
                return file_data, response.file_name
            else:
                logger.error(f"[{self.module_id}] 下载图片失败：code={response.code}, msg={response.msg}")
                return None, None
        except Exception as e:
            logger.error(f"[{self.module_id}] 下载图片异常：{e}")
            return None, None

    def _download_file_sync(
        self,
        message_id: str,
        file_key: str,
        resource_type: str = "file"
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """同步下载文件"""
        try:
            request = GetMessageResourceRequest.builder() \
                .message_id(message_id) \
                .file_key(file_key) \
                .type(resource_type) \
                .build()
            response = self._client.im.v1.message_resource.get(request)
            if response.success():
                file_data = response.file
                if hasattr(file_data, "read"):
                    file_data = file_data.read()
                return file_data, response.file_name
            else:
                logger.error(f"[{self.module_id}] 下载文件失败：code={response.code}, msg={response.msg}")
                return None, None
        except Exception as e:
            logger.error(f"[{self.module_id}] 下载文件异常：{e}")
            return None, None

    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法"""
        try:
            if not self._client:
                logger.error(f"[{self.module_id}] 客户端未初始化")
                return
            
            # 提取消息内容
            content = message.content.text if message.content else ""
            
            # 从 metadata 获取接收者 ID（支持多种字段名）
            # receiver: IFlowModule COMPLETE 消息使用
            # chat_id: 标准字段
            # receive_id: 兼容字段
            receive_id = (
                message.metadata.get("receiver") or
                message.metadata.get("chat_id") or
                message.metadata.get("receive_id") or
                message.chat_id
            )
            
            # 使用新的日志适配器记录飞书消息（完整内容）
            log_feishu_message(
                logger, 
                self.module_id,
                f"📨 飞书收到消息: msg_id={message.id[:8]}, receive_id={receive_id}, content={content}",
                level=logging.INFO
            )
            
            # 记录完整的消息元数据
            log_system_event(
                logger,
                self.module_id,
                f"📋 消息元数据: from_module={message.from_module}, chat_id={message.chat_id}, "
                f"is_group={message.metadata.get('is_group', False)}, metadata={message.metadata}",
                level=logging.DEBUG
            )
            
            logger.info(f"[{self.module_id}] [_on_receive] 收到消息: msg_id={message.id[:8]}, content={content[:80]}..., receive_id={receive_id}")
            
            if not content:
                logger.warning(f"[{self.module_id}] 消息内容为空")
                return
            
            # 如果有接收者 ID，直接发送
            if receive_id:
                receive_id_type = "chat_id" if receive_id.startswith("oc_") else "open_id"
                logger.info(f"[{self.module_id}] [_on_receive] 准备发送到飞书: receive_id={receive_id}, type={receive_id_type}")
                
                # 记录准备发送的消息
                log_feishu_message(
                    logger,
                    self.module_id,
                    f"📤 准备发送到飞书: receive_id={receive_id}, type={receive_id_type}, content={content}",
                    level=logging.INFO
                )
                
                success = await self.send_message(content, receive_id, receive_id_type)
                if success:
                    logger.info(f"[{self.module_id}] [_on_receive] ✅ 消息已发送到飞书：{receive_id}")
                    log_feishu_message(
                        logger,
                        self.module_id,
                        f"✅ 消息发送成功: receive_id={receive_id}",
                        level=logging.INFO
                    )
                else:
                    logger.error(f"[{self.module_id}] [_on_receive] ❌ 消息发送失败")
                    log_feishu_message(
                        logger,
                        self.module_id,
                        f"❌ 消息发送失败: receive_id={receive_id}",
                        level=logging.ERROR
                    )
            else:
                logger.warning(f"[{self.module_id}] [_on_receive] 未指定接收者 ID，无法发送消息")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理消息失败：{e}", exc_info=True)
            log_system_event(
                logger,
                self.module_id,
                f"❌ 处理消息失败: {str(e)}",
                level=logging.ERROR
            )

    async def send_message(
        self,
        content: str,
        receive_id: str,
        receive_id_type: str = "open_id",
        msg_type: str = "text"
    ) -> bool:
        """发送消息到飞书"""
        if not self._client:
            logger.error(f"[{self.module_id}] 客户端未初始化")
            return False
        
        try:
            loop = asyncio.get_running_loop()
            
            # 根据消息类型构建内容
            if msg_type == "text":
                # 转换为交互卡片（支持 Markdown）
                card_content = json.dumps({
                    "config": {"wide_screen_mode": True},
                    "elements": self._build_card_elements(content)
                }, ensure_ascii=False)
                
                # 同步发送
                message_id = await loop.run_in_executor(
                    None,
                    self._send_message_sync,
                    receive_id_type,
                    receive_id,
                    "interactive",
                    card_content
                )
            else:
                # 其他消息类型
                message_id = await loop.run_in_executor(
                    None,
                    self._send_message_sync,
                    receive_id_type,
                    receive_id,
                    msg_type,
                    content
                )
            
            return message_id is not None
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送消息异常：{e}", exc_info=True)
            return False

    def _send_message_sync(
        self,
        receive_id_type: str,
        receive_id: str,
        msg_type: str,
        content: str
    ) -> Optional[str]:
        """同步发送消息"""
        try:
            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                ).build()
            response = self._client.im.v1.message.create(request)
            
            if not response.success():
                logger.error(
                    f"[{self.module_id}] 发送消息失败：code={response.code}, "
                    f"msg={response.msg}, log_id={response.get_log_id()}"
                )
                return None
            
            message_id = None
            data = getattr(response, "data", None)
            if data is not None:
                message_id = getattr(data, "message_id", None)
                if message_id is None and isinstance(data, dict):
                    message_id = data.get("message_id")
            
            logger.debug(f"[{self.module_id}] 消息已发送：{receive_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送消息异常：{e}")
            return None

    def _build_card_elements(self, content: str) -> list:
        """将 Markdown 内容转换为飞书卡片元素"""
        logger.info(f"[{self.module_id}] [_build_card_elements] 接收到的内容长度: {len(content)}")
        logger.info(f"[{self.module_id}] [_build_card_elements] 接收到的内容（前500字符）: {content[:500]}")
        logger.info(f"[{self.module_id}] [_build_card_elements] 完整内容:\n{content}")
        # 简单实现：直接返回 Markdown 元素
        # 可以扩展为支持表格、标题等复杂格式
        return [{"tag": "markdown", "content": content}]

    async def add_reaction(self, message_id: str, emoji_type: str = "THUMBSUP") -> Optional[str]:
        """给消息添加表情反应
        
        Args:
            message_id: 消息 ID
            emoji_type: 表情类型，常用值：
                - THUMBSUP: 点赞 👍
                - SMILE: 笑脸 😀
                - HEART: 爱心 ❤️
                - FIRE: 火 🔥
                - OK: OK手势 👌
                - CLAP: 鼓掌 👏
            
        Returns:
            表情反应 ID，失败返回 None
        """
        if not self._client:
            logger.error(f"[{self.module_id}] 客户端未初始化")
            return None
        
        try:
            loop = asyncio.get_running_loop()
            
            def _add_reaction_sync():
                # reaction_type 需要传入 Emoji 对象
                emoji_obj = Emoji.builder().emoji_type(emoji_type).build()
                request = CreateMessageReactionRequest.builder() \
                    .message_id(message_id) \
                    .request_body(
                        CreateMessageReactionRequestBody.builder()
                        .reaction_type(emoji_obj)
                        .build()
                    ).build()
                
                response = self._client.im.v1.message_reaction.create(request)
                
                if not response.success():
                    logger.error(
                        f"[{self.module_id}] 添加表情失败：code={response.code}, "
                        f"msg={response.msg}"
                    )
                    return None
                
                data = getattr(response, "data", None)
                if data:
                    return getattr(data, "reaction_id", None)
                return None
            
            reaction_id = await loop.run_in_executor(None, _add_reaction_sync)
            
            if reaction_id:
                logger.debug(f"[{self.module_id}] 已添加表情 {emoji_type} 到消息 {message_id}")
                # 缓存表情反应 ID
                self._typing_reaction_ids[message_id] = reaction_id
            
            return reaction_id
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 添加表情异常：{e}", exc_info=True)
            return None

    async def remove_reaction(self, message_id: str, reaction_id: Optional[str] = None) -> bool:
        """删除消息的表情反应
        
        Args:
            message_id: 消息 ID
            reaction_id: 表情反应 ID（可选，如果不提供则从缓存中获取）
            
        Returns:
            是否删除成功
        """
        if not self._client:
            logger.error(f"[{self.module_id}] 客户端未初始化")
            return False
        
        # 如果没有提供 reaction_id，从缓存中获取
        if not reaction_id:
            reaction_id = self._typing_reaction_ids.pop(message_id, None)
        
        if not reaction_id:
            logger.debug(f"[{self.module_id}] 未找到表情反应 ID")
            return False
        
        try:
            loop = asyncio.get_running_loop()
            
            def _remove_reaction_sync():
                request = DeleteMessageReactionRequest.builder() \
                    .message_id(message_id) \
                    .reaction_id(reaction_id) \
                    .build()
                
                response = self._client.im.v1.message_reaction.delete(request)
                
                if not response.success():
                    logger.error(
                        f"[{self.module_id}] 删除表情失败：code={response.code}, "
                        f"msg={response.msg}"
                    )
                    return False
                
                return True
            
            result = await loop.run_in_executor(None, _remove_reaction_sync)
            
            if result:
                logger.debug(f"[{self.module_id}] 已删除表情反应 {reaction_id}")
                # 清理缓存
                self._typing_reaction_ids.pop(message_id, None)
            
            return result
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 删除表情异常：{e}", exc_info=True)
            return False

    async def _is_duplicate_message(self, message_id: str) -> bool:
        """检查是否为重复消息"""
        current_time = time.time()
        
        # 清理过期缓存（1 小时）
        self._processed_message_ids = OrderedDict(
            (k, v) for k, v in self._processed_message_ids.items()
            if current_time - v < 3600
        )
        
        if message_id in self._processed_message_ids:
            return True
        
        self._processed_message_ids[message_id] = current_time
        
        # 限制缓存大小
        if len(self._processed_message_ids) > self._max_cache_size:
            self._processed_message_ids.popitem(last=False)
        
        return False

    def _is_allowed(self, sender_id: str) -> bool:
        """检查发送者是否有权限"""
        if not self.allow_from:
            return True
        
        sender_str = str(sender_id)
        if sender_str in self.allow_from:
            return True
        
        if "|" in sender_str:
            for part in sender_str.split("|"):
                if part and part in self.allow_from:
                    return True
        
        return False

    async def _handle_startup_notification(self, data: Dict[str, Any]) -> bool:
        """处理启动通知"""
        try:
            content = data.get("content", "")
            user_id = self.config.get("user_id", "")
            
            if not content or not user_id:
                return False
            
            # 发送通知
            await self.send_message(content, user_id, "open_id")
            
            logger.info(f"[{self.module_id}] 启动通知已发送到 {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 启动通知处理失败：{e}", exc_info=True)
            return False

    async def _handle_shutdown_notification(self, data: Dict[str, Any]) -> bool:
        """处理停止通知"""
        try:
            content = data.get("content", "")
            user_id = self.config.get("user_id", "")
            
            if not content or not user_id:
                return False
            
            await self.send_message(content, user_id, "open_id")
            
            logger.info(f"[{self.module_id}] 停止通知已发送到 {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 停止通知处理失败：{e}", exc_info=True)
            return False

    async def _send_startup_notification(self) -> None:
        """发送启动通知到飞书"""
        try:
            # 获取引擎类型，决定 tmux 会话后缀和模块名称
            bot = getattr(self, '_bot', None)
            engine = getattr(bot, 'engine', 'iflow') if bot else 'iflow'
            channel_name = self.module_id.replace("feishu_", "")
            tmux_session = f"{channel_name}+{engine}"
            
            # 从 bot 获取工作目录（用户启动命令时的目录）
            workspace = bot
            if workspace and hasattr(workspace, 'workspace'):
                workspace = workspace.workspace
            else:
                workspace = os.environ.get("LING_IFLOW_WORKSPACE", str(Path.cwd()))
            
            # 根据引擎类型决定模块名称
            module_name = "Claude 飞书助手" if engine == "claude" else "iFlow 飞书助手"
            
            # 构建通知内容
            service_info = f"""📁 工作目录：{workspace}
💻 tmux 会话：{tmux_session} ✓"""
            
            quick_start = """• 直接发送消息：和 AI 对话
• `/lscmd`：查看所有可用命令"""
            
            tips = "输入 `/lscmd` 查看完整的命令列表和功能说明。"
            
            # 使用通知管理器发送
            await self.notification_manager.send_startup_notification(
                module_name=module_name,
                service_info=service_info,
                quick_start=quick_start,
                tips=tips
            )
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送启动通知失败：{e}", exc_info=True)

    async def _send_shutdown_notification(self) -> None:
        """发送停止通知到飞书"""
        try:
            # 获取引擎类型，决定 tmux 会话后缀和模块名称
            bot = getattr(self, '_bot', None)
            engine = getattr(bot, 'engine', 'iflow') if bot else 'iflow'
            channel_name = self.module_id.replace("feishu_", "")
            tmux_session = f"{channel_name}+{engine}"
            
            # 从 bot 获取工作目录（用户启动命令时的目录）
            workspace = bot
            if workspace and hasattr(workspace, 'workspace'):
                workspace = workspace.workspace
            else:
                workspace = os.environ.get("LING_IFLOW_WORKSPACE", str(Path.cwd()))
            
            service_info = f"""📁 工作目录：{workspace}
💻 tmux 会话：{tmux_session}"""
            
            # 根据引擎类型决定模块名称
            module_name = "Claude 飞书助手" if engine == "claude" else "iFlow 飞书助手"
            
            restart_command = f"./manage.py start --channel {channel_name}"
            
            await self.notification_manager.send_shutdown_notification(
                module_name=module_name,
                service_info=service_info,
                restart_command=restart_command
            )
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送停止通知失败：{e}", exc_info=True)

    async def _handle_startup_notification(self, data: Dict[str, Any]) -> bool:
        """处理启动通知
        
        优先发送到配置的 notify_user_id，其次使用最近联系人。
        
        Args:
            data: 通知数据，包含 content 字段
        
        Returns:
            是否发送成功
        """
        try:
            content = data.get("content", "")
            
            if not content:
                return False
            
            # 优先使用配置的用户ID，其次使用最近联系人
            receiver_id = self.notify_user_id or self._last_sender_id or self._last_chat_id
            
            if receiver_id:
                # 确定 receive_id_type
                receive_id_type = "chat_id" if receiver_id.startswith("oc_") else "open_id"
                await self.send_message(content, receiver_id, receive_id_type)
                logger.info(f"[{self.module_id}] 启动通知已发送到 {receiver_id}")
                return True
            else:
                # 没有联系人，跳过通知
                logger.warning(f"[{self.module_id}] 未配置 notify_user_id 且无最近联系人，跳过启动通知发送")
                logger.info(f"[{self.module_id}] 提示：在配置中添加 notify_user_id 以接收启动通知")
                return True  # 返回 True 表示处理成功，只是没有发送
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 启动通知处理失败：{e}", exc_info=True)
            return False

    async def _handle_shutdown_notification(self, data: Dict[str, Any]) -> bool:
        """处理停止通知
        
        优先发送到配置的 notify_user_id，其次使用最近联系人。
        
        Args:
            data: 通知数据，包含 content 字段
        
        Returns:
            是否发送成功
        """
        try:
            content = data.get("content", "")
            
            if not content:
                return False
            
            # 优先使用配置的用户ID，其次使用最近联系人
            receiver_id = self.notify_user_id or self._last_sender_id or self._last_chat_id
            
            if receiver_id:
                receive_id_type = "chat_id" if receiver_id.startswith("oc_") else "open_id"
                await self.send_message(content, receiver_id, receive_id_type)
                logger.info(f"[{self.module_id}] 停止通知已发送到 {receiver_id}")
                return True
            else:
                logger.warning(f"[{self.module_id}] 未配置 notify_user_id 且无最近联系人，跳过停止通知发送")
                return True
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 停止通知处理失败：{e}", exc_info=True)
            return False

    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "module_id": self.module_id,
            "running": self._running,
            "app_id": self.app_id,
            "websocket_connected": self._ws_client is not None,
            "client_initialized": self._client is not None
        }
