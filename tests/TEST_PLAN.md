# 新版本测试方案

## 测试目标

基于模块化设计，全面测试新架构的各个模块功能，确保系统稳定性和可靠性。

## 测试架构

### 核心模块
1. **Message 类**（src/core/message.py）
2. **BaseModule 类**（src/core/base.py）
3. **MessageBus 类**（src/core/bus.py）

### 功能模块
1. **IFlowModule**（src/modules/iflow/）
   - IFlowController
   - IFlowMonitor
   - IFlowModule

2. **WeChatModule**（src/modules/wechat/）
   - WeChatChannel
   - WeChatModule

---

## 1. 核心模块测试

### 1.1 Message 类测试

**测试文件**: `tests/test_message.py`

**测试内容**:

#### 1.1.1 消息创建
- [ ] 测试创建文本消息
- [ ] 测试创建图片消息
- [ ] 测试创建语音消息
- [ ] 测试创建视频消息
- [ ] 测试创建文件消息
- [ ] 测试创建系统消息
- [ ] 测试创建错误消息

#### 1.1.2 消息序列化
- [ ] 测试 to_dict() 方法
- [ ] 测试 to_json() 方法
- [ ] 测试 from_dict() 方法
- [ ] 测试 from_json() 方法
- [ ] 测试序列化/反序列化一致性

#### 1.1.3 消息复制
- [ ] 测试 copy() 方法
- [ ] 验证复制的消息与原消息相同
- [ ] 验证复制的消息是独立对象

#### 1.1.4 消息ID生成
- [ ] 测试 generate_id() 方法
- [ ] 验证ID唯一性
- [ ] 验证ID格式正确

**测试代码示例**:
```python
def test_create_text_message():
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="test",
        to_module="test"
    )
    assert msg.type == MessageType.TEXT
    assert msg.content.text == "Hello"
```

---

### 1.2 BaseModule 类测试

**测试文件**: `tests/test_base_module.py`

**测试内容**:

#### 1.2.1 模块生命周期
- [ ] 测试 start() 方法
- [ ] 测试 stop() 方法
- [ ] 测试多次启动/停止

#### 1.2.2 消息总线集成
- [ ] 测试 set_message_bus() 方法
- [ ] 测试消息总线连接
- [ ] 测试消息总线断开

#### 1.2.3 后台任务管理
- [ ] 测试 start_background_task() 方法
- [ ] 测试后台任务启动
- [ ] 测试后台任务停止
- [ ] 测试多个后台任务

#### 1.2.4 日志记录
- [ ] 测试日志输出
- [ ] 验证日志格式
- [ ] 验证日志级别

**测试代码示例**:
```python
def test_module_lifecycle():
    module = TestModule("test_module")
    await module.start()
    assert module.is_running
    await module.stop()
    assert not module.is_running
```

---

### 1.3 MessageBus 类测试

**测试文件**: `tests/test_message_bus.py`

**测试内容**:

#### 1.3.1 模块注册
- [ ] 测试 register_module() 方法
- [ ] 测试模块ID唯一性
- [ ] 测试注册已存在模块
- [ ] 测试 unregister_module() 方法

#### 1.3.2 消息路由
- [ ] 测试 send() 方法（点对点）
- [ ] 测试 route() 方法（基于绑定）
- [ ] 测试目标模块不存在
- [ ] 测试发送失败处理

#### 1.3.3 绑定管理
- [ ] 测试 bind() 方法
- [ ] 测试 unbind() 方法
- [ ] 测试循环绑定检测
- [ ] 测试绑定覆盖

#### 1.3.4 发布-订阅
- [ ] 测试 subscribe() 方法
- [ ] 测试 publish() 方法
- [ ] 测试多个订阅者
- [ ] 测试取消订阅

#### 1.3.5 批量操作
- [ ] 测试 start_all() 方法
- [ ] 测试 stop_all() 方法
- [ ] 测试部分模块启动失败

#### 1.3.6 统计信息
- [ ] 测试 get_stats() 方法
- [ ] 验证消息计数
- [ ] 验证错误计数

**测试代码示例**:
```python
def test_message_routing():
    bus = MessageBus()
    module1 = MockModule("module1")
    module2 = MockModule("module2")
    
    bus.register_module(module1)
    bus.register_module(module2)
    bus.bind("module1", "module2")
    
    msg = Message(...)
    await bus.route(msg)
    
    assert len(module2.messages_received) == 1
```

---

## 2. 功能模块测试

### 2.1 IFlowModule 测试

**测试文件**: `tests/test_iflow_module.py`

**测试内容**:

#### 2.1.1 IFlowController 测试
- [ ] 测试 tmux 会话检查
- [ ] 测试 iflow 进程检查
- [ ] 测试启动 iflow
- [ ] 测试停止 iflow
- [ ] 测试发送消息到 iflow
- [ ] 测试提取 tmux 输出
- [ ] 测试获取会话信息

#### 2.1.2 IFlowMonitor 测试
- [ ] 测试监听器启动
- [ ] 测试监听器停止
- [ ] 测试消息提取
- [ ] 测试消息过滤（✦、✻标记）
- [ ] 测试消息去重
- [ ] 测试用户问题提取
- [ ] 测试思考消息过滤

#### 2.1.3 IFlowModule 集成测试
- [ ] 测试模块启动（不自动启动 iflow）
- [ ] 测试模块启动（自动启动 iflow）
- [ ] 测试消息接收（注入到 iflow）
- [ ] 测试消息广播（iflow 回复）
- [ ] 测试模块停止
- [ ] 测试 tmux 会话清理

**测试场景**:
```python
# 场景 1: 发送消息到 iflow
async def test_send_to_iflow():
    iflow = IFlowModule(
        module_id="iflow_test",
        tmux_session="iflow_test",
        auto_start=True
    )
    
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="test",
        to_module="iflow_test"
    )
    
    await iflow.receive(msg)
    # 验证消息已注入到 iflow

# 场景 2: 监听 iflow 回复
async def test_receive_from_iflow():
    # 设置回调函数
    received_messages = []
    
    async def callback(msg):
        received_messages.append(msg)
    
    iflow.message_bus.subscribe(f"iflow.{iflow.tmux_session}", callback)
    
    # 等待 iflow 生成回复
    await asyncio.sleep(5)
    
    # 验证收到回复
    assert len(received_messages) > 0
```

---

### 2.2 WeChatModule 测试

**测试文件**: `tests/test_wechat_module.py`

**测试内容**:

#### 2.2.1 WeChatChannel 测试
- [ ] 测试 HTTP 回调服务器启动
- [ ] 测试 HTTP 回调服务器停止
- [ ] 测试 URL 验证（GET 请求）
- [ ] 测试消息接收（POST 请求）
- [ ] 测试消息解密
- [ ] 测试消息加密
- [ ] 测试消息签名验证
- [ ] 测试 access_token 获取
- [ ] 测试 access_token 刷新
- [ ] 测试消息发送到企业微信
- [ ] 测试消息去重（基于 MsgId）

#### 2.2.2 WeChatModule 集成测试
- [ ] 测试模块启动
- [ ] 测试模块停止
- [ ] 测试消息接收（从企业微信）
- [ ] 测试消息发送（到企业微信）
- [ ] 测试权限控制（白名单）
- [ ] 测试群聊消息处理
- [ ] 测试错误处理

**测试场景**:
```python
# 场景 1: 接收企业微信消息
async def test_receive_wechat_message():
    wechat = WeChatModule(
        module_id="wechat_test",
        config={...}
    )
    
    await wechat.start()
    
    # 模拟企业微信消息
    # 验证消息被正确接收和处理

# 场景 2: 发送消息到企业微信
async def test_send_wechat_message():
    wechat = WeChatModule(...)
    
    msg = Message(
        id=Message.generate_id(),
        type=MessageType.TEXT,
        content=MessageContent(type=MessageType.TEXT, text="Hello"),
        from_module="iflow_test",
        to_module="wechat_test"
    )
    
    await wechat.receive(msg)
    # 验证消息已发送到企业微信
```

---

## 3. 集成测试

### 3.1 端到端测试

**测试文件**: `tests/test_e2e.py`

**测试内容**:

#### 3.1.1 企业微信 → iflow 流程
- [ ] 企业微信接收消息
- [ ] WeChatModule 处理消息
- [ ] MessageBus 路由消息
- [ ] IFlowModule 接收消息
- [ ] 注入到 iflow CLI
- [ ] 验证消息到达 iflow

#### 3.1.2 iflow → 企业微信 流程
- [ ] iflow 生成回复
- [ ] IFlowMonitor 检测到回复
- [ ] IFlowModule 广播消息
- [ ] MessageBus 路由消息
- [ ] WeChatModule 接收消息
- [ ] 发送到企业微信
- [ ] 验证消息到达企业微信

#### 3.1.3 完整对话流程
- [ ] 用户发送消息到企业微信
- [ ] iflow 生成回复
- [ ] 用户再次发送消息（连续对话）
- [ ] iflow 保持上下文
- [ ] 验证对话连续性

**测试代码示例**:
```python
async def test_e2e_conversation():
    # 创建消息总线
    bus = MessageBus()
    
    # 创建模块
    iflow = IFlowModule(...)
    wechat = WeChatModule(...)
    
    # 注册和绑定
    bus.register_module(iflow)
    bus.register_module(wechat)
    bus.bind("wechat_test", "iflow_test")
    
    # 启动所有模块
    await bus.start_all()
    
    # 模拟用户消息
    user_msg = Message(...)
    await wechat.receive(user_msg)
    
    # 等待 iflow 回复
    await asyncio.sleep(10)
    
    # 验证回复
    # ...
    
    # 停止所有模块
    await bus.stop_all()
```

---

### 3.2 多实例测试

**测试文件**: `tests/test_multi_instance.py`

**测试内容**:

#### 3.2.1 多个 iflow 实例
- [ ] 创建 3 个 iflow 实例
- [ ] 每个实例使用不同的 tmux 会话
- [ ] 同时向所有实例发送消息
- [ ] 验证每个实例独立工作
- [ ] 验证互不干扰

#### 3.2.2 多个企业微信实例
- [ ] 创建 3 个企业微信实例
- [ ] 每个实例使用不同的配置
- [ ] 同时从所有实例接收消息
- [ ] 验证每个实例独立工作
- [ ] 验证互不干扰

#### 3.2.3 多对多绑定
- [ ] 创建 2 个企业微信实例
- [ ] 创建 2 个 iflow 实例
- [ ] 建立多对多绑定
- [ ] 验证消息正确路由
- [ ] 验证负载均衡

**测试代码示例**:
```python
async def test_multiple_iflow_instances():
    bus = MessageBus()
    
    # 创建多个 iflow 实例
    for i in range(3):
        iflow = IFlowModule(
            module_id=f"iflow_{i}",
            tmux_session=f"iflow_{i}",
            auto_start=True
        )
        bus.register_module(iflow)
    
    # 向所有实例发送消息
    for i in range(3):
        msg = Message(...)
        msg.to_module = f"iflow_{i}"
        await bus.send("test", f"iflow_{i}", msg)
    
    # 验证所有实例都收到消息
```

---

### 3.3 压力测试

**测试文件**: `tests/test_stress.py`

**测试内容**:

#### 3.3.1 高并发消息
- [ ] 同时发送 100 条消息
- [ ] 验证所有消息都被处理
- [ ] 验证无消息丢失
- [ ] 验证无消息重复

#### 3.3.2 长时间运行
- [ ] 连续运行 1 小时
- [ ] 每 10 秒发送一条消息
- [ ] 验证系统稳定性
- [ ] 监控内存使用
- [ ] 监控 CPU 使用

#### 3.3.3 错误恢复
- [ ] 模拟 iflow 崩溃
- [ ] 验证自动重启
- [ ] 验证消息不丢失
- [ ] 模拟网络中断
- [ ] 验证重连机制

**测试代码示例**:
```python
async def test_high_concurrency():
    bus = MessageBus()
    # 创建模块...
    
    # 同时发送 100 条消息
    tasks = []
    for i in range(100):
        msg = Message(...)
        task = bus.send("test", "iflow_test", msg)
        tasks.append(task)
    
    # 等待所有消息发送完成
    await asyncio.gather(*tasks)
    
    # 验证所有消息都被处理
```

---

## 4. 性能测试

### 4.1 响应时间测试

**测试内容**:
- [ ] 测试消息路由延迟
- [ ] 测试 iflow 响应时间
- [ ] 测试企业微信响应时间
- [ ] 生成性能报告

### 4.2 吞吐量测试

**测试内容**:
- [ ] 测试最大消息处理速率
- [ ] 测试并发处理能力
- [ ] 生成吞吐量报告

### 4.3 资源使用测试

**测试内容**:
- [ ] 监控内存使用
- [ ] 监控 CPU 使用
- [ ] 监控网络流量
- [ ] 生成资源使用报告

---

## 5. 兼容性测试

### 5.1 向后兼容性
- [ ] 测试与旧版本配置兼容性
- [ ] 测试与旧版本数据兼容性
- [ ] 测试迁移工具

### 5.2 环境兼容性
- [ ] 测试在不同 Python 版本运行
- [ ] 测试在不同操作系统运行
- [ ] 测试依赖库版本兼容性

---

## 6. 安全测试

### 6.1 消息安全
- [ ] 测试消息加密
- [ ] 测试消息解密
- [ ] 测试签名验证
- [ ] 测试消息完整性

### 6.2 权限控制
- [ ] 测试白名单机制
- [ ] 测试群聊权限
- [ ] 测试未授权访问
- [ ] 测试越权访问

---

## 7. 测试执行计划

### 阶段 1: 单元测试（1-2 天）
- 1.1 Message 类测试
- 1.2 BaseModule 类测试
- 1.3 MessageBus 类测试

### 阶段 2: 功能模块测试（2-3 天）
- 2.1 IFlowModule 测试
- 2.2 WeChatModule 测试

### 阶段 3: 集成测试（2-3 天）
- 3.1 端到端测试
- 3.2 多实例测试
- 3.3 压力测试

### 阶段 4: 性能和安全测试（1-2 天）
- 4.1 性能测试
- 4.2 安全测试

### 阶段 5: 验收测试（1 天）
- 5.1 功能验收
- 5.2 性能验收
- 5.3 安全验收

---

## 8. 测试工具

### 必需工具
- `pytest` - 测试框架
- `pytest-asyncio` - 异步测试支持
- `pytest-cov` - 代码覆盖率
- `pytest-mock` - Mock 工具

### 可选工具
- `locust` - 压力测试
- `memory_profiler` - 内存分析
- `py-spy` - 性能分析

---

## 9. 测试标准

### 通过标准
- 所有单元测试通过率 ≥ 95%
- 所有集成测试通过率 ≥ 90%
- 代码覆盖率 ≥ 80%
- 无严重内存泄漏
- 无 CPU 异常占用

### 性能标准
- 消息路由延迟 < 10ms
- iflow 响应时间 < 5s
- 支持并发消息 ≥ 100 条/秒
- 内存使用 < 500MB

---

## 10. 测试报告

测试完成后，生成以下报告：
- 测试执行报告
- 测试覆盖率报告
- 性能测试报告
- 安全测试报告
- 问题清单和修复建议
