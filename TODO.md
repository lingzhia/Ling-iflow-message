# Ling-iflow 待办任务

## 模块测试待办

### IFlowModule
- [x] 启动/停止 iflow
- [x] 发送消息
- [x] 接收回复
- [x] 状态检测 (idle/generating)
- [x] 消息分类 (reply/other)
- [x] 过滤机制 (scope)
- [x] 拒绝机制
- [x] 多轮对话来源归属
- [x] 交互日志记录
- [x] 多模块实例并行

### WeChatModule
- [ ] HTTP 回调接收测试
- [ ] 消息发送测试
- [ ] 消息确认机制测试
- [ ] 消息去重机制测试
- [ ] 与 IFlowModule 集成测试

### CommandHandler
- [ ] 与 MessageBus 集成测试
- [ ] 命令解析测试
- [ ] 命令执行测试

### MessageBus
- [ ] 模块注册/注销测试
- [ ] 消息路由测试
- [ ] 绑定关系测试
- [ ] 发布订阅测试

---

## 工具测试待办

### tools/iflow_interactive_tool.py
- [x] 启动/停止模块
- [x] 发送消息
- [x] 接收回复
- [x] `/source` 切换身份
- [x] `/scope` 切换模式
- [x] `/status` 状态查询
- [x] `/history` 历史记录
- [x] `/spam` 拒绝机制测试

### tools/wechat_test_tool.py
- [ ] listen 模式测试
- [ ] send 模式测试
- [ ] 与 IFlowModule 联动测试

---

## 功能完善待办

### P0 - 核心功能
- [ ] WeChatModule 与 IFlowModule 完整集成
- [ ] MessageBus 绑定机制完善
- [ ] CommandHandler 集成到消息流

### P1 - 增强功能
- [ ] 多机器人支持（多微信实例绑定多 iflow 实例）
- [ ] 错误处理和重试机制
- [ ] 日志系统优化

### P2 - 扩展功能
- [ ] Web 控制台
- [ ] 配置热更新
- [ ] 监控告警

---

## 已知问题

### 已修复
1. [已修复] IFlowModule 消息处理顺序问题
2. [已修复] duration 计算问题
3. [已修复] 消息来源丢失问题

### 待解决
1. [待解决] WeChatModule 需要真实企业微信环境测试
2. [待解决] CommandHandler 需要集成到消息流

---

## 下一步工作

1. **集成测试**：WeChatModule + IFlowModule + MessageBus
2. **工具测试**：wechat_test_tool.py 功能验证
3. **文档更新**：README.md 和使用说明

---

*最后更新: 2026-03-12*
