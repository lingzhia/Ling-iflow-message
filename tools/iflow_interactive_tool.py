#!/usr/bin/env python3
"""
IFlowModule 交互式体验工具

功能：
- tmux 会话管理：创建、停止、重启、切换、快照
- 消息交互：发送消息、查看状态
- 支持 JSON 输出，方便 AI 调用

使用方法：
    # Tmux 管理
    python tools/iflow_interactive_tool.py tmux create <name> [options]
    python tools/iflow_interactive_tool.py tmux stop <name>
    python tools/iflow_interactive_tool.py tmux restart <name> [options]
    python tools/iflow_interactive_tool.py tmux list
    python tools/iflow_interactive_tool.py tmux snapshot <name> [--lines N]
    python tools/iflow_interactive_tool.py tmux switch <name>

    # 消息交互
    python tools/iflow_interactive_tool.py send <message> [options]
    python tools/iflow_interactive_tool.py status [--json]

    # 交互模式
    python tools/iflow_interactive_tool.py interactive [options]

    # 兼容旧命令（保持向后兼容）
    python tools/iflow_interactive_tool.py --message "你好" [选项]

选项：
    --workspace DIR     工作目录（默认 ~/.iflow）
    --model NAME        模型名称（默认 kimi-k2.5）
    --mode MODE         运行模式：smart（智能）/ yolo（默认 smart）
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

from src.modules.iflow import IFlowModule
from src.modules.iflow.monitor import IFlowState
from src.core.message import Message, MessageContent, MessageType as CoreMessageType

# 设置日志配置
import logging

# 创建日志目录
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# 配置日志文件
log_file = log_dir / "iflow_tool.log"

# 创建日志格式器
file_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 文件处理器
file_handler = logging.FileHandler(log_file, encoding='utf-8')
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
logger = logging.getLogger("iflow_tool")
logger.setLevel(logging.DEBUG)


# ==================== 退出码定义 ====================
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_ARGS_ERROR = 2
EXIT_IFLOW_NOT_READY = 3
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


# ==================== IFlow Session 控制器 ====================
class SessionController:
    """IFlow 会话文件管理器
    
    管理工作目录下的 session-*.jsonl 文件
    """
    
    def __init__(self, workspace: str = None):
        """初始化
        
        Args:
            workspace: iflow 工作目录（默认 ~/.iflow）
        """
        if workspace:
            self.workspace = Path(workspace).expanduser().absolute()
        else:
            self.workspace = Path.home() / ".iflow"
        
        self.projects_dir = self.workspace / "projects"
    
    def _get_project_dir(self, cwd: str = None) -> Path:
        """获取项目目录
        
        Args:
            cwd: 当前工作目录（None 则使用当前目录）
            
        Returns:
            项目目录路径
        """
        if cwd:
            cwd_path = Path(cwd).absolute()
            # 将路径转换为 iflow 格式：/path/to/project -> -path-to-project
            dir_name = "-" + str(cwd_path).replace("/", "-").lstrip("-")
        else:
            # 使用当前工作目录
            cwd_path = Path.cwd()
            dir_name = "-" + str(cwd_path).replace("/", "-").lstrip("-")
        
        return self.projects_dir / dir_name
    
    def list_sessions(self, cwd: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """列出会话文件
        
        Args:
            cwd: 工作目录
            limit: 最大返回数量
            
        Returns:
            会话文件列表
        """
        project_dir = self._get_project_dir(cwd)
        
        if not project_dir.exists():
            return []
        
        sessions = []
        for session_file in sorted(project_dir.glob("session-*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            stat = session_file.stat()
            sessions.append({
                "name": session_file.name,
                "path": str(session_file),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        return sessions
    
    def get_current_session(self, cwd: str = None) -> Optional[Dict[str, Any]]:
        """获取最新的会话文件
        
        Args:
            cwd: 工作目录
            
        Returns:
            最新会话信息
        """
        sessions = self.list_sessions(cwd, limit=1)
        return sessions[0] if sessions else None
    
    def create_new_session(self, cwd: str = None) -> Dict[str, Any]:
        """创建新会话（清除上下文）
        
        通过删除当前会话文件来实现
        
        Args:
            cwd: 工作目录
            
        Returns:
            操作结果
        """
        project_dir = self._get_project_dir(cwd)
        
        if not project_dir.exists():
            return {"success": True, "message": "项目目录不存在，无需清理"}
        
        # 删除所有会话文件
        deleted = []
        for session_file in project_dir.glob("session-*.jsonl"):
            session_file.unlink()
            deleted.append(session_file.name)
        
        return {
            "success": True,
            "deleted_sessions": deleted,
            "message": f"已删除 {len(deleted)} 个会话文件，下次对话将开始新会话"
        }
    
    def view_session(self, session_name: str = None, cwd: str = None, 
                     lines: int = 50) -> Dict[str, Any]:
        """查看会话内容
        
        Args:
            session_name: 会话文件名（None 则使用最新的）
            cwd: 工作目录
            lines: 显示行数
            
        Returns:
            会话内容
        """
        project_dir = self._get_project_dir(cwd)
        
        if not project_dir.exists():
            return {"success": False, "error": "project_not_found", "message": "项目目录不存在"}
        
        if session_name:
            session_file = project_dir / session_name
            if not session_file.exists():
                return {"success": False, "error": "session_not_found", "message": f"会话文件 {session_name} 不存在"}
        else:
            # 使用最新的会话
            sessions = self.list_sessions(cwd, limit=1)
            if not sessions:
                return {"success": False, "error": "no_sessions", "message": "没有会话文件"}
            session_file = Path(sessions[0]["path"])
        
        try:
            content_lines = []
            with open(session_file, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= lines:
                        break
                    try:
                        data = json.loads(line.strip())
                        role = data.get("role", "unknown")
                        content = data.get("content", [{}])[0].get("text", "")[:200] if data.get("content") else ""
                        content_lines.append({"role": role, "content": content, "line": i + 1})
                    except json.JSONDecodeError:
                        content_lines.append({"role": "raw", "content": line.strip()[:200], "line": i + 1})
            
            return {
                "success": True,
                "session": session_file.name,
                "total_lines": sum(1 for _ in open(session_file, "r", encoding="utf-8")),
                "content": content_lines
            }
        except Exception as e:
            return {"success": False, "error": "read_error", "message": str(e)}


# ==================== Tmux 控制器 ====================
class TmuxController:
    """Tmux 会话控制器"""
    
    def __init__(self):
        self._sessions_cache: Dict[str, Dict] = {}
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有 tmux 会话"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "list-sessions", "-F", 
                "#{session_name}|#{session_created}|#{session_attached}|#{session_windows}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return []
            
            sessions = []
            for line in stdout.decode().strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) >= 4:
                    sessions.append({
                        "name": parts[0],
                        "created": int(parts[1]) if parts[1].isdigit() else 0,
                        "attached": parts[2] == "1",
                        "windows": int(parts[3]) if parts[3].isdigit() else 0
                    })
            return sessions
        except Exception as e:
            logger.error(f"列出 tmux 会话失败: {e}")
            return []
    
    async def session_exists(self, name: str) -> bool:
        """检查会话是否存在"""
        proc = await asyncio.create_subprocess_exec(
            "tmux", "has-session", "-t", name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        return proc.returncode == 0
    
    async def create_session(self, name: str, workspace: str = None, 
                            model: str = None, mode: str = "smart") -> Dict[str, Any]:
        """创建 tmux 会话并启动 iflow
        
        Args:
            name: 会话名称
            workspace: 工作目录
            model: 模型名称
            mode: 运行模式（smart/yolo）
            
        Returns:
            创建结果
        """
        # 检查会话是否已存在
        if await self.session_exists(name):
            return {"success": False, "error": "session_exists", "message": f"会话 {name} 已存在"}
        
        # 工作目录
        if workspace:
            workspace = str(Path(workspace).expanduser().absolute())
        else:
            workspace = str(Path.home() / ".iflow")
        
        # 确保 iflow 工作目录存在
        Path(workspace).mkdir(parents=True, exist_ok=True)
        
        try:
            # 创建 tmux 会话
            proc = await asyncio.create_subprocess_exec(
                "tmux", "new-session", "-d", "-s", name, "-c", workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return {"success": False, "error": "tmux_create_failed", 
                        "message": f"创建 tmux 会话失败: {stderr.decode()}"}
            
            # 构建 iflow 命令
            iflow_cmd = ["iflow"]
            if model:
                iflow_cmd.extend(["--model", model])
            if mode == "yolo":
                iflow_cmd.append("--yolo")
            
            # 在 tmux 中启动 iflow
            proc = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", name, " ".join(iflow_cmd), "C-m",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            # 等待 iflow 启动
            await asyncio.sleep(3)
            
            return {
                "success": True,
                "session": name,
                "workspace": workspace,
                "model": model,
                "mode": mode,
                "message": f"会话 {name} 创建成功，iflow 已启动"
            }
            
        except Exception as e:
            return {"success": False, "error": "exception", "message": str(e)}
    
    async def stop_session(self, name: str) -> Dict[str, Any]:
        """停止 tmux 会话"""
        if not await self.session_exists(name):
            return {"success": False, "error": "not_found", "message": f"会话 {name} 不存在"}
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "tmux", "kill-session", "-t", name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return {"success": False, "error": "kill_failed", 
                        "message": f"停止会话失败: {stderr.decode()}"}
            
            return {"success": True, "session": name, "message": f"会话 {name} 已停止"}
            
        except Exception as e:
            return {"success": False, "error": "exception", "message": str(e)}
    
    async def restart_session(self, name: str, model: str = None, 
                              mode: str = None) -> Dict[str, Any]:
        """重启 tmux 会话中的 iflow
        
        注意：重启 iflow 进程，不是重启 tmux 会话
        """
        if not await self.session_exists(name):
            return {"success": False, "error": "not_found", "message": f"会话 {name} 不存在"}
        
        try:
            # 发送 Ctrl+C 停止 iflow
            proc = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", name, "C-c",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            await asyncio.sleep(1)
            
            # 构建 iflow 命令
            iflow_cmd = ["iflow"]
            if model:
                iflow_cmd.extend(["--model", model])
            if mode == "yolo":
                iflow_cmd.append("--yolo")
            
            # 启动 iflow
            proc = await asyncio.create_subprocess_exec(
                "tmux", "send-keys", "-t", name, " ".join(iflow_cmd), "C-m",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            # 等待 iflow 启动
            await asyncio.sleep(3)
            
            return {
                "success": True, 
                "session": name,
                "model": model,
                "mode": mode,
                "message": f"会话 {name} 中的 iflow 已重启"
            }
            
        except Exception as e:
            return {"success": False, "error": "exception", "message": str(e)}
    
    async def get_snapshot(self, name: str, lines: int = 50) -> Dict[str, Any]:
        """获取 tmux 会话快照"""
        if not await self.session_exists(name):
            return {"success": False, "error": "not_found", "message": f"会话 {name} 不存在"}
        
        try:
            # 获取 tmux 输出
            proc = await asyncio.create_subprocess_exec(
                "tmux", "capture-pane", "-t", name, "-p", "-S", f"-{lines}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return {"success": False, "error": "capture_failed", 
                        "message": f"获取快照失败: {stderr.decode()}"}
            
            content = stdout.decode()
            content_lines = content.strip().split('\n')
            
            return {
                "success": True,
                "session": name,
                "lines": content_lines[-lines:] if len(content_lines) > lines else content_lines,
                "total_lines": len(content_lines)
            }
            
        except Exception as e:
            return {"success": False, "error": "exception", "message": str(e)}
    
    async def check_iflow_running(self, name: str) -> Dict[str, Any]:
        """检查 iflow 是否在运行"""
        if not await self.session_exists(name):
            return {"running": False, "reason": "session_not_found"}
        
        try:
            # 获取进程列表
            proc = await asyncio.create_subprocess_exec(
                "tmux", "list-panes", "-t", name, "-F", "#{pane_pid}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return {"running": False, "reason": "no_panes"}
            
            pane_pids = stdout.decode().strip().split('\n')
            
            # 检查是否有 iflow 进程
            for pane_pid in pane_pids:
                if not pane_pid:
                    continue
                try:
                    # 查找子进程中的 iflow
                    proc = await asyncio.create_subprocess_exec(
                        "pgrep", "-P", pane_pid, "-f", "iflow",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, _ = await proc.communicate()
                    if stdout.decode().strip():
                        return {"running": True, "pid": stdout.decode().strip()}
                except:
                    pass
            
            return {"running": False, "reason": "iflow_not_found"}
            
        except Exception as e:
            return {"running": False, "reason": str(e)}


# ==================== Mock 消息总线 ====================
class MockMessageBus:
    """模拟消息总线"""
    
    def __init__(self):
        self._iflow_module = None
        self._message_callback = None

    def bind(self, from_module, to_module, bidirectional=False):
        pass

    async def broadcast_to_bindings(self, message: Message, sender_id: str) -> int:
        if self._message_callback:
            try:
                await self._message_callback(message)
                return 1
            except Exception as e:
                logger.error(f"广播消息回调错误: {e}")
        return 0

    async def route(self, message: Message):
        if not self._iflow_module:
            return

        is_from_iflow = (message.from_module == self._iflow_module.module_id)

        if is_from_iflow:
            if self._message_callback:
                try:
                    await self._message_callback(message)
                except Exception as e:
                    logger.error(f"消息回调错误: {e}")
        else:
            await self._iflow_module.receive(message)

    def set_iflow_module(self, module):
        self._iflow_module = module

    def set_message_callback(self, callback):
        self._message_callback = callback


# ==================== 交互工具主类 ====================
class IFlowInteractiveTool:
    """IFlowModule 交互式体验工具"""
    
    def __init__(self, tmux_session: str = "iflow"):
        self.tmux_session_name = tmux_session
        self.tmux_controller = TmuxController()
        self.mock_bus = MockMessageBus()
        self.module: Optional[IFlowModule] = None
        
        # 当前身份和模式
        self.current_source: str = "tool"
        self.current_scope: str = "reply_only"
        
        # 消息历史
        self.message_history: List[dict] = []
        
        # 中断标志
        self._interrupt_event = asyncio.Event()
        
        # JSON 输出模式
        self.json_output: bool = False
    
    async def connect(self, tmux_session: str = None) -> bool:
        """连接到指定的 tmux 会话
        
        Args:
            tmux_session: 会话名称（None 则使用默认）
            
        Returns:
            是否连接成功
        """
        if tmux_session:
            self.tmux_session_name = tmux_session
        
        # 检查会话是否存在
        if not await self.tmux_controller.session_exists(self.tmux_session_name):
            logger.error(f"会话 {self.tmux_session_name} 不存在")
            return False
        
        # 检查 iflow 是否运行
        status = await self.tmux_controller.check_iflow_running(self.tmux_session_name)
        if not status.get("running"):
            logger.error(f"iflow 未在会话 {self.tmux_session_name} 中运行")
            return False
        
        # 创建 IFlowModule 实例（复用现有会话）
        self.module = IFlowModule(
            tmux_session=self.tmux_session_name,
            auto_restart=False,
            log_interactions=True,
            log_dir="logs/interactions"
        )
        
        # 设置消息总线
        self.module.set_message_bus(self.mock_bus)
        self.mock_bus.set_iflow_module(self.module)
        self.mock_bus.set_message_callback(self._on_iflow_message)
        self.module.set_message_sent_hook(self._on_iflow_message)
        
        # 同步 scope
        if self.current_scope == "all":
            self.module.set_reply_mode("all_messages")
        else:
            self.module.set_reply_mode("reply_only")
        
        # 启动模块
        try:
            await self.module.start()
            # 等待就绪
            ready = await self.module.wait_for_ready(timeout=30)
            if not ready:
                logger.warning("iflow 未就绪")
            await asyncio.sleep(2)
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接（保持 tmux 会话）"""
        if self.module:
            await self.module.monitor.stop()
            self.module._running = False
            self.module = None
    
    async def _on_iflow_message(self, message: Message):
        """接收消息回调"""
        message_type = message.metadata.get('reply_type', 'unknown')
        
        self.message_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": message_type,
            "content": message.content.text,
            "metadata": message.metadata
        })
        
        # 非 JSON 模式下打印消息
        if not self.json_output:
            if message_type == 'complete':
                print(f"\n✅ {message.content.text}")
            elif message_type == 'reply':
                print(f"\n📤 {message.content.text}")
            elif self.current_scope == "all":
                print(f"\n💭 [{message_type}] {message.content.text}")
    
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
        is_ready = await self.module.controller.check_iflow_ready()
        if not is_ready:
            return {"success": False, "error": "iflow_not_ready", "message": "iflow 未就绪"}
        
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
            
            if current_state == IFlowState.IDLE:
                await asyncio.sleep(2)
                if self.module.state == IFlowState.IDLE:
                    return True
            
            # 稳定检查
            if message_count == len(self.message_history):
                stable_count += 1
            else:
                stable_count = 0
            
            if stable_count >= 30 and current_state == IFlowState.IDLE:
                return True
        
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        result = {
            "tmux_session": self.tmux_session_name,
            "connected": self.module is not None,
        }
        
        if self.module:
            status = await self.module.get_status()
            result["iflow_state"] = status.get("iflow_state")
            result["iflow_running"] = status.get("iflow_state") != "unknown"
            result["generating_duration"] = status.get("generating_duration", 0)
            result["monitor_stats"] = status.get("monitor_stats", {})
            result["message_store"] = status.get("message_store", {})
        else:
            # 检查 tmux 会话状态
            if await self.tmux_controller.session_exists(self.tmux_session_name):
                iflow_status = await self.tmux_controller.check_iflow_running(self.tmux_session_name)
                result["tmux_exists"] = True
                result["iflow_running"] = iflow_status.get("running", False)
            else:
                result["tmux_exists"] = False
                result["iflow_running"] = False
        
        return result


# ==================== 命令处理 ====================
async def cmd_tmux_create(args):
    """处理 tmux create 命令"""
    controller = TmuxController()
    result = await controller.create_session(
        name=args.name,
        workspace=args.workspace,
        model=args.model,
        mode=args.mode
    )
    
    if args.json:
        output_json(result, success=result.get("success", False), command="tmux create")
    else:
        if result.get("success"):
            print(f"✅ {result['message']}")
            print(f"   会话名称: {result['session']}")
            print(f"   工作目录: {result['workspace']}")
            if result.get('model'):
                print(f"   模型: {result['model']}")
            if result.get('mode'):
                print(f"   模式: {result['mode']}")
        else:
            print(f"❌ {result['message']}")
    
    return EXIT_SUCCESS if result.get("success") else EXIT_ERROR


async def cmd_tmux_stop(args):
    """处理 tmux stop 命令"""
    controller = TmuxController()
    result = await controller.stop_session(args.name)
    
    if args.json:
        output_json(result, success=result.get("success", False), command="tmux stop")
    else:
        if result.get("success"):
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
    
    return EXIT_SUCCESS if result.get("success") else EXIT_TMUX_NOT_FOUND


async def cmd_tmux_restart(args):
    """处理 tmux restart 命令"""
    controller = TmuxController()
    result = await controller.restart_session(
        name=args.name,
        model=args.model,
        mode=args.mode
    )
    
    if args.json:
        output_json(result, success=result.get("success", False), command="tmux restart")
    else:
        if result.get("success"):
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result['message']}")
    
    return EXIT_SUCCESS if result.get("success") else EXIT_TMUX_NOT_FOUND


async def cmd_tmux_list(args):
    """处理 tmux list 命令"""
    controller = TmuxController()
    sessions = await controller.list_sessions()
    
    if args.json:
        output_json({"sessions": sessions, "count": len(sessions)}, command="tmux list")
    else:
        if not sessions:
            print("没有活动的 tmux 会话")
        else:
            print(f"活动的 tmux 会话 ({len(sessions)} 个):")
            print("-" * 50)
            for s in sessions:
                attached = " [attached]" if s["attached"] else ""
                print(f"  {s['name']}: {s['windows']} 个窗口{attached}")
    
    return EXIT_SUCCESS


async def cmd_tmux_snapshot(args):
    """处理 tmux snapshot 命令"""
    controller = TmuxController()
    result = await controller.get_snapshot(args.name, args.lines or 50)
    
    if args.json:
        output_json(result, success=result.get("success", False), command="tmux snapshot")
    else:
        if result.get("success"):
            print(f"会话 {args.name} 快照 (最近 {len(result['lines'])} 行):")
            print("-" * 50)
            for line in result["lines"]:
                print(line)
        else:
            print(f"❌ {result['message']}")
    
    return EXIT_SUCCESS if result.get("success") else EXIT_TMUX_NOT_FOUND


async def cmd_tmux_switch(args):
    """处理 tmux switch 命令"""
    controller = TmuxController()
    
    if not await controller.session_exists(args.name):
        if args.json:
            output_error("not_found", f"会话 {args.name} 不存在", "tmux switch")
        else:
            print(f"❌ 会话 {args.name} 不存在")
        return EXIT_TMUX_NOT_FOUND
    
    # 检查 iflow 是否运行
    status = await controller.check_iflow_running(args.name)
    
    if args.json:
        output_json({
            "session": args.name,
            "iflow_running": status.get("running", False)
        }, command="tmux switch")
    else:
        print(f"✅ 当前会话: {args.name}")
        if status.get("running"):
            print(f"   iflow 状态: 运行中")
        else:
            print(f"   iflow 状态: 未运行")
    
    return EXIT_SUCCESS


async def cmd_send(args):
    """处理 send 命令"""
    tool = IFlowInteractiveTool(tmux_session=args.tmux_session)
    tool.json_output = args.json
    tool.current_scope = args.scope or "reply_only"
    tool.current_source = args.source or "tool"
    
    # 连接
    connected = await tool.connect()
    if not connected:
        if args.json:
            output_error("connect_failed", f"无法连接到会话 {args.tmux_session}", "send")
        else:
            print(f"❌ 无法连接到会话 {args.tmux_session}")
        return EXIT_TMUX_NOT_FOUND
    
    try:
        # 发送消息
        result = await tool.send_message(args.message, timeout=args.timeout or 300)
        
        if args.json:
            output_json(result, success=result.get("success", False), command="send")
        else:
            if result.get("success"):
                print(f"\n✅ 消息发送成功，收到 {result['reply_count']} 条回复")
            else:
                print(f"\n❌ {result['message']}")
        
        return EXIT_SUCCESS if result.get("success") else EXIT_TIMEOUT
        
    finally:
        await tool.disconnect()


async def cmd_status(args):
    """处理 status 命令"""
    tool = IFlowInteractiveTool(tmux_session=args.tmux_session)
    
    status = await tool.get_status()
    
    if args.json:
        output_json(status, command="status")
    else:
        print(f"状态信息:")
        print(f"  tmux 会话: {status.get('tmux_session')}")
        print(f"  tmux 存在: {'是' if status.get('tmux_exists', True) else '否'}")
        print(f"  iflow 运行: {'是' if status.get('iflow_running') else '否'}")
        if status.get('iflow_state'):
            print(f"  iflow 状态: {status['iflow_state']}")
        if status.get('generating_duration', 0) > 0:
            print(f"  生成时长: {status['generating_duration']}秒")
    
    return EXIT_SUCCESS


async def cmd_interactive(args):
    """交互模式"""
    tool = IFlowInteractiveTool(tmux_session=args.tmux_session)
    tool.current_scope = args.scope or "reply_only"
    tool.current_source = args.source or "tool"
    
    # 连接
    print(f"正在连接到会话 {args.tmux_session}...")
    connected = await tool.connect()
    if not connected:
        print(f"❌ 无法连接到会话 {args.tmux_session}")
        return EXIT_TMUX_NOT_FOUND
    
    try:
        print("✅ 连接成功")
        await tool.interactive_loop()
        return EXIT_SUCCESS
    finally:
        await tool.disconnect()


# ==================== Session 命令处理 ====================
async def cmd_session_list(args):
    """处理 session list 命令"""
    controller = SessionController(workspace=args.workspace)
    sessions = controller.list_sessions(limit=args.limit or 20)
    
    if args.json:
        output_json({"sessions": sessions, "count": len(sessions)}, command="session list")
    else:
        if not sessions:
            print("没有会话文件")
        else:
            print(f"会话文件 ({len(sessions)} 个):")
            print("-" * 60)
            for s in sessions:
                modified = s["modified"][11:19]  # 只取时间部分
                size_kb = s["size"] / 1024
                print(f"  {s['name']}: {size_kb:.1f}KB, {modified}")
    return EXIT_SUCCESS


async def cmd_session_current(args):
    """处理 session current 命令"""
    controller = SessionController(workspace=args.workspace)
    session = controller.get_current_session()
    
    if args.json:
        output_json({"session": session}, command="session current")
    else:
        if session:
            print(f"当前会话: {session['name']}")
            print(f"  大小: {session['size'] / 1024:.1f}KB")
            print(f"  修改: {session['modified']}")
        else:
            print("没有当前会话")
    return EXIT_SUCCESS


async def cmd_session_new(args):
    """处理 session new 命令"""
    controller = SessionController(workspace=args.workspace)
    result = controller.create_new_session()
    
    if args.json:
        output_json(result, success=result.get("success", False), command="session new")
    else:
        if result.get("success"):
            print(f"✅ {result['message']}")
        else:
            print(f"❌ {result.get('message', '未知错误')}")
    return EXIT_SUCCESS if result.get("success") else EXIT_ERROR


async def cmd_session_view(args):
    """处理 session view 命令"""
    controller = SessionController(workspace=args.workspace)
    result = controller.view_session(
        session_name=args.name if hasattr(args, 'name') else None,
        lines=args.lines or 50
    )
    
    if args.json:
        output_json(result, success=result.get("success", False), command="session view")
    else:
        if result.get("success"):
            print(f"会话: {result['session']}")
            print(f"总行数: {result['total_lines']}")
            print("-" * 60)
            for item in result["content"]:
                role = item["role"]
                content = item["content"][:100]
                print(f"  [{role}] {content}...")
        else:
            print(f"❌ {result.get('message', '未知错误')}")
    return EXIT_SUCCESS if result.get("success") else EXIT_ERROR


# ==================== 参数解析 ====================
def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="IFlowModule 交互式体验工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # 全局选项
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument("--tmux-session", default="iflow", help="tmux 会话名称 (默认: iflow)")
    
    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # tmux 子命令
    tmux_parser = subparsers.add_parser("tmux", help="Tmux 会话管理")
    tmux_subparsers = tmux_parser.add_subparsers(dest="tmux_command", help="Tmux 命令")
    
    # tmux create
    create_parser = tmux_subparsers.add_parser("create", help="创建 tmux 会话")
    create_parser.add_argument("name", help="会话名称")
    create_parser.add_argument("--workspace", "-w", help="工作目录")
    create_parser.add_argument("--model", "-m", help="模型名称")
    create_parser.add_argument("--mode", choices=["smart", "yolo"], default="smart", help="运行模式")
    create_parser.set_defaults(func=cmd_tmux_create)
    
    # tmux stop
    stop_parser = tmux_subparsers.add_parser("stop", help="停止 tmux 会话")
    stop_parser.add_argument("name", help="会话名称")
    stop_parser.set_defaults(func=cmd_tmux_stop)
    
    # tmux restart
    restart_parser = tmux_subparsers.add_parser("restart", help="重启 tmux 会话中的 iflow")
    restart_parser.add_argument("name", help="会话名称")
    restart_parser.add_argument("--model", "-m", help="模型名称")
    restart_parser.add_argument("--mode", choices=["smart", "yolo"], help="运行模式")
    restart_parser.set_defaults(func=cmd_tmux_restart)
    
    # tmux list
    list_parser = tmux_subparsers.add_parser("list", help="列出所有 tmux 会话")
    list_parser.set_defaults(func=cmd_tmux_list)
    
    # tmux snapshot
    snapshot_parser = tmux_subparsers.add_parser("snapshot", help="查看 tmux 会话快照")
    snapshot_parser.add_argument("name", help="会话名称")
    snapshot_parser.add_argument("--lines", "-n", type=int, default=50, help="显示行数")
    snapshot_parser.set_defaults(func=cmd_tmux_snapshot)
    
    # tmux switch
    switch_parser = tmux_subparsers.add_parser("switch", help="切换 tmux 会话")
    switch_parser.add_argument("name", help="会话名称")
    switch_parser.set_defaults(func=cmd_tmux_switch)
    
    # send 命令
    send_parser = subparsers.add_parser("send", help="发送消息")
    send_parser.add_argument("message", help="消息内容")
    send_parser.add_argument("--scope", choices=["all", "reply_only"], default="reply_only", help="scope 模式")
    send_parser.add_argument("--source", default="tool", help="消息来源")
    send_parser.add_argument("--timeout", type=float, default=300, help="超时时间（秒）")
    send_parser.set_defaults(func=cmd_send)
    
    # status 命令
    status_parser = subparsers.add_parser("status", help="查看状态")
    status_parser.set_defaults(func=cmd_status)
    
    # interactive 命令
    interactive_parser = subparsers.add_parser("interactive", help="进入交互模式")
    interactive_parser.add_argument("--scope", choices=["all", "reply_only"], default="reply_only")
    interactive_parser.add_argument("--source", default="tool")
    interactive_parser.set_defaults(func=cmd_interactive)
    
    # session 子命令
    session_parser = subparsers.add_parser("session", help="IFlow 会话文件管理")
    session_subparsers = session_parser.add_subparsers(dest="session_command", help="Session 命令")
    
    # session list
    session_list_parser = session_subparsers.add_parser("list", help="列出会话文件")
    session_list_parser.add_argument("--workspace", "-w", help="工作目录")
    session_list_parser.add_argument("--limit", "-n", type=int, default=20, help="最大返回数量")
    session_list_parser.set_defaults(func=cmd_session_list)
    
    # session current
    session_current_parser = session_subparsers.add_parser("current", help="显示当前会话")
    session_current_parser.add_argument("--workspace", "-w", help="工作目录")
    session_current_parser.set_defaults(func=cmd_session_current)
    
    # session new
    session_new_parser = session_subparsers.add_parser("new", help="创建新会话（清空上下文）")
    session_new_parser.add_argument("--workspace", "-w", help="工作目录")
    session_new_parser.set_defaults(func=cmd_session_new)
    
    # session view
    session_view_parser = session_subparsers.add_parser("view", help="查看会话内容")
    session_view_parser.add_argument("name", nargs="?", help="会话文件名（默认最新）")
    session_view_parser.add_argument("--workspace", "-w", help="工作目录")
    session_view_parser.add_argument("--lines", "-n", type=int, default=50, help="显示行数")
    session_view_parser.set_defaults(func=cmd_session_view)
    
    # 兼容旧命令行参数
    parser.add_argument("--message", "-M", help="发送消息（兼容旧命令）")
    parser.add_argument("--scope", dest="scope_legacy", help="scope 模式（兼容旧命令）")
    parser.add_argument("--source", dest="source_legacy", help="消息来源（兼容旧命令）")
    parser.add_argument("--clean", action="store_true", help="清理残留会话")
    parser.add_argument("--keep-alive", action="store_true", default=True, help="保持会话")
    parser.add_argument("--cleanup", action="store_true", help="结束时销毁会话")
    
    return parser


# ==================== 交互循环 ====================
async def interactive_loop(self):
    """交互式循环"""
    print("\n" + "=" * 60)
    print("交互模式")
    print("=" * 60)
    self._print_help()

    try:
        import prompt_toolkit
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory
        from prompt_toolkit.completion import WordCompleter

        commands = ['/help', '/source', '/scope', '/status', '/history', '/tmux', 'quit', 'exit', 'q']
        completer = WordCompleter(commands, ignore_case=True)
        history = InMemoryHistory()
        
        session = PromptSession(history=history, completer=completer)

        while True:
            try:
                user_input = await session.prompt_async(f"\n💬 你: ")

                if not user_input:
                    continue

                if user_input.startswith('/'):
                    await self._handle_command(user_input)
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    break

                await self.send_message(user_input)
                await self._wait_for_complete()

            except KeyboardInterrupt:
                self._interrupt_event.set()
                print("\n⚠️ 等待已中断")
            except EOFError:
                break

    except ImportError:
        print("提示：安装 prompt_toolkit 可获得更好的交互体验")

        while True:
            try:
                user_input = input(f"\n💬 你: ").strip()

                if not user_input:
                    continue

                if user_input.startswith('/'):
                    await self._handle_command(user_input)
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    break

                await self.send_message(user_input)
                await self._wait_for_complete()

            except KeyboardInterrupt:
                self._interrupt_event.set()
                print("\n⚠️ 等待已中断")
            except EOFError:
                break


async def _handle_command(self, command: str):
    """处理交互命令"""
    parts = command.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None
    
    if cmd == '/help':
        self._print_help()
    elif cmd == '/source':
        if arg:
            self.current_source = arg
            print(f"✅ 已切换身份: {arg}")
        else:
            print(f"当前身份: {self.current_source}")
    elif cmd == '/scope':
        if arg in ['all', 'reply_only']:
            self.current_scope = arg
            if self.module:
                self.module.set_reply_mode("all_messages" if arg == "all" else "reply_only")
            print(f"✅ 已切换模式: {arg}")
        else:
            print(f"当前模式: {self.current_scope}")
    elif cmd == '/status':
        status = await self.get_status()
        print(f"\n📊 状态:")
        for k, v in status.items():
            print(f"   {k}: {v}")
    elif cmd == '/history':
        if not self.message_history:
            print("\n📝 暂无消息历史")
        else:
            print(f"\n📝 消息历史 ({len(self.message_history)} 条):")
            for msg in self.message_history[-10:]:
                print(f"  [{msg['type']}] {msg['content'][:50]}...")
    elif cmd == '/tmux':
        # tmux 子命令
        if arg:
            sub_parts = arg.split(maxsplit=1)
            sub_cmd = sub_parts[0]
            sub_arg = sub_parts[1] if len(sub_parts) > 1 else None
            
            if sub_cmd == 'list':
                sessions = await self.tmux_controller.list_sessions()
                print(f"\n活动的 tmux 会话 ({len(sessions)} 个):")
                for s in sessions:
                    print(f"  {s['name']}: {s['windows']} 个窗口")
            elif sub_cmd == 'snapshot':
                name = sub_arg or self.tmux_session_name
                result = await self.tmux_controller.get_snapshot(name, 30)
                if result.get("success"):
                    print(f"\n会话 {name} 快照:")
                    for line in result["lines"][-20:]:
                        print(f"  {line}")
                else:
                    print(f"❌ {result['message']}")
            else:
                print(f"未知 tmux 子命令: {sub_cmd}")
                print("可用: list, snapshot")
        else:
            print("用法: /tmux <list|snapshot> [args]")
    else:
        print(f"未知命令: {cmd}")


def _print_help(self):
    """打印帮助"""
    print("命令:")
    print("  直接输入文字     - 发送消息")
    print("  /source <name>   - 切换身份")
    print("  /scope <mode>    - 切换模式: all / reply_only")
    print("  /status          - 查看状态")
    print("  /history         - 查看消息历史")
    print("  /tmux list       - 列出 tmux 会话")
    print("  /tmux snapshot   - 查看当前快照")
    print("  /help            - 显示帮助")
    print("  quit/exit        - 退出")
    print("-" * 40)
    print(f"当前: source={self.current_source}, scope={self.current_scope}")


# 绑定方法到类
IFlowInteractiveTool.interactive_loop = interactive_loop
IFlowInteractiveTool._handle_command = _handle_command
IFlowInteractiveTool._print_help = _print_help


# ==================== 主函数 ====================
async def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 处理兼容旧命令
    if args.message and not args.command:
        # 旧命令模式：--message "xxx"
        tool = IFlowInteractiveTool(tmux_session=args.tmux_session)
        tool.current_scope = args.scope_legacy or "reply_only"
        tool.current_source = args.source_legacy or "tool"
        tool.json_output = args.json
        
        connected = await tool.connect()
        if not connected:
            if args.json:
                output_error("connect_failed", f"无法连接到会话 {args.tmux_session}", "send")
            else:
                print(f"❌ 无法连接到会话 {args.tmux_session}")
            return EXIT_TMUX_NOT_FOUND
        
        try:
            result = await tool.send_message(args.message)
            if args.json:
                output_json(result, success=result.get("success", False), command="send")
            elif result.get("success"):
                print(f"\n✅ 消息发送成功")
            else:
                print(f"\n❌ {result['message']}")
            return EXIT_SUCCESS if result.get("success") else EXIT_TIMEOUT
        finally:
            await tool.disconnect()
    
    # 处理子命令
    if hasattr(args, 'func') and args.func:
        return await args.func(args)
    
    # 无命令，显示帮助
    if not args.command:
        parser.print_help()
        return EXIT_SUCCESS
    
    return EXIT_SUCCESS


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
