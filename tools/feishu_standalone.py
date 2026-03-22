#!/usr/bin/env python3
"""
飞书渠道测试脚本（独立运行）

直接启动飞书渠道，不依赖其他模块。
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("feishu_standalone")

async def main():
    from src.modules.channel import FeishuChannel
    
    # 加载配置
    config_path = Path("config.json")
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
    print("飞书渠道测试")
    print("=" * 60)
    print(f"App ID: {feishu_config.get('app_id')}")
    print(f"tmux_session: {feishu_config.get('tmux_session')}")
    print()
    
    # 创建飞书模块
    feishu = FeishuChannel(
        module_id="feishu_standalone",
        config=feishu_config
    )
    
    # 设置信号处理
    running = True
    def signal_handler(sig, frame):
        nonlocal running
        running = False
        print("\n收到退出信号...")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动模块
    print("正在启动飞书渠道...")
    await feishu.start()
    print("✅ 飞书渠道已启动")
    print()
    print("正在等待消息...（按 Ctrl+C 退出）")
    print()
    
    # 等待退出
    try:
        while running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        # 停止模块
        print("正在停止飞书渠道...")
        await feishu.stop()
        print("✅ 飞书渠道已停止")

if __name__ == "__main__":
    asyncio.run(main())
