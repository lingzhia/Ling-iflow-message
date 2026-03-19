# /scope 命令历史消息重复问题修复方案

## 一、问题背景

### 1.1 问题描述

在使用 `/scope all` 命令切换回复模式后，历史消息会被重复发送，导致：
1. 历史消息被重复发送给用户
2. iflow 进入"生成中"状态
3. 新消息被拒绝

### 1.2 问题复现

```
测试场景：
1. 发送 "1+1=?" → 收到 "1+1=2"
2. 发送 "/scope all" → 切换到全部消息模式
3. 发送 "什么是Python？" → 收到3条消息：
   - 第一条：历史消息 "1+1=2"（重复！）
   - 第二条：Python 介绍
   - 第三条：Python 应用场景
4. 新消息被拒绝："iflow 生成中，请稍后再试"
```

### 1.3 日志证据

```
21:36:02 发送历史消息: "✦ - 2 + 3 = 5"
21:36:02 发送历史消息: "✻ - 思考中..."
21:36:08 iflow 生成中，拒绝消息 (duration=6s)
```

## 二、问题分析

### 2.1 根本原因

**双重失效导致历史消息被重复发送：**

1. **行号过滤失效**：
   - 虽然记录了 `_last_received_line`（发给 iflow 的消息行号）
   - 但是故意不使用它来过滤消息
   - 代码注释："只更新_last_received_line，不过滤内容"

2. **缓存去重失效**：
   - 每次回复完成后清空缓存（monitor.py 第 318-323 行）
   - 缓存被清空后，历史消息通过去重检查
   - 历史消息被重复发送

### 2.2 完整问题流程

```
1. 发送 "1+1=?"
   → iflow 收到消息，记录行号：_last_received_line = 100
   → iflow 回复 "1+1=2"，行号：150
   → IFlowMonitor 提取消息：["1+1=2"]
   → 发送 "1+1=2"
   → 添加到缓存：_sent_marker_strings = {"1+1=2"}
   → 状态变回 IDLE
   → ⚠️ 缓存被清空：_sent_marker_strings = {}  ← 问题1

2. 发送 "/scope all"
   → reply_mode 切换到 "all_messages"

3. 发送 "什么是Python？"
   → iflow 收到消息，记录行号：_last_received_line = 200
   → iflow 开始回复

4. IFlowMonitor 扫描 tmux 输出
   → 提取发给 iflow 的消息：找到 "> 什么是Python？"，行号 200
   → 更新 _last_received_line = 200
   → ⚠️ 但是！扫描消息时，从第 0 行开始扫描  ← 问题2
   → 提取所有标记消息：
     - 行号 150：✦ 1+1=2
     - 行号 250：✦ Python 介绍
     - 行号 300：✦ Python 应用场景
   → ⚠️ 没有使用 _last_received_line=200 来过滤
   → 所有历史消息都被重新提取
   → 缓存已清空，"1+1=2" 通过去重检查
   → "1+1=2" 被重复发送
   → iflow 进入"生成中"状态
   → 新消息被拒绝
```

### 2.3 关键代码

**monitor.py 第 318-323 行（缓存清空）：**
```python
# 清理去重集合（为下一次对话准备）
self._sent_message_hashes.clear()
self._sent_marker_strings.clear()
```

**monitor.py 第 593-594 行（不使用行号过滤）：**
```python
# 只更新_last_received_line，不过滤内容
# 这样可以确保新消息被正确提取
self._last_received_line = received_line
```

## 三、行号固定性分析

### 3.1 发现：行号不是固定的！

```
tmux history-limit = 2000 行
```

这意味着：

1. **tmux 会保留最近的 2000 行输出**
2. **超过 2000 行后，旧内容会被删除**
3. **行号会发生变化**

### 3.2 具体场景

```
场景1：正常情况（输出 < 2000 行）
第一次扫描：
  - 总行数：100
  - 问题 "1+1=?" 在第 50 行
  - 回复在第 60 行

第二次扫描：
  - 总行数：150
  - 问题 "1+1=?" 仍在第 50 行（相对位置不变）
  - 新问题 "什么是Python？" 在第 100 行

场景2：溢出情况（输出 > 2000 行）
第一次扫描：
  - 总行数：2000
  - 问题 "问题1" 在第 100 行
  - 回复在第 120 行

第2001行写入时：
  - 旧的第1行被删除
  - 所有行号都向前移动1位
  - 问题 "问题1" 现在第 99 行（行号变了！）

第三次扫描：
  - 问题 "问题1" 现在第 50 行（行号变了！）
  - 行号过滤失效
```

### 3.3 结论

**行号不可靠，不能依赖行号过滤消息！**

## 四、解决方案

### 4.1 方案对比

| 方案 | 描述 | 优点 | 缺点 | 可靠性 |
|------|------|------|------|--------|
| 方案1 | 使用行号过滤 | 简单直接 | 行号不可靠 | ❌ 不可靠 |
| 方案2 | 保留缓存，不清空 | 利用现有机制 | 缓存增长 | ✅ 可靠 |
| 方案3 | 使用消息内容定位 | 不依赖行号 | 内容可能变化 | ⚠️ 中等 |
| 方案4 | 双重保障 | 结合多种机制 | 实现复杂 | ✅ 可靠 |

### 4.2 推荐方案：方案2（保留缓存，不清空）

**核心思想：**
- 不清空缓存，利用现有的去重机制
- 定期清理旧缓存，控制内存占用

**实现步骤：**

#### 步骤1：修改缓存清空逻辑

```python
# monitor.py 第 318-323 行
# 原代码：
# 清理去重集合（为下一次对话准备）
self._sent_message_hashes.clear()
self._sent_marker_strings.clear()

# 修改为：
# 不清空缓存，保留去重机制
# 只在新会话开始时清空缓存（可选）
# self._sent_message_hashes.clear()  # 注释掉
# self._sent_marker_strings.clear()  # 注释掉
```

#### 步骤2：添加缓存清理机制

```python
# 在 _send_message 方法中添加
def _cleanup_cache(self):
    """清理旧缓存，保留最近的 N 条消息"""
    max_cache_size = 100
    
    if len(self._sent_marker_strings) > max_cache_size:
        # 保留最近的 max_cache_size/2 条
        keep_count = max_cache_size // 2
        self._sent_marker_strings = set(list(self._sent_marker_strings)[-keep_count:])
        self._sent_message_hashes = set(list(self._sent_message_hashes)[-keep_count:])
        logger.debug(f"[IFlowMonitor] 清理缓存：保留最近 {keep_count} 条消息")

# 在 _send_message 方法中调用
async def _send_message(self, message_data: Dict) -> None:
    # ... 去重逻辑 ...
    
    # 添加到已发送集合
    self._sent_marker_strings.add(marker_only)
    self._sent_message_hashes.add(content_hash)
    
    # 清理旧缓存
    self._cleanup_cache()
    
    # ... 发送消息 ...
```

#### 步骤3：可选：检测新会话开始

如果需要在新会话开始时清空缓存：

```python
def _detect_new_session(self, output: str) -> bool:
    """检测新会话开始
    
    检测到新会话时清空缓存。
    新会话特征：
    - tmux 输出中有新的提示符
    - 用户发送了 /new 命令
    """
    lines = output.split('\n')
    
    # 检测新提示符
    for line in lines:
        if '> ' in line and '输入消息' in line:
            # 找到新的提示符，可能是新会话
            return True
    
    return False

# 在 _check 方法中调用
if self._detect_new_session(output):
    logger.info("[IFlowMonitor] 检测到新会话，清空缓存")
    self._sent_message_hashes.clear()
    self._sent_marker_strings.clear()
```

### 4.3 方案优点

1. **简单可靠**：利用现有的去重机制
2. **不依赖行号**：不受 tmux history-limit 影响
3. **内存可控**：定期清理旧缓存
4. **性能良好**：集合查找 O(1) 时间复杂度

### 4.4 方案缺点

1. **缓存增长**：缓存会一直增长到清理阈值
2. **内存占用**：需要占用额外内存存储哈希值
3. **清理时机**：需要选择合适的清理时机

## 五、实施计划

### 5.1 实施步骤

1. **修改缓存清空逻辑**（monitor.py 第 318-323 行）
   - 注释掉缓存清空代码
   - 保留现有去重机制

2. **添加缓存清理机制**（monitor.py _send_message 方法）
   - 实现 _cleanup_cache 方法
   - 在添加新消息后调用清理

3. **可选：添加新会话检测**（monitor.py）
   - 实现 _detect_new_session 方法
   - 在检测到新会话时清空缓存

4. **测试验证**
   - 测试 `/scope all` 命令
   - 验证历史消息不再重复发送
   - 验证缓存清理正常工作

### 5.2 测试用例

```
测试1：基本功能
- 发送 "1+1=?" → 收到 "1+1=2"
- 发送 "/scope all" → 切换模式
- 发送 "2+2=?" → 收到 "2+2=4"
- 验证：历史消息 "1+1=2" 不被重复发送

测试2：多条回复
- 发送 "写一个 Python 脚本" → 收到多条回复
- 发送 "/scope all" → 切换模式
- 发送 "写一个 Bash 脚本" → 收到多条回复
- 验证：Python 脚本回复不被重复发送

测试3：长时间运行
- 发送多条消息（超过 100 条）
- 验证：缓存清理正常工作
- 验证：内存占用可控

测试4：新会话
- 发送 "1+1=?" → 收到 "1+1=2"
- 发送 "/new" → 开始新会话
- 发送 "2+2=?" → 收到 "2+2=4"
- 验证：历史消息 "1+1=2" 不被重复发送
```

## 六、设计文档更新

### 6.1 需要更新的文档

1. **design-v2/03-IFlow模块设计.md**
   - 更新消息去重原则章节
   - 添加缓存管理策略
   - 说明行号不可靠的问题

2. **design-v2/07-消息提取优化方案.md**
   - 更新消息提取策略
   - 说明为什么不使用行号过滤

3. **AGENTS.md**
   - 更新已知问题列表
   - 添加本次修复说明

### 6.2 新增内容

**消息去重原则（更新）：**

| 项目 | 修改前 | 修改后 |
|------|--------|--------|
| 缓存管理 | 每次回复完成后清空 | 保留缓存，定期清理 |
| 缓存清理时机 | GENERATING→IDLE | 达到阈值时清理 |
| 最大缓存大小 | 1000 条 | 100 条（可配置） |
| 保留数量 | 500 条 | 50 条 |
| 行号过滤 | 不使用（故意） | 不使用（不可靠） |

**缓存管理策略（新增）：**

```python
# 缓存管理策略
max_cache_size = 100  # 最大缓存大小
keep_count = 50       # 保留数量

# 清理逻辑
if len(cache) > max_cache_size:
    cache = set(list(cache)[-keep_count:])
```

## 七、风险评估

### 7.1 风险分析

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 内存泄漏 | 低 | 中 | 定期清理缓存 |
| 消息去重失效 | 低 | 高 | 使用双重定位（字符串+哈希） |
| 缓存清理时机不当 | 中 | 低 | 选择合适的清理阈值 |
| 新会话检测失效 | 低 | 低 | 可选功能 |

### 7.2 回滚方案

如果方案出现问题，可以回滚到原始方案：

1. 恢复缓存清空逻辑（monitor.py 第 318-323 行）
2. 删除缓存清理机制
3. 接受历史消息重复发送的问题

## 八、总结

### 8.1 核心发现

1. **行号不可靠**：tmux history-limit 导致行号变化
2. **缓存清空是主要原因**：每次回复完成后清空缓存
3. **保留缓存是最可靠方案**：不依赖行号，利用现有机制

### 8.2 推荐方案

**方案2（保留缓存，不清空）**
- 修改缓存清空逻辑
- 添加缓存清理机制
- 定期清理旧缓存

### 8.3 实施状态

- ✅ 问题分析完成
- ✅ 方案设计完成
- ⏳ 待实施
- ⏳ 待测试

## 九、参考资料

1. **design-v2/03-IFlow模块设计.md** - IFlow 模块设计文档
2. **src/modules/iflow/monitor.py** - IFlowMonitor 实现
3. **tmux 文档** - tmux history-limit 说明

## 十、附录

### A. 相关代码位置

- **monitor.py 第 318-323 行**：缓存清空逻辑
- **monitor.py 第 593-594 行**：行号记录逻辑
- **monitor.py 第 690-720 行**：消息发送逻辑

### B. 测试脚本

```python
# 测试脚本
import asyncio
import sys
sys.path.append('/opt/MyGitCode/Ling-iflow')

from tools.iflow_interactive_tool import IFlowInteractiveTool

async def test_scope_command():
    tool = IFlowInteractiveTool(
        tmux_session='simulator1+iflow',
        keep_alive=False
    )
    
    await tool.start()
    
    # 测试1：基本功能
    print("测试1：基本功能")
    await tool.send_message("1+1=?")
    await asyncio.sleep(2)
    
    await tool.send_message("/scope all")
    await asyncio.sleep(1)
    
    await tool.send_message("2+2=?")
    await asyncio.sleep(2)
    
    # 验证：历史消息 "1+1=2" 不被重复发送
    
    await tool.stop()

if __name__ == "__main__":
    asyncio.run(test_scope_command())
```

### C. 监控指标

需要监控的指标：

1. **缓存大小**：`len(self._sent_marker_strings)`
2. **缓存清理次数**：统计清理调用次数
3. **消息去重命中次数**：统计去重成功次数
4. **内存占用**：监控 Python 进程内存使用

---

**文档版本**：1.0  
**创建日期**：2026-03-18  
**作者**：iFlow CLI  
**状态**：待实施