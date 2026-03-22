#!/usr/bin/env python3
"""
飞书渠道测试工具

测试飞书消息收发流程：
1. 连接飞书 WebSocket
2. 接收消息并打印
3. 回复消息
"""

import asyncio
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("feishu_test")

# 加载配置
CONFIG_PATH = Path(__file__).parent.parent / "config.json"

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    for fs in config.get("feishu_channels", []):
        if fs.get("enabled", True):
            return fs
    return None


class FeishuTestBot:
    """简单的飞书测试机器人"""
    
    def __init__(self, config: dict):
        self.config = config
        self.app_id = config.get("app_id")
        self.app_secret = config.get("app_secret")
        
        self._client = None
        self._ws_client = None
        self._running = False
        self._loop = None
        
    async def start(self):
        """启动测试"""
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest,
            CreateMessageRequestBody,
            P2ImMessageReceiveV1,
        )
        
        logger.info("=" * 60)
        logger.info("飞书渠道测试")
        logger.info("=" * 60)
        logger.info(f"App ID: {self.app_id}")
        logger.info("")
        
        # 创建 SDK 客户端
        self._client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()
        
        logger.info("✓ SDK 客户端创建成功")
        
        # 保存主事件循环
        self._loop = asyncio.get_running_loop()
        self._running = True
        
        # 创建事件处理器
        def on_message(event: P2ImMessageReceiveV1):
            """处理消息事件"""
            logger.info("=" * 40)
            logger.info("收到飞书消息事件!")
            logger.info("=" * 40)
            
            try:
                message = event.event.message
                sender = event.event.sender
                
                message_id = message.message_id
                chat_id = message.chat_id
                msg_type = message.message_type
                content = message.content
                sender_id = sender.sender_id.open_id
                
                logger.info(f"消息ID: {message_id}")
                logger.info(f"会话ID: {chat_id}")
                logger.info(f"发送者: {sender_id}")
                logger.info(f"消息类型: {msg_type}")
                logger.info(f"内容: {content}")
                
                # 解析文本内容
                if msg_type == "text":
                    try:
                        content_json = json.loads(content)
                        text = content_json.get("text", "")
                        logger.info(f"文本内容: {text}")
                        
                        # 回复消息
                        reply_text = f"收到消息: {text}"
                        self._send_message_sync(chat_id, sender_id, reply_text)
                        
                    except json.JSONDecodeError:
                        logger.warning("内容解析失败")
                else:
                    logger.info(f"非文本消息类型: {msg_type}")
                    
            except Exception as e:
                logger.error(f"处理消息失败: {e}", exc_info=True)
            
            logger.info("=" * 40)
        
        # 创建事件处理器
        event_handler = lark.EventDispatcherHandler.builder(
            "",  # encrypt_key
            "",  # verification_token (WebSocket 模式可以为空)
        ).register_p2_im_message_receive_v1(on_message).build()
        
        # 创建 WebSocket 客户端
        self._ws_client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.DEBUG
        )
        
        logger.info("✓ WebSocket 客户端创建成功")
        logger.info("")
        logger.info("启动 WebSocket 连接...")
        logger.info("请在飞书中发送消息测试")
        logger.info("按 Ctrl+C 退出")
        logger.info("")
        
        # 在独立线程中运行 WebSocket（需要独立的事件循环）
        def run_ws():
            import lark_oapi.ws.client as ws_client_module
            
            # 创建新的事件循环
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            
            # 关键：替换 lark_oapi 模块级别的事件循环变量
            ws_client_module.loop = new_loop
            
            try:
                self._ws_client.start()
            except Exception as e:
                if "Event loop stopped" not in str(e):
                    logger.error(f"WebSocket 错误: {e}")
            finally:
                try:
                    new_loop.close()
                except:
                    pass
        
        ws_thread = threading.Thread(target=run_ws, daemon=True)
        ws_thread.start()
        
        # 等待 WebSocket 连接建立
        await asyncio.sleep(2)
        logger.info("✓ WebSocket 连接已建立")
        logger.info("")
        
        # 保持运行
        while self._running:
            await asyncio.sleep(1)
    
    def _send_message_sync(self, chat_id: str, sender_id: str, text: str):
        """同步发送消息"""
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest,
            CreateMessageRequestBody,
        )
        
        try:
            # 确定接收者
            if chat_id.startswith("oc_"):
                # 群聊
                receive_id = chat_id
                receive_id_type = "chat_id"
            else:
                # 私聊
                receive_id = sender_id
                receive_id_type = "open_id"
            
            # 构建消息内容
            content = json.dumps({"text": text}, ensure_ascii=False)
            
            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(receive_id)
                    .msg_type("text")
                    .content(content)
                    .build()
                ).build()
            
            response = self._client.im.v1.message.create(request)
            
            if response.success():
                logger.info(f"✓ 消息已发送: {text[:50]}...")
            else:
                logger.error(f"✗ 发送失败: code={response.code}, msg={response.msg}")
                
        except Exception as e:
            logger.error(f"发送消息异常: {e}", exc_info=True)
    
    def stop(self):
        """停止测试"""
        self._running = False
        logger.info("停止测试...")


async def main():
    config = load_config()
    if not config:
        logger.error("未找到飞书配置")
        return
    
    bot = FeishuTestBot(config)
    
    # 信号处理
    def signal_handler(sig, frame):
        bot.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
