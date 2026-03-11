#!/usr/bin/env python3
"""iflow 交互式对话 - 支持从 tmux 输出中提取回复"""

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from loguru import logger
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from interactive.session_monitor import SessionMonitor
from interactive.iflow_controller import IFlowController

# 颜色配置
COLOR_USER = "\033[32m"      # 绿色
COLOR_AI = "\033[36m"        # 青色
COLOR_SYSTEM = "\033[33m"    # 黄色
COLOR_RESET = "\033[0m"

class InteractiveChat:
    """iflow 交互式对话（改进版）"""
    
    def __init__(self, tmux_session="iflow", workspace="~/.iflow"):
        """初始化交互式对话。
        
        Args:
            tmux_session: tmux 会话名称
            workspace: iflow 工作目录
        """
        self.tmux_session = tmux_session
        self.workspace = workspace
        self.running = False
        
        self.monitor = SessionMonitor(workspace)
        self.controller = IFlowController(tmux_session)
        
        self.message_count = 0
        self.last_reply = ""
        self.initial_reply = ""  # 记录启动时的初始回复
        
        # 用于检测新回复
        self.last_tmux_output = ""
    
    async def start(self):
        """启动交互式对话。"""
        self.running = True
        
        # 检查 iflow 状态
        self._check_iflow_status()
        
        # 显示欢迎信息
        self._print_welcome()
        
        # 启动后台任务
        print(f"{COLOR_SYSTEM}[调试] 正在启动监控任务...{COLOR_RESET}", flush=True)
        
        try:
            monitor_task = asyncio.create_task(self._monitor_ai_responses())
            print(f"{COLOR_SYSTEM}[调试] 监控任务已创建{COLOR_RESET}", flush=True)
            
            input_task = asyncio.create_task(self._user_input_loop())
            print(f"{COLOR_SYSTEM}[调试] 输入任务已创建{COLOR_RESET}", flush=True)
            
            # 等待任务完成
            done, pending = await asyncio.wait(
                [monitor_task, input_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 取消未完成的任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # 检查是否有异常
            for task in done:
                if task.exception():
                    print(f"{COLOR_SYSTEM}[调试] 任务异常: {task.exception()}{COLOR_RESET}", flush=True)
            
        except Exception as e:
            print(f"{COLOR_SYSTEM}[调试] 启动异常: {e}{COLOR_RESET}", flush=True)
            import traceback
            traceback.print_exc()
        
        # 显示统计信息
        self._print_stats()
    
    def _check_iflow_status(self):
        """检查 iflow 状态。"""
        print(f"{COLOR_SYSTEM}[系统] 正在检查 iflow 状态...{COLOR_RESET}")
        
        if not self.controller.check_tmux_session():
            print(f"{COLOR_SYSTEM}[系统] ✗ iflow tmux 会话不存在{COLOR_RESET}")
            print(f"{COLOR_SYSTEM}[系统] 请先启动 iflow: tmux new-session -d -s iflow \"iflow --model kimi-k2.5\"{COLOR_RESET}")
            self.running = False
            return
        
        if not self.controller.check_iflow_running():
            print(f"{COLOR_SYSTEM}[系统] ✗ iflow 未运行{COLOR_RESET}")
            self.running = False
            return
        
        print(f"{COLOR_SYSTEM}[系统] ✓ iflow 运行正常{COLOR_RESET}")
        
        # 查找会话文件
        session_files = self.monitor.find_session_files()
        print(f"{COLOR_SYSTEM}[系统] ✓ 找到 {len(session_files)} 个会话文件{COLOR_RESET}")
    
    def _print_welcome(self):
        """打印欢迎信息。"""
        print()
        print("=" * 70)
        print("iflow 交互式对话")
        print("=" * 70)
        print(f"{COLOR_SYSTEM}[系统] 提示：{COLOR_RESET}")
        print(f"  - 输入消息并发送（按 Enter）")
        print(f"  - 输入 'quit'、'exit' 或 'q' 退出")
        print(f"  - 输入 'clear' 清屏")
        print(f"  - 输入 'status' 查看状态")
        print(f"  - iflow 的回复会自动显示")
        print("=" * 70)
        print()
    
    async def _user_input_loop(self):
        """用户输入循环。"""
        while self.running:
            try:
                user_input = input(f"{COLOR_USER}[你]{COLOR_RESET} ").strip()
                
                # 处理命令
                if user_input in ['quit', 'exit', 'q']:
                    print(f"{COLOR_SYSTEM}[系统] 再见！{COLOR_RESET}")
                    self.running = False
                    break
                
                if user_input == 'clear':
                    import os
                    os.system('clear')
                    continue
                
                if user_input == 'status':
                    self._print_status()
                    continue
                
                if not user_input:
                    continue
                
                # 发送消息到 iflow
                print(f"{COLOR_SYSTEM}[系统] 正在发送消息...{COLOR_RESET}")
                
                success = self.controller.send_message(user_input)
                
                if success:
                    self.message_count += 1
                    print(f"{COLOR_SYSTEM}[系统] ✓ 消息已发送{COLOR_RESET}")
                else:
                    print(f"{COLOR_SYSTEM}[系统] ✗ 消息发送失败{COLOR_RESET}")
                
            except EOFError:
                print(f"\n{COLOR_SYSTEM}[系统] 输入结束，正在退出...{COLOR_RESET}")
                break
            except Exception as e:
                print(f"{COLOR_SYSTEM}[系统] 错误: {e}{COLOR_RESET}")
    
    async def _monitor_ai_responses(self):
        """监控 AI 回复。"""
        print(f"{COLOR_SYSTEM}[调试] 监控任务开始运行{COLOR_RESET}", flush=True)
        
        # 第一次运行时记录初始回复（列表）
        if not self.initial_reply:
            self.initial_reply = self._extract_reply_from_tmux()
            print(f"{COLOR_SYSTEM}[调试] 初始回复: {len(self.initial_reply)} 条消息{COLOR_RESET}", flush=True)
        
        last_messages = []
        stable_count = 0
        max_stable_checks = 3
        loop_count = 0
        
        while self.running:
            try:
                loop_count += 1
                
                # 尝试从 tmux 输出中提取回复（返回消息列表）
                tmux_messages = self._extract_reply_from_tmux()
                current_count = len(tmux_messages)
                
                # 如果找到回复并且数量与初始回复不同
                if current_count > len(self.initial_reply):
                    if tmux_messages != last_messages:
                        # 新回复
                        last_messages = tmux_messages
                        stable_count = 0
                        print(f"{COLOR_SYSTEM}[调试] 检测到新回复: {current_count} 条消息 (稳定度: {stable_count}/{max_stable_checks}){COLOR_RESET}", flush=True)
                    else:
                        # 回复稳定
                        stable_count += 1
                        print(f"{COLOR_SYSTEM}[调试] 回复稳定: {current_count} 条消息 (稳定度: {stable_count}/{max_stable_checks}){COLOR_RESET}", flush=True)
                        
                        # 如果回复稳定了多次，显示回复
                        if stable_count >= max_stable_checks:
                            # 立即刷新输出，确保显示
                            import sys
                            sys.stdout.flush()
                            
                            # 显示新增的消息
                            new_messages = tmux_messages[len(self.initial_reply):]
                            for message in new_messages:
                                self._display_ai_response(message)
                            
                            self.last_reply = '\n\n'.join(new_messages)
                            
                            # 更新初始回复，避免重复显示
                            self.initial_reply = tmux_messages
                            last_messages = []
                            stable_count = 0
                            
                            # 再次刷新输出
                            sys.stdout.flush()
                else:
                    # 没有回复或回复与初始回复相同，重置
                    if loop_count % 10 == 0:  # 每10次循环打印一次，避免刷屏
                        print(f"{COLOR_SYSTEM}[调试] 监控中... (loop {loop_count}, 当前消息数: {current_count}){COLOR_RESET}", flush=True)
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                print(f"{COLOR_SYSTEM}[调试] 监控任务被取消{COLOR_RESET}", flush=True)
                break
            except Exception as e:
                logger.error(f"监控错误: {e}")
                print(f"{COLOR_SYSTEM}[调试] 监控错误: {e}{COLOR_RESET}", flush=True)
                await asyncio.sleep(1)
        
        print(f"{COLOR_SYSTEM}[调试] 监控任务结束{COLOR_RESET}", flush=True)
    
    def _extract_reply_from_tmux(self):
        """从 tmux 输出中提取最终回复。"""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", self.tmux_session, "-p"],
                capture_output=True,
                text=True
            )
            
            output = result.stdout
            lines = output.split('\n')
            
            reply_lines = []
            
            for i, line in enumerate(lines):
                # 查找以 "✦" 开头的行（这是最终回复的标记）
                if '✦' in line and '✻' not in line and '✹' not in line:
                    # 提取回复内容（去掉前面的符号）
                    reply_content = line.split('✦', 1)[1].strip() if '✦' in line else ''
                    
                    if reply_content:
                        reply_lines.append(reply_content)
                        
                        # 检查后续行是否也是回复的一部分
                        for j in range(i + 1, len(lines)):
                            next_line = lines[j].strip()
                            
                            # 如果遇到分隔线，停止
                            if '─' * 10 in next_line:
                                break
                            
                            # 如果遇到空行，可能是回复结束
                            if not next_line and len(reply_lines) > 0:
                                break
                            
                            # 如果遇到新的命令提示，停止
                            if '>' in next_line and '输入消息' in next_line:
                                break
                            
                            # 如果是回复的延续，添加到列表
                            if next_line and not next_line.startswith('│'):
                                reply_lines.append(next_line)
                        
                        break
            
            return '\n'.join(reply_lines)
        except Exception as e:
            logger.error(f"提取 tmux 回复失败: {e}")
            return ""
    
    def _display_ai_response(self, content):
        """显示 AI 回复。"""
        time_str = datetime.now().strftime("%H:%M:%S")
        
        # 显示回复
        print(f"\n{COLOR_AI}[iflow] {time_str}{COLOR_RESET}")
        
        # 处理多行文本
        lines = content.split('\n')
        for line in lines:
            print(f"{COLOR_AI}{line}{COLOR_RESET}")
        
        print()  # 空行分隔
    
    def _print_status(self):
        """打印状态信息。"""
        print(f"\n{COLOR_SYSTEM}[状态信息]{COLOR_RESET}")
        
        # iflow 状态
        session_info = self.controller.get_session_info()
        print(f"  tmux 会话: {session_info['tmux_session']}")
        print(f"  tmux 存在: {'是' if session_info['tmux_exists'] else '否'}")
        print(f"  iflow 运行: {'是' if session_info['iflow_running'] else '否'}")
        
        # 会话信息
        session_info = self.monitor.get_session_info()
        print(f"  会话文件数: {session_info['total_sessions']}")
        print(f"  已处理消息: {session_info['processed_messages']}")
        print(f"  发送消息数: {self.message_count}")
        print()
    
    def _print_stats(self):
        """打印统计信息。"""
        print(f"\n{COLOR_SYSTEM}[统计信息]{COLOR_RESET}")
        print(f"  总发送消息: {self.message_count} 条")
        print(f"  会话文件数: {len(self.monitor.find_session_files())} 个")
        print()

    async def send_and_get_reply(self, message: str, timeout: int = 60):
        """发送消息并获取回复（命令行模式）。
        
        Args:
            message: 要发送的消息
            timeout: 等待回复的超时时间（秒）
        """
        self.running = True
        
        # 检查 iflow 状态
        self._check_iflow_status()
        
        if not self.running:
            return
        
        # 获取发送前的回复（作为基准）
        initial_messages = self._extract_reply_from_tmux()
        
        # 发送消息
        print(f"{COLOR_USER}[发送消息]{COLOR_RESET} {message}")
        
        success = self.controller.send_message(message)
        
        if not success:
            print(f"{COLOR_SYSTEM}[错误] 消息发送失败{COLOR_RESET}")
            return
        
        print(f"{COLOR_SYSTEM}[状态] ✓ 消息已发送{COLOR_RESET}")
        print(f"{COLOR_SYSTEM}[状态] 等待回复...{COLOR_RESET}")
        print(f"{COLOR_SYSTEM}[状态] 初始消息数: {len(initial_messages)}{COLOR_RESET}", flush=True)
        
        # 等待 iflow 开始处理
        await asyncio.sleep(5)
        
        # 监控回复
        last_messages = []
        stable_count = 0
        max_stable_checks = 3
        
        for i in range(timeout):
            await asyncio.sleep(1)
            
            tmux_messages = self._extract_reply_from_tmux()
            current_count = len(tmux_messages)
            
            # 如果有回复，并且数量与初始回复不同
            if current_count > len(initial_messages):
                if tmux_messages != last_messages:
                    # 新回复
                    last_messages = tmux_messages
                    stable_count = 0
                    print(f"{COLOR_SYSTEM}[状态] 检测到新回复: {current_count} 条消息 (稳定度: {stable_count}/{max_stable_checks}){COLOR_RESET}", flush=True)
                else:
                    # 回复稳定
                    stable_count += 1
                    print(f"{COLOR_SYSTEM}[状态] 回复稳定: {current_count} 条消息 (稳定度: {stable_count}/{max_stable_checks}){COLOR_RESET}", flush=True)
                    
                    # 如果回复稳定了多次，认为完成
                    if stable_count >= max_stable_checks:
                        break
            else:
                # 没有回复或回复与初始回复相同，重置
                stable_count = 0
        
        # 打印回复
        if last_messages and len(last_messages) > len(initial_messages):
            print()
            print("=" * 70)
            print(f"{COLOR_AI}[iflow 回复]{COLOR_RESET}")
            print("=" * 70)
            
            # 打印新增的消息
            new_messages = last_messages[len(initial_messages):]
            for idx, msg in enumerate(new_messages, 1):
                print(f"{COLOR_AI}--- 消息 {idx} ---{COLOR_RESET}")
                print(msg)
                if idx < len(new_messages):
                    print()
            
            print("=" * 70)
        else:
            print(f"{COLOR_SYSTEM}[错误] 未收到回复（超时或 iflow 无响应）{COLOR_RESET}")
    
    def _extract_reply_from_tmux(self) -> list:
        """从 tmux 输出中提取所有回复（每个独立的"✦"标记一条消息）。
        
        Returns:
            提取到的回复列表，每个元素是一条独立的消息
        """
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", self.tmux_session, "-p"],
                capture_output=True,
                text=True
            )
            
            output = result.stdout
            lines = output.split('\n')
            
            messages = []
            in_thinking = False
            
            for i, line in enumerate(lines):
                curr_line_stripped = line.strip()
                
                # 检测思考区域的开始
                if '✻ 思考中' in line:
                    in_thinking = True
                    continue
                
                # 检测思考区域的结束（遇到"✦"标记，表示开始实际回复）
                if in_thinking and '✦' in line and '✻' not in line and '✹' not in line:
                    in_thinking = False
                    # 继续处理这条消息
                
                # 如果在思考区域中，跳过
                if in_thinking:
                    continue
                
                # 检查是否包含"✦"标记（任何位置的"✦"）
                if '✦' in line and '✻' not in line and '✹' not in line:
                    # 去掉所有"✦"符号
                    clean_line = curr_line_stripped.replace('✦', '').strip()
                    
                    # 排除用户输入（以 > 开头）
                    if clean_line.startswith('>'):
                        continue
                    
                    # 排除空行
                    if not clean_line:
                        continue
                    
                    # 添加到消息列表
                    messages.append(clean_line)
                    print(f"{COLOR_SYSTEM}[调试] 提取消息 {len(messages)}: {clean_line[:50]}{COLOR_RESET}", flush=True)
            
            print(f"{COLOR_SYSTEM}[调试] 提取完成，共 {len(messages)} 条消息{COLOR_RESET}", flush=True)
            
            return messages
        except Exception as e:
            logger.error(f"提取 tmux 回复失败: {e}")
            return []


async def main():
    """主函数。"""
    import argparse
    
    parser = argparse.ArgumentParser(description="iflow 交互式对话")
    parser.add_argument("--tmux-session", "-t", default="iflow", help="tmux 会话名称")
    parser.add_argument("--workspace", "-w", default="~/.iflow", help="iflow 工作目录")
    parser.add_argument("message", nargs="?", help="要发送的消息（可选）")
    parser.add_argument("--timeout", default=60, type=int, help="等待回复的超时时间（秒）")
    
    args = parser.parse_args()
    
    # 创建交互式对话
    chat = InteractiveChat(
        tmux_session=args.tmux_session,
        workspace=args.workspace
    )
    
    # 如果提供了消息，使用命令行模式
    if args.message:
        await chat.send_and_get_reply(args.message, args.timeout)
    else:
        # 否则进入交互模式
        await chat.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\033[33m[系统] 程序已退出\033[0m")