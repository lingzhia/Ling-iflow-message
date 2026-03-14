# IFlowModule 功能测试计划

## 已测试功能 ✅

1. **消息提取功能**
   - ✅ 接收消息识别
   - ✅ TUI 界面过滤
   - ✅ 消息定位
   - ✅ 完整对话记录

2. **IFlowController 功能**
   - ✅ 启动/停止 iflow
   - ✅ 发送消息
   - ✅ 捕获输出
   - ✅ 状态检测

3. **IFlowMonitor 功能**
   - ✅ 状态检测（空闲/生成中）
   - ✅ 消息提取（✦ 回复和 ✻ 思考）
   - ✅ 消息去重
   - ✅ 订阅机制

4. **完整对话测试**
   - ✅ 单条消息
   - ✅ 多条消息
   - ✅ 复杂对话

## 未测试功能 ❌

### P0 优先级

1. **生成中拒绝机制**
   - 在生成中状态时拒绝新消息
   - 返回正确的拒绝响应
   - 包含持续时间信息

2. **结束通知**
   - 生成结束时发送 complete 消息
   - 通知订阅者

### P1 优先级

3. **MessageStore**
   - 消息记录
   - 状态管理（pending/processing/completed）
   - 来源查询
   - scope 查询

4. **InteractionLogger**
   - 会话开始/结束记录
   - 消息发送/接收记录
   - 持久化存储
   - 会话历史查询

5. **SessionManager**
   - 会话创建
   - 会话查询
   - 会话删除

### P2 优先级

6. **scope 过滤**
   - reply_only 只发送 ✦ 回复
   - all 发送所有消息（✦ 和 ✻）

7. **状态变更回调**
   - IDLE -> GENERATING 回调
   - GENERATING -> IDLE 回调
   - 传递持续时间信息

## 测试计划

### 阶段 1: 核心功能测试（P0）

#### 测试 1: 生成中拒绝机制
- 启动 iflow
- 发送第一条消息，等待生成中状态
- 在生成中状态时发送第二条消息
- 验证第二条消息被拒绝
- 验证返回正确的拒绝响应

#### 测试 2: 结束通知
- 监听状态变更回调
- 发送消息并等待生成完成
- 验证收到 GENERATING -> IDLE 回调
- 验证收到 complete 消息

### 阶段 2: 数据管理测试（P1）

#### 测试 3: MessageStore
- 发送多条消息
- 验证消息记录到 MessageStore
- 验证状态更新（pending -> processing -> completed）
- 验证来源查询
- 验证 scope 查询

#### 测试 4: InteractionLogger
- 发送消息并接收回复
- 验证发送消息记录
- 验证接收消息记录
- 验证会话开始/结束记录
- 验证持久化存储

#### 测试 5: SessionManager
- 创建新会话
- 查询所有会话
- 删除指定会话

### 阶段 3: 高级功能测试（P2）

#### 测试 6: scope 过滤
- 设置 scope="reply_only"
- 发送消息并接收回复
- 验证只收到 ✦ 回复消息

- 设置 scope="all"
- 发送消息并接收回复
- 验证收到所有消息（✦ 和 ✻）

#### 测试 7: 状态变更回调
- 设置状态变更回调
- 发送消息
- 验证收到 IDLE -> GENERATING 回调
- 验证收到 GENERATING -> IDLE 回调
- 验证持续时间信息

## 测试脚本

1. `test_generating_rejection.py` - 生成中拒绝机制测试
2. `test_complete_notification.py` - 结束通知测试
3. `test_message_store.py` - MessageStore 测试
4. `test_interaction_logger.py` - InteractionLogger 测试
5. `test_session_manager.py` - SessionManager 测试
6. `test_scope_filtering.py` - scope 过滤测试
7. `test_state_callbacks.py` - 状态变更回调测试