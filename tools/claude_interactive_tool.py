#!/usr/bin/env python3
"""
Claude Code Module 交互式体验工具

功能：
- tmux 会话管理：创建、停止、重启、切换、快照
- 消息交互：发送消息、查看状态
- 支持 JSON 输出，方便 AI 调用

使用方法：
    # Tmux 管理
    python tools/claude_interactive_tool.py tmux create <name> [options]
    python tools/claude_interactive_tool.py tmux stop <name>
    python tools/claude_interactive_tool.py tmux restart <name> [options]
    python tools/claude_interactive_tool.py tmux list
    python tools/claude_interactive_tool.py tmux snapshot <name> [--lines N]
    python tools/claude_interactive_tool.py tmux switch <name>

    # 消息交互
    python tools/claude_interactive_tool.py send <message> [options]
    python tools/claude_interactive_tool.py status [--json]

    # 交互模式
    python tools/claude_interactive_tool.py interactive [options]

选项：
    --workspace DIR     工作目录（默认当前目录）
    --json              JSON 格式输出
    --scope MODE        scope 模式：all / reply_only（默认）
    --source NAME       消息来源（默认 "tool"）
    --timeout SECONDS   超时时间（默认 300）
    --lines N           快照行数（默认 50）
"""

import sys
import os
import asyncio
import json
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.modules.claudecode import ClaudeCodeModule
from src.modules.claudecode.monitor import ClaudeCodeState
from src.core.message import Message, MessageContent, MessageType as CoreMessageType

# 设置日志配置
import logging

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 配置日志文件
log_file = log_dir / "claude_tool.log"

# 创建日志格式器
file_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 文件处理器
file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(file_formatter)

# 控制台处理器（静默模式）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)

# 配置根日志
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.handlers.clear()
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# 工具专用日志
logger = logging.getLogger("claude_tool")
logger.setLevel(logging.DEBUG)


# ==================== 退出码定义 ====================
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_ARGS_ERROR = 2
EXIT_CLAUDE_NOT_READY = 3
EXIT_TIMEOUT = 4
EXIT_TMUX_NOT_FOUND = 5
EXIT_TMUX_EXISTS = 6


# ==================== JSON 输出工具 ====================
def output_json(data: Dict[str, Any], success: bool = True, command: str = ""):
    """输出 JSON 格式结果"""
    result = {
        "success": success,
        "timestamp": datetime.now().isoformat(),
    }
    if command:
        result["command"] = command
    if not success and "error" not in data:
        result["error"] = data
    else:
        result["data"] = data
    print(json.dumps(result, ensure_ascii=False, indent=2))


def output_error(code: str, message: str, command: str = "", exit_code: int = EXIT_ERROR):
    """输出错误信息"""
    output_json({"code": code, "message": message}, success=False, command=command)
    return exit_code


# ==================== Mock 消息总线 ====================
class MockMessageBus:
    """模拟消息总线"""

    def __init__(self, callback):
        self.callback = callback

    async def route(self, message: Message):
        """路由消息到回调"""
        if self.callback:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(message)
            else:
                self.callback(message)

    async def broadcast_to_bindings(self, message: Message):
        """广播消息"""
        if self.callback:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(message)
            else:
                self.callback(message)


# ==================== Claude Code 交互控制器 ====================
class ClaudeController:
    """Claude Code 交互控制器"""

    def __init__(self, workspace: str = None, scope: str = "reply_only", source: str = "tool"):
        """初始化

        Args:
            workspace: 工作目录（默认当前目录）
            scope: 回复模式（reply_only / all）
            source: 消息来源
        """
        if workspace:
            self.workspace = Path(workspace).expanduser().absolute()
        else:
            self.workspace = Path.cwd()

        self.current_scope = scope
        self.current_source = source

        self.module: Optional[ClaudeCodeModule] = None
        self.mock_bus: Optional[MockMessageBus] = None
        self.message_history: List[Dict[str, Any]] = []

        self._interrupt_event = asyncio.Event()

    async def connect(self, tmux_session: str) -> Dict[str, Any]:
        """连接到 tmux 会话

        Args:
            tmux_session: tmux 会话名称

        Returns:
            连接结果
        """
        # 检查 tmux 会话是否存在
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", tmux_session],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return {"success": False, "error": "tmux_not_found", "message": f"tmux 会话不存在: {tmux_session}"}
        except FileNotFoundError:
            return {"success": False, "error": "tmux_not_found", "message": "tmux 命令未找到"}

        # 创建模拟消息总线
        self.mock_bus = MockMessageBus(callback=self._on_message)

        # 创建 Claude Code 模块
        self.module = ClaudeCodeModule(
            module_id=f"claude_tool_{tmux_session}",
            tmux_session=tmux_session,
            workspace=str(self.workspace)
        )
        
        # 手动设置消息总线
        self.module._bus = self.mock_bus

        # 启动模块
        try:
            await self.module.start()
            logger.info(f"已连接到 tmux 会话: {tmux_session}")
            return {"success": True, "message": f"已连接到 tmux 会话: {tmux_session}"}
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return {"success": False, "error": "connection_failed", "message": str(e)}

    async def disconnect(self):
        """断开连接"""
        if self.module:
            try:
                await self.module.stop()
            except Exception as e:
                logger.error(f"断开连接失败: {e}")
            finally:
                self.module = None

        self.mock_bus = None
        self.message_history.clear()

    def _on_message(self, message: Message):
        """消息回调

        Args:
            message: 接收到的消息
        """
        # 记录消息历史
        content = ""
        if message.content and message.content.text:
            content = message.content.text

        self.message_history.append({
            "id": message.id,
            "type": message.metadata.get("type", "unknown") if message.metadata else "unknown",
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        logger.debug(f"收到消息: {message.metadata.get('type', 'unknown')} - {content[:50]}...")

    async def send_message(self, content: str, timeout: float = 300) -> Dict[str, Any]:
        """发送消息并等待回复

        Args:
            content: 消息内容
            timeout: 超时时间

        Returns:
            发送结果
        """
        if not self.module:
            return {"success": False, "error": "not_connected", "message": "未连接到 tmux 会话"}

        # 检查就绪状态
        is_ready = await self.module.controller.check_claude_ready()
        if not is_ready:
            return {"success": False, "error": "claude_not_ready", "message": "Claude Code 未就绪"}

        # 清空历史
        self.message_history.clear()

        # 创建消息
        msg = Message(
            id=Message.generate_id(),
            type=CoreMessageType.TEXT,
            content=MessageContent(type=CoreMessageType.TEXT, text=content),
            from_module=self.current_source,
            metadata={"scope": self.current_scope}
        )

        # 发送消息
        await self.mock_bus.route(msg)

        # 等待回复完成
        completed = await self._wait_for_complete(timeout)

        if not completed:
            return {"success": False, "error": "timeout", "message": "等待回复超时"}

        # 收集回复
        replies = []
        for msg in self.message_history:
            if msg["type"] == "reply":
                replies.append({"type": "reply", "content": msg["content"]})
            elif msg["type"] == "complete":
                replies.append({"type": "complete", "content": msg["content"]})

        return {
            "success": True,
            "replies": replies,
            "reply_count": len([r for r in replies if r["type"] == "reply"]),
            "duration": self.module.generating_duration if self.module else 0
        }

    async def _wait_for_complete(self, timeout: float = 300) -> bool:
        """等待回复完成"""
        if not self.module:
            return False

        self._interrupt_event.clear()
        elapsed = 0.0
        check_interval = 1.0

        # 等待消息
        while elapsed < timeout and len(self.message_history) == 0:
            if self._interrupt_event.is_set():
                return False
            await asyncio.sleep(check_interval)
            elapsed += check_interval

        if len(self.message_history) == 0:
            return False

        # 等待状态变为 IDLE
        stable_count = 0
        while elapsed < timeout:
            if self._interrupt_event.is_set():
                return False

            await asyncio.sleep(check_interval)
            elapsed += check_interval

            current_state = self.module.state
            message_count = len(self.message_history)

            if current_state == ClaudeCodeState.IDLE:
                await asyncio.sleep(2)
                if self.module.state == ClaudeCodeState.IDLE:
                    return True

            # 稳定检查
            if message_count == len(self.message_history):
                stable_count += 1
            else:
                stable_count = 0

            if stable_count >= 30 and current_state == ClaudeCodeState.IDLE:
                return True

        return False

    def interrupt(self):
        """中断等待"""
        self._interrupt_event.set()

    async def get_status(self) -> Dict[str, Any]:
        """获取状态

        Returns:
            状态信息
        """
        if not self.module:
            return {"success": False, "error": "not_connected", "message": "未连接到 tmux 会话"}

        return {
            "success": True,
            "state": self.module.state.value,
            "generating_duration": self.module.generating_duration,
            "message_count": len(self.message_history),
            "workspace": str(self.workspace),
            "tmux_session": self.module.controller.tmux_session
        }


# ==================== Tmux 管理 ====================
async def tmux_list():
    """列出所有 tmux 会话"""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            output_json({"sessions": []})
            return EXIT_SUCCESS

        sessions = []
        for line in result.stdout.strip().split('\n'):
            if line:
                # 格式: session_name: windows (created ...) [width x height]
                parts = line.split(':')
                if parts:
                    session_name = parts[0]
                    sessions.append({"name": session_name, "status": "active"})

        output_json({"sessions": sessions})
        return EXIT_SUCCESS
    except FileNotFoundError:
        return output_error("tmux_not_found", "tmux 命令未找到", "tmux list")


async def tmux_create(name: str, workspace: str = None):
    """创建 tmux 会话"""
    try:
        # 检查会话是否已存在
        result = subprocess.run(
            ["tmux", "has-session", "-t", name],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return output_error("tmux_exists", f"tmux 会话已存在: {name}", "tmux create", EXIT_TMUX_EXISTS)

        # 确定工作目录
        if workspace:
            work_dir = Path(workspace).expanduser().absolute()
        else:
            work_dir = Path.cwd()

        if not work_dir.exists():
            return output_error("workspace_not_found", f"工作目录不存在: {work_dir}", "tmux create")

        # 创建会话
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", name, "-c", str(work_dir)],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return output_error("tmux_create_failed", f"创建 tmux 会话失败: {result.stderr}", "tmux create")

        # 启动 Claude Code
        subprocess.run(
            ["tmux", "send-keys", "-t", name, "claude", "Enter"],
            capture_output=True
        )

        output_json({
            "session": name,
            "workspace": str(work_dir),
            "message": f"已创建 tmux 会话: {name}"
        })
        return EXIT_SUCCESS
    except FileNotFoundError:
        return output_error("tmux_not_found", "tmux 命令未找到", "tmux create")


async def tmux_stop(name: str):
    """停止 tmux 会话"""
    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", name],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return output_error("tmux_stop_failed", f"停止 tmux 会话失败: {result.stderr}", "tmux stop")

        output_json({
            "session": name,
            "message": f"已停止 tmux 会话: {name}"
        })
        return EXIT_SUCCESS
    except FileNotFoundError:
        return output_error("tmux_not_found", "tmux 命令未找到", "tmux stop")


async def tmux_snapshot(name: str, lines: int = 50):
    """获取 tmux 会话快照"""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", name, "-p", "-S", f"-{lines}"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            return output_error("tmux_snapshot_failed", f"获取快照失败: {result.stderr}", "tmux snapshot")

        output_json({
            "session": name,
            "lines": lines,
            "content": result.stdout
        })
        return EXIT_SUCCESS
    except FileNotFoundError:
        return output_error("tmux_not_found", "tmux 命令未找到", "tmux snapshot")


# ==================== 主程序 ====================
async def main():
    parser = argparse.ArgumentParser(description="Claude Code Module 交互式体验工具")
    parser.add_argument("--workspace", help="工作目录（默认当前目录）")
    parser.add_argument("--scope", choices=["all", "reply_only"], default="reply_only", help="回复模式")
    parser.add_argument("--source", default="tool", help="消息来源")
    parser.add_argument("--timeout", type=int, default=300, help="超时时间（秒）")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--tmux-session", help="指定 tmux 会话名称")

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # tmux 子命令
    tmux_parser = subparsers.add_parser("tmux", help="tmux 会话管理")
    tmux_subparsers = tmux_parser.add_subparsers(dest="tmux_command", help="tmux 子命令")

    tmux_create_parser = tmux_subparsers.add_parser("create", help="创建 tmux 会话")
    tmux_create_parser.add_argument("name", help="会话名称")
    tmux_create_parser.add_argument("--workspace", help="工作目录")

    tmux_stop_parser = tmux_subparsers.add_parser("stop", help="停止 tmux 会话")
    tmux_stop_parser.add_argument("name", help="会话名称")

    tmux_list_parser = tmux_subparsers.add_parser("list", help="列出 tmux 会话")

    tmux_snapshot_parser = tmux_subparsers.add_parser("snapshot", help="获取 tmux 会话快照")
    tmux_snapshot_parser.add_argument("name", help="会话名称")
    tmux_snapshot_parser.add_argument("--lines", type=int, default=50, help="行数")

    # send 子命令
    send_parser = subparsers.add_parser("send", help="发送消息")
    send_parser.add_argument("message", help="消息内容")

    # status 子命令
    status_parser = subparsers.add_parser("status", help="查看状态")

    # interactive 子命令
    interactive_parser = subparsers.add_parser("interactive", help="交互模式")

    args = parser.parse_args()

    # JSON 输出模式
    if args.json or args.command in ["tmux"]:
        # 已经是 JSON 输出
        pass
    else:
        # 非交互模式需要指定命令
        if not args.command:
            parser.print_help()
            return EXIT_ARGS_ERROR

    # 处理 tmux 命令
    if args.command == "tmux":
        if args.tmux_command == "list":
            return await tmux_list()
        elif args.tmux_command == "create":
            return await tmux_create(args.name, args.workspace)
        elif args.tmux_command == "stop":
            return await tmux_stop(args.name)
        elif args.tmux_command == "snapshot":
            return await tmux_snapshot(args.name, args.lines)
        else:
            parser.print_help()
            return EXIT_ARGS_ERROR

    # 处理其他命令（需要连接到 tmux 会话）
    if not args.tmux_session:
        return output_error("args_error", "需要指定 --tmux-session 参数", args.command or "")

    controller = ClaudeController(
        workspace=args.workspace,
        scope=args.scope,
        source=args.source
    )

    try:
        # 连接到 tmux 会话
        connect_result = await controller.connect(args.tmux_session)
        if not connect_result["success"]:
            return output_error(connect_result["error"], connect_result["message"], args.command)

        # 处理命令
        if args.command == "send":
            result = await controller.send_message(args.message, args.timeout)
            if args.json:
                output_json(result)
            else:
                if result["success"]:
                    print(f"✅ 发送成功")
                    print(f"回复数量: {result['reply_count']}")
                    print(f"耗时: {result['duration']}s")
                    for reply in result["replies"]:
                        print(f"\n{reply['type']}: {reply['content']}")
                else:
                    print(f"❌ 发送失败: {result.get('message', '未知错误')}")
            return EXIT_SUCCESS if result["success"] else EXIT_ERROR

        elif args.command == "status":
            status = await controller.get_status()
            if args.json:
                output_json(status)
            else:
                print(f"状态: {status['state']}")
                print(f"生成耗时: {status['generating_duration']}s")
                print(f"消息数量: {status['message_count']}")
                print(f"工作目录: {status['workspace']}")
                print(f"tmux 会话: {status['tmux_session']}")
            return EXIT_SUCCESS

        elif args.command == "interactive":
            print(f"已连接到 tmux 会话: {args.tmux_session}")
            print("输入消息（输入 'exit' 退出）：")

            while True:
                try:
                    message = input("> ").strip()
                    if message == "exit":
                        break
                    if not message:
                        continue

                    result = await controller.send_message(message, args.timeout)
                    if result["success"]:
                        print(f"✅ 回复数量: {result['reply_count']}, 耗时: {result['duration']}s")
                        for reply in result["replies"]:
                            print(f"\n{reply['content']}")
                    else:
                        print(f"❌ {result.get('message', '未知错误')}")

                except KeyboardInterrupt:
                    print("\n退出交互模式")
                    break

            return EXIT_SUCCESS

        else:
            parser.print_help()
            return EXIT_ARGS_ERROR

    finally:
        await controller.disconnect()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
