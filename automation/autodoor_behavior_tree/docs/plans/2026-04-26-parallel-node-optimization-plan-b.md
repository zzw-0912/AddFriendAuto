# 并行节点优化方案B：多线程并行执行

## 1 方案概述

使用多线程实现真正的并行执行。ParallelNode 为每个子节点创建独立线程，子节点在各自线程中独立 tick，通过线程安全的状态收集器汇总结果。

## 2 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    ParallelNode 多线程架构                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────────────────────────────┐ │
│  │  Engine      │     │  ParallelNode                        │ │
│  │  (主线程)    │────▶│  tick() → 检查子节点状态              │ │
│  │              │     │                                      │ │
│  └──────────────┘     │  ┌─────────┐  ┌─────────┐           │ │
│                       │  │ Thread1 │  │ Thread2 │  ...       │ │
│                       │  │ Child1  │  │ Child2  │           │ │
│                       │  │ tick()  │  │ tick()  │           │ │
│                       │  └────┬────┘  └────┬────┘           │ │
│                       │       │            │                 │ │
│                       │       ▼            ▼                 │ │
│                       │  ┌──────────────────────────────────┐│ │
│                       │  │    线程安全状态收集器              ││ │
│                       │  │  _child_status: Dict[int, Status] ││ │
│                       │  └──────────────────────────────────┘│ │
│                       └──────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 3 核心组件

### 3.1 线程安全的子节点状态收集器

```python
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional


class ChildStatusCollector:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._child_status: Dict[str, NodeStatus] = {}
        self._child_lock = threading.Lock()
        self._futures: Dict[str, Future] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(max_workers=4)
        return cls._instance

    def submit_child(self, child_id: str, tick_func, context) -> None:
        with self._child_lock:
            if child_id in self._futures and not self._futures[child_id].done():
                return
            self._futures[child_id] = self._executor.submit(tick_func, context)

    def get_child_status(self, child_id: str) -> Optional[NodeStatus]:
        with self._child_lock:
            if child_id in self._child_status:
                return self._child_status[child_id]
            if child_id in self._futures:
                future = self._futures[child_id]
                if future.done():
                    try:
                        status = future.result()
                        self._child_status[child_id] = status
                        return status
                    except Exception:
                        self._child_status[child_id] = NodeStatus.FAILURE
                        return NodeStatus.FAILURE
            return None

    def is_child_running(self, child_id: str) -> bool:
        with self._child_lock:
            if child_id in self._futures:
                return not self._futures[child_id].done()
            return False

    def clear_child(self, child_id: str) -> None:
        with self._child_lock:
            if child_id in self._futures:
                future = self._futures[child_id]
                if not future.done():
                    future.cancel()
                del self._futures[child_id]
            self._child_status.pop(child_id, None)

    def clear_all(self) -> None:
        with self._child_lock:
            for future in self._futures.values():
                if not future.done():
                    future.cancel()
            self._futures.clear()
            self._child_status.clear()
```

### 3.2 线程安全的执行上下文代理

```python
class ThreadSafeContextProxy:
    _input_lock = threading.Lock()
    _window_lock = threading.Lock()

    def __init__(self, original_context: ExecutionContext):
        self._original = original_context

    @property
    def blackboard(self):
        return self._original.blackboard

    @property
    def elapsed_time(self):
        return self._original.elapsed_time

    @property
    def tick_count(self):
        return self._original.tick_count

    def check_running(self) -> bool:
        return self._original.check_running()

    def notify_node_status(self, node_id: str, status: str) -> None:
        self._original.notify_node_status(node_id, status)

    def get_screenshot(self, region=None):
        return self._original.get_screenshot(region)

    def execute_key_press(self, key, action="press", duration=0):
        with self._input_lock:
            self._original.execute_key_press(key, action, duration)

    def execute_mouse_click(self, button="left", position=None, action="press", duration=0):
        with self._input_lock:
            self._original.execute_mouse_click(button, position, action, duration)

    def execute_mouse_move(self, position, relative=False):
        with self._input_lock:
            self._original.execute_mouse_move(position, relative)

    def resolve_path(self, relative_path):
        return self._original.resolve_path(relative_path)

    def get_bound_window(self):
        return self._original.get_bound_window()

    def smart_switch_to_bound_window(self):
        with self._window_lock:
            return self._original.smart_switch_to_bound_window()

    def smart_restore_foreground_window(self):
        with self._window_lock:
            return self._original.smart_restore_foreground_window()

    def record_node_stats(self, node_id, node_type, node_name, status, duration_ms):
        self._original.record_node_stats(node_id, node_type, node_name, status, duration_ms)
```

### 3.3 ParallelNode 多线程改造

```python
class ParallelNode(CompositeNode):
    NODE_TYPE = "ParallelNode"
    SUCCESS_POLICY_ALL = "require_all"
    SUCCESS_POLICY_ONE = "require_one"

    def __init__(self, node_id=None, config=None):
        super().__init__(node_id, config)
        self.cached_statuses: Dict[int, NodeStatus] = {}
        self.success_policy = self.config.get("success_policy", self.SUCCESS_POLICY_ALL)
        self._child_threads: Dict[int, threading.Thread] = {}
        self._child_results: Dict[int, NodeStatus] = {}
        self._child_lock = threading.Lock()
        self._started = False

    def tick(self, context):
        return self._execute_with_decorators(context, self._tick_internal)

    def _tick_internal(self, context):
        from bt_utils.log_manager import LogManager

        if not self.children:
            LogManager.instance().log_success(node_type="并行节点", node_name=self.name)
            return NodeStatus.SUCCESS

        if not self._started:
            self._start_all_children(context)
            self._started = True

        return self._collect_results(context)

    def _start_all_children(self, context):
        for i, child in enumerate(self.children):
            if not child.config.enabled:
                continue
            if i in self.cached_statuses:
                self._child_results[i] = self.cached_statuses[i]
                continue

            proxy = ThreadSafeContextProxy(context)
            thread = threading.Thread(
                target=self._run_child,
                args=(i, child, proxy),
                daemon=True
            )
            self._child_threads[i] = thread
            thread.start()

    def _run_child(self, index, child, context_proxy):
        while True:
            status = child.tick(context_proxy)
            with self._child_lock:
                self._child_results[index] = status
            if status != NodeStatus.RUNNING:
                break
            if not context_proxy.check_running():
                break
            time.sleep(0.01)

    def _collect_results(self, context):
        from bt_utils.log_manager import LogManager

        success_count = 0
        failure_count = 0
        running_count = 0
        enabled_count = 0

        for i, child in enumerate(self.children):
            if not child.config.enabled:
                continue
            enabled_count += 1

            if i in self.cached_statuses:
                status = self.cached_statuses[i]
                if status == NodeStatus.SUCCESS:
                    success_count += 1
                elif status == NodeStatus.FAILURE:
                    failure_count += 1
                continue

            with self._child_lock:
                status = self._child_results.get(i, NodeStatus.RUNNING)

            if status == NodeStatus.SUCCESS:
                self.cached_statuses[i] = NodeStatus.SUCCESS
                success_count += 1
            elif status == NodeStatus.FAILURE:
                self.cached_statuses[i] = NodeStatus.FAILURE
                failure_count += 1
            elif status == NodeStatus.RUNNING:
                running_count += 1

        if self.success_policy == self.SUCCESS_POLICY_ONE and success_count > 0:
            self._abort_running_children(context)
            LogManager.instance().log_success(node_type="并行节点", node_name=self.name)
            return NodeStatus.SUCCESS

        if running_count > 0:
            return NodeStatus.RUNNING

        if self.success_policy == self.SUCCESS_POLICY_ALL:
            if success_count == enabled_count:
                LogManager.instance().log_success(node_type="并行节点", node_name=self.name)
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="并行节点", node_name=self.name,
                    reason=f"成功 {success_count}/{enabled_count} 个子节点")
                return NodeStatus.FAILURE
        else:
            if success_count > 0:
                LogManager.instance().log_success(node_type="并行节点", node_name=self.name)
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="并行节点", node_name=self.name,
                    reason="所有子节点都执行失败")
                return NodeStatus.FAILURE

    def _abort_running_children(self, context):
        for i, thread in self._child_threads.items():
            if thread.is_alive():
                with self._child_lock:
                    if self._child_results.get(i) == NodeStatus.RUNNING:
                        self.children[i].abort(context)

    def reset(self, reset_counters=True):
        super().reset(reset_counters)
        self.cached_statuses.clear()
        self._child_threads.clear()
        self._child_results.clear()
        self._started = False

    def _reset_for_retry(self):
        super()._reset_for_retry()
        self.cached_statuses.clear()
        self._child_threads.clear()
        self._child_results.clear()
        self._started = False

    def _reset_for_repeat(self):
        super()._reset_for_repeat()
        self.cached_statuses.clear()
        self._child_threads.clear()
        self._child_results.clear()
        self._started = False
```

## 4 线程安全分析

| 共享资源 | 安全措施 | 说明 |
|---------|---------|------|
| Blackboard | 已有 `threading.RLock` | blackboard.py:23 已实现线程安全 |
| ExecutionContext | `ThreadSafeContextProxy` 代理 | 输入操作加锁串行化，避免并发输入冲突 |
| UI 通知 | `UIUpdateDispatcher` 已有队列 | ui_dispatcher.py 已实现线程安全 |
| 子节点状态 | `_child_lock` | 新增锁保护 `_child_results` |
| OCRManager | 单例 + 缓存 | 需要验证线程安全性 |
| InputController | 代理加锁 | 输入操作串行化 |

## 5 关键风险与缓解

| 风险 | 严重程度 | 缓解措施 |
|------|---------|---------|
| 并发输入冲突（鼠标/键盘） | 高 | ThreadSafeContextProxy 对输入操作加锁串行化 |
| OCR 线程安全 | 中 | OCRManager 使用缓存 + 独立实例 |
| 窗口切换冲突 | 高 | 窗口切换操作加锁，同一时间只有一个线程操作窗口 |
| 子节点异常传播 | 中 | 线程内捕获异常，转换为 FAILURE 状态 |
| 资源泄漏 | 中 | reset() 时清理所有线程和 Future |

## 6 优缺点

| 维度 | 评价 |
|------|------|
| 并行效果 | 优秀 - 真正的并行执行，阻塞操作互不影响 |
| 实现复杂度 | 高 - 需要线程安全代理、状态收集器等基础设施 |
| 风险 | 高 - 线程安全问题难以调试，可能引入新 bug |
| 兼容性 | 中等 - 需要验证所有节点的线程安全性 |
| 性能提升 | 优秀 - 总执行时间等于最长子节点时间 |

## 7 新增文件清单

| 文件 | 说明 |
|------|------|
| bt_core/child_status_collector.py | 线程安全的子节点状态收集器 |
| bt_core/context_proxy.py | 线程安全的执行上下文代理 |

## 8 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| bt_core/nodes.py | ParallelNode 改为多线程执行模式 |
