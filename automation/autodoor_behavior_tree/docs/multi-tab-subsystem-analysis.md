# 多 Tab 并行 — 子系统分析文档

> 创建日期：2026-05-07
> 目的：确定多 Tab 需要适配的子系统

---

## 1. 子系统清单

| 子系统 | 文件位置 | 当前模式 | 多 Tab 影响程度 |
|--------|---------|---------|---------------|
| AutoSaveManager | `bt_utils/auto_save.py` | 非单例 | 中等 |
| UIUpdateDispatcher | `bt_utils/ui_dispatcher.py` | 单例 | 高 |
| LogManager | `bt_utils/log_manager.py` | 单例 | 高 |
| CrashRecoveryHandler | `bt_utils/crash_recovery.py` | 非单例 | 中等 |
| GlobalHotkeyManager | `bt_utils/global_hotkey.py` | 单例 | 中等 |
| PropertyPanel | `bt_gui/bt_editor/property.py` | 非单例 | 中等 |
| CommandManager | `bt_gui/bt_editor/undo_redo.py` | 非单例 | 低 |

---

## 2. 详细分析

### 2.1 AutoSaveManager

**当前实现：**
```python
class AutoSaveManager:
    def __init__(
        self,
        get_data_func: Callable[[], Dict[str, Any]],
        on_save_callback: Optional[Callable[[bool], None]] = None,
        autosave_dir: str = "data/autosave",
        get_file_path_func: Optional[Callable[[], Optional[str]]] = None
    ):
        # ...
```

**特点：**
- 非单例模式
- 通过 `get_data_func` 回调获取数据
- 通过 `get_file_path_func` 获取文件路径
- 每个实例独立管理定时器和保存逻辑

**多 Tab 适配方案：**
- ✅ 每个 Tab 创建独立的 `AutoSaveManager` 实例
- ✅ 每个 Tab 有独立的 `get_data_func` 和 `get_file_path_func`
- ✅ Tab 关闭时调用 `stop()` 停止定时器

**风险点：**
- 需要确保每个 Tab 有独立的 `autosave_dir` 或使用不同的文件名

---

### 2.2 UIUpdateDispatcher

**当前实现：**
```python
@singleton
class UIUpdateDispatcher:
    def __init__(self):
        self._task_queue: Queue = Queue()
        self._widget = None  # 只能绑定一个 widget
        self._polling_active = False
```

**特点：**
- 单例模式
- 只能绑定一个 `_widget`
- 使用队列处理更新任务
- 支持轮询模式

**多 Tab 适配方案：**
- 方案 A：为每个 Canvas 创建独立的 `UIUpdateDispatcher` 实例（移除单例）
- 方案 B：修改单例支持多个 widget，通过 `tab_id` 路由

**推荐方案 A：**
```python
class UIUpdateDispatcher:  # 移除 @singleton
    def __init__(self):
        self._task_queue: Queue = Queue()
        self._widget = None
        # ...

# 每个 Canvas 创建独立实例
canvas._ui_dispatcher = UIUpdateDispatcher()
canvas._ui_dispatcher.attach(canvas)
canvas._ui_dispatcher.start_polling()
```

**风险点：**
- 需要修改 `@singleton` 装饰器
- 需要确保每个 Canvas 有独立的更新队列

---

### 2.3 LogManager

**当前实现：**
```python
@singleton
class LogManager:
    def __init__(self):
        self._buffer: List[LogEntry] = []
        self._buffer_lock = threading.Lock()
        self._stopped = False
```

**特点：**
- 单例模式
- 所有日志存储在同一个 `_buffer` 中
- 线程安全（使用锁）

**多 Tab 适配方案：**
- 方案 A：日志按 `tab_name` 分组，在 `LogEntry` 中添加 `tab_name` 字段
- 方案 B：每个 Tab 有独立的日志缓冲区

**推荐方案 A：**
```python
@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    node_type: str
    node_name: str
    message: str
    tab_name: Optional[str] = None  # 新增字段

    def format(self) -> str:
        if self.tab_name:
            return f"[{self.timestamp.strftime('%H:%M:%S')}] [{self.tab_name}] ..."
        return f"[{self.timestamp.strftime('%H:%M:%S')}] ..."
```

**风险点：**
- 多 Tab 并行运行时，日志会交叉显示
- 需要在 Tab 切换时设置当前 `tab_name`

---

### 2.4 CrashRecoveryHandler

**当前实现：**
```python
class CrashRecoveryHandler:
    def __init__(
        self,
        get_data_func: Callable[[], Dict[str, Any]] = None,
        recovery_dir: str = "data/recovery",
        log_func: Optional[Callable[[str], None]] = None
    ):
        # ...
```

**特点：**
- 非单例模式
- 通过 `get_data_func` 获取崩溃时的数据
- 崩溃文件存储在 `recovery_dir`

**多 Tab 适配方案：**
- 方案 A：保存所有打开 Tab 的状态到同一个崩溃文件
- 方案 B：每个 Tab 有独立的崩溃恢复文件

**推荐方案 A：**
```python
def _save_crash_recovery(self, ...):
    # 收集所有 Tab 的数据
    all_tabs_data = {
        "tabs": [
            {
                "tab_id": tab_id,
                "name": instance.name,
                "file_path": instance.file_path,
                "project_root": instance.project_root,
                "modified": instance.modified,
                "tree_data": instance.canvas.get_tree_data() if instance.canvas else None
            }
            for tab_id, instance in tab_manager._trees.items()
        ],
        "active_tab_id": tab_manager.active_tab_id
    }
    # 保存到崩溃文件
```

**风险点：**
- 需要修改 `get_data_func` 的实现
- 恢复时需要恢复所有 Tab

---

### 2.5 GlobalHotkeyManager

**当前实现：**
```python
class GlobalHotkeyManager:
    _instance: Optional["GlobalHotkeyManager"] = None
    
    def register(self, key_name: str, callback: Callable):
        # 注册热键回调
```

**特点：**
- 单例模式
- F10/F12 快捷键控制启动/停止
- 回调函数在注册时绑定

**多 Tab 适配方案：**
- 快捷键控制当前活动 Tab
- 在回调中获取 `tab_manager.get_active_tab()`

```python
def _start_running(self):
    active_tab = self.tab_manager.get_active_tab()
    if not active_tab:
        return
    # 使用 active_tab 的 canvas/engine/context
    self.tab_manager.start_tab(active_tab.tab_id)
```

**风险点：**
- 无需修改 `GlobalHotkeyManager`，只需修改回调实现

---

### 2.6 PropertyPanel

**当前实现：**
```python
class PropertyPanel(ctk.CTkFrame):
    def save_and_clear(self):
        self.current_node_id = None
        self.current_node_type = None
        self._show_empty()
```

**特点：**
- 非单例模式
- `save_and_clear()` 只清空，不保存状态
- 切换 Tab 时会丢失当前选中节点

**多 Tab 适配方案：**
- 在 `TreeInstance` 中添加 `selected_node_id` 字段
- 切换 Tab 时保存/恢复选中状态

```python
# TreeInstance 扩展
@dataclass
class TreeInstance:
    # ... 现有字段 ...
    selected_node_id: Optional[str] = None

# 切换 Tab 时
def _switch_to_tab(self, instance: TreeInstance):
    # 保存当前 Tab 的选中节点
    current_tab = self.tab_manager.get_active_tab()
    if current_tab and current_tab.canvas:
        selected = current_tab.canvas.get_selected_nodes()
        current_tab.selected_node_id = selected[0] if selected else None
    
    # 切换画布
    instance.canvas.tkraise()
    
    # 恢复新 Tab 的选中节点
    if instance.selected_node_id:
        instance.canvas.select_node(instance.selected_node_id)
```

**风险点：**
- 需要在 `TreeInstance` 中添加状态字段
- 需要确保 Canvas 的 `select_node` 方法存在

---

### 2.7 CommandManager

**当前实现：**
```python
class CommandManager:
    def __init__(self, max_history: int = 50):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
```

**特点：**
- 非单例模式
- 每个实例有独立的撤销/重做栈

**多 Tab 适配方案：**
- ✅ 每个 Tab 有独立的 `CommandManager` 实例
- ✅ 存储在 `TreeInstance.command_manager` 中

**风险点：**
- 切换 Tab 时需要更新工具栏的撤销/重做按钮状态

---

## 3. 适配优先级

| 优先级 | 子系统 | 原因 |
|--------|--------|------|
| P0 | UIUpdateDispatcher | 每个 Canvas 必须有独立的更新队列 |
| P0 | CommandManager | 每个 Tab 必须有独立的撤销栈 |
| P1 | AutoSaveManager | 每个 Tab 需要独立保存 |
| P1 | PropertyPanel | 切换 Tab 时需要保存/恢复状态 |
| P2 | LogManager | 日志分组，提升用户体验 |
| P2 | GlobalHotkeyManager | 快捷键控制当前 Tab |
| P3 | CrashRecoveryHandler | 崩溃恢复所有 Tab |

---

## 4. 实施建议

### 4.1 必须修改的子系统

1. **UIUpdateDispatcher** - 移除单例，每个 Canvas 创建独立实例
2. **LogEntry** - 添加 `tab_name` 字段

### 4.2 无需修改的子系统

1. **AutoSaveManager** - 已支持多实例
2. **CrashRecoveryHandler** - 已支持多实例，只需修改 `get_data_func`
3. **GlobalHotkeyManager** - 只需修改回调实现
4. **CommandManager** - 已支持多实例

### 4.3 需要扩展的组件

1. **TreeInstance** - 添加 `selected_node_id`、`command_manager` 等字段
2. **PropertyPanel** - 添加 `save_state()` / `restore_state()` 方法

---

## 5. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| UIUpdateDispatcher 移除单例可能导致其他模块引用错误 | 高 | 保留 `get_dispatcher()` 函数，返回当前活动 Tab 的 Dispatcher |
| LogManager 日志交叉 | 中 | 在日志格式中添加 Tab 名称前缀 |
| 切换 Tab 时状态丢失 | 中 | 在 TreeInstance 中保存状态 |

---

## 6. 测试要点

1. **UIUpdateDispatcher 多实例测试**
   - 验证每个 Canvas 有独立的更新队列
   - 验证节点状态更新不会串 Tab

2. **LogManager 多 Tab 测试**
   - 验证日志显示正确的 Tab 名称
   - 验证多 Tab 并行运行时日志不丢失

3. **PropertyPanel 状态保存测试**
   - 验证切换 Tab 后选中节点正确恢复
   - 验证属性面板内容正确更新

4. **CrashRecovery 多 Tab 测试**
   - 验证崩溃后恢复所有打开的 Tab
   - 验证恢复后 Tab 状态正确
