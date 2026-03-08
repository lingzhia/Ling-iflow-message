#!/usr/bin/env python3
"""简单测试HTTP服务是否能正常启动。"""

import asyncio
from aiohttp import web

async def start_server():
    """启动HTTP服务。"""
    async def handle_callback(request):
        """处理回调请求。"""
        method = request.method
        print(f"收到请求: {method} {request.path}")
        
        if method == "GET":
            msg_signature = request.query.get("msg_signature", "")
            timestamp = request.query.get("timestamp", "")
            nonce = request.query.get("nonce", "")
            echostr = request.query.get("echostr", "")
            
            print(f"参数: signature={msg_signature}, timestamp={timestamp}, nonce={nonce}, echostr={echostr}")
            
            # 简单返回 echostr
            return web.Response(text=echostr)
        else:
            return web.Response(text="success")
    
    app = web.Application()
    app.router.add_route("*", "/wechat/callback", handle_callback)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8787)
    
    print("正在启动HTTP服务...")
    await site.start()
    print(f"✓ HTTP服务已启动，监听 0.0.0.0:8787")
    print("等待请求...")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("正在停止服务...")
        await runner.cleanup()
        print("服务已停止")

if __name__ == "__main__":
    print("简单HTTP服务测试")
    print("=" * 50)
    asyncio.run(start_server())