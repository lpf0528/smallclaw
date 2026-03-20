# asyncio

## asyncio.create_task
用来把一个协程对象包装成一个并发运行的任务（Task），并交给事件循环调度执行。




## run_coroutine_threadsafe  

把一个协程提交到“另一个线程中的事件循环”执行 的工具函数。
它的典型场景是：你当前在 别的线程 里，想让那个 loop 去执行一个协程

> 本质是：从别的线程，安全地把一个协程提交到指定事件循环中执行，并返回一个可在线程中等待结果的 Future。



### 函数的作用
```python
asyncio.run_coroutine_threadsafe(
    coroutine,
    loop,
)
```
返回值：concurrent.futures.Future
- 获取执行结果：future.result()
- 获取异常：future.exception()
- 取消任务：future.cancel()

### 为什么需要它
asyncio 的事件循环通常是 线程不安全的。
比如：
- A线程跑：loop.fun_forever()
- B线程跑：loop.create_task(coro)
这样通常不安全

这个时候应该用线程安全的方法把任务投递给loop:
- 投递普通回调：loop.call_soon_threadsafe(..)
- 投递协程：asyncio.run_coroutine_threadsafe(...)


### 基本示例
```python
import asyncio
import threading
import time

async def say_hello():
    await asyncio.sleep(1)
    return "hello"

def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

# 1. 创建一个事件循环
loop = asyncio.new_event_loop()

# 2. 在子线程中启动事件循环
t = threading.Thread(target=start_loop, args=(loop,))
t.start()

# 3. 在主线程中，向子线程的 loop 提交协程
future = asyncio.run_coroutine_threadsafe(say_hello(), loop)

# 4. 获取结果
result = future.result()
print(result)   # hello

# 5. 停止事件循环
loop.call_soon_threadsafe(loop.stop)
t.join()

```

### 例子
比如你有一个消息发送协程，事件循环跑在后台线程中，主线程提交任务：
```python
import asyncio
import threading

async def send_message(msg):
    await asyncio.sleep(1)
    print(f"发送消息: {msg}")
    return f"{msg} 已发送"

def run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

loop = asyncio.new_event_loop()
thread = threading.Thread(target=run_loop, args=(loop,), daemon=True)
thread.start()

def push_message(msg):
    future = asyncio.run_coroutine_threadsafe(send_message(msg), loop)
    return future.result()

print(push_message("hello"))
print(push_message("world"))

loop.call_soon_threadsafe(loop.stop)
thread.join()
```

### add_done_callback(...)
当这个任务完成时（成功、失败、取消都算完成），执行指定回调函数。

```python
future.add_done_callback(lambda f: print(f.result()))
```