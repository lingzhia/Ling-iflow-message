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
from typing import Optional, Dict, Any, Callable
from urllib.parse import quote

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


class WeChatChannel:
    """企业微信消息通道
    
    纯粹的企业微信 API 封装，不处理业务逻辑。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """初始化企业微信通道
        
        Args:
            config: 企业微信配置
        """
        self.config = config
        self._http: Optional[httpx.AsyncClient] = None
        self._crypto: Optional[WeChatCrypto] = None
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        
        # 消息去重缓存
        self._processed_msg_ids: Dict[str, float] = {}
        
        # 消息处理器
        self._message_handler: Optional[Callable] = None
        
        # 回调服务
        self._callback_runner = None
        self._running = False
    
    async def start(self) -> bool:
        """启动通道"""
        if not HTTPX_AVAILABLE:
            logger.error("[WeChatChannel] httpx not installed")
            return False
        
        self._http = httpx.AsyncClient(timeout=30.0)
        
        # 初始化加解密工具
        if self.config.get("encoding_aes_key"):
            try:
                self._crypto = WeChatCrypto(
                    self.config["encoding_aes_key"],
                    self.config["corp_id"]
                )
                logger.info("[WeChatChannel] Crypto initialized")
            except Exception as e:
                logger.warning(f"[WeChatChannel] Failed to init crypto: {e}")
        
        # 获取 access_token
        await self._refresh_access_token()
        
        # 启动回调服务
        if AIOHTTP_AVAILABLE:
            host = self.config.get("callback_host", "0.0.0.0")
            port = self.config.get("callback_port", 8788)
            await self._start_callback_server(host, port)
        
        self._running = True
        logger.info("[WeChatChannel] Started")
        return True
    
    async def stop(self) -> None:
        """停止通道"""
        self._running = False
        
        if self._callback_runner:
            await self._callback_runner.cleanup()
        
        if self._http:
            await self._http.aclose()
        
        logger.info("[WeChatChannel] Stopped")
    
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
            logger.error("[WeChatChannel] HTTP client not initialized")
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
                f"[WeChatChannel] 发送消息到企业微信\n"
                f"  接收者: {chat_id}\n"
                f"  类型: {'群聊' if is_group else '私聊'}\n"
                f"  消息内容: {content[:200] if content else ''}"
            )
            
            # 发送请求
            url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self._access_token}"
            response = await self._http.post(url, json=payload)
            result = response.json()
            
            if result.get("errcode") == 0:
                logger.info(f"[WeChatChannel] 消息发送成功: {chat_id}")
                return True
            else:
                logger.error(f"[WeChatChannel] 消息发送失败: {result.get('errmsg', result)}")
                return False
                
        except Exception as e:
            logger.error(f"[WeChatChannel] Error sending message: {e}", exc_info=True)
            return False
    
    def set_message_handler(self, handler: Callable) -> None:
        """设置消息处理器
        
        Args:
            handler: 消息处理函数
        """
        self._message_handler = handler
    
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
                logger.error(f"[WeChatChannel] Error handling message: {e}")
                return web.Response(text="success")  # 总是返回success避免重试
        
        app = web.Application()
        app.router.add_get("/wechat/callback", handle_verify)
        app.router.add_post("/wechat/callback", handle_message)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        
        self._callback_runner = runner
        logger.info(f"[WeChatChannel] Callback server started on {host}:{port}")
    
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
                logger.info(f"[WeChatChannel] 忽略重复消息: MsgId={msg_id}")
                return
            
            # 详细日志：收到消息
            logger.info(
                f"[WeChatChannel] 收到企业微信消息\n"
                f"  来源: {from_user_name}\n"
                f"  类型: {'群聊' if is_group else '私聊'}\n"
                f"  消息类型: {msg_type}\n"
                f"  消息内容: {content[:200] if content else ''}"
            )
            
            # 消息确认机制：立即发送确认消息
            if content:
                confirmation = f"✅ 收到消息\n\n正在处理中...\n\n消息内容: {content[:100]}{'...' if len(content) > 100 else ''}"
                await self.send_message(confirmation, chat_id, is_group)
                logger.info(f"[WeChatChannel] 已发送消息确认到 {chat_id}")
            
            # 调用消息处理器
            if self._message_handler:
                await self._message_handler({
                    "content": content,
                    "sender_id": from_user_name,
                    "chat_id": chat_id,
                    "is_group": is_group,
                    "msg_type": msg_type
                })
            
        except Exception as e:
            logger.error(f"[WeChatChannel] Error processing callback: {e}", exc_info=True)
    
    async def _refresh_access_token(self) -> bool:
        """刷新 access_token"""
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.config['corp_id']}&corpsecret={self.config['secret']}"
        
        response = await self._http.get(url)
        result = response.json()
        
        if result.get("errcode") == 0:
            self._access_token = result["access_token"]
            self._token_expiry = time.time() + result["expires_in"] - 60
            return True
        
        logger.error(f"[WeChatChannel] Failed to refresh token: {result}")
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