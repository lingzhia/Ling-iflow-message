#!/usr/bin/env python3
"""
飞书测试工具（简化版）

用于测试飞书模块与飞书的消息交互。

使用方法：
    # 监听消息
    python tools/feishu_test_tool.py listen

    # 发送消息
    python tools/feishu_test_tool.py send "测试消息"
"""

import sys
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core import MessageBus, Message, MessageType, MessageContent
from src.modules.channel import FeishuChannel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("feishu_test")


async def listen():
    """监听飞书消息"""
    # 加载配置
    config_path = project_root / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 获取飞书配置
    feishu_config = None
    for ch in config.get("feishu_channels", []):
        if ch.get("enabled", False):
            feishu_config = ch
            break

    if not feishu_config:
        logger.error("未找到启用的飞书配置")
        return

    print("=" * 60)
    print("飞书测试工具 - 监听模式")
    print("=" * 60)
    print(f"飞书渠道：{feishu_config.get('name')}")
    print(f"App ID: {feishu_config.get('app_id')}")
    print(f"tmux_session: {feishu_config.get('tmux_session')}")
    print("")
    print("正在启动飞书渠道...")
    print("")

    # 创建消息总线
    bus = MessageBus()

    # 创建飞书模块
    feishu_module = FeishuChannel(
        module_id=f"feishu_{feishu_config['name']}",
        config=feishu_config
    )
    feishu_module.set_message_bus(bus)

    # 注册模块
    bus.register_module(feishu_module)

    # 订阅飞书消息
    async def on_message(message: Message):
        print("")
        print("=" * 60)
        print("📨 收到飞书消息:")
        print(f"   发送者：{message.user_id}")
        print(f"   聊天 ID: {message.chat_id}")
        print(f"   内容：{message.content.text}")
        print(f"   时间：{message.timestamp}")
        print("=" * 60)
        print("")

    bus.subscribe(f"feishu_{feishu_config['name']}", on_message)

    # 启动模块
    await feishu_module.start()

    print("✅ 飞书渠道已启动")
    print("正在等待消息...（按 Ctrl+C 退出）")
    print("")

    # 等待退出
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n收到退出信号")
    finally:
        # 停止模块
        await feishu_module.stop()
        print("飞书渠道已停止")


async def send(message_text: str):
    """发送消息到飞书（需要飞书 API 支持）"""
    logger.warning("发送消息功能需要飞书 API 支持，当前版本仅支持监听")
    print("提示：请使用飞书客户端向机器人发送消息进行测试")


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("飞书测试工具")
        print("")
        print("使用方法:")
        print("  python tools/feishu_test_tool.py listen     - 监听消息")
        print("  python tools/feishu_test_tool.py send <msg> - 发送消息")
        print("")
        return

    command = sys.argv[1]

    if command == "listen":
        await listen()
    elif command == "send":
        if len(sys.argv) < 3:
            print("请指定消息内容")
            print("使用方法：python tools/feishu_test_tool.py send <消息内容>")
            return
        message = " ".join(sys.argv[2:])
        await send(message)
    else:
        print(f"未知命令：{command}")
        print("使用方法：python tools/feishu_test_tool.py listen|send")


if __name__ == "__main__":
    asyncio.run(main())
