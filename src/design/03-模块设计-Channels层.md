# 模块设计 - Channels 层

## 概述

Channels 层负责实现与外部渠道的通信，定义了渠道的抽象接口和具体实现。当前实现了企业微信渠道（WechatWorkChannel），支持应用机器人和群机器人。

## 目录结构

```
channels/
├── __init__.py
├── base.py         # 渠道基类
└── wechat_work.py  # 企业微信渠道
```

## BaseChannel（基类）

### 职责
定义渠道的抽象接口，所有渠道实现都需要继承此基类。

### 主要功能
- 定义 send() 方法
- 定义消息处理回调
- 生命周期管理（start/stop）

### 接口定义

```python
class BaseChannel(ABC):
    """渠道基类。"""
    
    @abstractmethod
    async def start(self) -> bool:
        """启动渠道。"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止渠道。"""
        pass
    
    @abstractmethod
    async def send(self, content: str, chat_id: str, **kwargs) -> bool:
        """发送消息。
        
        Args:
            content: 消息内容
            chat_id: 聊天 ID
            **kwargs: 其他参数
            
        Returns:
            是否发送成功
        """
        pass
    
    @abstractmethod
    def set_message_handler(self, handler: Callable) -> None:
        """设置消息处理器。"""
        pass
```

## WechatWorkChannel（企业微信渠道）

### 职责
实现企业微信应用机器人和群机器人的消息收发。

### 主要功能
- 应用机器人：通过企业微信 API 接收消息（回调模式）
- 群机器人：通过 Webhook 发送消息
- 消息加解密（AES-256-CBC）
- 消息去重（基于 MsgId）
- 权限控制（白名单）
- 内嵌 HTTP 回调服务

### 核心组件

#### 1. WechatWorkCrypto（加解密工具）

**职责**：处理企业微信消息的加解密

**技术方案**：
- 加密算法：AES-256-CBC
- 填充方式：PKCS7
- 签名算法：SHA1

**关键方法**：
```python
class WechatWorkCrypto:
    def __init__(self, encoding_aes_key: str, corp_id: str):
        """初始化加解密工具。"""
        self.corp_id = corp_id
        self.aes_key = self._decode_key(encoding_aes_key)
        self.iv = self.aes_key[:16]
    
    def decrypt(self, encrypted_msg: str) -> str:
        """解密消息。"""
        pass
    
    def encrypt(self, msg: str) -> str:
        """加密消息。"""
        pass
    
    def generate_signature(self, token: str, timestamp: str, nonce: str, encrypted_msg: str) -> str:
        """生成签名。"""
        pass
```

**实现细节**：

1. **解码 EncodingAESKey**
```python
def _decode_key(self, encoding_aes_key: str) -> bytes:
    """解码 EncodingAESKey。"""
    import base64
    # 补充 '=' 使长度为 4 的倍数
    key = encoding_aes_key + "=" * (4 - len(encoding_aes_key) % 4)
    return base64.b64decode(key)
```

2. **PKCS7 填充**
```python
def _pkcs7_pad(self, data: bytes, block_size: int = 32) -> bytes:
    """手动 PKCS7 padding。"""
    pad = block_size - (len(data) % block_size)
    return data + bytes([pad] * pad)

def _pkcs7_unpad(self, data: bytes) -> bytes:
    """手动 PKCS7 unpadding。"""
    pad = data[-1]
    return data[:-pad]
```

3. **解密流程**
```python
def decrypt(self, encrypted_msg: str) -> str:
    """解密消息。"""
    import base64
    
    # Base64 解码
    encrypted_data = base64.b64decode(encrypted_msg)
    
    # AES 解密
    cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
    
    # PKCS7 unpadding
    decrypted_data = self._pkcs7_unpad(decrypted_data)
    
    # 提取消息（去掉前 16 字节随机字符串和 4 字节长度）
    msg_len = decrypted_data[16:20]
    msg_len_int = int.from_bytes(msg_len, byteorder='big')
    msg = decrypted_data[20:20 + msg_len_int]
    
    # 验证 corp_id
    received_corp_id = decrypted_data[20 + msg_len_int:].decode('utf-8')
    if received_corp_id != self.corp_id:
        raise ValueError("Corp ID mismatch")
    
    return msg.decode('utf-8')
```

#### 2. WechatWorkWebhookBot（群机器人）

**职责**：实现企业微信群机器人的消息发送

**支持的消息类型**：
- 文本消息
- Markdown 消息
- 图片消息
- 图文消息

**关键方法**：
```python
class WechatWorkWebhookBot:
    def __init__(self, webhook_url: str):
        """初始化群机器人。"""
        self.webhook_url = webhook_url
    
    async def send_text(self, content: str, mentioned_list: List[str] = None) -> bool:
        """发送文本消息。"""
        pass
    
    async def send_markdown(self, content: str) -> bool:
        """发送 Markdown 消息。"""
        pass
    
    async def send_image(self, base64: str, md5: str) -> bool:
        """发送图片消息。"""
        pass
    
    async def send_news(self, articles: List[Dict]) -> bool:
        """发送图文消息。"""
        pass
```

### 配置项

```python
class WechatWorkConfig(BaseModel):
    """企业微信配置。"""
    enabled: bool = False
    corp_id: str = ""
    agent_id: int = 0
    secret: str = ""
    token: str = ""
    encoding_aes_key: str = ""
    callback_port: int = 8788
    callback_host: str = "0.0.0.0"
    stream_mode: bool = False
    poll_interval: int = 5
    allow_from: List[str] = []
    group_policy: str = "mention"  # mention/all/none
    group_allow_from: List[str] = []
    user_id: str = ""  # 用于发送消息的用户 ID
```

**配置说明**：
- `enabled`：是否启用企业微信
- `corp_id`：企业 ID
- `agent_id`：应用 AgentId
- `secret`：应用 Secret
- `token`：回调 Token
- `encoding_aes_key`：回调 EncodingAESKey
- `callback_port`：回调服务端口
- `callback_host`：回调服务监听地址
- `stream_mode`：是否启用 Stream Mode（长轮询）
- `poll_interval`：轮询间隔（秒）
- `allow_from`：用户 ID 白名单
- `group_policy`：群聊消息响应策略
- `group_allow_from`：群聊白名单
- `user_id`：用于发送消息的用户 ID

### 工作流程

#### 1. 启动流程

```
1. 初始化 WechatWorkCrypto
2. 获取 access_token
3. 启动内嵌 HTTP 回调服务
4. 设置消息处理器
```

```python
async def start(self) -> bool:
    """启动渠道。"""
    # 1. 初始化加解密工具
    self.crypto = WechatWorkCrypto(
        self.config.encoding_aes_key,
        self.config.corp_id
    )
    
    # 2. 获取 access_token
    await self._refresh_access_token()
    
    # 3. 启动 HTTP 回调服务
    self._runner = web.AppRunner(self._app)
    await self._runner.setup()
    site = web.TCPSite(self._runner, self.config.callback_host, self.config.callback_port)
    await site.start()
    
    logger.info(f"[WechatWorkChannel] Started on port {self.config.callback_port}")
    return True
```

#### 2. 消息接收流程

```
1. 接收企业微信回调请求
2. 验证签名
3. 解密消息
4. 解析 XML
5. 消息去重检查
6. 权限检查
7. 调用消息处理器
8. 发送确认消息
```

```python
async def _handle_callback_message(self, request: web.Request) -> web.Response:
    """处理回调消息。"""
    # 1. 立即返回 "success"
    # 2. 创建后台任务异步处理消息
    asyncio.create_task(self._process_callback_async(request))
    return web.Response(text="success")

async def _process_callback_async(self, request: web.Request) -> None:
    """异步处理回调。"""
    # 1. 解析请求体和查询参数
    # 2. 验证签名
    # 3. 解密消息
    # 4. 解析 XML
    # 5. 消息去重检查
    # 6. 权限检查
    # 7. 调用消息处理器
    # 8. 发送确认消息
```

#### 3. 消息发送流程

```
1. 获取 access_token（如果过期则刷新）
2. 构建消息体
3. 调用企业微信 API
4. 处理响应
```

```python
async def send(self, content: str, chat_id: str, is_group: bool = False, **kwargs) -> bool:
    """发送消息。"""
    # 1. 获取 access_token
    if self._is_access_token_expired():
        await self._refresh_access_token()
    
    # 2. 构建消息体
    payload = {
        "touser": "" if is_group else chat_id,
        "chatid": chat_id if is_group else "",
        "msgtype": "text",
        "agentid": self.config.agent_id,
        "text": {
            "content": content
        }
    }
    
    # 3. 调用 API
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={self._access_token}"
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        result = response.json()
        
    # 4. 处理响应
    return result.get("errcode") == 0
```

### 消息去重机制

**目的**：避免重复处理企业微信的重试消息

**实现**：
- 使用 MsgId 作为消息唯一标识
- 使用字典缓存已处理的消息 ID
- 定期清理过期的缓存（TTL：1 小时）

```python
class WechatWorkChannel:
    def __init__(self, ...):
        self._msg_cache: Dict[str, float] = {}
        self._cache_ttl = 3600  # 1 小时
    
    def _is_duplicate_message(self, msg_id: str) -> bool:
        """检查是否为重复消息。"""
        current_time = time.time()
        
        # 清理过期缓存
        self._msg_cache = {
            k: v for k, v in self._msg_cache.items()
            if current_time - v < self._cache_ttl
        }
        
        # 检查是否已处理
        if msg_id in self._msg_cache:
            return True
        
        # 记录消息
        self._msg_cache[msg_id] = current_time
        return False
```

### 权限控制

#### 1. 用户权限检查

```python
def _check_user_permission(self, user_id: str) -> bool:
    """检查用户权限。"""
    # 如果白名单为空，允许所有用户
    if not self.config.allow_from:
        return True
    
    # 检查用户是否在白名单中
    return user_id in self.config.allow_from
```

#### 2. 群聊权限检查

```python
def _check_group_permission(self, chat_id: str, mentioned: bool) -> bool:
    """检查群聊权限。"""
    # 如果群聊不在白名单中，不允许
    if self.config.group_allow_from and chat_id not in self.config.group_allow_from:
        return False
    
    # 根据 group_policy 决定是否响应
    if self.config.group_policy == "mention":
        return mentioned
    elif self.config.group_policy == "all":
        return True
    else:  # none
        return False
```

### Access Token 管理

**目的**：管理和刷新企业微信 API 的 access_token

**实现**：
- 启动时获取 access_token
- 提前 60 秒刷新 access_token
- 失败时自动重试

```python
class WechatWorkChannel:
    def __init__(self, ...):
        self._access_token: str = ""
        self._token_expires_at: float = 0
    
    async def _refresh_access_token(self) -> bool:
        """刷新 access_token。"""
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.config.corp_id}&corpsecret={self.config.secret}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            result = response.json()
        
        if result.get("errcode") == 0:
            self._access_token = result["access_token"]
            self._token_expires_at = time.time() + result["expires_in"] - 60  # 提前 60 秒刷新
            return True
        
        logger.error(f"[WechatWorkChannel] Failed to refresh access_token: {result}")
        return False
    
    def _is_access_token_expired(self) -> bool:
        """检查 access_token 是否过期。"""
        return time.time() >= self._token_expires_at
```

### HTTP 回调服务

**目的**：接收企业微信的回调消息

**实现**：
- 使用 aiohttp 提供 HTTP 服务
- 支持验证接口（用于配置回调 URL）
- 支持消息接收接口

```python
class WechatWorkChannel:
    def __init__(self, ...):
        self._app = web.Application()
        self._app.router.add_get("/wechat/callback", self._handle_verify)
        self._app.router.add_post("/wechat/callback", self._handle_callback_message)
    
    async def _handle_verify(self, request: web.Request) -> web.Response:
        """处理验证请求（用于配置回调 URL）。"""
        msg_signature = request.query.get("msg_signature")
        timestamp = request.query.get("timestamp")
        nonce = request.query.get("nonce")
        echostr = request.query.get("echostr")
        
        # 验证签名
        signature = self.crypto.generate_signature(
            self.config.token,
            timestamp,
            nonce,
            echostr
        )
        
        if signature == msg_signature:
            return web.Response(text=echostr)
        else:
            return web.Response(text="error", status=403)
```

### 消息格式

#### 1. 回调消息格式（XML）

```xml
<xml>
   <ToUserName><![CDATA[toUser]]></ToUserName>
   <FromUserName><![CDATA[fromUser]]></FromUserName>
   <CreateTime>1348831860</CreateTime>
   <MsgType><![CDATA[text]]></MsgType>
   <Content><![CDATA[this is a test]]></Content>
   <MsgId>1234567890123456</MsgId>
   <AgentID>1</AgentID>
</xml>
```

#### 2. 发送消息格式（JSON）

```json
{
   "touser": "UserID",
   "msgtype": "text",
   "agentid": 1,
   "text": {
       "content": "Hello"
   },
   "safe": 0
}
```

### 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 签名验证失败 | 记录日志，跳过处理 |
| 消息解密失败 | 记录日志，返回 success |
| 权限检查失败 | 记录日志，跳过处理 |
| Access Token 刷新失败 | 记录错误，重试 |
| 消息发送失败 | 记录错误，增加错误计数 |

### 扩展性

**添加新渠道**：

```python
from .base import BaseChannel

class NewChannel(BaseChannel):
    """新渠道实现。"""
    
    def __init__(self, config):
        self.config = config
    
    async def start(self) -> bool:
        # 实现启动逻辑
        pass
    
    async def stop(self) -> None:
        # 实现停止逻辑
        pass
    
    async def send(self, content: str, chat_id: str, **kwargs) -> bool:
        # 实现发送逻辑
        pass
    
    def set_message_handler(self, handler: Callable) -> None:
        # 设置消息处理器
        self.message_handler = handler
```

## 相关文档

- [设计总览](./01-设计总览.md) - 项目概述、整体架构、核心目标
- [架构设计](./02-架构设计.md) - 详细的架构设计
- [模块设计-Interactive层](./04-模块设计-Interactive层.md) - 交互层的详细设计
- [技术设计](./07-技术设计.md) - 关键技术点、数据模型、安全设计