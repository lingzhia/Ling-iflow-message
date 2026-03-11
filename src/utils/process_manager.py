"""进程管理工具。

用于管理 wechat_bot.py 进程，包括启动、停止、状态检查等。
"""

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

from loguru import logger


class ProcessManager:
    """进程管理器。"""
    
    def __init__(self, project_root: Path):
        """初始化进程管理器。
        
        Args:
            project_root: 项目根目录
        """
        self.project_root = project_root
        self.pids_dir = project_root / ".pids"
        self.pids_dir.mkdir(exist_ok=True)
    
    def get_pid_file(self, bot_name: str) -> Path:
        """获取 PID 文件路径。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            PID 文件路径
        """
        return self.pids_dir / f"bot_{bot_name}.pid"
    
    def start_bot(
        self,
        bot_name: str,
        config_path: str = "config.json",
        daemon: bool = True,
        verbose: bool = False
    ) -> int:
        """启动机器人进程。
        
        Args:
            bot_name: 机器人名称
            config_path: 配置文件路径
            daemon: 是否后台运行
            verbose: 是否详细日志
            
        Returns:
            进程 PID
            
        Raises:
            RuntimeError: 启动失败
        """
        # 检查是否已运行
        if self.is_running(bot_name):
            raise RuntimeError(f"机器人已在运行: {bot_name}")
        
        # 构建 Python 路径
        python_path = os.sys.executable
        bot_script = self.project_root / "wechat_bot.py"
        
        # 构建命令
        cmd = [
            python_path,
            str(bot_script),
            "--bot", bot_name,
            "--config", config_path
        ]
        
        if verbose:
            cmd.append("--verbose")
        
        # 启动进程
        try:
            if daemon:
                # 后台运行
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                    cwd=str(self.project_root)
                )
            else:
                # 前台运行
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.project_root)
                )
            
            pid = process.pid
            
            # 保存 PID
            self._save_pid(bot_name, pid)
            
            logger.info(f"[ProcessManager] 已启动机器人: {bot_name} (PID: {pid})")
            
            # 等待一下，确保进程启动成功
            time.sleep(1)
            
            # 检查进程是否仍在运行
            if not self.is_running(bot_name):
                # 清理 PID 文件
                self._remove_pid_file(bot_name)
                raise RuntimeError(f"机器人启动失败: {bot_name}")
            
            return pid
            
        except Exception as e:
            logger.error(f"[ProcessManager] 启动机器人失败: {e}")
            raise RuntimeError(f"启动机器人失败: {e}")
    
    def stop_bot(self, bot_name: str) -> bool:
        """停止机器人进程。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            是否成功停止
        """
        pid_file = self.get_pid_file(bot_name)
        
        if not pid_file.exists():
            logger.warning(f"[ProcessManager] PID 文件不存在: {bot_name}")
            return False
        
        try:
            # 读取 PID
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 检查进程是否存在
            if not self._process_exists(pid):
                logger.warning(f"[ProcessManager] 进程不存在: {pid}")
                self._remove_pid_file(bot_name)
                return False
            
            # 发送 SIGTERM 信号
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                logger.warning(f"[ProcessManager] 进程已不存在: {pid}")
                self._remove_pid_file(bot_name)
                return False
            
            # 等待进程结束
            max_wait = 10  # 最多等待 10 秒
            for _ in range(max_wait):
                time.sleep(1)
                if not self._process_exists(pid):
                    break
            else:
                # 进程未正常结束，强制终止
                logger.warning(f"[ProcessManager] 进程未正常结束，强制终止: {pid}")
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            
            # 清理 PID 文件
            self._remove_pid_file(bot_name)
            
            logger.info(f"[ProcessManager] 已停止机器人: {bot_name}")
            return True
            
        except Exception as e:
            logger.error(f"[ProcessManager] 停止机器人失败: {e}")
            return False
    
    def is_running(self, bot_name: str) -> bool:
        """检查机器人是否运行。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            是否运行
        """
        pid_file = self.get_pid_file(bot_name)
        
        if not pid_file.exists():
            return False
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            return self._process_exists(pid)
            
        except Exception as e:
            logger.error(f"[ProcessManager] 检查进程状态失败: {e}")
            return False
    
    def get_pid(self, bot_name: str) -> Optional[int]:
        """获取机器人进程 PID。
        
        Args:
            bot_name: 机器人名称
            
        Returns:
            进程 PID，如果不存在返回 None
        """
        pid_file = self.get_pid_file(bot_name)
        
        if not pid_file.exists():
            return None
        
        try:
            with open(pid_file, 'r') as f:
                return int(f.read().strip())
        except Exception:
            return None
    
    def _save_pid(self, bot_name: str, pid: int) -> None:
        """保存 PID 到文件。
        
        Args:
            bot_name: 机器人名称
            pid: 进程 PID
        """
        pid_file = self.get_pid_file(bot_name)
        
        try:
            with open(pid_file, 'w') as f:
                f.write(str(pid))
        except Exception as e:
            logger.error(f"[ProcessManager] 保存 PID 失败: {e}")
    
    def _remove_pid_file(self, bot_name: str) -> None:
        """删除 PID 文件。
        
        Args:
            bot_name: 机器人名称
        """
        pid_file = self.get_pid_file(bot_name)
        
        try:
            if pid_file.exists():
                pid_file.unlink()
        except Exception as e:
            logger.error(f"[ProcessManager] 删除 PID 文件失败: {e}")
    
    def _process_exists(self, pid: int) -> bool:
        """检查进程是否存在。
        
        Args:
            pid: 进程 PID
            
        Returns:
            进程是否存在
        """
        try:
            os.kill(pid, 0)  # 发送空信号，检查进程是否存在
            return True
        except (ProcessLookupError, OSError):
            return False
    
    def list_running_bots(self) -> list[str]:
        """列出所有运行中的机器人。
        
        Returns:
            运行中的机器人名称列表
        """
        running_bots = []
        
        for pid_file in self.pids_dir.glob("bot_*.pid"):
            bot_name = pid_file.stem.replace("bot_", "")
            
            if self.is_running(bot_name):
                running_bots.append(bot_name)
        
        return running_bots
    
    def kill_all_bots(self) -> int:
        """停止所有机器人。
        
        Returns:
            停止的机器人数量
        """
        count = 0
        
        for pid_file in self.pids_dir.glob("bot_*.pid"):
            bot_name = pid_file.stem.replace("bot_", "")
            
            if self.stop_bot(bot_name):
                count += 1
        
        return count