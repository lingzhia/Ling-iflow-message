#!/usr/bin/env python3
"""
从日志中提取完整的对话链路

功能：
1. 提取企业微信消息
2. 提取发送到 iflow 的消息
3. 提取 iflow 的回复
4. 提取发送回企业微信的消息
5. 按时间顺序组织成完整的对话链路
"""

import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import json


class LogEntry:
    """日志条目"""
    def __init__(self, timestamp: str, level: str, module: str, message: str, raw: str):
        self.timestamp = timestamp
        self.level = level
        self.module = module
        self.message = message
        self.raw = raw


class Conversation:
    """完整的对话链路"""
    def __init__(self, conversation_id: str):
        self.id = conversation_id
        self.receive_wechat: Optional[Dict] = None  # 收到企业微信消息
        self.send_iflow: Optional[Dict] = None      # 发送到 iflow
        self.receive_iflow: Optional[Dict] = None   # iflow 回复
        self.send_wechat: Optional[Dict] = None     # 发送回企业微信
        self.timestamp: Optional[str] = None
    
    def to_dict(self):
        """转换为字典"""
        return {
            "conversation_id": self.id,
            "timestamp": self.timestamp,
            "receive_wechat": self.receive_wechat,
            "send_iflow": self.send_iflow,
            "receive_iflow": self.receive_iflow,
            "send_wechat": self.send_wechat
        }
    
    def print_conversation(self):
        """打印对话内容"""
        print("=" * 80)
        print(f"对话 ID: {self.id}")
        print(f"时间: {self.timestamp}")
        print("=" * 80)
        
        if self.receive_wechat:
            print("\n【1. 收到企业微信消息】")
            for key, value in self.receive_wechat.items():
                print(f"  {key}: {value}")
        
        if self.send_iflow:
            print("\n【2. 发送到 iflow】")
            for key, value in self.send_iflow.items():
                print(f"  {key}: {value}")
        
        if self.receive_iflow:
            print("\n【3. iflow 回复】")
            for key, value in self.receive_iflow.items():
                if key == "full_message":
                    continue  # 跳过完整消息（包含头部）
                print(f"  {key}: {value}")
        
        if self.send_wechat:
            print("\n【4. 发送回企业微信】")
            for key, value in self.send_wechat.items():
                print(f"  {key}: {value}")
        
        print("\n" + "=" * 80 + "\n")


class ConversationExtractor:
    """对话提取器"""
    
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.entries: List[LogEntry] = []
        self.conversations: List[Conversation] = []
    
    def parse_log(self):
        """解析日志文件"""
        print(f"正在解析日志文件: {self.log_file}")
        
        # 日志格式: 2026-03-10 21:17:31 | INFO     | module:function:line | message
        pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.\d+)?\s+\|\s+(\w+)\s+\|\s+([^|]+)\|\s+(.*)'
        )
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # 合并多行日志（不以时间戳开头的行属于上一条日志的续行）
                if line and not re.match(r'^\d{4}-\d{2}-\d{2}', line):
                    # 这是一个续行，添加到上一条日志的 message 中
                    if self.entries:
                        self.entries[-1].message += "\n" + line
                        self.entries[-1].raw += "\n" + line
                else:
                    # 这是一个新日志行
                    match = pattern.match(line)
                    if match:
                        entry = LogEntry(
                            timestamp=match.group(1),
                            level=match.group(2),
                            module=match.group(3).strip(),
                            message=match.group(4),
                            raw=line
                        )
                        self.entries.append(entry)
                
                i += 1
        
        print(f"解析完成，共 {len(self.entries)} 条日志")
    
    def extract_conversations(self):
        """提取对话链路"""
        print("正在提取对话链路...")
        
        current_conversation = None
        conversation_id = 0
        
        for entry in self.entries:
            # 检测收到消息（处理命令）
            if "处理命令:" in entry.message and "type=run" in entry.message:
                if current_conversation and not current_conversation.send_wechat:
                    # 上一个对话未完成，保存
                    self.conversations.append(current_conversation)
                
                conversation_id += 1
                current_conversation = Conversation(f"conv_{conversation_id}")
                current_conversation.timestamp = entry.timestamp
                current_conversation.receive_wechat = self._parse_handle_message(entry)
            
            # 检测发送到 iflow
            elif "发送命令到 iflow" in entry.message:
                if current_conversation:
                    current_conversation.send_iflow = {
                        "timestamp": entry.timestamp,
                        "content": entry.message
                    }
            
            # 检测 iflow 回复（后台监控）
            elif "检测到 iflow 交互界面回复" in entry.message and "完整回复:" in entry.message:
                if current_conversation:
                    current_conversation.receive_iflow = self._parse_background_monitor(entry)
            
            # 检测发送回企业微信
            elif "通过分发器发送消息到企业微信" in entry.message:
                if current_conversation:
                    current_conversation.send_wechat = {
                        "timestamp": entry.timestamp,
                        "content": entry.message
                    }
        
        # 保存最后一个对话
        if current_conversation:
            self.conversations.append(current_conversation)
        
        print(f"提取完成，共 {len(self.conversations)} 条对话链路")
    
    def _parse_wechat_message(self, entry: LogEntry) -> Dict:
        """解析企业微信消息"""
        data = {
            "timestamp": entry.timestamp
        }
        
        # 解析多行消息
        lines = entry.message.split("\n")
        for line in lines:
            if "来源:" in line:
                data["from_user"] = line.split("来源:")[1].strip()
            elif "类型:" in line:
                data["chat_type"] = line.split("类型:")[1].strip()
            elif "消息类型:" in line:
                data["msg_type"] = line.split("消息类型:")[1].strip()
            elif "消息内容:" in line:
                data["content"] = line.split("消息内容:")[1].strip()
        
        return data
    
    def _parse_handle_message(self, entry: LogEntry) -> Dict:
        """解析处理命令日志"""
        data = {
            "timestamp": entry.timestamp
        }
        
        # 解析: 处理命令: type=run, command=你好
        if "command=" in entry.message:
            command = entry.message.split("command=")[1]
            data["command"] = command
        
        return data
    
    def _parse_background_monitor(self, entry: LogEntry) -> Dict:
        """解析后台监控日志"""
        data = {
            "timestamp": entry.timestamp
        }
        
        # 解析多行消息
        lines = entry.message.split("\n")
        content_lines = []
        
        for line in lines:
            if "用户问题:" in line:
                data["user_question"] = line.split("用户问题:")[1].strip()
            elif "消息数量:" in line:
                data["message_count"] = line.split("消息数量:")[1].strip()
            elif "完整回复:" in line:
                # 完整回复可能在同一行或后续行
                full_reply = line.split("完整回复:")[1].strip()
                if full_reply:
                    content_lines.append(full_reply)
            elif line and not line.startswith("  "):
                # 后续内容行
                content_lines.append(line)
        
        if content_lines:
            full_message = "\n".join(content_lines)
            data["full_message"] = full_message
            
            # 提取真实的 iflow 回复（去除系统添加的头部）
            # 头部格式: 🔔 iflow交互模式请求：原消息=[xxx]，当前回复完成，回复结果如下：
            if "回复结果如下：" in full_message:
                # 提取"回复结果如下："之后的内容
                iflow_reply = full_message.split("回复结果如下：", 1)[1].strip()
                data["content"] = iflow_reply
            else:
                data["content"] = full_message
        
        return data
    
    def _parse_wechat_send(self, entry: LogEntry) -> Dict:
        """解析发送到企业微信的消息"""
        data = {
            "timestamp": entry.timestamp
        }
        
        # 解析多行消息
        lines = entry.message.split("\n")
        content_lines = []
        for line in lines:
            if "接收者:" in line:
                data["to_user"] = line.split("接收者:")[1].strip()
            elif "类型:" in line:
                data["chat_type"] = line.split("类型:")[1].strip()
            elif "消息ID:" in line:
                data["msg_id"] = line.split("消息ID:")[1].strip()
            elif "消息内容:" in line:
                # 消息内容可能在同一行或后续行
                content = line.split("消息内容:")[1].strip()
                if content:
                    content_lines.append(content)
            elif line and not line.startswith("  "):
                # 后续内容行
                content_lines.append(line)
        
        if content_lines:
            data["content"] = "\n".join(content_lines)
        
        return data
    
    def _parse_iflow_reply(self, entry: LogEntry) -> Dict:
        """解析 iflow 回复"""
        data = {
            "timestamp": entry.timestamp
        }
        
        # 解析多行消息
        lines = entry.message.split("\n")
        content_lines = []
        for line in lines:
            if "用户问题:" in line:
                data["user_question"] = line.split("用户问题:")[1].strip()
            elif "消息数量:" in line:
                data["message_count"] = line.split("消息数量:")[1].strip()
            elif "完整回复:" in line:
                # 完整回复可能在同一行或后续行
                content = line.split("完整回复:")[1].strip()
                if content:
                    content_lines.append(content)
            elif line and not line.startswith("  "):
                # 后续内容行
                content_lines.append(line)
        
        if content_lines:
            data["content"] = "\n".join(content_lines)
        
        return data
    
    def print_all_conversations(self, limit: int = 10):
        """打印所有对话"""
        print(f"\n显示最近 {min(limit, len(self.conversations))} 条对话\n")
        
        for conv in self.conversations[-limit:]:
            conv.print_conversation()
    
    def export_json(self, output_file: str):
        """导出为 JSON"""
        data = [conv.to_dict() for conv in self.conversations]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"已导出到: {output_file}")
    
    def export_markdown(self, output_file: str):
        """导出为 Markdown"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 对话记录\n\n")
            
            for conv in self.conversations:
                f.write(f"## 对话 ID: {conv.id}\n\n")
                f.write(f"**时间:** {conv.timestamp}\n\n")
                
                if conv.receive_wechat:
                    f.write("### 1. 收到企业微信消息\n\n")
                    for key, value in conv.receive_wechat.items():
                        f.write(f"- **{key}:** {value}\n")
                    f.write("\n")
                
                if conv.send_iflow:
                    f.write("### 2. 发送到 iflow\n\n")
                    f.write(f"- **时间:** {conv.send_iflow.get('timestamp', '')}\n")
                    f.write(f"- **内容:** {conv.send_iflow.get('content', '')}\n\n")
                
                if conv.receive_iflow:
                    f.write("### 3. iflow 回复\n\n")
                    for key, value in conv.receive_iflow.items():
                        f.write(f"- **{key}:** {value}\n")
                    f.write("\n")
                
                if conv.send_wechat:
                    f.write("### 4. 发送回企业微信\n\n")
                    for key, value in conv.send_wechat.items():
                        f.write(f"- **{key}:** {value}\n")
                    f.write("\n")
                
                f.write("---\n\n")
        
        print(f"已导出到: {output_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="从日志中提取完整的对话链路")
    parser.add_argument(
        "log_file",
        help="日志文件路径"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="显示最近 N 条对话 (默认: 10)"
    )
    parser.add_argument(
        "--export-json", "-j",
        help="导出为 JSON 文件"
    )
    parser.add_argument(
        "--export-md", "-m",
        help="导出为 Markdown 文件"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="显示所有对话"
    )
    
    args = parser.parse_args()
    
    # 检查日志文件
    if not Path(args.log_file).exists():
        print(f"错误: 日志文件不存在: {args.log_file}")
        return
    
    # 创建提取器
    extractor = ConversationExtractor(args.log_file)
    
    # 解析日志
    extractor.parse_log()
    
    # 提取对话
    extractor.extract_conversations()
    
    # 显示对话
    if args.all:
        extractor.print_all_conversations(limit=len(extractor.conversations))
    else:
        extractor.print_all_conversations(limit=args.limit)
    
    # 导出文件
    if args.export_json:
        extractor.export_json(args.export_json)
    
    if args.export_md:
        extractor.export_markdown(args.export_md)


if __name__ == "__main__":
    main()
