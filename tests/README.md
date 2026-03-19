# 测试目录

此目录用于存储测试文件。

## 目录结构

```
tests/
├── unit/              # 单元测试
├── integration/       # 集成测试
├── e2e/               # 端到端测试
├── fixtures/          # 测试数据和 Mock 对象
└── docs/              # 测试文档
```

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/unit/test_message_bus.py

# 运行测试并显示详细输出
pytest tests/ -v

# 运行测试并显示覆盖率
pytest tests/ --cov=src
```

## 测试工具

项目提供了以下测试工具：

- `tools/iflow_interactive_tool.py` - IFlow 交互式测试工具
- `tools/test_client.py` - 模拟器测试客户端
- `tools/wechat_test_tool.py` - 企业微信测试工具
- `tools/tmux_viewer.py` - Tmux 查看工具

## 测试文档

- `TEST_PLAN.md` - 测试计划
- `TEST_SUMMARY.md` - 测试总结

## 注意事项

- 测试文件命名：`test_*.py`
- 测试类命名：`Test*`
- 测试函数命名：`test_*`