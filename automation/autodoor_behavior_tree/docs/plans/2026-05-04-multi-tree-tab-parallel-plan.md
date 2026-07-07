# 顶部Tab页签多行为树并行 — 实现计划 (修订版 v2.0)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将单画布编辑器改造为多Tab页签编辑器，每个Tab对应独立的行为树项目，支持多行为树并行运行。

**Architecture:** 
- **复用现有组件**：扩展 `TreeInstance` 添加 GUI 字段，复用 `MultiTreeManager` 核心逻辑
- **代理模式重构**：`BehaviorTreeEditor` 通过属性代理访问当前活动 Tab 的画布/引擎/上下文
- **TabBar 替换 MultiTreePanel**：Tab 页签交互更直观
- **子系统适配**：每个 Tab 独立的 CommandManager、AutoSave、UIUpdateDispatcher

**Tech Stack:** Python 3.x, CustomTkinter, threading.Lock

---

## 设计决策

### 决策1：复用现有核心组件

| 现有组件 | 复用方式 |
|---------|---------|
| `TreeInstance` | 扩展添加 GUI 字段（canvas, file_path, modified, tab_id, command_manager） |
| `MultiTreeManager` | 继承为 `GuiTabManager`，添加 Tab 切换和 UI 回调 |

### 决策2：废弃 MultiTreePanel

用 `TabBar` + `TabButton` 替换现有的 `MultiTreePanel`：
- Tab 页签交互更直观
- 每棵树有独立的 Tab 页，包含运行/停止/关闭按钮
- 删除 `multi_tree_panel.py` 或标记为废弃

### 决策3：Editor 代理模式

```python
class BehaviorTreeEditor:
    @property
    def canvas(self):
        tab = self.tab_manager.get_active_tab()
        return tab.canvas if tab else None
    
    @property
    def engine(self):
        tab = self.tab_manager.get_active_tab()
        return tab.engine if tab else None
    
    @property
    def context(self):
        tab = self.tab_manager.get_active_tab()
        return tab.context if tab else None
```

### 决策4：Canvas 管理方案

使用 `tkraise()` 而非 `pack_forget/pack`：
- 所有 Canvas 都 pack 在 `canvas_frame` 中
- 切换 Tab 时调用 `canvas.tkraise()` 提到最上层
- 避免重绘和状态丢失问题

### 决策5：导入项目使用工作区

多树并行的项目导入使用工作区目录（`%APPDATA%/autodoor_behavior_tree/workspace/`），而非 `subtrees/` 目录。`subtrees/` 专用于 SubtreeNode 子树引用。

---

## 阶段0：前置准备 — 子系统分析

### Task 0.1: 分析现有子系统依赖

**目的：** 确定多 Tab 需要适配的子系统

**分析清单：**

| 子系统 | 当前状态 | 多 Tab 适配方案 |
|--------|---------|----------------|
| `UIUpdateDispatcher` | 单例，绑定一个画布 | 每个 Tab 的 Canvas 绑定自己的 Dispatcher |
| `AutoSaveManager` | 单例，保存一个画布 | 每个 Tab 独立 AutoSaveManager |
| `CrashRecovery` | 恢复单个项目 | 保存所有打开 Tab 的状态 |
| `CommandManager` | 单一撤销栈 | 每个 Tab 独立 CommandManager（存在 TreeInstance 中） |
| `GlobalHotkeyManager` | F10/F12 控制单一引擎 | 快捷键控制当前活动 Tab |
| `LogManager` | 单例，所有日志混在一起 | 日志按 tab_id 分组，或添加 Tab 名称前缀 |
| `PropertyPanel` | 单例，显示单一节点 | 切换 Tab 时保存当前属性，加载新 Tab 属性 |

**产出：** 创建 `docs/multi-tab-subsystem-analysis.md` 文档

---

## 阶段1：扩展 TreeInstance + 继承 MultiTreeManager

### Task 1.1: 扩展 TreeInstance 数据类

**Files:**
- Modify: `bt_core/tree_instance.py`
- Test: `tests/test_tree_instance.py` (修改现有测试)

**Step 1: 分析现有 TreeInstance**

现有字段：
- `name: str`
- `engine: BehaviorTreeEngine`
- `context: ExecutionContext`
- `blackboard: Blackboard`
- `status: str = "idle"`
- `error_message: Optional[str] = None`
- `start_time: Optional[float] = None`
- `tick_count: int = 0`

**Step 2: 添加 GUI 字段**

```python
from dataclasses import dataclass, field
from typing import Optional, Any

from .engine import BehaviorTreeEngine
from .context import ExecutionContext
from .blackboard import Blackboard


@dataclass
class TreeInstance:
    """行为树实例

    封装单个行为树实例的运行时状态。
    支持多 Tab 并行场景，包含 GUI 相关字段。
    """
    name: str
    engine: BehaviorTreeEngine
    context: ExecutionContext
    blackboard: Blackboard
    status: str = "idle"
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    tick_count: int = 0
    
    tab_id: Optional[str] = None
    canvas: Optional[Any] = None
    file_path: Optional[str] = None
    project_root: Optional[str] = None
    modified: bool = False
    command_manager: Optional[Any] = None

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "name": self.name,
            "status": self.status,
            "error_message": self.error_message,
            "tick_count": self.tick_count,
            "tab_id": self.tab_id,
            "file_path": self.file_path,
            "project_root": self.project_root,
            "modified": self.modified,
        }
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.status == "running"
    
    def set_running(self, running: bool) -> None:
        """设置运行状态"""
        self.status = "running" if running else "stopped"
```

**Step 3: 更新测试**

```python
def test_tree_instance_gui_fields():
    from bt_core.tree_instance import TreeInstance
    from bt_core.engine import BehaviorTreeEngine
    from bt_core.context import ExecutionContext
    from bt_core.blackboard import Blackboard
    
    instance = TreeInstance(
        name="测试树",
        engine=BehaviorTreeEngine(None),
        context=ExecutionContext(),
        blackboard=Blackboard(),
        tab_id="tab_1",
        file_path="/path/to/tree.json",
        project_root="/path/to/project",
        modified=True
    )
    
    assert instance.tab_id == "tab_1"
    assert instance.file_path == "/path/to/tree.json"
    assert instance.project_root == "/path/to/project"
    assert instance.modified is True
    assert instance.is_running is False
    
    instance.set_running(True)
    assert instance.is_running is True
    assert instance.status == "running"
```

**Step 4: Run test**

Run: `pytest tests/test_tree_instance.py -v`

**Step 5: Commit**

```bash
git add bt_core/tree_instance.py tests/test_tree_instance.py
git commit -m "feat(core): extend TreeInstance with GUI fields for multi-tab"
```

---

### Task 1.2: 创建 GuiTabManager 继承 MultiTreeManager

**Files:**
- Create: `bt_gui/bt_editor/gui_tab_manager.py`
- Test: `tests/test_gui_tab_manager.py`

**Step 1: Write the failing test**

```python
import pytest
from unittest.mock import MagicMock

def test_gui_tab_manager_init():
    from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
    
    manager = GuiTabManager()
    assert manager.active_tab_id is None
    assert manager.on_tab_switched is None
    assert manager.on_tab_status_changed is None

def test_gui_tab_manager_add_tab():
    from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
    from bt_core.tree_instance import TreeInstance
    from bt_core.engine import BehaviorTreeEngine
    from bt_core.context import ExecutionContext
    from bt_core.blackboard import Blackboard
    
    manager = GuiTabManager()
    
    mock_canvas = MagicMock()
    instance = TreeInstance(
        name="主任务",
        engine=BehaviorTreeEngine(None),
        context=ExecutionContext(),
        blackboard=Blackboard(),
        tab_id="tab_1",
        canvas=mock_canvas
    )
    
    manager.add_tab("tab_1", instance)
    assert manager.active_tab_id == "tab_1"
    assert manager.get_tab("tab_1") == instance

def test_gui_tab_manager_switch_tab():
    from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
    from bt_core.tree_instance import TreeInstance
    
    manager = GuiTabManager()
    
    instance1 = TreeInstance(
        name="Tab1", engine=MagicMock(), context=MagicMock(), 
        blackboard=MagicMock(), tab_id="tab_1"
    )
    instance2 = TreeInstance(
        name="Tab2", engine=MagicMock(), context=MagicMock(), 
        blackboard=MagicMock(), tab_id="tab_2"
    )
    
    manager.add_tab("tab_1", instance1)
    manager.add_tab("tab_2", instance2)
    
    manager.switch_tab("tab_2")
    assert manager.active_tab_id == "tab_2"
    
    active = manager.get_active_tab()
    assert active == instance2

def test_gui_tab_manager_switch_nonexistent():
    from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
    
    manager = GuiTabManager()
    with pytest.raises(ValueError):
        manager.switch_tab("nonexistent")

def test_gui_tab_manager_remove_tab():
    from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
    from bt_core.tree_instance import TreeInstance
    
    manager = GuiTabManager()
    
    instance = TreeInstance(
        name="Tab1", engine=MagicMock(), context=MagicMock(), 
        blackboard=MagicMock(), tab_id="tab_1"
    )
    
    manager.add_tab("tab_1", instance)
    result = manager.remove_tab("tab_1")
    
    assert result is True
    assert manager.active_tab_id is None
    assert manager.get_tab("tab_1") is None

def test_gui_tab_manager_callbacks():
    from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
    from bt_core.tree_instance import TreeInstance
    
    manager = GuiTabManager()
    
    switched_called = []
    status_changed_called = []
    
    def on_switched(tab_id, instance):
        switched_called.append((tab_id, instance.name))
    
    def on_status_changed(tab_id, running):
        status_changed_called.append((tab_id, running))
    
    manager.on_tab_switched = on_switched
    manager.on_tab_status_changed = on_status_changed
    
    instance = TreeInstance(
        name="Tab1", engine=MagicMock(), context=MagicMock(), 
        blackboard=MagicMock(), tab_id="tab_1"
    )
    
    manager.add_tab("tab_1", instance)
    manager.switch_tab("tab_1")
    manager.update_tab_status("tab_1", True)
    
    assert len(switched_called) == 1
    assert switched_called[0] == ("tab_1", "Tab1")
    assert len(status_changed_called) == 1
    assert status_changed_called[0] == ("tab_1", True)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_gui_tab_manager.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write implementation**

```python
import threading
from typing import Dict, Optional, Callable, Any

from bt_core.tree_manager import MultiTreeManager
from bt_core.tree_instance import TreeInstance


class GuiTabManager(MultiTreeManager):
    """GUI Tab 管理器
    
    继承 MultiTreeManager，添加 Tab 切换和 UI 回调支持。
    用于管理多 Tab 页签编辑器中的行为树实例。
    """
    
    def __init__(self, shared_blackboard: bool = False):
        super().__init__(shared_blackboard)
        self._active_tab_id: Optional[str] = None
        self._tab_lock = threading.Lock()
        
        self.on_tab_switched: Optional[Callable[[str, TreeInstance], None]] = None
        self.on_tab_status_changed: Optional[Callable[[str, bool], None]] = None
        self.on_tab_added: Optional[Callable[[str, TreeInstance], None]] = None
        self.on_tab_removed: Optional[Callable[[str], None]] = None
    
    @property
    def active_tab_id(self) -> Optional[str]:
        return self._active_tab_id
    
    def add_tab(self, tab_id: str, instance: TreeInstance) -> TreeInstance:
        """添加 Tab 实例
        
        Args:
            tab_id: Tab 唯一标识
            instance: 行为树实例
            
        Returns:
            添加的实例
        """
        with self._tab_lock:
            instance.tab_id = tab_id
            self._trees[tab_id] = instance
            
            if self._active_tab_id is None:
                self._active_tab_id = tab_id
            
            if self.on_tab_added:
                self.on_tab_added(tab_id, instance)
            
            return instance
    
    def remove_tab(self, tab_id: str) -> bool:
        """移除 Tab 实例
        
        Args:
            tab_id: Tab 唯一标识
            
        Returns:
            是否成功移除
        """
        with self._tab_lock:
            if tab_id not in self._trees:
                return False
            
            instance = self._trees[tab_id]
            
            if instance.status == "running":
                instance.engine.stop()
            
            del self._trees[tab_id]
            
            if self._active_tab_id == tab_id:
                tab_ids = list(self._trees.keys())
                self._active_tab_id = tab_ids[0] if tab_ids else None
            
            if self.on_tab_removed:
                self.on_tab_removed(tab_id)
            
            return True
    
    def switch_tab(self, tab_id: str) -> None:
        """切换活动 Tab
        
        Args:
            tab_id: 目标 Tab ID
            
        Raises:
            ValueError: Tab 不存在
        """
        with self._tab_lock:
            if tab_id not in self._trees:
                raise ValueError(f"Tab '{tab_id}' does not exist")
            
            if self._active_tab_id == tab_id:
                return
            
            self._active_tab_id = tab_id
            instance = self._trees[tab_id]
        
        if self.on_tab_switched:
            self.on_tab_switched(tab_id, instance)
    
    def get_active_tab(self) -> Optional[TreeInstance]:
        """获取当前活动 Tab"""
        with self._tab_lock:
            if self._active_tab_id is None:
                return None
            return self._trees.get(self._active_tab_id)
    
    def get_tab(self, tab_id: str) -> Optional[TreeInstance]:
        """获取指定 Tab"""
        return self._trees.get(tab_id)
    
    def update_tab_status(self, tab_id: str, running: bool) -> None:
        """更新 Tab 运行状态"""
        with self._tab_lock:
            instance = self._trees.get(tab_id)
            if instance:
                instance.set_running(running)
        
        if self.on_tab_status_changed:
            self.on_tab_status_changed(tab_id, running)
    
    def start_tab(self, tab_id: str) -> bool:
        """启动指定 Tab 的行为树
        
        注意：此方法不在锁内调用 engine.start()，避免死锁
        """
        instance = self._trees.get(tab_id)
        if not instance or instance.status == "running":
            return False
        
        instance.engine.start(instance.context)
        self.update_tab_status(tab_id, True)
        return True
    
    def stop_tab(self, tab_id: str) -> bool:
        """停止指定 Tab 的行为树
        
        注意：此方法不在锁内调用 engine.stop()，避免死锁
        """
        instance = self._trees.get(tab_id)
        if not instance or instance.status != "running":
            return False
        
        instance.engine.stop()
        self.update_tab_status(tab_id, False)
        return True
    
    def start_all(self) -> int:
        """启动所有 Tab 的行为树"""
        count = 0
        for tab_id in list(self._trees.keys()):
            if self.start_tab(tab_id):
                count += 1
        return count
    
    def stop_all(self) -> int:
        """停止所有 Tab 的行为树"""
        count = 0
        for tab_id in list(self._trees.keys()):
            if self.stop_tab(tab_id):
                count += 1
        return count
    
    def get_all_status(self) -> list:
        """获取所有 Tab 状态"""
        return [
            {
                "tab_id": tab_id,
                "name": instance.name,
                "is_running": instance.is_running,
                "status": instance.status,
                "modified": instance.modified
            }
            for tab_id, instance in self._trees.items()
        ]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_gui_tab_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_gui/bt_editor/gui_tab_manager.py tests/test_gui_tab_manager.py
git commit -m "feat(gui): add GuiTabManager extending MultiTreeManager"
```

---

## 阶段2：TabBar UI 组件

### Task 2.1: TabButton 组件

**Files:**
- Create: `bt_gui/bt_editor/tab_bar.py`
- Test: `tests/test_tab_button.py`

**Step 1: Write the failing test**

```python
import pytest

class MockTabButton:
    """Mock for testing without GUI"""
    def __init__(self, tab_id: str, name: str):
        self.tab_id = tab_id
        self.name = name
        self.is_running = False
        self.is_active = False

    def set_running(self, running: bool):
        self.is_running = running

    def set_active(self, active: bool):
        self.is_active = active

def test_tab_button_creation():
    btn = MockTabButton(tab_id="tab_1", name="主任务")
    assert btn.tab_id == "tab_1"
    assert btn.name == "主任务"
    assert btn.is_running is False
    assert btn.is_active is False

def test_tab_button_set_running():
    btn = MockTabButton(tab_id="tab_1", name="主任务")
    btn.set_running(True)
    assert btn.is_running is True
    btn.set_running(False)
    assert btn.is_running is False

def test_tab_button_set_active():
    btn = MockTabButton(tab_id="tab_1", name="主任务")
    btn.set_active(True)
    assert btn.is_active is True
    btn.set_active(False)
    assert btn.is_active is False
```

**Step 2: Run test**

Run: `pytest tests/test_tab_button.py -v`
Expected: PASS (mock test)

**Step 3: Write GUI implementation**

```python
import customtkinter as ctk
from typing import Callable, Optional


class TabButton(ctk.CTkFrame):
    """Tab 按钮组件
    
    包含运行/停止按钮、名称标签、状态指示器、关闭按钮
    """
    ICON_RUN = "\u25b6"
    ICON_STOP = "\u25a0"
    ICON_CLOSE = "\u2715"

    def __init__(self, master, tab_id: str, name: str,
                 on_run_stop: Optional[Callable[[str, bool], None]] = None,
                 on_close: Optional[Callable[[str], None]] = None,
                 on_click: Optional[Callable[[str], None]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)

        self.tab_id = tab_id
        self._name = name
        self._is_running = False
        self._is_active = False

        self._on_run_stop = on_run_stop
        self._on_close = on_close
        self._on_click = on_click

        self._create_widgets()

    def _create_widgets(self):
        self._run_stop_btn = ctk.CTkButton(
            self,
            text=self.ICON_RUN,
            width=24,
            height=24,
            font=("Arial", 10),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self._on_run_stop_click
        )
        self._run_stop_btn.pack(side="left", padx=2)

        self._name_label = ctk.CTkLabel(
            self,
            text=self._name,
            font=("Microsoft YaHei", 11),
            cursor="hand2"
        )
        self._name_label.pack(side="left", padx=4, fill="x", expand=True)
        self._name_label.bind("<Button-1>", self._on_name_click)

        self._status_indicator = ctk.CTkLabel(
            self,
            text="",
            font=("Arial", 8),
            text_color="#22c55e"
        )
        self._status_indicator.pack(side="left", padx=2)

        self._close_btn = ctk.CTkButton(
            self,
            text=self.ICON_CLOSE,
            width=20,
            height=20,
            font=("Arial", 8),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            text_color=("gray10", "gray90"),
            command=self._on_close_click
        )
        self._close_btn.pack(side="right", padx=2)

        self._update_style()

    def _update_style(self):
        if self._is_active:
            self.configure(fg_color=("gray75", "gray25"))
            self._name_label.configure(font=("Microsoft YaHei", 11, "bold"))
        else:
            self.configure(fg_color="transparent")
            self._name_label.configure(font=("Microsoft YaHei", 11))

        if self._is_running:
            self._run_stop_btn.configure(text=self.ICON_STOP, text_color="#22c55e")
            self._status_indicator.configure(text="\u2022")
        else:
            self._run_stop_btn.configure(text=self.ICON_RUN, text_color=("gray10", "gray90"))
            self._status_indicator.configure(text="")

    def _on_run_stop_click(self):
        if self._on_run_stop:
            self._on_run_stop(self.tab_id, not self._is_running)

    def _on_close_click(self):
        if self._on_close:
            self._on_close(self.tab_id)

    def _on_name_click(self, event):
        if self._on_click:
            self._on_click(self.tab_id)

    def set_running(self, running: bool):
        self._is_running = running
        self._update_style()

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    @property
    def name(self) -> str:
        return self._name

    def set_name(self, name: str):
        self._name = name
        self._name_label.configure(text=name)
```

**Step 4: Run test**

Run: `pytest tests/test_tab_button.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_gui/bt_editor/tab_bar.py tests/test_tab_button.py
git commit -m "feat(gui): add TabButton UI component"
```

---

### Task 2.2: TabBar 容器组件

**Files:**
- Modify: `bt_gui/bt_editor/tab_bar.py`
- Test: `tests/test_tab_bar.py`

**Step 1: Write the failing test**

```python
import pytest

class MockTabBar:
    """Mock for testing without GUI"""
    def __init__(self):
        self.tabs = {}
        self.active_tab_id = None

    def add_tab(self, tab_id: str, name: str):
        self.tabs[tab_id] = {"name": name, "is_running": False}
        if self.active_tab_id is None:
            self.active_tab_id = tab_id

    def remove_tab(self, tab_id: str):
        if tab_id in self.tabs:
            del self.tabs[tab_id]
            if self.active_tab_id == tab_id:
                tab_ids = list(self.tabs.keys())
                self.active_tab_id = tab_ids[0] if tab_ids else None

    def set_active(self, tab_id: str):
        if tab_id in self.tabs:
            self.active_tab_id = tab_id

    def set_running(self, tab_id: str, running: bool):
        if tab_id in self.tabs:
            self.tabs[tab_id]["is_running"] = running

def test_tab_bar_add_tab():
    bar = MockTabBar()
    bar.add_tab("tab_1", "主任务")
    assert "tab_1" in bar.tabs
    assert bar.active_tab_id == "tab_1"

def test_tab_bar_remove_tab():
    bar = MockTabBar()
    bar.add_tab("tab_1", "主任务")
    bar.remove_tab("tab_1")
    assert "tab_1" not in bar.tabs
    assert bar.active_tab_id is None

def test_tab_bar_set_active():
    bar = MockTabBar()
    bar.add_tab("tab_1", "Tab1")
    bar.add_tab("tab_2", "Tab2")
    bar.set_active("tab_2")
    assert bar.active_tab_id == "tab_2"

def test_tab_bar_set_running():
    bar = MockTabBar()
    bar.add_tab("tab_1", "主任务")
    bar.set_running("tab_1", True)
    assert bar.tabs["tab_1"]["is_running"] is True
```

**Step 2: Run test**

Run: `pytest tests/test_tab_bar.py -v`
Expected: PASS (mock test)

**Step 3: Write GUI implementation**

在 `tab_bar.py` 中添加 TabBar 类：

```python
from typing import Dict, Optional, Callable


class TabBar(ctk.CTkFrame):
    """Tab 栏容器
    
    管理多个 TabButton，提供 Tab 切换、关闭、运行控制
    """
    
    def __init__(self, master,
                 on_tab_switch: Optional[Callable[[str], None]] = None,
                 on_tab_close: Optional[Callable[[str], None]] = None,
                 on_tab_run: Optional[Callable[[str], None]] = None,
                 on_tab_stop: Optional[Callable[[str], None]] = None,
                 on_import: Optional[Callable[[], None]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)

        self._tab_buttons: Dict[str, TabButton] = {}
        self._active_tab_id: Optional[str] = None

        self._on_tab_switch = on_tab_switch
        self._on_tab_close = on_tab_close
        self._on_tab_run = on_tab_run
        self._on_tab_stop = on_tab_stop
        self._on_import = on_import

        self._create_widgets()

    def _create_widgets(self):
        self._tabs_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._tabs_frame.pack(side="left", fill="x", expand=True)

        self._import_btn = ctk.CTkButton(
            self,
            text="+ \u5bfc\u5165",
            width=60,
            height=28,
            font=("Microsoft YaHei", 10),
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=self._on_import_click
        )
        self._import_btn.pack(side="right", padx=4)

    def _on_import_click(self):
        if self._on_import:
            self._on_import()

    def add_tab(self, tab_id: str, name: str) -> None:
        btn = TabButton(
            self._tabs_frame,
            tab_id=tab_id,
            name=name,
            on_run_stop=self._handle_run_stop,
            on_close=self._handle_close,
            on_click=self._handle_click
        )
        btn.pack(side="left", padx=2, pady=4)
        self._tab_buttons[tab_id] = btn

        if self._active_tab_id is None:
            self.set_active(tab_id)

    def remove_tab(self, tab_id: str) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].destroy()
            del self._tab_buttons[tab_id]

            if self._active_tab_id == tab_id:
                tab_ids = list(self._tab_buttons.keys())
                self._active_tab_id = tab_ids[0] if tab_ids else None
                if self._active_tab_id:
                    self.set_active(self._active_tab_id)

    def set_active(self, tab_id: str) -> None:
        for tid, btn in self._tab_buttons.items():
            btn.set_active(tid == tab_id)
        self._active_tab_id = tab_id

    def set_running(self, tab_id: str, running: bool) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].set_running(running)

    def _handle_run_stop(self, tab_id: str, should_run: bool):
        if should_run:
            if self._on_tab_run:
                self._on_tab_run(tab_id)
        else:
            if self._on_tab_stop:
                self._on_tab_stop(tab_id)

    def _handle_close(self, tab_id: str):
        if self._on_tab_close:
            self._on_tab_close(tab_id)

    def _handle_click(self, tab_id: str):
        if self._on_tab_switch:
            self._on_tab_switch(tab_id)

    def update_tab_name(self, tab_id: str, name: str) -> None:
        if tab_id in self._tab_buttons:
            self._tab_buttons[tab_id].set_name(name)

    def get_tab_count(self) -> int:
        return len(self._tab_buttons)
```

**Step 4: Run test**

Run: `pytest tests/test_tab_bar.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add bt_gui/bt_editor/tab_bar.py tests/test_tab_bar.py
git commit -m "feat(gui): add TabBar container component"
```

---

## 阶段3：Editor 代理模式重构

### Task 3.1: 添加代理属性

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 添加代理属性**

在 `BehaviorTreeEditor` 类中添加代理属性，使现有方法无需修改即可访问当前活动 Tab 的资源：

```python
    @property
    def canvas(self):
        """代理到当前活动 Tab 的画布"""
        tab = self.tab_manager.get_active_tab()
        return tab.canvas if tab else self._fallback_canvas
    
    @canvas.setter
    def canvas(self, value):
        """设置画布（用于初始化第一个 Tab）"""
        self._fallback_canvas = value
    
    @property
    def engine(self):
        """代理到当前活动 Tab 的引擎"""
        tab = self.tab_manager.get_active_tab()
        return tab.engine if tab else self._fallback_engine
    
    @engine.setter
    def engine(self, value):
        self._fallback_engine = value
    
    @property
    def context(self):
        """代理到当前活动 Tab 的上下文"""
        tab = self.tab_manager.get_active_tab()
        return tab.context if tab else self._fallback_context
    
    @context.setter
    def context(self, value):
        self._fallback_context = value
    
    @property
    def project_root(self):
        """代理到当前活动 Tab 的项目根目录"""
        tab = self.tab_manager.get_active_tab()
        return tab.project_root if tab else self._fallback_project_root
    
    @project_root.setter
    def project_root(self, value):
        self._fallback_project_root = value
    
    @property
    def file_path(self):
        """代理到当前活动 Tab 的文件路径"""
        tab = self.tab_manager.get_active_tab()
        return tab.file_path if tab else self._fallback_file_path
    
    @file_path.setter
    def file_path(self, value):
        self._fallback_file_path = value
```

**Step 2: 初始化 fallback 属性**

在 `__init__` 中添加：

```python
        self._fallback_canvas = None
        self._fallback_engine = None
        self._fallback_context = None
        self._fallback_project_root = None
        self._fallback_file_path = None
```

**Step 3: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "refactor(editor): add proxy properties for multi-tab support"
```

---

### Task 3.2: 集成 GuiTabManager 和 TabBar

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 导入新组件**

```python
from .gui_tab_manager import GuiTabManager
from .tab_bar import TabBar
from bt_core.tree_instance import TreeInstance
```

**Step 2: 初始化 TabManager**

在 `__init__` 中添加：

```python
        self.tab_manager = GuiTabManager()
        self.tab_manager.on_tab_switched = self._on_tab_switched
        self.tab_manager.on_tab_status_changed = self._on_tab_status_changed
        self.tab_manager.on_tab_removed = self._on_tab_removed
```

**Step 3: 创建 TabBar UI**

在 `_create_ui` 中，工具栏创建后、主区域创建前添加：

```python
    def _create_ui(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)
        
        self._create_toolbar()
        self._create_tab_bar()
        self._create_main_area()
    
    def _create_tab_bar(self):
        self.tab_bar = TabBar(
            self.main_container,
            on_tab_switch=self._handle_tab_switch,
            on_tab_close=self._handle_tab_close,
            on_tab_run=self._handle_tab_run,
            on_tab_stop=self._handle_tab_stop,
            on_import=self._handle_import_project
        )
        self.tab_bar.pack(fill="x")
```

**Step 4: 实现回调方法**

```python
    def _on_tab_switched(self, tab_id: str, instance: TreeInstance):
        self._switch_to_tab(instance)
    
    def _on_tab_status_changed(self, tab_id: str, running: bool):
        self.tab_bar.set_running(tab_id, running)
    
    def _on_tab_removed(self, tab_id: str):
        self.tab_bar.remove_tab(tab_id)
    
    def _handle_tab_switch(self, tab_id: str):
        self.tab_manager.switch_tab(tab_id)
        self.tab_bar.set_active(tab_id)
    
    def _handle_tab_run(self, tab_id: str):
        self.tab_manager.start_tab(tab_id)
    
    def _handle_tab_stop(self, tab_id: str):
        self.tab_manager.stop_tab(tab_id)
    
    def _handle_tab_close(self, tab_id: str):
        instance = self.tab_manager.get_tab(tab_id)
        if not instance:
            return
        
        if instance.is_running:
            if not messagebox.askyesno("确认", "行为树正在运行，是否停止并关闭？"):
                return
            self.tab_manager.stop_tab(tab_id)
        
        if instance.modified:
            result = messagebox.askyesnocancel("保存", "是否保存修改？")
            if result is None:
                return
            if result:
                self._save_tab(tab_id)
        
        self.tab_manager.remove_tab(tab_id)
    
    def _switch_to_tab(self, instance: TreeInstance):
        """切换到指定 Tab"""
        if not instance or not instance.canvas:
            return
        
        instance.canvas.tkraise()
        
        self.property_panel.save_and_clear()
        
        if instance.canvas.get_selected_nodes():
            node_id = instance.canvas.get_selected_nodes()[0]
            self._on_node_select(node_id, instance.canvas.nodes[node_id].node_type)
        
        self._update_title(instance.name)
        self.toolbar.set_project_path(instance.project_root)
        self.toolbar.set_running(instance.is_running)
    
    def _save_tab(self, tab_id: str):
        instance = self.tab_manager.get_tab(tab_id)
        if not instance or not instance.canvas:
            return
        
        tree_data = instance.canvas.get_tree_data()
        save_path = instance.file_path or os.path.join(instance.project_root, "tree.json")
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=2)
        
        instance.modified = False
```

**Step 5: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(editor): integrate GuiTabManager and TabBar"
```

---

### Task 3.3: 初始化第一个 Tab

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 修改 _create_canvas**

在 `_create_canvas` 方法末尾，将创建的画布包装为第一个 Tab：

```python
    def _create_canvas(self):
        self.canvas_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.canvas_frame.pack(side="left", fill="both", expand=True)
        
        self._fallback_canvas = BehaviorTreeCanvas(
            self.canvas_frame,
            self.app,
            on_node_select=self._on_node_select,
            on_node_move=self._on_node_move,
            on_nodes_move=self._on_nodes_move,
            on_connection_add=self._on_connection_add,
            on_node_deselect=self._on_node_deselect,
            property_panel=None
        )
        self._fallback_canvas.pack(fill="both", expand=True)
        
        self.property_panel = PropertyPanel(
            self.main_area,
            self.app,
            on_change=self._on_property_change
        )
        self.property_panel.pack(side="right", fill="y")
        
        self._fallback_canvas.property_panel = self.property_panel
        
        self._init_first_tab()
        
        self._init_autosave()
        self._start_autosave()
    
    def _init_first_tab(self):
        """将初始画布包装为第一个 Tab"""
        from bt_core.engine import BehaviorTreeEngine
        from bt_core.context import ExecutionContext
        from bt_core.blackboard import Blackboard
        from .undo_redo import CommandManager
        
        tab_id = "tab_1"
        
        context = ExecutionContext(project_root=self._fallback_project_root)
        engine = BehaviorTreeEngine(None)
        command_manager = CommandManager()
        
        instance = TreeInstance(
            name=self._get_project_name(),
            engine=engine,
            context=context,
            blackboard=Blackboard(),
            tab_id=tab_id,
            canvas=self._fallback_canvas,
            file_path=self._fallback_file_path,
            project_root=self._fallback_project_root,
            modified=False,
            command_manager=command_manager
        )
        
        self.tab_manager.add_tab(tab_id, instance)
        self.tab_bar.add_tab(tab_id, instance.name)
    
    def _get_project_name(self) -> str:
        if self._fallback_project_root:
            return os.path.basename(self._fallback_project_root)
        return "未命名"
```

**Step 2: 修改 command_manager 属性**

```python
    @property
    def command_manager(self):
        """代理到当前活动 Tab 的命令管理器"""
        tab = self.tab_manager.get_active_tab()
        return tab.command_manager if tab else self._fallback_command_manager
    
    @command_manager.setter
    def command_manager(self, value):
        self._fallback_command_manager = value
```

**Step 3: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(editor): wrap initial canvas as first tab"
```

---

## 阶段4：Canvas 管理与项目导入

### Task 4.1: 创建新 Tab 的画布

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 实现 _create_new_tab 方法**

```python
    def _create_new_tab(self, name: str, project_root: str = None, 
                        file_path: str = None) -> str:
        """创建新 Tab
        
        Args:
            name: Tab 名称
            project_root: 项目根目录
            file_path: 文件路径
            
        Returns:
            新 Tab 的 ID
        """
        from bt_core.engine import BehaviorTreeEngine
        from bt_core.context import ExecutionContext
        from bt_core.blackboard import Blackboard
        from .undo_redo import CommandManager
        
        tab_id = f"tab_{len(self.tab_manager._trees) + 1}"
        
        new_canvas = BehaviorTreeCanvas(
            self.canvas_frame,
            self.app,
            on_node_select=self._on_node_select,
            on_node_move=self._on_node_move,
            on_nodes_move=self._on_nodes_move,
            on_connection_add=self._on_connection_add,
            on_node_deselect=self._on_node_deselect,
            property_panel=self.property_panel
        )
        new_canvas.pack(fill="both", expand=True)
        
        context = ExecutionContext(project_root=project_root)
        engine = BehaviorTreeEngine(None)
        command_manager = CommandManager()
        
        instance = TreeInstance(
            name=name,
            engine=engine,
            context=context,
            blackboard=Blackboard(),
            tab_id=tab_id,
            canvas=new_canvas,
            file_path=file_path,
            project_root=project_root,
            modified=False,
            command_manager=command_manager
        )
        
        self.tab_manager.add_tab(tab_id, instance)
        self.tab_bar.add_tab(tab_id, name)
        
        return tab_id
```

**Step 2: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(editor): add _create_new_tab method"
```

---

### Task 4.2: 修改项目导入流程

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 修改 _handle_import_project**

```python
    def _handle_import_project(self):
        """导入项目到新 Tab"""
        from tkinter import filedialog
        
        folder_path = filedialog.askdirectory(title="选择行为树项目文件夹")
        if not folder_path:
            return
        
        self.import_project_to_new_tab(folder_path)

    def import_project_to_new_tab(self, project_path: str) -> str:
        """导入项目到新 Tab
        
        使用工作区目录，而非 subtrees/ 目录
        
        Args:
            project_path: 项目路径
            
        Returns:
            新 Tab 的 ID
        """
        import os
        import shutil
        from config.settings_manager import SettingsManager
        
        folder_name = os.path.basename(project_path)
        workspace_path = SettingsManager.get_default_workspace_path()
        
        os.makedirs(workspace_path, exist_ok=True)
        
        target_dir = os.path.join(workspace_path, folder_name)
        
        if os.path.exists(target_dir):
            result = messagebox.askyesnocancel(
                "项目已存在",
                f"工作区中已存在同名项目 '{folder_name}'。\n\n"
                f"是否覆盖？"
            )
            if result is None:
                return None
            elif result:
                shutil.rmtree(target_dir)
            else:
                return None
        
        shutil.copytree(project_path, target_dir)
        
        tab_id = self._create_new_tab(folder_name, target_dir)
        
        tree_file = os.path.join(target_dir, "tree.json")
        if os.path.exists(tree_file):
            self._load_tree_to_tab(tab_id, tree_file)
        
        self.tab_manager.switch_tab(tab_id)
        self.tab_bar.set_active(tab_id)
        instance = self.tab_manager.get_tab(tab_id)
        self._switch_to_tab(instance)
        
        return tab_id
    
    def _load_tree_to_tab(self, tab_id: str, tree_file: str):
        """加载行为树到指定 Tab"""
        instance = self.tab_manager.get_tab(tab_id)
        if not instance or not instance.canvas:
            return
        
        try:
            root_node, canvas_state, _ = Serializer.load_from_file(tree_file)
            instance.canvas.load_tree_data(root_node, canvas_state)
            instance.file_path = tree_file
        except Exception as e:
            messagebox.showerror("错误", f"加载行为树失败: {e}")
```

**Step 2: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(editor): import project to workspace instead of subtrees"
```

---

## 阶段5：子系统适配

### Task 5.1: AutoSave 多 Tab 支持

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`
- Modify: `bt_utils/auto_save.py` (如需要)

**Step 1: 分析现有 AutoSave**

当前 `AutoSaveManager` 是单例，保存单一画布。

**Step 2: 为每个 Tab 创建独立 AutoSave**

修改 `_create_new_tab` 方法：

```python
    def _create_new_tab(self, name: str, project_root: str = None, 
                        file_path: str = None) -> str:
        # ... 现有代码 ...
        
        from bt_utils.auto_save import AutoSaveManager
        
        tab_autosave = AutoSaveManager(
            canvas=new_canvas,
            interval_ms=self.AUTOSAVE_INTERVAL,
            backup_dir=self.BACKUP_DIR
        )
        tab_autosave.start()
        
        instance._autosave_manager = tab_autosave
        
        return tab_id
```

**Step 3: 修改 remove_tab 停止 AutoSave**

```python
    def _handle_tab_close(self, tab_id: str):
        instance = self.tab_manager.get_tab(tab_id)
        if not instance:
            return
        
        if hasattr(instance, '_autosave_manager') and instance._autosave_manager:
            instance._autosave_manager.stop()
        
        # ... 现有关闭逻辑 ...
```

**Step 4: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(editor): add per-tab AutoSave support"
```

---

### Task 5.2: UIUpdateDispatcher 多 Tab 支持

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`
- Modify: `bt_utils/ui_dispatcher.py` (如需要)

**Step 1: 分析现有 Dispatcher**

当前 `UIUpdateDispatcher` 是单例，绑定一个画布。

**Step 2: 为每个 Canvas 创建独立 Dispatcher**

修改 `_create_canvas` 和 `_create_new_tab`：

```python
    def _create_canvas(self):
        # ... 现有代码 ...
        
        self._init_ui_dispatcher_for_canvas(self._fallback_canvas)
    
    def _create_new_tab(self, ...):
        # ... 现有代码 ...
        
        self._init_ui_dispatcher_for_canvas(new_canvas)
        
        return tab_id
    
    def _init_ui_dispatcher_for_canvas(self, canvas):
        """为画布初始化 UIUpdateDispatcher"""
        from bt_utils.ui_dispatcher import UIUpdateDispatcher
        
        dispatcher = UIUpdateDispatcher.get_instance()
        dispatcher.attach(canvas)
        dispatcher.start_polling()
        
        canvas._ui_dispatcher = dispatcher
```

**Step 3: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(editor): add per-canvas UIUpdateDispatcher support"
```

---

### Task 5.3: LogManager 多 Tab 支持

**Files:**
- Modify: `bt_utils/log_manager.py`
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 修改 LogManager 支持按 Tab 分组**

```python
class LogManager:
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self._buffer: List[LogEntry] = []
        self._max_logs = 1000
        self._current_tab_name: Optional[str] = None
    
    def set_current_tab(self, tab_name: Optional[str]):
        """设置当前活动 Tab 名称"""
        self._current_tab_name = tab_name
    
    def log_success(self, node_type: str, node_name: str, message: str = ""):
        entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.SUCCESS,
            node_type=node_type,
            node_name=node_name,
            message=message,
            tab_name=self._current_tab_name
        )
        self._log(entry)
```

**Step 2: 在 Tab 切换时更新 LogManager**

```python
    def _switch_to_tab(self, instance: TreeInstance):
        # ... 现有代码 ...
        
        from bt_utils.log_manager import LogManager
        LogManager.instance().set_current_tab(instance.name)
```

**Step 3: 修改 LogEntry 数据类**

```python
@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    node_type: str
    node_name: str
    message: str
    tab_name: Optional[str] = None
    
    def format(self) -> str:
        if self.tab_name:
            return f"[{self.timestamp.strftime('%H:%M:%S')}] [{self.tab_name}] [{self.level.value}] [{self.node_type}] {self.node_name}: {self.message}"
        return f"[{self.timestamp.strftime('%H:%M:%S')}] [{self.level.value}] [{self.node_type}] {self.node_name}: {self.message}"
```

**Step 4: Commit**

```bash
git add bt_utils/log_manager.py bt_gui/bt_editor/editor.py
git commit -m "feat(log): add tab name prefix to log entries"
```

---

### Task 5.4: GlobalHotkey 多 Tab 支持

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 修改快捷键处理**

```python
    def _start_running(self):
        """启动当前活动 Tab 的行为树"""
        active_tab = self.tab_manager.get_active_tab()
        if not active_tab:
            return
        
        if active_tab.is_running:
            return
        
        # ... 现有启动逻辑，使用 active_tab 的 canvas/engine/context ...
        
        self.tab_manager.start_tab(active_tab.tab_id)
    
    def _stop_running(self):
        """停止当前活动 Tab 的行为树"""
        active_tab = self.tab_manager.get_active_tab()
        if not active_tab or not active_tab.is_running:
            return
        
        self.tab_manager.stop_tab(active_tab.tab_id)
```

**Step 2: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(hotkey): global hotkeys control active tab"
```

---

### Task 5.5: PropertyPanel 多 Tab 支持

**Files:**
- Modify: `bt_gui/bt_editor/editor.py`

**Step 1: 修改 Tab 切换时保存属性**

```python
    def _switch_to_tab(self, instance: TreeInstance):
        if not instance or not instance.canvas:
            return
        
        self.property_panel.save_and_clear()
        
        instance.canvas.tkraise()
        
        selected_nodes = instance.canvas.get_selected_nodes()
        if selected_nodes:
            node_id = selected_nodes[0]
            node = instance.canvas.nodes.get(node_id)
            if node:
                self._on_node_select(node_id, node.node_type)
        
        # ... 其他切换逻辑 ...
```

**Step 2: Commit**

```bash
git add bt_gui/bt_editor/editor.py
git commit -m "feat(property): save and restore property panel on tab switch"
```

---

## 阶段6：工具栏全局控制

### Task 6.1: 添加全局控制按钮

**Files:**
- Modify: `bt_gui/bt_editor/toolbar.py`

**Step 1: 添加全局控制按钮**

在 `_create_run_buttons` 方法中添加：

```python
    def _create_run_buttons(self):
        # ... 现有开始/停止按钮 ...
        
        self._separator_3 = self._create_separator(self.button_frame)
        self._separator_3.pack(side="left", padx=5)
        
        self._all_run_btn = ctk.CTkButton(
            self.button_frame,
            text="\u25b6\u25b6 全部运行",
            width=90,
            height=28,
            font=ctk.CTkFont(size=10),
            fg_color="#22c55e",
            hover_color="#16a34a",
            command=self._on_all_run
        )
        self._all_run_btn.pack(side="left", padx=2)
        
        self._all_stop_btn = ctk.CTkButton(
            self.button_frame,
            text="\u25a0\u25a0 全部停止",
            width=90,
            height=28,
            font=ctk.CTkFont(size=10),
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._on_all_stop
        )
        self._all_stop_btn.pack(side="left", padx=2)
```

**Step 2: 添加回调**

```python
    def set_on_all_run(self, callback: Callable[[], None]):
        self._on_all_run_callback = callback
    
    def set_on_all_stop(self, callback: Callable[[], None]):
        self._on_all_stop_callback = callback
    
    def _on_all_run(self):
        if hasattr(self, '_on_all_run_callback') and self._on_all_run_callback:
            self._on_all_run_callback()
    
    def _on_all_stop(self):
        if hasattr(self, '_on_all_stop_callback') and self._on_all_stop_callback:
            self._on_all_stop_callback()
```

**Step 3: 在 Editor 中连接回调**

```python
        self.toolbar.set_on_all_run(self._handle_all_run)
        self.toolbar.set_on_all_stop(self._handle_all_stop)
    
    def _handle_all_run(self):
        count = self.tab_manager.start_all()
        LogManager.instance().log_info(
            node_type="系统",
            node_name="",
            message=f"启动了 {count} 个行为树"
        )
    
    def _handle_all_stop(self):
        count = self.tab_manager.stop_all()
        LogManager.instance().log_info(
            node_type="系统",
            node_name="",
            message=f"停止了 {count} 个行为树"
        )
```

**Step 4: Commit**

```bash
git add bt_gui/bt_editor/toolbar.py bt_gui/bt_editor/editor.py
git commit -m "feat(toolbar): add global run/stop buttons"
```

---

## 阶段7：废弃 MultiTreePanel

### Task 7.1: 标记 MultiTreePanel 为废弃

**Files:**
- Modify: `bt_gui/bt_editor/multi_tree_panel.py`
- Modify: `bt_gui/bt_editor/__init__.py`

**Step 1: 添加废弃警告**

在 `multi_tree_panel.py` 文件头部添加：

```python
"""
多行为树管理面板

⚠️ 已废弃：此组件已被 TabBar + GuiTabManager 替代。
保留此文件仅用于向后兼容，新代码请使用 TabBar。

废弃日期：2026-05-07
计划移除日期：2026-08-01
"""

import warnings

warnings.warn(
    "MultiTreePanel 已废弃，请使用 TabBar + GuiTabManager 替代",
    DeprecationWarning,
    stacklevel=2
)
```

**Step 2: 从 __init__.py 移除导出**

```python
# 移除以下行（如果存在）：
# from .multi_tree_panel import MultiTreePanel
```

**Step 3: Commit**

```bash
git add bt_gui/bt_editor/multi_tree_panel.py bt_gui/bt_editor/__init__.py
git commit -m "deprecate: mark MultiTreePanel as deprecated, use TabBar instead"
```

---

## 阶段8：测试与验证

### Task 8.1: 核心层测试

**Files:**
- Test: `tests/test_tree_instance.py` (修改)
- Test: `tests/test_gui_tab_manager.py` (新建)
- Test: `tests/test_tree_manager.py` (修改现有)

**测试覆盖：**

1. `TreeInstance` GUI 字段测试
2. `GuiTabManager` 基础操作测试
3. `GuiTabManager` 线程安全测试
4. `GuiTabManager` 回调测试

**Step 1: Run tests**

Run: `pytest tests/test_tree_instance.py tests/test_gui_tab_manager.py tests/test_tree_manager.py -v`

**Step 2: Commit**

```bash
git add tests/
git commit -m "test: add tests for multi-tab core components"
```

---

### Task 8.2: 手动测试清单

**测试项目：**

| 测试项 | 预期结果 |
|--------|---------|
| 启动应用 | 显示默认 Tab "未命名" |
| 导入项目 | 新 Tab 打开，Tab 栏显示项目名 |
| 切换 Tab | 画布切换，属性面板更新，标题更新 |
| 运行单个 Tab | Tab 显示运行状态，日志显示 Tab 名称前缀 |
| 停止单个 Tab | Tab 显示停止状态 |
| 全部运行 | 所有 Tab 开始运行 |
| 全部停止 | 所有 Tab 停止运行 |
| 关闭运行中的 Tab | 提示确认，停止后关闭 |
| 关闭修改的 Tab | 提示保存 |
| 快捷键 F10 | 启动当前活动 Tab |
| 快捷键 F12 | 停止当前活动 Tab |
| 自动保存 | 每个 Tab 独立保存 |
| 撤销/重做 | 每个Tab 独立撤销栈 |

---

## 最终步骤

### Task 9.1: 更新 __init__.py

**Files:**
- Modify: `bt_gui/bt_editor/__init__.py`

```python
from .gui_tab_manager import GuiTabManager
from .tab_bar import TabBar, TabButton
```

### Task 9.2: 运行完整测试套件

Run: `pytest tests/ -v --tb=short`

### Task 9.3: 更新架构文档

更新 `doc/01_架构文档.md`，添加多 Tab 并行架构说明。

---

## 任务清单汇总

| 阶段 | 任务 | 文件 | 状态 |
|------|------|------|------|
| 0 | Task 0.1: 分析现有子系统依赖 | docs/ | 待完成 |
| 1 | Task 1.1: 扩展 TreeInstance | bt_core/tree_instance.py | 待完成 |
| 1 | Task 1.2: 创建 GuiTabManager | bt_gui/bt_editor/gui_tab_manager.py | 待完成 |
| 2 | Task 2.1: TabButton 组件 | bt_gui/bt_editor/tab_bar.py | 待完成 |
| 2 | Task 2.2: TabBar 容器 | bt_gui/bt_editor/tab_bar.py | 待完成 |
| 3 | Task 3.1: 添加代理属性 | bt_gui/bt_editor/editor.py | 待完成 |
| 3 | Task 3.2: 集成 GuiTabManager 和 TabBar | bt_gui/bt_editor/editor.py | 待完成 |
| 3 | Task 3.3: 初始化第一个 Tab | bt_gui/bt_editor/editor.py | 待完成 |
| 4 | Task 4.1: 创建新 Tab 的画布 | bt_gui/bt_editor/editor.py | 待完成 |
| 4 | Task 4.2: 修改项目导入流程 | bt_gui/bt_editor/editor.py | 待完成 |
| 5 | Task 5.1: AutoSave 多 Tab 支持 | bt_gui/bt_editor/editor.py | 待完成 |
| 5 | Task 5.2: UIUpdateDispatcher 多 Tab 支持 | bt_gui/bt_editor/editor.py | 待完成 |
| 5 | Task 5.3: LogManager 多 Tab 支持 | bt_utils/log_manager.py | 待完成 |
| 5 | Task 5.4: GlobalHotkey 多 Tab 支持 | bt_gui/bt_editor/editor.py | 待完成 |
| 5 | Task 5.5: PropertyPanel 多 Tab 支持 | bt_gui/bt_editor/editor.py | 待完成 |
| 6 | Task 6.1: 添加全局控制按钮 | bt_gui/bt_editor/toolbar.py | 待完成 |
| 7 | Task 7.1: 废弃 MultiTreePanel | bt_gui/bt_editor/multi_tree_panel.py | 待完成 |
| 8 | Task 8.1: 核心层测试 | tests/ | 待完成 |
| 8 | Task 8.2: 手动测试清单 | - | 待完成 |
| 9 | Task 9.1: 更新 __init__.py | bt_gui/bt_editor/__init__.py | 待完成 |
| 9 | Task 9.2: 运行完整测试套件 | - | 待完成 |
| 9 | Task 9.3: 更新架构文档 | doc/01_架构文档.md | 待完成 |

---

> 文档版本：v2.0 (修订版)
> 修订日期：2026-05-07
> 修订说明：根据代码审查结果，解决原有计划的 8 个核心问题
