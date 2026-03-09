# Python 异步编程教程（第一部分）

## 目录

1. [异步编程简介](#异步编程简介)
2. [asyncio 核心概念](#asyncio-核心概念)
3. [协程与 async/await](#协程与-asyncawait)
4. [事件循环](#事件循环)
5. [任务管理](#任务管理)
6. [基础实践示例](#基础实践示例)

---

## 异步编程简介

### 什么是异步编程？

异步编程是一种编程范式，允许程序在等待某些操作（如 I/O）完成时，继续执行其他任务，而不是阻塞整个程序。

### 同步 vs 异步

**同步编程：**
```python
import time

def sync_task(name, duration):
    print(f"开始任务 {name}")
    time.sleep(duration)  # 阻塞等待
    print(f"完成任务 {name}")
    return f"{name} 完成"

# 执行时间：6 秒（串行执行）
sync_task("A", 2)
sync_task("B", 2)
sync_task("C", 2)
```

**异步编程：**
```python
import asyncio

async def async_task(name, duration):
    print(f"开始任务 {name}")
    await asyncio.sleep(duration)  # 非阻塞等待
    print(f"完成任务 {name}")
    return f"{name} 完成"

async def main():
    # 执行时间：约 2 秒（并发执行）
    await asyncio.gather(
        async_task("A", 2),
        async_task("B", 2),
        async_task("C", 2)
    )

asyncio.run(main())
```

### 异步编程的优势

- **高并发**：同时处理多个 I/O 操作
- **低延迟**：减少等待时间
- **资源高效**：单线程处理大量连接
- **响应性强**：保持界面和服务的响应性

### 适用场景

- 网络请求（HTTP、WebSocket）
- 数据库操作
- 文件 I/O
- 实时通信
- 微服务架构

### 不适用场景

- CPU 密集型计算（使用多进程）
- 需要真正并行的场景

---

## asyncio 核心概念

### asyncio 简介

`asyncio` 是 Python 3.4+ 内置的异步 I/O 库，提供以下核心功能：

- **事件循环**：调度和执行协程
- **协程**：可暂停和恢复的函数
- **任务**：包装协程，提供额外功能
- **Future**：表示尚未完成的操作结果

### 基本结构

```python
import asyncio

# 定义协程
async def my_coroutine():
    print("协程开始")
    await asyncio.sleep(1)
    print("协程结束")
    return "完成"

# 运行协程
async def main():
    result = await my_coroutine()
    print(f"结果: {result}")

# 启动事件循环
asyncio.run(main())
```

### 关键术语

| 术语 | 说明 |
|------|------|
| **协程（Coroutine）** | 使用 `async def` 定义的函数，可以暂停和恢复 |
| **事件循环（Event Loop）** | 调度和执行协程的机制 |
| **任务（Task）** | 包装协程的对象，可以追踪状态 |
| **Future** | 表示异步操作的结果 |
| **await** | 暂停协程执行，等待异步操作完成 |
| **async** | 定义协程函数的关键字 |

---

## 协程与 async/await

### 定义协程

```python
import asyncio

# 简单协程
async def simple_coroutine():
    print("协程执行中")
    await asyncio.sleep(1)
    return "协程完成"

# 带参数的协程
async def parameterized_coroutine(name, delay):
    print(f"协程 {name} 开始")
    await asyncio.sleep(delay)
    print(f"协程 {name} 结束")
    return f"{name} 完成（延迟 {delay} 秒）"
```

### await 表达式

`await` 只能在 `async def` 函数中使用，用于等待异步操作完成。

```python
import asyncio
import random

async def fetch_data(url):
    print(f"获取 {url}")
    await asyncio.sleep(random.uniform(0.5, 2))
    return f"{url} 的数据"

async def process_data(data):
    print(f"处理数据: {data}")
    await asyncio.sleep(1)
    return f"已处理: {data}"

async def main():
    # 串行执行
    data = await fetch_data("https://api.example.com")
    result = await process_data(data)
    print(result)

asyncio.run(main())
```

### 协程链式调用

```python
import asyncio

async def step1():
    print("步骤 1：初始化")
    await asyncio.sleep(1)
    return "初始化完成"

async def step2(prev_result):
    print(f"步骤 2：处理 {prev_result}")
    await asyncio.sleep(1)
    return "处理完成"

async def step3(prev_result):
    print(f"步骤 3：验证 {prev_result}")
    await asyncio.sleep(1)
    return "验证完成"

async def chain_example():
    result1 = await step1()
    result2 = await step2(result1)
    result3 = await step3(result2)
    print(f"最终结果: {result3}")

asyncio.run(chain_example())
```

### 协程对象

```python
import asyncio

async def my_coroutine():
    return "协程结果"

# 创建协程对象（不立即执行）
coro = my_coroutine()
print(f"类型: {type(coro)}")  # <class 'coroutine'>

# 运行协程
result = asyncio.run(coro)
print(result)
```

---

## 事件循环

### 事件循环简介

事件循环是异步编程的核心，负责：
- 调度协程的执行
- 管理 I/O 事件
- 处理回调函数
- 管理任务和 Future

### 获取事件循环

```python
import asyncio

async def task():
    print("任务执行")
    await asyncio.sleep(1)
    return "完成"

# 方法 1：使用 asyncio.run（推荐）
asyncio.run(task())

# 方法 2：手动获取事件循环
async def main2():
    loop = asyncio.get_event_loop()
    result = await loop.create_task(task())
    print(result)

asyncio.run(main2())
```

### 事件循环方法

```python
import asyncio

async def simple_task(name):
    print(f"任务 {name} 开始")
    await asyncio.sleep(1)
    print(f"任务 {name} 结束")

async def loop_methods():
    loop = asyncio.get_event_loop()
    
    # 创建任务
    task1 = loop.create_task(simple_task("A"))
    task2 = loop.create_task(simple_task("B"))
    
    # 获取当前时间
    current_time = loop.time()
    print(f"当前时间: {current_time}")
    
    # 调度回调
    def callback():
        print("回调函数执行")
    
    loop.call_soon(callback)
    
    # 延迟调度
    loop.call_later(2, callback)
    
    # 定时调度
    loop.call_at(loop.time() + 3, callback)
    
    # 等待任务完成
    await task1
    await task2

asyncio.run(loop_methods())
```

### 事件循环控制

```python
import asyncio

async def controlled_task(name, duration):
    print(f"任务 {name} 开始")
    try:
        await asyncio.sleep(duration)
        print(f"任务 {name} 完成")
        return f"{name} 成功"
    except asyncio.CancelledError:
        print(f"任务 {name} 被取消")
        raise

async def loop_control():
    # 创建任务
    task1 = asyncio.create_task(controlled_task("A", 5))
    task2 = asyncio.create_task(controlled_task("B", 2))
    
    # 等待部分任务
    await task2
    print("任务 B 已完成")
    
    # 取消任务 A
    task1.cancel()
    
    try:
        await task1
    except asyncio.CancelledError:
        print("任务 A 取消成功")

asyncio.run(loop_control())
```

---

## 任务管理

### 创建任务

```python
import asyncio

async def background_task(name, duration):
    print(f"后台任务 {name} 开始")
    await asyncio.sleep(duration)
    print(f"后台任务 {name} 完成")
    return f"{name} 的结果"

async def task_creation():
    # 创建任务
    task1 = asyncio.create_task(background_task("任务1", 2))
    task2 = asyncio.create_task(background_task("任务2", 1))
    
    print("任务已创建，可以执行其他操作...")
    
    # 执行其他操作
    await asyncio.sleep(0.5)
    print("执行其他操作中...")
    
    # 等待任务完成
    await task1
    await task2
    
    # 获取结果
    result1 = task1.result()
    result2 = task2.result()
    print(f"结果: {result1}, {result2}")

asyncio.run(task_creation())
```

### 任务状态

```python
import asyncio

async def task_with_status(name, duration):
    await asyncio.sleep(duration)
    return f"{name} 完成"

async def task_status():
    task = asyncio.create_task(task_with_status("示例任务", 2))
    
    # 检查任务状态
    print(f"任务完成: {task.done()}")
    print(f"任务取消: {task.cancelled()}")
    
    # 等待任务完成
    await task
    
    print(f"任务完成: {task.done()}")
    print(f"任务结果: {task.result()}")

asyncio.run(task_status())
```

### 任务取消

```python
import asyncio

async def long_running_task():
    print("长时间任务开始")
    try:
        for i in range(10):
            print(f"进度: {i + 1}/10")
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("任务被取消")
        raise  # 重新抛出取消异常

async def cancellation_example():
    task = asyncio.create_task(long_running_task())
    
    # 等待 3 秒后取消
    await asyncio.sleep(3)
    
    print("正在取消任务...")
    task.cancel()
    
    try:
        await task
    except asyncio.CancelledError:
        print("任务已被取消")

asyncio.run(cancellation_example())
```

### 超时控制

```python
import asyncio

async def slow_operation():
    print("开始慢操作")
    await asyncio.sleep(5)
    return "操作完成"

async def timeout_control():
    try:
        # 设置 2 秒超时
        result = await asyncio.wait_for(
            slow_operation(),
            timeout=2.0
        )
        print(result)
    except asyncio.TimeoutError:
        print("操作超时！")

asyncio.run(timeout_control())
```

### 任务组（Python 3.11+）

```python
import asyncio

async def task(name, duration):
    print(f"任务 {name} 开始")
    await asyncio.sleep(duration)
    print(f"任务 {name} 完成")
    return f"{name} 结果"

async def task_group_example():
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(task("A", 2))
            tg.create_task(task("B", 1))
            tg.create_task(task("C", 3))
    except Exception as e:
        print(f"任务组出错: {e}")
    else:
        print("所有任务完成")

asyncio.run(task_group_example())
```

---

## 基础实践示例

### 示例 1：并发执行多个任务

```python
import asyncio
import random

async def fetch_data(url):
    print(f"获取 {url}")
    delay = random.uniform(0.5, 2)
    await asyncio.sleep(delay)
    return f"{url} 的数据（耗时 {delay:.1f} 秒）"

async def concurrent_fetch():
    urls = [
        "https://api1.com",
        "https://api2.com",
        "https://api3.com",
        "https://api4.com"
    ]
    
    # 并发执行
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    
    print("\n结果:")
    for result in results:
        print(f"  - {result}")

asyncio.run(concurrent_fetch())
```

### 示例 2：带错误处理的任务

```python
import asyncio

async def task_with_error(name, should_fail):
    print(f"任务 {name} 开始")
    await asyncio.sleep(1)
    
    if should_fail:
        raise ValueError(f"{name} 失败")
    
    return f"{name} 成功"

async def error_handling():
    tasks = [
        task_with_error("任务A", False),
        task_with_error("任务B", True),
        task_with_error("任务C", False)
    ]
    
    # return_exceptions=True 不会抛出异常
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ 任务 {chr(65+i)} 失败: {result}")
        else:
            print(f"✅ 任务 {chr(65+i)} 成功: {result}")

asyncio.run(error_handling())
```

### 示例 3：限制并发数量

```python
import asyncio

async def worker(name, queue):
    while True:
        item = await queue.get()
        print(f"{name} 处理: {item}")
        await asyncio.sleep(1)
        queue.task_done()

async def limited_concurrency():
    # 创建任务队列
    queue = asyncio.Queue()
    
    # 添加任务
    for i in range(10):
        await queue.put(f"任务 {i}")
    
    # 创建 3 个工作协程
    workers = [
        asyncio.create_task(worker(f"Worker {i}", queue))
        for i in range(3)
    ]
    
    # 等待所有任务完成
    await queue.join()
    
    # 取消工作协程
    for w in workers:
        w.cancel()
    
    print("所有任务完成")

asyncio.run(limited_concurrency())
```

### 示例 4：按完成顺序处理结果

```python
import asyncio
import random

async def fetch_data(url):
    delay = random.uniform(0.5, 3)
    await asyncio.sleep(delay)
    return {
        "url": url,
        "data": f"{url} 的数据",
        "duration": delay
    }

async def process_in_order():
    urls = [
        "https://api1.com",
        "https://api2.com",
        "https://api3.com",
        "https://api4.com"
    ]
    
    # 按完成顺序处理
    for coro in asyncio.as_completed([
        fetch_data(url) for url in urls
    ]):
        result = await coro
        print(f"✅ {result['url']} 完成（耗时 {result['duration']:.1f}秒）")

asyncio.run(process_in_order())
```

### 示例 5：等待第一个完成的任务

```python
import asyncio
import random

async def task(name, duration):
    print(f"任务 {name} 开始（预计 {duration} 秒）")
    await asyncio.sleep(duration)
    return f"{name} 完成"

async def wait_first():
    tasks = [
        asyncio.create_task(task("快速任务", 1)),
        asyncio.create_task(task("中等任务", 2)),
        asyncio.create_task(task("慢速任务", 3))
    ]
    
    # 等待第一个任务完成
    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED
    )
    
    print("\n完成的任务:")
    for task in done:
        print(f"  - {task.result()}")
    
    print("\n取消未完成的任务:")
    for task in pending:
        task.cancel()
        print(f"  - 已取消")

asyncio.run(wait_first())
```

### 示例 6：生产者-消费者模式

```python
import asyncio
import random

async def producer(queue, name):
    for i in range(5):
        item = f"{name}-产品{i}"
        print(f"生产: {item}")
        await queue.put(item)
        await asyncio.sleep(random.uniform(0.1, 0.5))
    print(f"{name} 生产完成")

async def consumer(queue, name):
    while True:
        item = await queue.get()
        print(f"消费: {item}")
        await asyncio.sleep(random.uniform(0.2, 0.8))
        queue.task_done()

async def producer_consumer():
    queue = asyncio.Queue(maxsize=10)
    
    # 创建生产者和消费者
    producers = [
        asyncio.create_task(producer(queue, f"生产者{i}"))
        for i in range(2)
    ]
    
    consumers = [
        asyncio.create_task(consumer(queue, f"消费者{i}"))
        for i in range(3)
    ]
    
    # 等待所有生产者完成
    await asyncio.gather(*producers)
    
    # 等待队列清空
    await queue.join()
    
    # 取消消费者
    for c in consumers:
        c.cancel()
    
    print("生产消费完成")

asyncio.run(producer_consumer())
```

---

## 最佳实践

### 1. 使用 asyncio.run() 作为入口点

```python
# ✅ 推荐
async def main():
    # 主逻辑
    pass

asyncio.run(main())

# ❌ 不推荐
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
```

### 2. 始终使用 await 等待协程

```python
# ✅ 正确
async def correct():
    result = await some_async_function()
    print(result)

# ❌ 错误（协程不会执行）
async def incorrect():
    result = some_async_function()  # 创建了协程对象但没有等待
    print(result)
```

### 3. 避免在协程中使用阻塞操作

```python
import time
import asyncio

# ❌ 错误：阻塞事件循环
async def bad():
    time.sleep(2)  # 阻塞整个事件循环

# ✅ 正确：使用异步等待
async def good():
    await asyncio.sleep(2)  # 非阻塞

# ✅ 对于 CPU 密集型操作，使用线程池
async def cpu_bound():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: sum(i * i for i in range(1000000))
    )
    return result
```

### 4. 正确处理异常

```python
import asyncio

async def task_with_error():
    raise ValueError("任务失败")

async def proper_error_handling():
    try:
        await task_with_error()
    except ValueError as e:
        print(f"捕获到错误: {e}")
    else:
        print("任务成功")

asyncio.run(proper_error_handling())
```

### 5. 使用上下文管理器管理资源

```python
import asyncio

async def with_context_manager():
    # 使用 async with 确保资源正确释放
    async with some_async_resource() as resource:
        await resource.do_something()
    # 资源自动释放
```

---

## 常见陷阱

### 陷阱 1：忘记 await

```python
# ❌ 错误
async def forgot_await():
    result = async_function()  # 协程没有执行
    print(result)  # 输出: <coroutine object>

# ✅ 正确
async def with_await():
    result = await async_function()  # 等待协程完成
    print(result)
```

### 陷阱 2：在非协程函数中使用 await

```python
# ❌ 错误
def normal_function():
    await async_function()  # 语法错误

# ✅ 正确
async def async_function():
    await async_function()  # 可以使用
```

### 陷阱 3：混用同步和异步代码

```python
import time
import asyncio

# ❌ 错误：在异步代码中使用同步阻塞
async def mixed_bad():
    await asyncio.sleep(1)
    time.sleep(2)  # 阻塞事件循环
    await asyncio.sleep(1)

# ✅ 正确：全部使用异步
async def mixed_good():
    await asyncio.sleep(1)
    await asyncio.sleep(2)
    await asyncio.sleep(1)
```

### 陷阱 4：不取消未完成的任务

```python
import asyncio

async def never_ending():
    while True:
        await asyncio.sleep(1)

async def forget_cancel():
    task = asyncio.create_task(never_ending())
    await asyncio.sleep(2)
    # 忘记取消任务，会导致程序无法正常退出

# ✅ 正确
async def proper_cancel():
    task = asyncio.create_task(never_ending())
    await asyncio.sleep(2)
    task.cancel()  # 取消任务
    try:
        await task
    except asyncio.CancelledError:
        pass
```

---

## 总结

本教程第一部分涵盖了 Python 异步编程的基础知识：

1. **异步编程简介**：理解同步与异步的区别和优势
2. **asyncio 核心概念**：事件循环、协程、任务、Future
3. **协程与 async/await**：定义和使用协程
4. **事件循环**：管理和控制事件循环
5. **任务管理**：创建、取消、超时控制
6. **基础实践示例**：多个实际应用场景
7. **最佳实践**：编写高质量异步代码的准则
8. **常见陷阱**：避免常见错误

### 关键要点

- `async def` 定义协程函数
- `await` 等待异步操作完成
- `asyncio.run()` 启动事件循环
- `asyncio.create_task()` 创建任务
- `asyncio.gather()` 并发执行多个任务
- 避免阻塞事件循环
- 正确处理异常和资源清理

### 下一步

在第二部分中，我们将学习：
- 异步 I/O 操作（网络请求、文件操作）
- 高级并发模式
- 性能优化技巧
- 实战案例分析

继续学习第二部分，掌握更多高级异步编程技巧！