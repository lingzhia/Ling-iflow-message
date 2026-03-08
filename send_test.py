#!/usr/bin/env python3
"""快速发送测试消息到企业微信。"""

import asyncio
import httpx
from loguru import logger

# 配置信息
CORP_ID = "ww6e6c8f55511c0100"
AGENT_ID = "1000002"
SECRET = "glGm51i1mbRzGZVpzRePogV-2829E-peKVJkiMIM3gg"
USER_ID = "YuLingZhi"

async def send_message(content: str):
    """发送消息到企业微信。"""
    # 获取 access_token
    token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={SECRET}"
    
    async with httpx.AsyncClient(timeout=10.0) as http:
        # 获取 token
        logger.info("正在获取 access_token...")
        resp = await http.get(token_url)
        data = resp.json()
        
        if data.get("errcode") != 0:
            logger.error(f"获取 token 失败: {data.get('errmsg')}")
            return
        
        access_token = data.get("access_token")
        logger.info("✓ access_token 获取成功")
        
        # 发送消息
        message_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        message_data = {
            "touser": USER_ID,
            "msgtype": "text",
            "agentid": int(AGENT_ID),
            "text": {
                "content": content
            },
            "safe": 0
        }
        
        logger.info(f"正在发送消息: {content}")
        resp = await http.post(message_url, json=message_data)
        data = resp.json()
        
        if data.get("errcode") == 0:
            logger.info("✓ 消息发送成功！")
            return True
        else:
            logger.error(f"✗ 消息发送失败: {data.get('errmsg')}")
            return False

if __name__ == "__main__":
    import sys
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>",
        level="INFO"
    )
    
    message = "👋 你好！这是 Ling-iflow 发送的测试消息\n\n时间: " + __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    asyncio.run(send_message(message))