# 模块设计 - Interactive 层

## 概述

Interactive 层是项目的核心层，负责协调各个组件，实现 iflow CLI 和企业微信的双向同步。包含同步管理、机器人集成、会话监控、iflow 控制、会话管理和消息分发等核心功能。

## 目录结构

```
interactive/
├── __init__.py
├── bot_integration.py   # 机器人集成模块
├── iflow_controller.py  # iflow CLI 控制器
├── message_dispatcher.py # 消息分发器
├── session_manager.py   # 会话管理器
├── session_monitor.py   # 会话监控器
└── sync_manager.py      # 同步管理器
```

## SyncManager（同步管理器）

### 职责
协调各个组件，实现 iflow CLI 和企业微信的双向同步。

### 主要功能
- 启动/停止同步服务
- 企业微信消息队列管理
- iflow 回复监控
- 统计信息收集

### 核心属性

```python
class SyncManager:
    def __init__(
        self,
        workspace: str = "~/.iflow",
        tmux_session: str = "iflow",
        wechat_config: Optional[WechatWorkConfig] = None,
    ):
        self.workspace = workspace
        self.tmux_session = tmux_session
        self.wechat_config = wechat_config
        
        # 核心组件
        self.monitor = SessionMonitor(workspace)
        self.controller = IFlowController(tmux_session)
        self.wechat_channel = None
        
        # 消息队列
        self._wechat_queue = asyncio.Queue()
        
        # 运行状态
        self.running = False
        self._tasks = []
        
        # 统计信息
        self.stats = {
            "messages_sent_to_iflow": 0,
            "messages_synced_to_wechat": 0,
            "errors": 0,
        }
```

### 核心方法

#### 1. start() - 启动同步服务

```python
async def start(self, auto_start_iflow: bool = True) -> bool:
    """启动同步服务。
    
    Args:
        auto_start_iflow: 是否自动启动 iflow
        
    Returns:
        是否启动成功
    """
    if self.running:
        logger.warning("[SyncManager] Already running")
        return True
    
    logger.info("[SyncManager] Starting sync service...")
    
    # 1. 检查 iflow 是否运行
    if not self.controller.check_iflow_running():
        if auto_start_iflow:
            logger.info("[SyncManager] iflow not running, starting...")
            if not self.controller.start_iflow():
                logger.error("[SyncManager] Failed to start iflow")
                return False
        else:
            logger.error("[SyncManager] iflow not running and auto_start disabled")
            return False
    
    # 2. 初始化企业微信渠道
    if self.wechat_config and self.wechat_config.enabled:
        logger.info("[SyncManager] Initializing WeChat Work channel...")
        self.wechat_channel = WechatWorkChannel(
            config=self.wechat_config,
            bus=None,
        )
        
        # 设置消息处理器
        async def _message_handler(content, sender_id, chat_id, is_group, metadata):
            await self.receive_wechat_message(content, sender_id, chat_id, metadata)
        
        self.wechat_channel.set_message_handler(_message_handler)
        
        # 启动企业微信渠道
        try:
            await asyncio.wait_for(self.wechat_channel.start(), timeout=30)
            logger.info("[SyncManager] WeChat Work channel started")
        except asyncio.TimeoutError:
            logger.error("[SyncManager] Timeout starting WeChat Work channel")
            return False
    
    # 3. 启动监控循环
    self.running = True
    self._tasks.append(asyncio.create_task(self._monitor_loop()))
    self._tasks.append(asyncio.create_task(self._wechat_loop()))
    
    logger.info("[SyncManager] Sync service started")
    return True
```

#### 2. _monitor_loop() - 监控循环

```python
async def _monitor_loop(self) -> None:
    """监控 iflow 输出循环。"""
    logger.info("[SyncManager] Monitor loop started")
    
    while self.running:
        try:
            # 检查是否有新消息
            if self.monitor.should_check():
                new_messages = self.monitor.read_new_assistant_messages()
                
                # 发送新消息到企业微信
                for msg in new_messages:
                    await self.send_to_wechat(msg)
            
            # 等待一段时间再检查
            await asyncio.sleep(0.2)
            
        except Exception as e:
            logger.error(f"[SyncManager] Monitor loop error: {e}", exc_info=True)
            await asyncio.sleep(1)
```

#### 3. _wechat_loop() - 企业微信消息处理循环

```python
async def _wechat_loop(self) -> None:
    """企业微信消息处理循环。"""
    logger.info("[SyncManager] WeChat loop started")
    
    while self.running:
        try:
            # 从队列中取出消息
            msg = await asyncio.wait_for(self._wechat_queue.get(), timeout=1.0)
            
            # 发送到 iflow
            await self._send_to_iflow(msg)
            
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"[SyncManager] WeChat loop error: {e}", exc_info=True)
```

#### 4. send_to_wechat() - 发送消息到企业微信

```python
async def send_to_wechat(self, message: Dict[str, Any]) -> None:
    """发送消息到企业微信。
    
    Args:
        message: 消息字典
    """
    if not self.wechat_channel:
        logger.warning("[SyncManager] WeChat channel not available")
        return
    
    try:
        # 提取消息内容
        content = message.get("content", "")
        
        # 发送到企业微信
        success = await self.wechat_channel.send(
            content=content,
            chat_id="",  # 发送给配置的用户
            is_group=False
        )
        
        if success:
            self.stats["messages_synced_to_wechat"] += 1
            logger.debug(f"[SyncManager] Message synced to WeChat")
        else:
            self.stats["errors"] += 1
            logger.error("[SyncManager] Failed to send message to WeChat")
            
    except Exception as e:
        logger.error(f"[SyncManager] Error sending to WeChat: {e}", exc_info=True)
```

#### 5. receive_wechat_message() - 接收企业微信消息

```python
async def receive_wechat_message(
    self,
    content: str,
    sender_id: str,
    chat_id: str,
    metadata: Optional[dict] = None
) -> None:
    """接收企业微信消息。
    
    Args:
        content: 消息内容
        sender_id: 发送者 ID
        chat_id: 聊天 ID
        metadata: 元数据
    """
    try:
        # 将消息放入队列
        await self._wechat_queue.put({
            "content": content,
            "sender_id": sender_id,
            "chat_id": chat_id,
            "metadata": metadata
        })
        
        logger.debug(f"[SyncManager] Message received from WeChat: {content[:50]}")
        
    except Exception as e:
        logger.error(f"[SyncManager] Error receiving WeChat message: {e}", exc_info=True)
```

## BotIntegration（机器人集成）

### 职责
连接企业微信渠道和 iflow CLI，实现消息双向流转。

### 主要功能
- 接收企业微信消息
- 解析命令（/run, /new, /sessions, /help, /status, /lscmd, /start-iflow, /stop-iflow, /restart-iflow）
- 调用 iflow CLI
- 发送回复到企业微信
- 支持连续对话（自动恢复上次会话）
- 管理 iflow 服务（启动、停止、重启）

### 核心属性

```python
class BotIntegration:
    def __init__(
        self,
        wechat_channel: Any,
        tmux_session: str = "iflow",
        workspace: str = "~/.iflow",
        filter_thinking: bool = True,
        extract_all_messages: bool = False
    ):
        self.wechat_channel = wechat_channel
        self.tmux_session = tmux_session
        self.workspace = workspace
        self.filter_thinking = filter_thinking
        self.extract_all_messages = extract_all_messages
        
        # 初始化组件
        self.session_manager = SessionManager(workspace)
        self.iflow_controller = IFlowController(tmux_session)
        
        # 消息缓冲区
        self._message_buffer: Dict[str, str] = {}
        self._sent_marker_ids: set = set()
        self._wechat_message_markers: set = set()
        self._last_sent_marker_id: str = ""
        self._current_marker: Optional[str] = None
        self._sent_message_hashes: set = set()
        self._sent_markers: set = set()
        
        # 消息来源跟踪
        self._current_source: str = ""
        self._pending_messages: list = []
        self._processing_wechat_request: bool = False
```

### 核心方法

#### 1. handle_message() - 处理入站消息

```python
async def handle_message(
    self,
    content: str,
    sender_id: str,
    chat_id: str,
    is_group: bool,
    metadata: Optional[dict] = None,
    source: str = "wechat"
) -> None:
    """处理入站消息。
    
    Args:
        content: 消息内容
        sender_id: 发送者 ID
        chat_id: 聊天 ID
        is_group: 是否为群聊
        metadata: 元数据
        source: 消息来源（wechat/tool）
    """
    try:
        # 解析命令
        parsed = self._parse_command(content)
        
        if not parsed["valid"]:
            await self._send_help(chat_id, is_group)
            return
        
        # 处理命令
        await self._handle_command(
            parsed["type"],
            parsed.get("command", ""),
            chat_id,
            is_group
        )
        
    except Exception as e:
        logger.error(f"[BotIntegration] Error handling message: {e}", exc_info=True)
        await self.wechat_channel.send(
            f"❌ 处理消息时出错: {str(e)}",
            chat_id,
            is_group=is_group
        )
```

#### 2. _parse_command() - 解析命令

```python
def _parse_command(self, content: str) -> Dict:
    """解析用户消息，提取命令。"""
    trimmed = content.strip()
    
    # 支持的命令格式
    if trimmed.startswith("/run "):
        return {"valid": True, "type": "run", "command": trimmed[5:].strip()}
    if trimmed == "/new":
        return {"valid": True, "type": "new"}
    if trimmed == "/sessions":
        return {"valid": True, "type": "sessions"}
    if trimmed == "/status":
        return {"valid": True, "type": "status"}
    if trimmed == "/lscmd":
        return {"valid": True, "type": "lscmd"}
    if trimmed == "/start-iflow":
        return {"valid": True, "type": "start-iflow"}
    if trimmed == "/stop-iflow":
        return {"valid": True, "type": "stop-iflow"}
    if trimmed == "/restart-iflow":
        return {"valid": True, "type": "restart-iflow"}
    if trimmed == "/help":
        return {"valid": True, "type": "help"}
    
    # 直接发送命令（不带前缀）
    if trimmed and not trimmed.startswith("/"):
        return {"valid": True, "type": "run", "command": trimmed}
    
    return {"valid": False, "type": "unknown"}
```

#### 3. _run_command() - 运行 iFlow 命令

```python
async def _run_command(
    self,
    chat_id: str,
    is_group: bool,
    command: str,
    source: str = "wechat"
) -> None:
    """运行 iFlow 命令。
    
    Args:
        chat_id: 聊天 ID
        is_group: 是否为群聊
        command: 命令内容
        source: 消息来源（wechat/tool）
    """
    # 设置当前来源
    self._current_source = source
    
    try:
        # 检查 iflow 是否运行
        if not self.iflow_controller.check_iflow_running():
            await self.wechat_channel.send(
                "❌ iflow 未运行，请先启动 iflow",
                chat_id,
                is_group=is_group
            )
            return
        
        # 发送确认消息
        await self.wechat_channel.send(
            f"⏳ 正在执行: {command}",
            chat_id,
            is_group=is_group
        )
        
        # 发送命令到 iflow
        success = self.iflow_controller.send_message(command)
        
        if not success:
            await self.wechat_channel.send(
                "❌ 发送命令失败",
                chat_id,
                is_group=is_group
            )
            return
        
        # 等待 iflow 回复
        await asyncio.sleep(2)
        
        # 提取回复
        messages, is_generating, generation_time, user_question = self._extract_reply_from_tmux()
        
        # 清理消息内容
        cleaned_messages = []
        for msg in messages:
            content = msg.get('content', '')
            cleaned_content = self._clean_message_content(content)
            if cleaned_content:
                cleaned_messages.append(cleaned_content)
        
        # 发送回复
        for msg in cleaned_messages:
            await self.wechat_channel.send(msg, chat_id, is_group=is_group)
        
        # 发送完成提示
        await self.wechat_channel.send(
            "✅ 执行完成",
            chat_id,
            is_group=is_group
        )
        
    except Exception as e:
        logger.error(f"[BotIntegration] Error running command: {e}", exc_info=True)
        await self.wechat_channel.send(
            f"❌ 执行命令时出错: {str(e)}",
            chat_id,
            is_group=is_group
        )
    finally:
        # 清理当前来源
        self._current_source = ""
```

#### 4. _extract_reply_from_tmux() - 从 tmux 提取回复

```python
def _extract_reply_from_tmux(self) -> Tuple[List[Dict], bool, float, str]:
    """从 tmux 输出中提取回复。
    
    Returns:
        (消息列表, 是否在生成中, 生成时间, 用户问题)
    """
    # 捕获 tmux 输出
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", self.tmux_session, "-S", "-1000", "-p"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode != 0:
        logger.error("[BotIntegration] Failed to capture tmux output")
        return [], False, 0.0, ""
    
    lines = result.stdout.split('\n')
    
    # 定位当前对话（查找用户提问）
    user_question = ""
    current_dialog = []
    found_question = False
    
    for line in reversed(lines):
        if line.startswith("> "):
            user_question = line[2:].strip()
            found_question = True
            break
        current_dialog.insert(0, line)
    
    # 提取标记消息
    messages = []
    current_message = []
    current_marker = None
    
    for line in current_dialog:
        if '✦' in line or '✻' in line:
            # 保存上一条消息
            if current_marker and current_message:
                content = '\n'.join(current_message).strip()
                messages.append({
                    'marker_id': current_marker,
                    'content': content,
                    'full_marker': f'✦ {current_marker}' if '✦' in line else f'✻ {current_marker}'
                })
            
            # 开始新消息
            current_marker = line.replace('✦', '').replace('✻', '').strip()
            current_message = []
        else:
            current_message.append(line)
    
    # 保存最后一条消息
    if current_marker and current_message:
        content = '\n'.join(current_message).strip()
        messages.append({
            'marker_id': current_marker,
            'content': content,
            'full_marker': f'✦ {current_marker}' if current_marker else ''
        })
    
    return messages, False, 0.0, user_question
```

#### 5. _clean_message_content() - 清理消息内容

```python
def _clean_message_content(self, content: str) -> str:
    """清理消息内容，去除 iflow 的 UI 元素。"""
    if not content:
        return content
    
    # 类型检查
    if not isinstance(content, str):
        logger.error(f"[BotIntegration] 收到非字符串类型: {type(content)}")
        return ''
    
    # 查找分隔符
    separators = [
        '---', '══', '────────', '────────────────',
        '════════════════', '══════════════════════════',
        '══════════════════════════════════════',
        '══════════════════════════════════════════════════',
    ]
    
    # 找到第一个分隔符的位置
    first_separator_pos = -1
    for sep in separators:
        pos = content.find(sep)
        if pos != -1 and (first_separator_pos == -1 or pos < first_separator_pos):
            first_separator_pos = pos
    
    # 如果找到分隔符，只保留之前的内容
    if first_separator_pos != -1:
        cleaned_content = content[:first_separator_pos].strip()
        logger.debug(f"[BotIntegration] 清理消息：移除 {len(content) - len(cleaned_content)} 个字符")
        return cleaned_content
    
    return content.strip()
```

## SessionManager（会话管理器）

### 职责
管理 iflow 的会话文件，提供会话查询、创建等功能。

### 主要功能
- 获取最新的会话文件
- 获取所有会话列表
- 创建新会话
- 删除指定会话
- 获取当前会话信息

### 核心方法

```python
class SessionManager:
    def __init__(self, workspace: str = "~/.iflow"):
        self.workspace = Path(workspace).expanduser()
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
    
    def get_latest_session(self) -> Optional[Dict]:
        """获取最新的 session 文件。"""
        pass
    
    def get_all_sessions(self, limit: int = 20) -> List[Dict]:
        """获取所有 session 列表。"""
        pass
    
    def create_new_session(self) -> bool:
        """创建新会话。"""
        pass
    
    def delete_session(self, session_id: str) -> bool:
        """删除指定 session。"""
        pass
    
    def get_status_message(self) -> str:
        """获取状态信息的 Markdown 文本。"""
        pass
```

## IFlowController（iflow 控制器）

### 职责
通过 tmux send-keys 命令向 iflow CLI 会话注入消息。

### 主要功能
- 检查 tmux 会话是否存在
- 检查 iflow CLI 是否运行
- 发送消息到 iflow CLI
- 启动/停止 iflow CLI

### 核心方法

```python
class IFlowController:
    def __init__(self, tmux_session: str = "iflow"):
        self.tmux_session = tmux_session
    
    def check_tmux_session(self) -> bool:
        """检查 tmux 会话是否存在。"""
        pass
    
    def check_iflow_running(self) -> bool:
        """检查 iflow CLI 是否运行。"""
        pass
    
    def send_message(self, message: str) -> bool:
        """发送消息到 iflow CLI。"""
        pass
    
    def start_iflow(self, model: str = "kimi-k2.5") -> bool:
        """在 tmux 会话中启动 iflow CLI。"""
        pass
    
    def stop_iflow(self) -> bool:
        """停止 iflow CLI。"""
        pass
    
    def get_session_info(self) -> Optional[Dict]:
        """获取会话信息。"""
        pass
```

## SessionMonitor（会话监控器）

### 职责
监控 iflow CLI 的会话文件，实时读取 AI 回复。

### 主要功能
- 查找所有会话文件
- 读取新增的 AI 回复消息
- 消息去重
- 自动检测新会话

### 核心方法

```python
class SessionMonitor:
    def __init__(self, workspace: str = "~/.iflow"):
        self.workspace = Path(workspace).expanduser()
        self.session_files: Dict[Path, int] = {}
        self.processed_ids = set()
        self.last_check_time = 0
        self.check_interval = 0.2
    
    def find_session_files(self) -> List[Path]:
        """查找所有会话文件。"""
        pass
    
    def read_new_assistant_messages(self) -> List[Dict[str, Any]]:
        """读取新增的 AI 回复消息。"""
        pass
    
    def should_check(self) -> bool:
        """检查是否应该执行监控检查。"""
        pass
    
    def reset(self) -> None:
        """重置监控器状态。"""
        pass
```

## MessageDispatcher（消息分发器）

### 职责
处理消息分发逻辑，支持多种消息来源和目的地。

### 主要功能
- 消息路由
- 消息过滤
- 消息转换

## 相关文档

- [设计总览](./01-设计总览.md) - 项目概述、整体架构、核心目标
- [架构设计](./02-架构设计.md) - 详细的架构设计
- [模块设计-Channels层](./03-模块设计-Channels层.md) - 渠道层的详细设计
- [模块设计-Config层](./05-模块设计-Config层.md) - 配置层的详细设计
- [模块设计-CLI层](./06-模块设计-CLI层.md) - CLI层的详细设计