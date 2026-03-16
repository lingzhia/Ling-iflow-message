#!/usr/bin/env python3
"""
Test Client Tool

消息模拟器测试客户端工具，支持交互模式和命令行模式。
"""

import asyncio
import json
import logging
import struct
import sys
from typing import Optional, Dict, Any, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class TestClient:
    """测试客户端
    
    连接到 SimulatorChannel，发送消息并接收回复。
    """
    
    def __init__(self, host: str = "localhost", port: int = 19999):
        """初始化测试客户端
        
        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        
        # 消息统计
        self.sent_count = 0
        self.received_count = 0
    
    async def connect(self) -> bool:
        """连接到服务器
        
        Returns:
            是否连接成功
        """
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host,
                self.port
            )
            self._connected = True
            logger.info(f"已连接到服务器 {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            error_msg = f"连接被拒绝: {self.host}:{self.port}"
            logger.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"连接失败: {e}"
            logger.error(error_msg)
            return False
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass
        
        self._connected = False
        logger.info("已断开连接")
    
    async def send_message(self, content: str, user_id: str = "test_user", chat_id: str = "test_chat") -> bool:
        """发送消息到服务器
        
        Args:
            content: 消息内容
            user_id: 用户 ID
            chat_id: 聊天 ID
            
        Returns:
            是否发送成功
        """
        if not self._connected:
            logger.error("未连接到服务器")
            return False
        
        try:
            # 构建消息
            message = {
                "type": "user_message",
                "id": f"msg_{self.sent_count + 1}",
                "timestamp": asyncio.get_event_loop().time(),
                "content": content,
                "metadata": {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "is_group": False
                }
            }
            
            # 序列化为 JSON
            message_data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            
            # 写入长度（4字节）和内容
            self.writer.write(struct.pack('>I', len(message_data)))
            self.writer.write(message_data)
            await self.writer.drain()
            
            self.sent_count += 1
            logger.info(f"消息已发送: {content[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    async def receive_message(self, timeout: float = 30.0) -> Optional[Dict]:
        """接收服务器消息
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            消息字典，超时返回 None
        """
        if not self._connected:
            logger.error("未连接到服务器")
            return None
        
        try:
            # 读取消息长度（4字节）
            length_data = await asyncio.wait_for(
                self.reader.readexactly(4),
                timeout=timeout
            )
            length = struct.unpack('>I', length_data)[0]
            
            # 读取消息内容
            message_data = await asyncio.wait_for(
                self.reader.readexactly(length),
                timeout=timeout
            )
            
            # 解析 JSON
            message = json.loads(message_data.decode('utf-8'))
            
            self.received_count += 1
            logger.info(f"消息已接收: {message.get('content', '')[:50]}...")
            return message
            
        except asyncio.TimeoutError:
            logger.warning("接收消息超时")
            return None
        except Exception as e:
            logger.error(f"接收消息失败: {e}")
            return None
    
    async def send_and_receive(self, content: str, timeout: float = 30.0) -> Optional[Dict]:
        """发送消息并接收回复
        
        Args:
            content: 消息内容
            timeout: 超时时间（秒）
            
        Returns:
            回复消息
        """
        if await self.send_message(content):
            return await self.receive_message(timeout)
        return None


class InteractiveMode:
    """交互模式"""
    
    def __init__(self, client: TestClient):
        """初始化交互模式
        
        Args:
            client: 测试客户端
        """
        self.client = client
        self._running = False
    
    async def start(self) -> None:
        """启动交互模式"""
        self._running = True
        
        # 连接到服务器
        if not await self.client.connect():
            print("\n❌ 连接失败")
            print(f"\n⚠️  无法连接到模拟器服务器 {self.client.host}:{self.client.port}")
            print("\n可能的原因：")
            print("  1. 模拟器服务未启动")
            print("  2. 端口配置错误")
            print("  3. 防火墙阻止连接")
            print("\n解决方案：")
            print("  1. 启动模拟器服务:")
            print("     ./manage.py start -g g_simulator -d")
            print("  2. 检查配置文件 config.json 中的 simulator_channels 配置")
            print("  3. 检查端口是否被占用")
            return
        
        print("\n" + "=" * 50)
        print("消息模拟器测试工具 - 交互模式")
        print("=" * 50)
        print(f"连接状态: 已连接 ({self.client.host}:{self.client.port})")
        print(f"消息统计: 发送 {self.client.sent_count}, 接收 {self.client.received_count}")
        print("-" * 50)
        print("输入消息（输入 /help 查看命令）:")
        
        # 命令循环
        while self._running:
            try:
                # 获取用户输入
                content = input("> ").strip()
                
                if not content:
                    continue
                
                # 处理命令
                if content.startswith("/"):
                    result = await self._handle_command(content)
                    if result == "quit":
                        break
                    continue
                
                # 发送消息
                print("⏳ 发送消息中...")
                response = await self.client.send_and_receive(content)
                
                if response:
                    print(f"📥 回复: {response.get('content', '')}")
                else:
                    print("⚠️  未收到回复")
                    
            except KeyboardInterrupt:
                print("\n\n用户中断")
                break
            except Exception as e:
                logger.error(f"错误: {e}")
        
        # 断开连接
        await self.client.disconnect()
        print("\n已退出")
    
    async def _handle_command(self, command: str) -> Optional[str]:
        """处理命令
        
        Args:
            command: 命令字符串
            
        Returns:
            命令结果，"quit" 表示退出
        """
        cmd_parts = command.split()
        cmd_name = cmd_parts[0].lower()
        
        if cmd_name == "/help":
            print("""
**可用命令**:
- /help     显示帮助信息
- /status   显示连接状态
- /stats    显示消息统计
- /quit     退出工具
""")
        elif cmd_name == "/status":
            print(f"""
**连接状态**:
- 地址: {self.client.host}:{self.client.port}
- 状态: {'已连接' if self.client._connected else '未连接'}
""")
        elif cmd_name == "/stats":
            print(f"""
**消息统计**:
- 发送: {self.client.sent_count}
- 接收: {self.client.received_count}
""")
        elif cmd_name == "/quit" or cmd_name == "/exit":
            return "quit"
        else:
            print(f"❌ 未知命令: {cmd_name}")
        
        return None


async def main() -> None:
    """主函数"""
    # 解析命令行参数
    args = sys.argv[1:]
    
    if len(args) > 0 and args[0] == "--send":
        # 命令行模式：发送单条消息
        if len(args) < 2:
            print("用法: python test_client.py --send <消息> [host] [port]")
            sys.exit(1)
        
        content = args[1]
        host = args[2] if len(args) > 2 else "localhost"
        port = int(args[3]) if len(args) > 3 else 19999
        
        client = TestClient(host, port)
        
        if await client.connect():
            response = await client.send_and_receive(content)
            
            if response:
                print(f"✅ 发送成功")
                print(f"📥 回复: {response.get('content', '')}")
            else:
                print("❌ 未收到回复")
            
            await client.disconnect()
        else:
            print("❌ 连接失败")
            print(f"\n⚠️  无法连接到模拟器服务器 {host}:{port}")
            print("\n可能的原因：")
            print("  1. 模拟器服务未启动")
            print("  2. 端口配置错误")
            print("  3. 防火墙阻止连接")
            print("\n解决方案：")
            print("  1. 启动模拟器服务:")
            print("     ./manage.py start -g g_simulator -d")
            print("  2. 检查配置文件 config.json 中的 simulator_channels 配置")
            print("  3. 检查端口是否被占用")
            
    elif len(args) > 0 and args[0] == "--mode":
        # 指定模式
        mode = args[1]
        
        if mode == "interactive":
            host = args[2] if len(args) > 2 else "localhost"
            port = int(args[3]) if len(args) > 3 else 19999
            
            client = TestClient(host, port)
            interactive = InteractiveMode(client)
            await interactive.start()
        else:
            print(f"❌ 未知模式: {mode}")
            sys.exit(1)
            
    else:
        # 默认：交互模式
        host = args[0] if len(args) > 0 else "localhost"
        port = int(args[1]) if len(args) > 1 else 19999
        
        client = TestClient(host, port)
        interactive = InteractiveMode(client)
        await interactive.start()


if __name__ == "__main__":
    asyncio.run(main())