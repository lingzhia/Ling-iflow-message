#!/usr/bin/env python3
"""测试企业微信回调处理。"""

import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import base64
from Crypto.Random import get_random_bytes
from Crypto.Hash import SHA1

# 配置
TOKEN = "UdP3NJDU3T86VBktdtw"
ENCODING_AES_KEY = "eCrMvRSZjACg4uSJL4h2fP5o7WeJ8UKgaDidHwocruI"
CORP_ID = "ww6e6c8f55511c0100"

def decrypt_message(encrypted):
    """解密企业微信消息。"""
    # EncodingAESKey 补充 '=' 后 Base64 解码
    aes_key = base64.b64decode(ENCODING_AES_KEY + '=')
    iv = aes_key[:16]
    
    # AES-256-CBC 解密
    encrypted_data = base64.b64decode(encrypted)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    
    # 解析消息格式：random(16) + msgLen(4) + msg + corpId
    msg_len = int.from_bytes(decrypted[16:20], byteorder='big')
    msg = decrypted[20:20 + msg_len].decode('utf-8')
    corp_id = decrypted[20 + msg_len:].decode('utf-8')
    
    return msg

def generate_signature(timestamp, nonce, encrypted):
    """生成签名。"""
    arr = [TOKEN, timestamp, nonce, encrypted]
    arr.sort()
    str_data = ''.join(arr)
    return SHA1.new(str_data.encode('utf-8')).hexdigest()

def encrypt_message(message):
    """加密消息。"""
    aes_key = base64.b64decode(ENCODING_AES_KEY + '=')
    iv = aes_key[:16]
    
    random = get_random_bytes(16)
    msg_len = len(message)
    len_buf = msg_len.to_bytes(4, byteorder='big')
    
    plain_text = random + len_buf + message.encode('utf-8') + CORP_ID.encode('utf-8')
    
    # PKCS7 填充
    pad_len = 32 - (len(plain_text) % 32)
    padded = plain_text + bytes([pad_len] * pad_len)
    
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(padded)
    
    return base64.b64encode(encrypted).decode('utf-8')

def test_callback():
    """测试回调。"""
    # 构造XML消息
    xml_msg = f"""<xml>
<ToUserName><![CDATA[YuLingZhi]]></ToUserName>
<FromUserName><![CDATA[YuLingZhi]]></FromUserName>
<CreateTime>{int(__import__('time').time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[这是一条测试消息]]></Content>
<MsgId>123456789</MsgId>
</xml>"""
    
    # 加密
    encrypted = encrypt_message(xml_msg)
    
    # 生成签名
    timestamp = str(int(__import__('time').time()))
    nonce = "test_nonce"
    signature = generate_signature(timestamp, nonce, encrypted)
    
    # 发送POST请求
    import requests
    url = "http://localhost:8787/wechat/callback"
    params = {
        "msg_signature": signature,
        "timestamp": timestamp,
        "nonce": nonce
    }
    
    print(f"发送POST请求到 {url}")
    print(f"参数: {params}")
    print(f"加密消息长度: {len(encrypted)}")
    
    response = requests.post(url, params=params, data=encrypted)
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")

if __name__ == "__main__":
    test_callback()