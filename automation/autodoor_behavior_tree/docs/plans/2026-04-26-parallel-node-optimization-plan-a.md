# 并行节点优化方案A：检测节点异步非阻塞改造

## 1 方案概述

将4个检测条件节点（OCRConditionNode、ImageConditionNode、NumberConditionNode、TextExtractNode）改造为异步非阻塞执行模式。检测操作在后台线程中执行，不阻塞引擎的 tick 循环，使并行节点中的多个检测子节点可以真正交替执行。

**不改造的节点**：MouseMoveNode（拖拽）、TextInputNode — 这些节点的阻塞行为是正确执行所必需的。

## 2 问题分析

### 2.1 当前执行流程

在并行节点中，4个检测节点的 `_check_condition()` 方法包含阻塞操作：

```
ParallelNode._tick_internal():
    for child in children:
        child.tick(context)
            → ConditionNode._tick_internal()
                → _check_condition(context)   ← 阻塞！OCR/图像匹配耗时 50-500ms
```

当一个检测节点执行 OCR 识别（耗时 200ms），后续子节点必须等待 200ms 才能开始 tick。

### 2.2 各节点阻塞分析

| 节点 | 阻塞操作 | 阻塞时长 | 位置 |
|------|---------|---------|------|
| OCRConditionNode | `OCRManager().recognize()` | 50-500ms | ocr.py:37-40 |
| ImageConditionNode | `ImageProcessor.find_template()` | 10-200ms | image.py:37-39 |
| NumberConditionNode | `OCRManager().recognize_number_with_position()` | 50-500ms | number.py:35-42 |
| TextExtractNode | `OCRManager().get_all_text()` | 50-500ms | text_extract.py:61-63 |

### 2.3 非阻塞改造后的预期执行流程

```
ParallelNode._tick_internal():
    for child in children:
        child.tick(context)
            → ConditionNode._tick_internal()
                → _check_condition(context)
                    → 提交异步任务 → 返回 RUNNING  ← 不阻塞！
                    → 检查异步结果 → 返回 SUCCESS/FAILURE/RUNNING
```

## 3 设计方案

### 3.1 核心思路

在 ConditionNode 基类中增加异步检测支持，通过 `concurrent.futures.ThreadPoolExecutor` 将阻塞的检测操作提交到后台线程执行。每个检测节点维护一个 `_detect_future` 属性，用于跟踪异步任务状态。

**状态机**：
```
idle → (首次tick) → 提交异步任务 → detecting
detecting → (任务未完成) → 返回上一次状态
detecting → (任务完成) → 处理结果 → idle
```

### 3.2 ConditionNode 基类改造

修改文件：`bt_core/nodes.py` 中 `ConditionNode` 类

**新增属性**：

```python
class ConditionNode(Node):
    def __init__(self, node_id=None, config=None):
        super().__init__(node_id, config)
        ...
        self._detect_future = None
        self._detect_executor = None
        self._async_detecting = False
        self._last_async_result = None
```

**修改 `_tick_internal` 方法**：

```python
def _tick_internal(self, context):
    if self._children_running and self.children:
        return self._execute_children(context)

    current_time = context.elapsed_time * 1000
    if current_time - self._last_check_time < self.check_interval_ms:
        return self.status

    if self._async_detecting:
        if self._detect_future is not None and self._detect_future.done():
            try:
                result = self._detect_future.result()
                self._detect_future = None
                self._async_detecting = False
                self._last_async_result = result
            except Exception as e:
                from bt_utils.exception_handler import log_exception
                log_exception(e, f"{self.NODE_TYPE} '{self.name}' 异步检测异常")
                self._detect_future = None
                self._async_detecting = False
                self._last_async_result = False
        else:
            return self.status

    if self._last_async_result is not None:
        result = self._last_async_result
        self._last_async_result = None
    else:
        self._last_check_time = current_time
        result = self._check_condition(context)

    if self.invert:
        result = not result

    status = NodeStatus.SUCCESS if result else NodeStatus.FAILURE
    self.status = status

    if status == NodeStatus.SUCCESS and self.children:
        context.notify_node_status(self.node_id, "success")
        self._children_running = True
        return self._execute_children(context)

    return status
```

**新增异步检测提交方法**：

```python
def _submit_async_detect(self, detect_func, *args, **kwargs):
    if self._detect_executor is None:
        from concurrent.futures import ThreadPoolExecutor
        self._detect_executor = ThreadPoolExecutor(max_workers=1)

    self._async_detecting = True
    self._detect_future = self._detect_executor.submit(detect_func, *args, **kwargs)
```

**修改 `reset` 方法**：

```python
def reset(self, reset_counters=True):
    super().reset(reset_counters)
    self._last_check_time = 0
    if self._detect_future is not None and not self._detect_future.done():
        self._detect_future.cancel()
    self._detect_future = None
    self._async_detecting = False
    self._last_async_result = None
```

### 3.3 OCRConditionNode 改造

修改文件：`bt_nodes/conditions/ocr.py`

**改造 `_check_condition` 方法**：

```python
def _check_condition(self, context) -> bool:
    if self._async_detecting:
        return self.status == NodeStatus.SUCCESS

    try:
        screenshot = self._get_region_image(context)
        if screenshot is None:
            return False

        self._submit_async_detect(
            self._do_ocr_detect, screenshot
        )
        return self.status == NodeStatus.SUCCESS
    except Exception as e:
        from bt_utils.exception_handler import log_exception
        log_exception(e, f"OCRConditionNode '{self.name}'")
        self._log_condition_result(False, "检测异常，详情见终端日志")
        return False

def _do_ocr_detect(self, screenshot) -> bool:
    found, position, all_text = OCRManager().recognize(
        screenshot, self.keywords, self.language,
        preprocess_mode=self.preprocess_mode, region=self.region
    )
    if found:
        self._pending_position = position
        self._pending_log_success = True
        self._pending_log_failure = None
    else:
        self._pending_position = None
        self._pending_log_success = False
        self._pending_log_failure = (f"未找到关键词: {self.keywords}",
                                     f"识别到的文本: {all_text}" if all_text else None)
    return found
```

**修改 `_tick_internal` 中的结果处理**（在基类中统一处理）：

在基类 `_tick_internal` 的异步结果处理部分，需要调用子类的结果处理方法：

```python
if self._detect_future is not None and self._detect_future.done():
    try:
        result = self._detect_future.result()
        self._detect_future = None
        self._async_detecting = False
        self._process_async_result(result)
        self._last_async_result = result
    except Exception as e:
        ...
```

**新增 `_process_async_result` 方法**（在 ConditionNode 基类中）：

```python
def _process_async_result(self, result: bool):
    if result:
        self._log_condition_result(True)
    else:
        self._log_condition_result(False)
```

**OCRConditionNode 重写 `_process_async_result`**：

```python
def _process_async_result(self, result: bool):
    if result:
        if hasattr(self, '_pending_position') and self._pending_position:
            self._save_position(self._pending_context, self._pending_position)
            self._pending_position = None
        self._log_condition_result(True)
    else:
        if hasattr(self, '_pending_log_failure') and self._pending_log_failure:
            reason, extra = self._pending_log_failure
            self._log_condition_result(False, reason, extra)
            self._pending_log_failure = None
        else:
            self._log_condition_result(False)
```

### 3.4 ImageConditionNode 改造

修改文件：`bt_nodes/conditions/image.py`

```python
def _check_condition(self, context) -> bool:
    if self._async_detecting:
        return self.status == NodeStatus.SUCCESS

    try:
        resolved_path = self._resolve_template_path(context)
        if resolved_path is None:
            return False

        screenshot = self._get_region_image(context)
        if screenshot is None:
            return False

        if not os.path.exists(resolved_path):
            self._log_condition_result(False, f"模板文件不存在: {self.template_path}")
            return False

        template = Image.open(resolved_path)
        if template is None:
            self._log_condition_result(False, f"无法加载模板文件: {self.template_path}")
            return False

        self._pending_context = context
        self._submit_async_detect(
            self._do_image_detect, screenshot, template
        )
        return self.status == NodeStatus.SUCCESS
    except Exception as e:
        from bt_utils.exception_handler import log_exception
        log_exception(e, f"ImageConditionNode '{self.name}'")
        self._log_condition_result(False, "检测异常，详情见终端日志")
        return False

def _do_image_detect(self, screenshot, template) -> bool:
    found, position, confidence = ImageProcessor.find_template(
        screenshot, template, self.threshold
    )
    if found:
        actual_position = self._adjust_position(position)
        self._pending_position = actual_position
        self._pending_log_success = True
        self._pending_log_failure = None
    else:
        self._pending_position = None
        self._pending_log_success = False
        self._pending_log_failure = (
            f"未找到匹配模板 (阈值: {self.threshold}, 最高置信度: {confidence:.2f})", None)
    return found

def _process_async_result(self, result: bool):
    if result:
        if hasattr(self, '_pending_position') and self._pending_position:
            self._save_position(self._pending_context, self._pending_position)
            self._pending_position = None
        self._log_condition_result(True)
    else:
        if hasattr(self, '_pending_log_failure') and self._pending_log_failure:
            reason, extra = self._pending_log_failure
            self._log_condition_result(False, reason, extra)
            self._pending_log_failure = None
        else:
            self._log_condition_result(False)
```

### 3.5 NumberConditionNode 改造

修改文件：`bt_nodes/conditions/number.py`

```python
def _check_condition(self, context) -> bool:
    if self._async_detecting:
        return self.status == NodeStatus.SUCCESS

    try:
        if self.region is None:
            self._log_condition_result(False, "请先设置检测区域")
            return False

        screenshot = self._get_region_image(context)
        if screenshot is None:
            return False

        self._pending_context = context
        self._submit_async_detect(
            self._do_number_detect, screenshot
        )
        return self.status == NodeStatus.SUCCESS
    except Exception as e:
        from bt_utils.exception_handler import log_exception
        log_exception(e, f"NumberConditionNode '{self.name}'")
        self._log_condition_result(False, "检测异常，详情见终端日志")
        return False

def _do_number_detect(self, screenshot) -> bool:
    success, value, all_text, position = OCRManager().recognize_number_with_position(
        screenshot,
        language=self.language,
        preprocess_mode=self.preprocess_mode,
        extract_mode=self.extract_mode,
        extract_pattern=self.extract_pattern,
        min_confidence=self.min_confidence
    )
    self._pending_number_result = (success, value, all_text, position)
    return success and value is not None

def _process_async_result(self, result: bool):
    if hasattr(self, '_pending_number_result'):
        success, value, all_text, position = self._pending_number_result
        self._pending_number_result = None

        if not success or value is None:
            self._log_condition_result(False, f"无法识别数字 (文本: {all_text})")
            return

        if position:
            actual_position = (position[0] + self.region[0], position[1] + self.region[1])
            self._save_position(self._pending_context, actual_position)

        self._pending_context.blackboard.set("last_number_value", value)
        if self.value_key and self.value_key != "last_number_value":
            self._pending_context.blackboard.set(self.value_key, value)

        compare_result = self._compare_value(value)
        if compare_result:
            self._log_condition_result(True, extra_info=f"值: {value}")
        else:
            self._log_condition_result(False,
                f"数值比较失败: {value} {self.comparison} {self.target_value}")
```

### 3.6 TextExtractNode 改造

修改文件：`bt_nodes/conditions/text_extract.py`

```python
def _check_condition(self, context) -> bool:
    if self._async_detecting:
        return self.status == NodeStatus.SUCCESS

    try:
        screenshot = self._get_region_image(context)
        if screenshot is None:
            return False

        self._pending_context = context
        self._submit_async_detect(
            self._do_text_extract, screenshot
        )
        return self.status == NodeStatus.SUCCESS
    except Exception as e:
        from bt_utils.exception_handler import log_exception
        log_exception(e, f"TextExtractNode '{self.name}'")
        self._log_condition_result(False, "执行异常，详情见终端日志")
        return False

def _do_text_extract(self, screenshot) -> bool:
    ocr_manager = OCRManager()
    all_text = ocr_manager.get_all_text(
        screenshot, self.language, self.preprocess_mode
    )
    self._pending_all_text = all_text
    if not all_text:
        return False

    if self.extract_mode == "all":
        extracted_text = all_text
    else:
        extracted_text = self._extract_keywords_text(all_text, self.keywords)

    self._pending_extracted_text = extracted_text
    return bool(extracted_text)

def _process_async_result(self, result: bool):
    all_text = getattr(self, '_pending_all_text', '')
    extracted_text = getattr(self, '_pending_extracted_text', '')

    if not all_text:
        self._log_condition_result(False, "未识别到文本")
        return

    context = self._pending_context
    context.blackboard.set(self.output_key, extracted_text)

    if self.save_all_text:
        context.blackboard.set(self.all_text_key, all_text)

    if self.save_position and self.region:
        center_x = (self.region[0] + self.region[2]) // 2
        center_y = (self.region[1] + self.region[3]) // 2
        context.blackboard.set(self.position_key, (center_x, center_y))

    if extracted_text:
        self._log_condition_result(True)
        LogManager.instance().log_info(
            node_type="文本提取节点",
            node_name=self.name,
            message=f"提取文本: {extracted_text[:50]}..."
        )
    else:
        self._log_condition_result(False, "未提取到匹配的文本")

    self._pending_all_text = None
    self._pending_extracted_text = None
```

## 4 线程安全分析

### 4.1 OCRManager 线程安全性

OCRManager 是单例模式，已有 `_cache_lock` 保护缓存操作。但 `_engine`（RapidOCR 实例）的线程安全性需要验证：

- RapidOCR 基于 ONNX Runtime，ONNX Runtime 的 `InferenceSession` 默认是线程安全的（支持并发推理）
- OCRManager 的缓存机制已有 `_cache_lock` 保护
- 结论：**OCRManager 可以安全地在多线程中使用**

### 4.2 ImageProcessor 线程安全性

`ImageProcessor.find_template()` 是纯静态方法，使用 OpenCV 的 `cv2.matchTemplate`，无共享状态。结论：**线程安全**。

### 4.3 Blackboard 线程安全性

Blackboard 已有 `threading.RLock` 保护。但异步检测的 `_process_async_result` 中写黑板是在主线程（引擎 tick）中执行的，不在后台线程中。结论：**安全，黑板操作在主线程中执行**。

### 4.4 关键设计决策

**检测操作在后台线程执行，结果处理在主线程执行**。这确保了：
- 黑板写入操作在主线程中执行，无并发问题
- UI 通知在主线程中执行，无并发问题
- 只有纯计算操作（OCR 识别、模板匹配）在后台线程中执行

## 5 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| bt_core/nodes.py | ConditionNode 基类新增异步检测支持 |
| bt_nodes/conditions/ocr.py | OCRConditionNode 改为异步检测 |
| bt_nodes/conditions/image.py | ImageConditionNode 改为异步检测 |
| bt_nodes/conditions/number.py | NumberConditionNode 改为异步检测 |
| bt_nodes/conditions/text_extract.py | TextExtractNode 改为异步检测 |

## 6 不改造的节点及原因

| 节点 | 不改造原因 |
|------|-----------|
| MouseMoveNode（拖拽） | 拖拽操作必须按顺序执行：移动→按下→拖动→释放，每步之间有固定延迟，拆分为非阻塞会破坏操作完整性 |
| TextInputNode | 逐字符输入必须按顺序执行，每个字符之间有固定延迟，拆分会破坏输入完整性 |
| ColorConditionNode | 颜色检测耗时极短（1-20ms），无需异步化 |

## 7 预期效果

### 7.1 并行执行场景

假设 ParallelNode 包含 OCRConditionNode(200ms) + DelayNode(1000ms)：

**改造前**：
```
Tick 1 (t=0ms):
  ├─ OCRConditionNode.tick() → 同步执行 OCR，耗时 200ms → SUCCESS
  └─ DelayNode.tick() → 开始计时（已延迟 200ms）→ RUNNING
Tick 2-120 (t=210ms-1200ms):
  └─ DelayNode → RUNNING
Tick 121 (t=1210ms):
  └─ DelayNode → SUCCESS
总时间: ≈ 1210ms
```

**改造后**：
```
Tick 1 (t=0ms):
  ├─ OCRConditionNode.tick() → 提交异步 OCR → 返回 RUNNING（不阻塞）
  └─ DelayNode.tick() → 开始计时 → RUNNING
Tick 2-20 (t=10ms-200ms):
  ├─ OCRConditionNode → 检查异步结果 → RUNNING（OCR 还在执行）
  └─ DelayNode → RUNNING
Tick 21 (t=200ms):
  ├─ OCRConditionNode → 异步结果完成 → SUCCESS
  └─ DelayNode → RUNNING
Tick 22-100 (t=210ms-1000ms):
  └─ DelayNode → RUNNING
Tick 101 (t=1010ms):
  └─ DelayNode → SUCCESS
总时间: ≈ 1010ms（节省 200ms）
```

### 7.2 多检测节点并行场景

假设 ParallelNode 包含 OCRConditionNode(200ms) + ImageConditionNode(100ms)：

**改造前**：
```
Tick 1 (t=0ms):
  ├─ OCRConditionNode.tick() → 同步 OCR，耗时 200ms → SUCCESS
  └─ ImageConditionNode.tick() → 同步匹配，耗时 100ms（已延迟 200ms）→ SUCCESS
总时间: ≈ 300ms
```

**改造后**：
```
Tick 1 (t=0ms):
  ├─ OCRConditionNode.tick() → 提交异步 OCR → RUNNING
  └─ ImageConditionNode.tick() → 提交异步匹配 → RUNNING
Tick 2-10 (t=10ms-100ms):
  ├─ OCRConditionNode → RUNNING
  └─ ImageConditionNode → RUNNING
Tick 11 (t=100ms):
  ├─ OCRConditionNode → RUNNING
  └─ ImageConditionNode → 异步结果完成 → SUCCESS
Tick 12-20 (t=110ms-200ms):
  └─ OCRConditionNode → RUNNING
Tick 21 (t=200ms):
  └─ OCRConditionNode → 异步结果完成 → SUCCESS
总时间: ≈ 200ms（节省 100ms）
```

## 8 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 异步检测期间 status 返回旧值 | 并行节点中旧值为 SUCCESS/FAILURE，不影响缓存逻辑 |
| _pending_context 引用过期 | context 对象在整个执行期间有效，不会过期 |
| ThreadPoolExecutor 资源泄漏 | reset() 中取消 Future 并清理 executor |
| 检测结果延迟一个 tick | 延迟仅 10ms，对用户体验无影响 |
| OCRManager 并发调用 | RapidOCR 基于 ONNX Runtime，支持并发推理 |

## 9 测试验证

### 9.1 功能测试

1. 单独执行每个检测节点，验证异步模式下检测结果正确
2. 并行节点中执行多个检测节点，验证并行效果
3. 验证黑板数据写入正确
4. 验证位置保存正确

### 9.2 性能测试

1. 并行节点包含 2 个 OCR 节点，对比改造前后总执行时间
2. 并行节点包含 OCR 节点 + DelayNode，对比改造前后总执行时间

### 9.3 边界测试

1. 异步检测期间重置节点
2. 异步检测期间停止执行
3. 异步检测异常处理
