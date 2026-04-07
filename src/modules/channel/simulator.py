"""
Simulator Channel

消息模拟器渠道，通过 Socket 接收测试工具的消息。
"""

import asyncio
import json
import logging
import struct
from typing import Optional, Dict, Any, Callable

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from ...core.base import BaseModule
from ...core.message import Message, MessageType, MessageContent
from ...core.logger_adapter import log_feishu_message, log_system_event, MessageType as LogMessageType


logger = logging.getLogger(__name__)


class SimulatorChannel(BaseModule):
    """消息模拟器渠道
    
    通过 Socket 接收测试工具的消息，发送到 MessageBus。
    """
    
    def __init__(self, module_id: str, config: Dict[str, Any]):
        """初始化模拟器通道
        
        Args:
            module_id: 模块唯一标识符
            config: 模拟器配置
        """
        super().__init__(module_id)
        
        self.config = config
        self._server_runner = None
        self._running = False
        
        # Socket 配置
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 19999)
        
        # 客户端连接管理
        self._connections: Dict[str, Dict] = {}
        
        # 命令处理器
        from ..command import CommandHandler
        self.command_handler = CommandHandler()
        
        # 导入通用组件
        from ..common.converter import MessageConverter
        self.converter = MessageConverter()
    
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
        self._manager = manager
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
        logger.info(f"[{self.module_id}] 启动模拟器通道")
        
        if not AIOHTTP_AVAILABLE:
            logger.error(f"[{self.module_id}] aiohttp not installed")
            raise RuntimeError(f"[{self.module_id}] aiohttp 未安装")
        
        # 启动 Socket 服务器
        await self._start_socket_server()
        
        self._running = True
        logger.info(f"[{self.module_id}] 模拟器通道启动完成，监听 {self.host}:{self.port}")
    
    async def _on_stop(self) -> None:
        """停止时的钩子方法"""
        logger.info(f"[{self.module_id}] 停止模拟器通道")
        
        self._running = False
        
        # 关闭所有客户端连接
        for conn_id, conn in self._connections.items():
            try:
                if "reader" in conn:
                    conn["reader"].feed_eof()
                if "writer" in conn:
                    conn["writer"].close()
                    await conn["writer"].wait_closed()
            except Exception as e:
                logger.error(f"[{self.module_id}] 关闭连接 {conn_id} 失败: {e}")
        
        self._connections.clear()
        
        # 停止服务器
        if self._server_runner:
            await self._server_runner.cleanup()
        
        logger.info(f"[{self.module_id}] 模拟器通道已停止")
    
    async def _on_receive(self, message: Message) -> None:
        """接收消息时的钩子方法
        
        Args:
            message: 接收到的消息
        """
        logger.info(f"[{self.module_id}] 收到来自消息总线的消息: {message.content.text[:50] if message.content else '(空)'}...")
        try:
            # 将消息发送给所有连接的客户端
            for conn_id, conn in self._connections.items():
                try:
                    await self._send_message_to_client(conn, message)
                except Exception as e:
                    logger.error(f"[{self.module_id}] 发送消息到客户端 {conn_id} 失败: {e}")
                    
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理消息失败: {e}", exc_info=True)
    
    async def _start_socket_server(self) -> None:
        """启动 Socket 服务器"""
        server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        
        # 在后台运行服务器
        async def run_server():
            async with server:
                await server.serve_forever()
        
        self.create_background_task(run_server())
        logger.info(f"[{self.module_id}] Socket 服务器已启动")
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接
        
        Args:
            reader: 流读取器
            writer: 流写入器
        """
        conn_id = f"conn_{id(writer)}"
        
        try:
            # 存储连接
            address = writer.get_extra_info('peername')
            self._connections[conn_id] = {
                "reader": reader,
                "writer": writer,
                "address": address
            }
            
            logger.info(f"[{self.module_id}] 客户端已连接: {conn_id}")
            log_system_event(
                logger,
                self.module_id,
                f"🔗 客户端已连接: conn_id={conn_id}, address={address}",
                level=logging.INFO
            )
            
            # 接收消息循环
            while self._running:
                try:
                    # 读取消息长度（4字节）
                    length_data = await reader.readexactly(4)
                    length = struct.unpack('>I', length_data)[0]
                    
                    # 读取消息内容
                    message_data = await reader.readexactly(length)
                    
                    # 解析 JSON
                    message_json = json.loads(message_data.decode('utf-8'))
                    
                    # 处理消息
                    await self._handle_client_message(conn_id, message_json)
                    
                except asyncio.IncompleteReadError:
                    # 连接关闭
                    logger.info(f"[{self.module_id}] 客户端 {conn_id} 连接关闭（IncompleteReadError）")
                    log_system_event(
                        logger,
                        self.module_id,
                        f"🔌 客户端连接关闭: conn_id={conn_id}, reason=IncompleteReadError",
                        level=logging.INFO
                    )
                    break
                except Exception as e:
                    logger.error(f"[{self.module_id}] 处理客户端 {conn_id} 消息失败: {e}")
                    log_system_event(
                        logger,
                        self.module_id,
                        f"❌ 处理客户端 {conn_id} 消息失败: {str(e)}",
                        level=logging.ERROR
                    )
                    break
                    
        except Exception as e:
            logger.error(f"[{self.module_id}] 客户端 {conn_id} 连接错误: {e}")
            log_system_event(
                logger,
                self.module_id,
                f"❌ 客户端 {conn_id} 连接错误: {str(e)}",
                level=logging.ERROR
            )
        finally:
            # 清理连接
            if conn_id in self._connections:
                del self._connections[conn_id]
            
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
            
            logger.info(f"[{self.module_id}] 客户端已断开: {conn_id}")
            log_system_event(
                logger,
                self.module_id,
                f"🔌 客户端已断开: conn_id={conn_id}",
                level=logging.INFO
            )
    
    async def _handle_client_message(self, conn_id: str, message_json: Dict[str, Any]) -> None:
        """处理客户端消息
        
        Args:
            conn_id: 连接 ID
            message_json: 消息 JSON
        """
        try:
            message_type = message_json.get("type", "")
            
            if message_type == "user_message":
                # 用户消息
                content = message_json.get("content", "")
                metadata = message_json.get("metadata", {})
                chat_id = metadata.get("chat_id", conn_id)
                
                # 使用日志适配器记录接收到的模拟器消息
                log_feishu_message(
                    logger,
                    self.module_id,
                    f"📨 模拟器收到消息: conn_id={conn_id}, chat_id={chat_id}, content={content}",
                    level=logging.INFO
                )
                
                # 记录完整的消息元数据
                log_system_event(
                    logger,
                    self.module_id,
                    f"📋 消息元数据: conn_id={conn_id}, message_id={message_json.get('id')}, "
                    f"from_module={self.module_id}, chat_id={chat_id}, metadata={metadata}",
                    level=logging.DEBUG
                )
                
                logger.info(f"[{self.module_id}] [_handle_client_message] 收到消息: content={content[:80]}..., conn_id={conn_id}")
                
                # 解析命令
                parsed = self.command_handler.parse_command(content)
                
                # 如果是命令，执行命令并回复
                if parsed.get("is_command"):
                    result = await self.command_handler.execute(parsed, chat_id)
                    if result:
                        # 记录命令回复
                        log_system_event(
                            logger,
                            self.module_id,
                            f"📤 命令回复: chat_id={chat_id}, result={result}",
                            level=logging.INFO
                        )
                        # 发送命令回复到客户端
                        await self._send_to_client(conn_id, {
                            "type": "bot_message",
                            "id": Message.generate_id(),
                            "content": result,
                            "metadata": {
                                "msg_type": "command_reply",
                                "chat_id": chat_id
                            }
                        })
                    return
                
                # 创建标准消息
                message = Message(
                    id=Message.generate_id(),
                    type=MessageType.TEXT,
                    content=MessageContent(type=MessageType.TEXT, text=content),
                    from_module=self.module_id,
                    metadata={
                        "msg_type": "simulator_message",
                        "conn_id": conn_id,
                        **metadata
                    }
                )
                
                # 记录发送到消息总线的消息
                log_system_event(
                    logger,
                    self.module_id,
                    f"📤 发送消息到消息总线: msg_id={message.id}, content={content}, chat_id={chat_id}",
                    level=logging.INFO
                )
                
                # 发送到消息总线
                if self.message_bus:
                    await self.send_to_bus(message)
                    logger.info(f"[{self.module_id}] 模拟器消息已发送到消息总线")
                else:
                    logger.warning(f"[{self.module_id}] 消息总线未设置")
                    
            elif message_type == "heartbeat":
                # 心跳消息：忽略
                pass
                
            elif message_type == "close":
                # 关闭消息：断开连接
                log_system_event(
                    logger,
                    self.module_id,
                    f"🔌 客户端请求关闭: conn_id={conn_id}",
                    level=logging.INFO
                )
                if conn_id in self._connections:
                    conn = self._connections[conn_id]
                    if "writer" in conn:
                        conn["writer"].close()
                        await conn["writer"].wait_closed()
                        
            else:
                logger.warning(f"[{self.module_id}] 未知消息类型: {message_type}")
                log_system_event(
                    logger,
                    self.module_id,
                    f"⚠️  未知消息类型: {message_type}",
                    level=logging.WARNING
                )
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 处理客户端 {conn_id} 消息失败: {e}", exc_info=True)
            log_system_event(
                logger,
                self.module_id,
                f"❌ 处理客户端 {conn_id} 消息失败: {str(e)}",
                level=logging.ERROR
            )
    
    async def _send_message_to_client(self, conn: Dict, message: Message) -> None:
        """发送消息到客户端
        
        Args:
            conn: 连接对象
            message: 消息对象
        """
        try:
            # 转换为 Socket 消息格式
            # 根据消息类型设置 message_type
            from ...core.message import MessageType
            message_type_map = {
                MessageType.REPLY: "reply",
                MessageType.OTHER: "other",
                MessageType.TEXT: "text",
                MessageType.IMAGE: "image",
                MessageType.FILE: "file"
            }
            
            # 从metadata中获取scope（如果存在）
            scope = message.metadata.get("scope", "all") if message.metadata else "all"
            
            message_json = {
                "type": "reply_message",
                "id": Message.generate_id(),
                "request_id": message.id,
                "timestamp": asyncio.get_event_loop().time(),
                "content": message.content.text if message.content else "",
                "metadata": {
                    "message_type": message_type_map.get(message.type, "text"),
                    "scope": scope
                }
            }
            
            # 记录发送到客户端的消息
            content = message.content.text if message.content else ""
            log_feishu_message(
                logger,
                self.module_id,
                f"📤 发送消息到模拟器客户端: msg_id={message.id}, content={content[:80]}..., message_type={message.type}, scope={scope}",
                level=logging.INFO
            )
            
            # 记录完整的消息元数据
            log_system_event(
                logger,
                self.module_id,
                f"📋 发送消息元数据: msg_id={message.id}, from_module={message.from_module}, "
                f"message_type={message.type}, scope={scope}, metadata={message.metadata}",
                level=logging.DEBUG
            )
            
            logger.info(f"[{self.module_id}] [_send_message_to_client] 发送消息: content={content[:80]}..., type={message.type}")
            
            writer = conn.get("writer")
            if writer:
                message_data = json.dumps(message_json, ensure_ascii=False).encode('utf-8')
                writer.write(struct.pack('>I', len(message_data)))
                writer.write(message_data)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送消息到客户端失败: {e}")
            log_system_event(
                logger,
                self.module_id,
                f"❌ 发送消息到客户端失败: {str(e)}",
                level=logging.ERROR
            )
    
    async def _send_to_client(self, conn_id: str, message_json: Dict) -> None:
        """发送消息到客户端（直接发送JSON）
        
        Args:
            conn_id: 连接 ID
            message_json: 消息 JSON 对象
        """
        try:
            conn = self._connections.get(conn_id)
            if not conn:
                logger.warning(f"[{self.module_id}] 连接不存在: {conn_id}")
                log_system_event(
                    logger,
                    self.module_id,
                    f"⚠️  发送消息失败: 连接不存在 conn_id={conn_id}",
                    level=logging.WARNING
                )
                return
            
            # 记录发送到客户端的直接JSON消息
            msg_type = message_json.get("type", "unknown")
            content = message_json.get("content", "")
            log_feishu_message(
                logger,
                self.module_id,
                f"📤 发送直接JSON消息到客户端: conn_id={conn_id}, type={msg_type}, content={content[:80] if content else 'N/A'}...",
                level=logging.INFO
            )
            
            logger.info(f"[{self.module_id}] [_send_to_client] 发送消息: conn_id={conn_id}, type={msg_type}")
            
            writer = conn.get("writer")
            if writer:
                message_data = json.dumps(message_json, ensure_ascii=False).encode('utf-8')
                writer.write(struct.pack('>I', len(message_data)))
                writer.write(message_data)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"[{self.module_id}] 发送消息到客户端失败: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态
        
        Returns:
            状态信息字典
        """
        return {
            "module_id": self.module_id,
            "running": self._running,
            "host": self.host,
            "port": self.port,
            "connections": len(self._connections),
            "connection_ids": list(self._connections.keys())
        }