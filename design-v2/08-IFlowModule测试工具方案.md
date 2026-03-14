# IFlowModule 测试工具设计方案

## 目标

创建一个测试工具，用于单独测试 IFlowModule 的功能，排除消息总线的干扰。

## 设计原则

1. **消息格式一致** - 发送和接收的消息格式与消息总线完全一致
2. **排除消息总线风险** - 使用模拟的消息总线，不依赖真实的消息总线实现
3. **介于消息总线与 IFlowModule 之间** - 工具模拟消息总线的功能
4. **完整测试流程** - 测试 IFlowModule 的完整消息处理流程
5. **工具不感知 tmux** - 工具只对接 IFlowModule，不感知 tmux 的存在
6. **保持 IFlowModule 接口不变** - 不修改 IFlowModule 的接口，不影响现有代码

## 架构设计

```
工具 (IFlowInteractiveTool)
  ↓ 从配置文件读取参数
  ↓ 传递给 IFlowModule
IFlowModule (接口不变)
  ↓ 发送 Message
模拟消息总线 (MockMessageBus)
  ↓ 路由
IFlowModule.receive(Message)
  ↓ _on_receive
IFlowModule.send()
  ↓ controller.send_message()

Monitor 提取 OutboundMessage
  ↓ _on_monitor_message
scope 过滤
  ↓ 转换为 Message
调用钩子 _message_sent_hook(Message)  ← 工具拦截
  ↓ send_to_bus
真实消息总线（可选）
```

## 实现步骤

### 1. IFlowModule - 保持接口不变

IFlowModule 的接口保持不变，由调用者（bot.py 或工具）负责传递参数：

```python
# IFlowModule 接口（不变）
def __init__(
    self,
    module_id: Optional[str] = None,
    tmux_session: Optional[str] = None,
    model: str = "kimi-k2.5",
    workspace: str = "~/.iflow",
    auto_restart: bool = True,
    log_interactions: bool = True,
    log_dir: str = "logs/interactions"
):
    ...
```

### 2. 工具实现模拟消息总线

```python
class MockMessageBus:
    """模拟消息总线（用于测试）"""

    def __init__(self):
        self._iflow_module = None

    def bind(self, from_module, to_module, bidirectional=False):
        """绑定（简化版，不需要路由逻辑）"""
        pass

    async def route(self, message: Message):
        """路由消息（直接调用 IFlowModule）"""
        if self._iflow_module:
            await self._iflow_module.receive(message)

    def set_iflow_module(self, module):
        """设置 IFlowModule"""
        self._iflow_module = module
```

### 3. 工具修改

```python
class IFlowInteractiveTool:
    """IFlowModule 交互式测试工具"""

    def __init__(self, config_path: str = "config.json"):
        """初始化工具

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.mock_bus = MockMessageBus()
        self.module: Optional[IFlowModule] = None

        # 当前身份和模式
        self.current_source: str = "tool"
        self.current_scope: str = "reply_only"

        # 消息历史
        self.message_history: List[dict] = []

    async def start(self):
        """启动工具"""
        print("=" * 60)
        print("IFlowModule 交互式体验工具")
        print("=" * 60)

        print(f"\n正在创建 IFlowModule 实例...")

        # 工具负责从配置文件读取参数，然后传递给 IFlowModule
        tmux_session = self.config.get("tmux_session")
        model = self.config.get("model", "kimi-k2.5")
        workspace = self.config.get("workspace", "~/.iflow")
        auto_restart = self.config.get("auto_restart", True)
        log_interactions = self.config.get("log_interactions", True)
        log_dir = self.config.get("log_dir", "logs/interactions")

        # 创建模块实例
        self.module = IFlowModule(
            tmux_session=tmux_session,
            model=model,
            workspace=workspace,
            auto_restart=auto_restart,
            log_interactions=log_interactions,
            log_dir=log_dir
        )

        # 设置模拟消息总线
        self.module.set_message_bus(self.mock_bus)
        self.mock_bus.set_iflow_module(self.module)

        # 设置钩子（拦截返回的消息）
        self.module.set_message_sent_hook(self._on_iflow_message)

        # 启动 IFlowModule
        await self.module.start()
```

## 关键优势

1. **消息格式一致** - 发送和接收的都是 `Message` 对象
2. **不依赖真实消息总线** - 使用模拟的消息总线
3. **测试完整流程** - 包括 scope 过滤、消息转换
4. **代码改动最小** - 只在 IFlowModule 中添加钩子，不影响现有代码
5. **工具介于消息总线与 IFlowModule 之间** - 符合要求
6. **工具不感知 tmux** - 工具只对接 IFlowModule
7. **保持 IFlowModule 接口不变** - 不影响现有代码（bot.py）

## 测试场景

1. **基本消息发送** - 验证消息能正确发送到 iflow
2. **scope 过滤** - 验证只发送 ✦ 标记的消息
3. **✻ 标记记录** - 验证 ✻ 标记的消息被正确记录但不发送
4. **状态检测** - 验证状态正确变化
5. **重复消息** - 验证去重逻辑
6. **多行内容** - 验证多行内容正确提取

## 使用方法

```bash
# 交互模式（使用配置文件默认参数）
python tools/iflow_interactive_tool.py

# 交互模式（指定配置文件）
python tools/iflow_interactive_tool.py --config config.json

# 命令行模式
python tools/iflow_interactive_tool.py --message "你好"

# 交互命令
直接输入文字 → 发送消息
/status → 查看状态
/history → 查看历史
/help → 显示帮助
quit → 退出
```

## 参数说明

| 参数 | 说明 | 是否必须 |
|------|------|---------|
| `--config PATH` | 配置文件路径 | 否（默认 config.json） |
| `--message TEXT` | 命令行模式：发送消息后退出 | 否 |
| `--scope MODE` | scope 模式：all 或 reply_only（默认） | 否 |

## 与现有代码的兼容性

**不影响现有代码：**
- IFlowModule 的接口保持不变
- bot.py 中对 IFlowModule 的调用不需要任何修改
- 工具单独负责配置文件的读取和参数传递

**职责分离：**
- bot.py - 负责生产环境的配置管理和参数传递
- 工具 - 负责测试环境的配置管理和参数传递
- IFlowModule - 只负责功能实现