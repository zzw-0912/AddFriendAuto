# 坐标拆分与动态检测区域 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现条件节点坐标自动拆分为 x/y 变量，以及动态区域检测（基于黑板锚点+偏移量），使检测区域能跟随移动目标。

**Architecture:** 在 `_save_position` 中自动写入 `last_detection_x`/`last_detection_y`；在 `_get_region_image` 中新增动态区域分支，根据 `region_mode` 配置选择固定区域或动态区域；在属性面板中新增 `RegionOffsetField` 和 `region_mode` 切换，复用 `hide_if` 机制控制字段显隐。

**Tech Stack:** Python 3.11 / CustomTkinter / Tkinter Canvas / screeninfo

---

## Task 1: Blackboard 新增内置变量 + _save_position 自动拆分

**Files:**
- Modify: `bt_core/blackboard.py:14-18` (BUILTIN_VARS)
- Modify: `bt_core/nodes.py:968-986` (_save_position)

**Step 1: 修改 BUILTIN_VARS**

在 `bt_core/blackboard.py` 中，将：

```python
    BUILTIN_VARS = {
        "last_detection_position": None,
        "last_number_value": None,
    }
```

改为：

```python
    BUILTIN_VARS = {
        "last_detection_position": None,
        "last_detection_x": None,
        "last_detection_y": None,
        "last_number_value": None,
    }
```

**Step 2: 修改 _save_position**

在 `bt_core/nodes.py` 的 `_save_position` 方法中，在 `context.blackboard.set(position_key, final_position)` 之后新增 2 行：

```python
    def _save_position(self, context, position: tuple):
        save_position = self.config.get_bool("save_position", True)
        if position and save_position:
            final_position = self._apply_offset(position)
            try:
                from config.settings_manager import get_default_position_key
                default_position_key = get_default_position_key()
            except ImportError:
                default_position_key = "last_detection_position"
            position_key = self.config.get("position_key", "") or default_position_key
            context.blackboard.set(position_key, final_position)
            context.blackboard.set("last_detection_x", final_position[0])
            context.blackboard.set("last_detection_y", final_position[1])
```

**Step 3: 语法检查**

Run: `python -m py_compile bt_core/blackboard.py; python -m py_compile bt_core/nodes.py`

---

## Task 2: 后端 _get_region_image 支持动态区域

**Files:**
- Modify: `bt_core/nodes.py:1069-1084` (_get_region_image)
- Add: `_resolve_dynamic_region` method in ConditionNode class

**Step 1: 修改 _get_region_image**

将：

```python
    def _get_region_image(self, context):
        try:
            region = self._parse_region(self.config.get("region", None))
            return context.get_screenshot(region)
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"{self.NODE_TYPE} '{self.name}' 截图失败")
            return None
```

改为：

```python
    def _get_region_image(self, context):
        try:
            region_mode = self.config.get("region_mode", "fixed")
            if region_mode == "dynamic":
                region = self._resolve_dynamic_region(context)
            else:
                region = self._parse_region(self.config.get("region", None))
            return context.get_screenshot(region)
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"{self.NODE_TYPE} '{self.name}' 截图失败")
            return None
```

**Step 2: 新增 _resolve_dynamic_region 方法**

在 `_get_region_image` 方法之后新增：

```python
    def _resolve_dynamic_region(self, context):
        use_last_pos = self.config.get_bool("region_use_last_pos", True)
        if use_last_pos:
            anchor_key = "last_detection_position"
        else:
            anchor_key = self.config.get("region_anchor", "") or "last_detection_position"

        pos = context.blackboard.get(anchor_key)
        if pos is None or not isinstance(pos, (tuple, list)) or len(pos) < 2:
            from bt_utils.log_manager import LogManager
            LogManager.instance().log_failure(
                node_type=self.NODE_TYPE,
                node_name=self.name,
                reason=f"动态区域锚点 '{anchor_key}' 不存在或格式无效，使用全屏截图"
            )
            return None

        cx, cy = int(pos[0]), int(pos[1])

        offset = self.config.get("region_offset", [-50, -50, 50, 50])
        if isinstance(offset, str):
            try:
                offset = [int(x.strip()) for x in offset.split(",")]
            except (ValueError, AttributeError):
                offset = [-50, -50, 50, 50]

        if not isinstance(offset, (list, tuple)) or len(offset) < 4:
            offset = [-50, -50, 50, 50]

        return (cx + int(offset[0]), cy + int(offset[1]),
                cx + int(offset[2]), cy + int(offset[3]))
```

**Step 3: 语法检查**

Run: `python -m py_compile bt_core/nodes.py`

---

## Task 3: 新增 RegionOffsetField 组件

**Files:**
- Modify: `bt_gui/bt_editor/property.py` (新增 RegionOffsetField 类 + 注册)

**Step 1: 新增 RegionOffsetField 类**

在 `OffsetField` 类定义之后（约第 1675 行），新增 `RegionOffsetField` 类：

```python
class RegionOffsetField(FieldWidget):
    def __init__(self, master, label, key, on_change, app, **kwargs):
        self.app = app
        super().__init__(master, label, key, on_change, **kwargs)
        self._create_widget()

    def _create_widget(self):
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x")

        self.var = tk.StringVar(value="-50, -50, 50, 50")

        self.entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.var,
            font=Theme.get_font('sm'),
            height=Theme.DIMENSIONS['input_height'],
            fg_color=self._dark_colors['bg_tertiary'],
            border_color=self._dark_colors['border'],
            text_color=self._dark_colors['text_primary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius']
        )
        self.entry.pack(side="left", fill="x", expand=True,
                        padx=(0, Theme.DIMENSIONS['spacing_xs']))
        self.entry.bind("<FocusOut>", lambda e: self._parse_and_change())

        self.btn = ctk.CTkButton(
            input_frame,
            text="测量",
            font=Theme.get_font('sm'),
            width=60,
            height=Theme.DIMENSIONS['input_height'],
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
        )
        self.btn.pack(side="right")
        self.btn.bind("<ButtonRelease-1>", lambda e: self._measure_region_offset())

    def _parse_and_change(self):
        try:
            parts = self.var.get().replace(" ", "").split(",")
            if len(parts) >= 4:
                value = [int(p) for p in parts[:4]]
                self.on_change(self.key, value)
        except (ValueError, AttributeError):
            pass

    def _measure_region_offset(self):
        import time
        try:
            from bt_utils.magnifier import MagnifierWindow
        except ImportError:
            MagnifierWindow = None

        try:
            import screeninfo

            self.app.iconify()
            time.sleep(0.2)

            monitors = screeninfo.get_monitors()
            min_x = min(m.x for m in monitors)
            min_y = min(m.y for m in monitors)
            max_x = max(m.x + m.width for m in monitors)
            max_y = max(m.y + m.height for m in monitors)

            select_window = tk.Toplevel(self.app)
            select_window.geometry(f"{max_x - min_x}x{max_y - min_y}+{min_x}+{min_y}")
            select_window.overrideredirect(True)
            select_window.attributes("-alpha", 0.3)
            select_window.attributes("-topmost", True)
            select_window.configure(cursor="crosshair")

            canvas = tk.Canvas(select_window, bg=self._dark_colors['primary'],
                               highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)

            label = tk.Label(
                canvas,
                text="第一步：点击锚点（参考位置）",
                font=("Microsoft YaHei", 24),
                bg=self._dark_colors['primary'],
                fg="#FFFFFF"
            )
            canvas.create_window((max_x - min_x) // 2, (max_y - min_y) // 2, window=label)

            magnifier = MagnifierWindow(zoom_factor=4, size=150) if MagnifierWindow else None
            magnifier_shown = [False]
            reference_point = [None]
            drag_start = [None]
            rect_id = [None]

            def on_mouse_move(event):
                if magnifier:
                    if not magnifier_shown[0]:
                        magnifier.show(event.x_root, event.y_root)
                        magnifier_shown[0] = True
                    else:
                        magnifier.update(event.x_root, event.y_root)

                if reference_point[0] and drag_start[0]:
                    if rect_id[0]:
                        canvas.delete(rect_id[0])
                    rect_id[0] = canvas.create_rectangle(
                        drag_start[0][0], drag_start[0][1],
                        event.x_root, event.y_root,
                        outline="#00FF00", width=2
                    )

            def on_click(event):
                if reference_point[0] is None:
                    reference_point[0] = (event.x_root, event.y_root)
                    label.config(text="第二步：按住并拖拽选择区域范围")
                elif drag_start[0] is None:
                    drag_start[0] = (event.x_root, event.y_root)

            def on_release(event):
                if reference_point[0] and drag_start[0]:
                    if magnifier:
                        magnifier.hide()
                        magnifier_shown[0] = False

                    rx, ry = reference_point[0]
                    sx, sy = drag_start[0]
                    ex, ey = event.x_root, event.y_root

                    offset_x1 = min(sx, ex) - rx
                    offset_y1 = min(sy, ey) - ry
                    offset_x2 = max(sx, ex) - rx
                    offset_y2 = max(sy, ey) - ry

                    self.var.set(f"{offset_x1}, {offset_y1}, {offset_x2}, {offset_y2}")
                    self.on_change(self.key, [offset_x1, offset_y1, offset_x2, offset_y2])
                    select_window.destroy()
                    self.app.deiconify()

            def on_escape(e):
                if magnifier:
                    magnifier.hide()
                    magnifier_shown[0] = False
                select_window.destroy()
                self.app.deiconify()

            canvas.bind("<Motion>", on_mouse_move)
            canvas.bind("<Button-1>", on_click)
            canvas.bind("<ButtonRelease-1>", on_release)
            canvas.bind("<Escape>", on_escape)
            canvas.focus_set()
            canvas.grab_set()

        except ImportError:
            self.app.deiconify()
            messagebox.showerror("错误", "screeninfo库未安装，无法支持区域偏移测量。")
        except Exception as e:
            self.app.deiconify()
            messagebox.showerror("错误", f"区域偏移测量失败: {str(e)}")

    def set_value(self, value):
        if value is not None:
            if isinstance(value, (list, tuple)) and len(value) >= 4:
                self.var.set(f"{value[0]}, {value[1]}, {value[2]}, {value[3]}")
            else:
                self.var.set("-50, -50, 50, 50")
        else:
            self.var.set("-50, -50, 50, 50")

    def get_value(self):
        try:
            parts = self.var.get().replace(" ", "").split(",")
            if len(parts) >= 4:
                return [int(p) for p in parts[:4]]
            return [-50, -50, 50, 50]
        except (ValueError, AttributeError):
            return [-50, -50, 50, 50]
```

**Step 2: 注册 region_offset 字段类型**

在 `property.py` 中搜索 `elif field_type == "offset":`，在其后新增：

```python
            elif field_type == "region_offset":
                field_widget = RegionOffsetField(container, label, key, self._on_field_change, self.app)
```

**Step 3: 语法检查**

Run: `python -m py_compile bt_gui/bt_editor/property.py`

---

## Task 4: 修改 5 个条件节点 Schema

**Files:**
- Modify: `bt_gui/bt_editor/property.py:14-141` (NODE_CONFIG_SCHEMAS)

**重要**：`region_mode` 使用英文内部值 `"fixed"` / `"dynamic"`，通过 `display_names` 映射中文显示名。

**Step 1: 修改 OCRConditionNode Schema**

将：

```python
    "OCRConditionNode": [
        {"key": "region", "label": "检测区域", "type": "region"},
```

改为：

```python
    "OCRConditionNode": [
        {"key": "region_mode", "label": "区域选择方式", "type": "select", "options": ["fixed", "dynamic"], "display_names": {"fixed": "固定区域检测", "dynamic": "动态区域检测"}, "default": "fixed"},
        {"key": "region", "label": "检测区域", "type": "region", "hide_if": {"field": "region_mode", "value": "dynamic"}},
        {"key": "region_use_last_pos", "label": "设置最近检测点", "type": "bool", "default": True, "hide_if": {"field": "region_mode", "value": "fixed"}},
        {"key": "region_anchor", "label": "位置变量名", "type": "text", "default": "last_detection_position", "hide_if": {"field": "region_mode", "value": "fixed"}},
        {"key": "region_offset", "label": "区域偏移量", "type": "region_offset", "default": [-50, -50, 50, 50], "hide_if": {"field": "region_mode", "value": "fixed"}},
```

**Step 2: 修改 ImageConditionNode Schema**

将：

```python
    "ImageConditionNode": [
        {"key": "region", "label": "检测区域", "type": "region"},
```

改为（同上模式）：

```python
    "ImageConditionNode": [
        {"key": "region_mode", "label": "区域选择方式", "type": "select", "options": ["fixed", "dynamic"], "display_names": {"fixed": "固定区域检测", "dynamic": "动态区域检测"}, "default": "fixed"},
        {"key": "region", "label": "检测区域", "type": "region", "hide_if": {"field": "region_mode", "value": "dynamic"}},
        {"key": "region_use_last_pos", "label": "设置最近检测点", "type": "bool", "default": True, "hide_if": {"field": "region_mode", "value": "fixed"}},
        {"key": "region_anchor", "label": "位置变量名", "type": "text", "default": "last_detection_position", "hide_if": {"field": "region_mode", "value": "fixed"}},
        {"key": "region_offset", "label": "区域偏移量", "type": "region_offset", "default": [-50, -50, 50, 50], "hide_if": {"field": "region_mode", "value": "fixed"}},
```

**Step 3: 修改 ColorConditionNode Schema**

将：

```python
    "ColorConditionNode": [
        {"key": "region", "label": "检测区域", "type": "region"},
```

改为（同上模式）。

**Step 4: 修改 NumberConditionNode Schema**

将：

```python
    "NumberConditionNode": [
        {"key": "region", "label": "检测区域", "type": "region"},
```

改为（同上模式，5 行替换 1 行）。

**Step 5: 修改 TextExtractNode Schema**

将：

```python
    "TextExtractNode": [
        {"key": "region", "label": "检测区域", "type": "region"},
```

改为（同上模式，5 行替换 1 行）。

**Step 6: 语法检查**

Run: `python -m py_compile bt_gui/bt_editor/property.py`

---

## Task 5: 端到端集成测试

**Files:**
- 无代码修改，仅测试

**Step 1: 编写并运行集成测试脚本**

创建临时测试脚本 `_test_integration.py` 并运行，验证所有核心功能。

**Step 2: 清理测试文件**

Delete: `_test_integration.py`

---

## Task 6: 启动应用验证

**Step 1: 启动应用**

Run: `python main.py`

Expected: 应用正常启动，无报错

**Step 2: 验证属性面板**

1. 添加一个 OCRConditionNode
2. 查看属性面板，确认"区域选择方式"显示在"检测区域"上方
3. 默认选中"固定区域检测"，检测区域正常显示
4. 切换到"动态区域检测"，检测区域隐藏，区域锚点和区域偏移量显示
5. 切换回"固定区域检测"，动态区域字段隐藏，检测区域恢复显示

**Step 3: 对其他 4 个条件节点重复 Step 2 验证**
