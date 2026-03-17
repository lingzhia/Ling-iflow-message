"""
WeChat Channel

企业微信消息通道，支持应用机器人。
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from ...core.base import BaseModule
from ...core.message import Message, MessageType, MessageContent
from ..command import CommandHandler


logger = logging.getLogger(__name__)


class WeChatCrypto:
    """企业微信消息加解密工具"""
    
    def __init__(self, encoding_aes_key: str, corp_id: str):
        """初始化加解密工具"""
        self.corp_id = corp_id
        self.aes_key = self._decode_key(encoding_aes_key)
        self.iv = self.aes_key[:16]
    
    def _decode_key(self, encoding_aes_key: str) -> bytes:
        """解码 EncodingAESKey"""
        import base64
        key = encoding_aes_key + "=" * (4 - len(encoding_aes_key) % 4)
        return base64.b64decode(key)
    
    def _pkcs7_unpad(self, data: bytes) -> bytes:
        """PKCS7 unpadding"""
        pad = data[-1]
        return data[:-pad]
    
    def decrypt(self, encrypted_msg: str) -> str:
        """解密消息"""
        import base64
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
        
        encrypted_data = base64.b64decode(encrypted_msg)
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        decrypted_data = self._pkcs7_unpad(decrypted_data)
        
        msg_len = int.from_bytes(decrypted_data[16:20], byteorder='big')
        msg = decrypted_data[20:20 + msg_len].decode('utf-8')
        
        return msg
    
    def generate_signature(self, token: str, timestamp: str, nonce: str, encrypted_msg: str) -> str:
        """生成消息签名"""
        params = [token, timestamp, nonce, encrypted_msg]
        params.sort()
        joined = ''.join(params)
        return hashlib.sha1(joined.encode('utf-8')).hexdigest()


class WeChatChannel(BaseModule):
    """企业微信消息通道
    
    继承 BaseModule，包含完整的企业微信功能。
    """
    
    def __init__(self, module_id: str, config: Dict[str, Any]):
        """初始化企业微信通道
        
        Args:
            module_id: 模块唯一标识符
            config: 企业微信配置
        """
        super().__init__(module_id)
        
        self.config = config
        self._http: Optional[httpx.AsyncClient] = None
        self._crypto: Optional[WeChatCrypto] = None
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        
        # 消息去重缓存
        self._processed_msg_ids: Dict[str, float] = {}
        
        # 命令处理器
        self.command_handler = CommandHandler()
        
        # 回调服务
        self._callback_runner = None
        self._running = False
        
        # 导入通用组件
        from ..common.converter import MessageConverter
        from ..common.notifications import NotificationManager
        self.converter = MessageConverter()
        self.notification_manager = NotificationManager()
        
        # 注册通知处理器
        self.notification_manager.register_notification_handler("startup", self._handle_startup_notification)
        self.notification_manager.register_notification_handler("shutdown", self._handle_shutdown_notification)
    
    def set_message_bus(self, bus) -> None:
        """设置消息总线
        
        Args:
            bus: 消息总线实例
        """
        super().set_message_bus(bus)
        # 同时设置给 CommandHandler
        self.command_handler.set_message_bus(bus)
    
    def set_manager(self, manager) -> None:
        """设置模块管理器
        
        Args:
            manager: 模块管理器实例
        """
        # 设置给 CommandHandler
        self.command_handler.set_manager(manager)
    
    def set_bot(self, bot) -> None:
        """设置 bot 实例
        
        Args:
            bot: bot 实例
        """
        # 设置给 CommandHandler
        self.command_handler.set_bot(bot)
    
    async def _on_start(self) -> None:
        """启动时的钩子方法"""
        logger.info(f"[{self.module_id}] 启动企业微信通道")
        
        if not HTTPX_AVAILABLE:
            logger.error(f"[{self.module_id}] httpx not installed")
            raise RuntimeError(f"[{self.module_id}] httpx 未安装")
        
        self._http = httpx.AsyncClient(timeout=30.0)
        
        # 初始化加解密工具
        if self.config.get("encoding_aes_key"):
            try:
                self._crypto = WeChatCrypto(
                    self.config["encoding_aes_key"],
                    self.config["corp_id"]
                )
                logger.info(f"[{self.module_id}] Crypto initialized")
            except Exception as e:
                logger.warning(f"[{self.module_id}] Failed to init crypto: {e}")
        
        # 获取 access_token
        await self._refresh_access_token()
        
        # 启动回调服务
        if AIOHTTP_AVAILABLE:
            host = self.config.get("callback_host", "0.0.0.0")
            port = self.config.get("callback_port", 8788)
            await self._start_callback_server(host, port)
        
        self._running = True
        logger.info(f"[{self.module_id}] 企业微信通道启动完成")
        
        # 发送启动通知
        await self._send_startup_notification()
    
    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        logger.info(f"[{self.module_id}] 停止企业微信通道")
        
        # 发送停止通知
        await self._send_shutdown_notification()
        
        self._running = False
        
        if self._callback_runner:
            await self._callback_runner.cleanup()
        
        if self._http:
            await self._http.aclose()
        
        logger.info(f"[{self.module_id}] 企业微信通道已停止")
    
    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法
        
        Args:
            message: 接收到的消息
        """
        try:
            # 使用消息转换器转换为平台消息
            platform_msg = self.converter.create_wechat_outbound_message(message)
            
            # 提取消息内容
            content = platform_msg.get("content", "")
            
            if not content:
                logger.warning(f"[{self.module_id}] 收到空消息")
                return
            
            # 获取聊天ID
            chat_id = platform_msg.get("chat_id") or self.config.get("user_id", "")
            is_group = platform_msg.get("is_group", False)
            
            # 发送到企业微信
            success = await self.send_message(content, chat_id, is_group)
            
            if success:
                logger.info(f"[{self.module_id}] 消息已发送到企业微信")
            else:
                logger.error(f"[{self.module_id}] 消息发送失败")
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理消息失败: {e}", exc_info=True)
    
    async def _send_startup_notification(self) -> None:
        """发送启动通知到企业微信"""
        try:
            user_id = self.config.get("user_id", "")
            if not user_id:
                logger.warning(f"[{self.module_id}] 未配置 user_id，跳过启动通知")
                return
            
            callback_port = self.config.get("callback_port", 8788)
            tmux_session = self.config.get("tmux_session", "iflow")
            workspace = self.config.get("workspace", "~/.iflow")
            
            # 扩展工作目录路径
            from pathlib import Path
            # 使用当前目录作为工作目录
            expanded_workspace = Path.cwd()
            
            # 获取 iflow 运行状态
            iflow_running = self._check_iflow_status()
            
            if iflow_running:
                service_info = f"""📁 工作目录: {expanded_workspace}
💻 tmux 会话: {tmux_session} ✓
🌐 回调端口: {callback_port}"""
                quick_start = """• 直接发送消息：执行 iFlow 命令
• `/lscmd`：查看所有可用命令"""
                tips = "输入 `/lscmd` 查看完整的命令列表和功能说明。"
                
                await self.notification_manager.send_startup_notification(
                    module_name="iFlow 企业微信机器人",
                    service_info=service_info,
                    quick_start=quick_start,
                    tips=tips
                )
            else:
                service_info = f"""💻 tmux 会话: 无连接
📁 工作目录: {expanded_workspace}
🌐 回调端口: {callback_port}"""
                available_commands = """• `/lscmd`：查看所有可用命令"""
                tips = "检查 iflow 是否正常启动。"
                
                await self.notification_manager.send_startup_notification(
                    module_name="iFlow 企业微信机器人",
                    service_info=service_info,
                    tips=tips,
                    error_message="iflow 未运行，无法处理消息",
                    available_commands=available_commands
                )
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送启动通知失败: {e}", exc_info=True)
    
    async def _send_shutdown_notification(self) -> None:
        """发送停止通知到企业微信"""
        try:
            user_id = self.config.get("user_id", "")
            if not user_id:
                logger.warning(f"[{self.module_id}] 未配置 user_id，跳过停止通知")
                return
            
            tmux_session = self.config.get("tmux_session", "iflow")
            
            # 使用当前目录作为工作目录
            from pathlib import Path
            expanded_workspace = Path.cwd()
            
            # 检查 iflow 运行状态
            iflow_running = self._check_iflow_status()
            
            if iflow_running:
                service_info = f"""📁 工作目录: {expanded_workspace}
💻 tmux 会话: {tmux_session}"""
            else:
                service_info = f"""💻 tmux 会话: 无连接
📁 工作目录: {expanded_workspace}"""
            
            restart_command = "python3 -m src.bot config.json"
            
            await self.notification_manager.send_shutdown_notification(
                module_name="iFlow 企业微信机器人",
                service_info=service_info,
                restart_command=restart_command
            )
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送停止通知失败: {e}", exc_info=True)
    
    def _handle_startup_notification(self, data: Dict[str, Any]) -> bool:
        """处理启动通知
        
        Args:
            data: 通知数据
            
        Returns:
            是否发送成功
        """
        try:
            content = data.get("content", "")
            user_id = self.config.get("user_id", "")
            
            if not content or not user_id:
                return False
            
            # 在后台执行
            asyncio.create_task(self.send_message(content, user_id, False))
            
            logger.info(f"[{self.module_id}] 启动通知已发送到 {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 启动通知处理失败: {e}", exc_info=True)
            return False
    
    async def _handle_shutdown_notification(self, data: Dict[str, Any]) -> bool:
        """处理停止通知
        
        Args:
            data: 通知数据
            
        Returns:
            是否发送成功
        """
        try:
            content = data.get("content", "")
            user_id = self.config.get("user_id", "")
            
            if not content or not user_id:
                return False
            
            # 确保在停止前完成发送
            await self.send_message(content, user_id, False)
            
            logger.info(f"[{self.module_id}] 停止通知已发送到 {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.module_id}] 停止通知处理失败: {e}", exc_info=True)
            return False
    
    def _check_iflow_status(self) -> bool:
        """检查 iflow 运行状态
        
        Returns:
            iflow 是否运行中
        """
        try:
            # 这里简化处理，通过检查绑定关系来判断
            # 实际应该检查 iflow 模块的运行状态
            return True
        except Exception:
            return False
    
    async def send_message(self, content: str, chat_id: str, is_group: bool = False) -> bool:
        """发送消息到企业微信
        
        Args:
            content: 消息内容
            chat_id: 聊天ID
            is_group: 是否为群聊
            
        Returns:
            是否发送成功
        """
        if not self._http:
            logger.error(f"[{self.module_id}] HTTP client not initialized")
            return False
        
        # 刷新 access_token
        if await self._is_access_token_expired():
            await self._refresh_access_token()
        
        try:
            # 构建消息体
            payload = {
                "touser": "" if is_group else chat_id,
                "chatid": chat_id if is_group else "",
                "msgtype": "text",
                "agentid": self.config["agent_id"],
                "text": {
                    "content": content
                }
            }
            
            # 详细日志：发送消息
            logger.info(
                f"[{self.module_id}] 发送消息到企业微信\n"
                f"  接收者: {chat_id}\n"
                f"  类型: {'群聊' if is_group else '私聊'}\n"
                f"  消息内容: {content[:200] if content else ''}"
            )
            
            # 发送请求
            url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self._access_token}"
            response = await self._http.post(url, json=payload)
            result = response.json()
            
            if result.get("errcode") == 0:
                logger.info(f"[{self.module_id}] 消息发送成功: {chat_id}")
                return True
            else:
                logger.error(f"[{self.module_id}] 消息发送失败: {result.get('errmsg', result)}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.module_id}] Error sending message: {e}", exc_info=True)
            return False
    
    async def _start_callback_server(self, host: str = "0.0.0.0", port: int = 8788) -> None:
        """启动回调服务器"""
        async def handle_verify(request: web.Request) -> web.Response:
            """处理URL验证"""
            msg_signature = request.query.get("msg_signature")
            timestamp = request.query.get("timestamp")
            nonce = request.query.get("nonce")
            echostr = request.query.get("echostr")
            
            if self._crypto:
                signature = self._crypto.generate_signature(
                    self.config["token"],
                    timestamp,
                    nonce,
                    echostr
                )
                
                if signature == msg_signature:
                    return web.Response(text=echostr)
            
            return web.Response(text="error", status=403)
        
        async def handle_message(request: web.Request) -> web.Response:
            """处理消息"""
            try:
                body = await request.text()
                
                # 异步处理消息
                asyncio.create_task(self._process_callback_async(body))
                
                return web.Response(text="success")
            except Exception as e:
                logger.error(f"[{self.module_id}] Error handling message: {e}")
                return web.Response(text="success")  # 总是返回success避免重试
        
        app = web.Application()
        app.router.add_get("/wechat/callback", handle_verify)
        app.router.add_post("/wechat/callback", handle_message)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        self._callback_runner = runner
        logger.info(f"[{self.module_id}] Callback server started on {host}:{port}")
    
    async def _process_callback_async(self, body: str) -> None:
        """异步处理回调消息"""
        try:
            # 解析XML
            root = ET.fromstring(body)
            
            # 先检查是否为加密消息
            encrypt = root.find("Encrypt")
            if encrypt is not None and self._crypto:
                # 加密消息：需要先解密
                decrypted = self._crypto.decrypt(encrypt.text)
                decrypted_root = ET.fromstring(decrypted)
                
                # 从解密后的消息中读取所有字段
                msg_type = decrypted_root.find("MsgType").text if decrypted_root.find("MsgType") is not None else ""
                msg_id = decrypted_root.find("MsgId").text if decrypted_root.find("MsgId") is not None else ""
                from_user_name = decrypted_root.find("FromUserName").text if decrypted_root.find("FromUserName") is not None else ""
                to_user_name = decrypted_root.find("ToUserName").text if decrypted_root.find("ToUserName") is not None else ""
                content_elem = decrypted_root.find("Content")
                content = content_elem.text if content_elem is not None else ""
                
                # 检查是否为群聊
                chat_id_elem = decrypted_root.find("ChatId")
                is_group = chat_id_elem is not None and chat_id_elem.text
                chat_id = chat_id_elem.text if is_group else from_user_name
            else:
                # 非加密消息：直接读取字段
                msg_type = root.find("MsgType").text if root.find("MsgType") is not None else ""
                msg_id = root.find("MsgId").text if root.find("MsgId") is not None else ""
                from_user_name = root.find("FromUserName").text if root.find("FromUserName") is not None else ""
                to_user_name = root.find("ToUserName").text if root.find("ToUserName") is not None else ""
                content_elem = root.find("Content")
                content = content_elem.text if content_elem is not None else ""
                
                # 检查是否为群聊
                chat_id_elem = root.find("ChatId")
                is_group = chat_id_elem is not None and chat_id_elem.text
                chat_id = chat_id_elem.text if is_group else from_user_name
            
            # 消息去重
            if msg_id and await self._is_duplicate_message(msg_id):
                logger.info(f"[{self.module_id}] 忽略重复消息: MsgId={msg_id}")
                return
            
            # 详细日志：收到消息
            logger.info(
                f"[{self.module_id}] 收到企业微信消息\n"
                f"  来源: {from_user_name}\n"
                f"  类型: {'群聊' if is_group else '私聊'}\n"
                f"  消息类型: {msg_type}\n"
                f"  消息内容: {content[:200] if content else ''}"
            )
            
            # 消息确认机制：立即发送确认消息
            if content:
                confirmation = f"✅ 收到消息\n\n正在处理中...\n\n消息内容: {content[:100]}{'...' if len(content) > 100 else ''}"
                await self.send_message(confirmation, chat_id, is_group)
                logger.info(f"[{self.module_id}] 已发送消息确认到 {chat_id}")
            
            # 解析命令
            parsed = self.command_handler.parse_command(content)
            
            # 如果是命令，执行命令并回复
            if parsed.get("is_command"):
                result = await self.command_handler.execute(parsed, chat_id)
                if result:
                    await self.send_message(result, chat_id, is_group)
                return
            
            # 使用消息转换器创建标准消息对象
            message = self.converter.create_wechat_inbound_message({
                "content": content,
                "sender_id": from_user_name,
                "chat_id": chat_id,
                "is_group": is_group,
                "msg_type": msg_type
            }, self.module_id)
            
            # 发送到消息总线
            if self.message_bus:
                await self.send_to_bus(message)
                logger.info(f"[{self.module_id}] 企业微信消息已发送到消息总线")
            else:
                logger.warning(f"[{self.module_id}] 消息总线未设置")
            
        except Exception as e:
            logger.error(f"[{self.module_id}] Error processing callback: {e}", exc_info=True)
    
    async def _refresh_access_token(self) -> bool:
        """刷新 access_token"""
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.config['corp_id']}&corpsecret={self.config['secret']}"
        
        response = await self._http.get(url)
        result = response.json()
        
        if result.get("errcode") == 0:
            self._access_token = result["access_token"]
            self._token_expiry = time.time() + result["expires_in"] - 60
            return True
        
        logger.error(f"[{self.module_id}] Failed to refresh token: {result}")
        return False
    
    async def _is_access_token_expired(self) -> bool:
        """检查 access_token 是否过期"""
        return time.time() >= self._token_expiry
    
    async def _is_duplicate_message(self, msg_id: str) -> bool:
        """检查是否为重复消息"""
        current_time = time.time()
        
        # 清理过期缓存
        self._processed_msg_ids = {
            k: v for k, v in self._processed_msg_ids.items()
            if current_time - v < 3600
        }
        
        if msg_id in self._processed_msg_ids:
            return True
        
        self._processed_msg_ids[msg_id] = current_time
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态
        
        Returns:
            状态信息字典
        """
        return {
            "module_id": self.module_id,
            "running": self._running,
            "corp_id": self.config.get("corp_id", ""),
            "agent_id": self.config.get("agent_id", ""),
            "user_id": self.config.get("user_id", ""),
            "callback_port": self.config.get("callback_port", 8788)
        }