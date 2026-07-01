# 设变量与变量判断节点改造 — 执行计划

> 基于《设变量与变量判断节点改造方案》，本文档定义完整的执行步骤、每个关键节点的测试用例，以及最终的冒烟测试和回归测试用例。

---

## 一、执行阶段总览

```
阶段1: 基础设施（hide_if 扩展 + VariableSelectField）
  ↓ 测试检查点 A
阶段2: 前端 Schema 改造（SetVariableNode + VariableConditionNode）
  ↓ 测试检查点 B
阶段3: 后端逻辑改造（SetVariableNode + VariableConditionNode）
  ↓ 测试检查点 C
阶段4: 旧数据兼容与清理
  ↓ 测试检查点 D
阶段5: 冒烟测试 + 回归测试
```

---

## 二、阶段 1 — 基础设施

### 任务 1.1：扩展 hide_if 支持 OR 多条件

**文件**：`bt_gui/bt_editor/property.py`

**改动位置**：`_update_single_field_visibility` 方法（第 2963 行起）

**具体操作**：

1. 将现有 `_update_single_field_visibility` 中的单条件判断逻辑提取为 `_check_hide_condition` 方法
2. 修改 `_update_single_field_visibility` 支持 `hide_if` 为列表格式（OR 逻辑）

**改动前**（第 2963-2996 行）：

```python
def _update_single_field_visibility(self, key: str, field: Dict[str, Any]):
    hide_if = field.get("hide_if")
    if not hide_if:
        return
    
    depend_field = hide_if.get("field")
    hide_value = hide_if.get("value")
    
    if not depend_field or depend_field not in self.widgets:
        return
    
    depend_widget = self.widgets.get(depend_field)
    if not depend_widget:
        return
    
    current_value = depend_widget.get_value()
    
    if isinstance(hide_value, list):
        should_hide = current_value in hide_value
    else:
        should_hide = (current_value == hide_value)
    
    widget = self.widgets.get(key)
    container = self.field_containers.get(key)
    
    if widget and container:
        if should_hide:
            widget.pack_forget()
        else:
            next_widget = self._find_next_visible_widget(key, container)
            if next_widget:
                widget.pack(fill="x", pady=Theme.DIMENSIONS['spacing_xs'], before=next_widget)
            else:
                widget.pack(fill="x", pady=Theme.DIMENSIONS['spacing_xs'])
```

**改动后**：

```python
def _update_single_field_visibility(self, key: str, field: Dict[str, Any]):
    hide_if = field.get("hide_if")
    if not hide_if:
        return

    if isinstance(hide_if, list):
        should_hide = any(
            self._check_hide_condition(cond) for cond in hide_if
        )
    else:
        should_hide = self._check_hide_condition(hide_if)

    widget = self.widgets.get(key)
    container = self.field_containers.get(key)

    if widget and container:
        if should_hide:
            widget.pack_forget()
        else:
            next_widget = self._find_next_visible_widget(key, container)
            if next_widget:
                widget.pack(fill="x", pady=Theme.DIMENSIONS['spacing_xs'], before=next_widget)
            else:
                widget.pack(fill="x", pady=Theme.DIMENSIONS['spacing_xs'])

def _check_hide_condition(self, condition: Dict[str, Any]) -> bool:
    depend_field = condition.get("field")
    hide_value = condition.get("value")

    if not depend_field or depend_field not in self.widgets:
        return False

    depend_widget = self.widgets.get(depend_field)
    if not depend_widget:
        return False

    current_value = depend_widget.get_value()

    if isinstance(hide_value, list):
        return current_value in hide_value
    else:
        return current_value == hide_value
```

**关键点**：
- `_check_hide_condition` 返回 `bool`，不执行隐藏操作
- `_update_single_field_visibility` 根据返回值执行隐藏/显示
- 现有单条件 `hide_if` 走 `_check_hide_condition` 单次调用，行为完全不变

---

### 任务 1.2：Blackboard 增加内置变量中文显示名和动态获取方法

**文件**：`bt_core/blackboard.py`

**改动位置**：`Blackboard` 类中 `BUILTIN_VARS` 之后

**具体操作**：

1. 在 `BUILTIN_VARS` 之后增加 `BUILTIN_VAR_DISPLAY_NAMES` 类级别常量
2. 增加 `get_builtin_vars_info()` 类方法，合并 `BlackboardConfig` 可配置键名

**改动后**：

```python
class Blackboard:
    BUILTIN_VARS = {
        "last_detection_position": None,
        "last_detection_x": None,
        "last_detection_y": None,
        "last_number_value": None,
    }

    BUILTIN_VAR_DISPLAY_NAMES = {
        "last_detection_position": "最近检测点",
        "last_detection_x": "最近检测点x值",
        "last_detection_y": "最近检测点y值",
        "last_number_value": "最近数字值",
    }

    @classmethod
    def get_builtin_vars_info(cls) -> Dict[str, str]:
        result = dict(cls.BUILTIN_VAR_DISPLAY_NAMES)
        try:
            from config.settings_manager import get_blackboard_config
            config = get_blackboard_config()
            config_mapping = {
                config.default_position_key: "最近检测点",
                config.default_value_key: "最近数字值",
            }
            for key, display_name in config_mapping.items():
                if key not in result:
                    result[key] = display_name
        except ImportError:
            pass
        return result
```

---

### 任务 1.3：新增 VariableSelectField 组件

**文件**：`bt_gui/bt_editor/property.py`

**插入位置**：在 `TextListField` 类之后、`PropertyPanel` 类之前

**完整代码**：

```python
class VariableSelectField(FieldWidget):
    @classmethod
    def _get_builtin_vars(cls) -> Dict[str, str]:
        from bt_core.blackboard import Blackboard
        return Blackboard.get_builtin_vars_info()

    def __init__(self, master, label: str, key: str, on_change: Callable, **kwargs):
        builtin_vars = self._get_builtin_vars()
        self._REVERSE_NAMES = {v: k for k, v in builtin_vars.items()}
        self._display_options = list(builtin_vars.values())
        super().__init__(master, label, key, on_change, **kwargs)
        self._create_widget()

    def _create_widget(self):
        self.var = tk.StringVar(value="")
        self.combobox = ctk.CTkComboBox(
            self,
            variable=self.var,
            values=self._display_options,
            font=Theme.get_font('sm'),
            height=Theme.DIMENSIONS['input_height'],
            fg_color=self._dark_colors['bg_tertiary'],
            border_color=self._dark_colors['border'],
            button_color=self._dark_colors['border'],
            button_hover_color=self._dark_colors['node_selected'],
            text_color=self._dark_colors['text_primary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            command=self._on_dropdown_select
        )
        self.combobox.pack(fill="x")
        self.combobox.bind("<FocusOut>", lambda e: self._on_value_change())
        self.combobox.bind("<Return>", lambda e: self._on_value_change())

    def _on_dropdown_select(self, choice: str):
        internal_value = self._REVERSE_NAMES.get(choice, choice)
        self.on_change(self.key, internal_value)

    def _on_value_change(self):
        current = self.var.get()
        internal_value = self._REVERSE_NAMES.get(current, current)
        self.on_change(self.key, internal_value)

    def set_value(self, value: Any):
        if value is None:
            self.var.set("")
            return
        builtin_vars = self._get_builtin_vars()
        display = builtin_vars.get(str(value), str(value))
        self.var.set(display)

    def get_value(self) -> Any:
        current = self.var.get()
        return self._REVERSE_NAMES.get(current, current)
```

---

### 任务 1.4：注册 variable_select 字段类型

**文件**：`bt_gui/bt_editor/property.py`

**改动位置**：`_create_field` 方法的类型分发（第 2935 行附近）

在 `elif field_type == "text_list":` 分支之后添加：

```python
elif field_type == "variable_select":
    field_widget = VariableSelectField(container, label, key, self._on_field_change)
```

---

### 检查点 A 测试用例

**测试方式**：编写独立 Python 测试脚本，验证 hide_if 扩展和 VariableSelectField 的核心逻辑。

| 编号 | 测试项 | 测试方法 | 预期结果 |
|------|--------|---------|---------|
| A-01 | `_check_hide_condition` 单条件匹配 | 调用 `_check_hide_condition({"field": "op", "value": "delete"})`，op widget 值为 `"delete"` | 返回 `True` |
| A-02 | `_check_hide_condition` 单条件不匹配 | 同上，op widget 值为 `"set"` | 返回 `False` |
| A-03 | `_check_hide_condition` value 为列表匹配 | 调用 `_check_hide_condition({"field": "op", "value": ["increment", "delete"]})`，op widget 值为 `"increment"` | 返回 `True` |
| A-04 | `_check_hide_condition` value 为列表不匹配 | 同上，op widget 值为 `"set"` | 返回 `False` |
| A-05 | `_check_hide_condition` 依赖字段不存在 | 调用 `_check_hide_condition({"field": "nonexistent", "value": "x"})` | 返回 `False` |
| A-06 | hide_if 列表格式 OR 逻辑 | `_update_single_field_visibility` 传入 `[{"field": "op", "value": "delete"}, {"field": "vt", "value": "variable"}]`，op=delete, vt=constant | 字段隐藏（条件1满足） |
| A-07 | hide_if 列表格式 OR 逻辑 | 同上，op=set, vt=variable | 字段隐藏（条件2满足） |
| A-08 | hide_if 列表格式 OR 逻辑 | 同上，op=set, vt=constant | 字段显示（均不满足） |
| A-09 | hide_if 单条件字典向后兼容 | 传入 `{"field": "op", "value": "delete"}`，op=delete | 字段隐藏（行为与改造前一致） |
| A-10 | 现有 region_mode hide_if 不受影响 | 加载含 region_mode 的节点，切换 fixed/dynamic | 字段隐藏/显示行为不变 |
| A-11 | VariableSelectField 下拉选择内置变量 | 选择「最近检测点x值」 | `get_value()` 返回 `"last_detection_x"` |
| A-12 | VariableSelectField 下拉选择内置变量 | 选择「最近检测点」 | `get_value()` 返回 `"last_detection_position"` |
| A-13 | VariableSelectField 自定义输入 | 输入 `my_counter` | `get_value()` 返回 `"my_counter"` |
| A-14 | VariableSelectField set_value 内置变量名 | `set_value("last_detection_y")` | 输入框显示「最近检测点y值」 |
| A-15 | VariableSelectField set_value 自定义变量名 | `set_value("custom_var")` | 输入框显示 `custom_var` |
| A-16 | VariableSelectField set_value None | `set_value(None)` | 输入框显示空字符串 |

---

## 三、阶段 2 — 前端 Schema 改造

### 任务 2.1：改造 SetVariableNode Schema

**文件**：`bt_gui/bt_editor/property.py`

**改动位置**：`NODE_CONFIG_SCHEMAS` 中 `"SetVariableNode"` 键（第 113-117 行）

**改动前**：

```python
"SetVariableNode": [
    {"key": "variable_name", "label": "变量名", "type": "text"},
    {"key": "operation", "label": "操作", "type": "select", "options": ["set", "increment", "delete", "clear"], "default": "set"},
    {"key": "value", "label": "值", "type": "text"},
],
```

**改动后**：

```python
"SetVariableNode": [
    {"key": "variable_name", "label": "变量名", "type": "text"},
    {"key": "operation", "label": "操作", "type": "select",
     "options": ["set", "increment", "delete"],
     "display_names": {"set": "设置", "increment": "递增", "delete": "删除"},
     "default": "set"},
    {"key": "value_type", "label": "赋值方式", "type": "select",
     "options": ["constant", "variable"],
     "display_names": {"constant": "常量值", "variable": "变量名"},
     "default": "constant",
     "hide_if": [{"field": "operation", "value": ["increment", "delete"]}]},
    {"key": "value", "label": "值", "type": "text",
     "hide_if": [{"field": "operation", "value": "delete"},
                 {"field": "value_type", "value": "variable"}]},
    {"key": "source_variable", "label": "来源变量", "type": "variable_select",
     "hide_if": [{"field": "value_type", "value": "constant"},
                 {"field": "operation", "value": ["increment", "delete"]}]},
],
```

---

### 任务 2.2：改造 VariableConditionNode Schema

**文件**：`bt_gui/bt_editor/property.py`

**改动位置**：`NODE_CONFIG_SCHEMAS` 中 `"VariableConditionNode"` 键（第 67-71 行）

**改动前**：

```python
"VariableConditionNode": [
    {"key": "variable_name", "label": "变量名", "type": "text"},
    {"key": "operator", "label": "运算符", "type": "select", "options": ["==", "!=", ">", "<", ">=", "<=", "exists", "not_exists", "contains", "not_contains", "starts_with", "ends_with"], "default": "=="},
    {"key": "compare_value", "label": "比较值", "type": "text", "hide_if": {"field": "operator", "value": ["exists", "not_exists"]}},
],
```

**改动后**：

```python
"VariableConditionNode": [
    {"key": "variable_name", "label": "变量名", "type": "text"},
    {"key": "operator", "label": "运算符", "type": "select",
     "options": ["==", "!=", ">", "<", ">=", "<=", "exists", "not_exists",
                 "contains", "not_contains", "starts_with", "ends_with"],
     "display_names": {
         "==": "等于", "!=": "不等于",
         ">": "大于", "<": "小于",
         ">=": "大于等于", "<=": "小于等于",
         "exists": "存在", "not_exists": "不存在",
         "contains": "包含", "not_contains": "不包含",
         "starts_with": "开头是", "ends_with": "结尾是"
     },
     "default": "=="},
    {"key": "compare_type", "label": "比较值类型", "type": "select",
     "options": ["constant", "variable"],
     "display_names": {"constant": "常量值", "variable": "变量名"},
     "default": "constant",
     "hide_if": {"field": "operator", "value": ["exists", "not_exists"]}},
    {"key": "compare_value", "label": "比较值", "type": "text",
     "hide_if": [{"field": "operator", "value": ["exists", "not_exists"]},
                 {"field": "compare_type", "value": "variable"}]},
    {"key": "compare_variable", "label": "比较变量", "type": "variable_select",
     "hide_if": [{"field": "compare_type", "value": "constant"},
                 {"field": "operator", "value": ["exists", "not_exists"]}]},
],
```

---

### 检查点 B 测试用例

**测试方式**：启动应用，在 UI 中验证字段显示和交互行为。

| 编号 | 测试项 | 操作步骤 | 预期结果 |
|------|--------|---------|---------|
| B-01 | 设变量操作下拉中文化 | 添加设变量节点，查看操作下拉 | 显示「设置/递增/删除」，无 clear |
| B-02 | 变量判断运算符中文化 | 添加变量判断节点，查看运算符下拉 | 显示「等于/不等于/大于/小于/大于等于/小于等于/存在/不存在/包含/不包含/开头是/结尾是」 |
| B-03 | 设变量-设置-常量值 | 操作=设置，赋值方式=常量值 | 显示「变量名」「操作」「赋值方式」「值」4个字段 |
| B-04 | 设变量-设置-变量名 | 操作=设置，赋值方式=变量名 | 显示「变量名」「操作」「赋值方式」「来源变量」4个字段，「值」隐藏 |
| B-05 | 设变量-递增 | 操作=递增 | 显示「变量名」「操作」「值」3个字段，「赋值方式」和「来源变量」隐藏 |
| B-06 | 设变量-删除 | 操作=删除 | 仅显示「变量名」「操作」2个字段，「赋值方式」「值」「来源变量」隐藏 |
| B-07 | 来源变量下拉选项 | 赋值方式=变量名，点击来源变量下拉 | 显示「最近检测点」「最近检测点x值」「最近检测点y值」 |
| B-08 | 来源变量自定义输入 | 赋值方式=变量名，在来源变量输入 `my_var` | 可正常输入，值存储为 `my_var` |
| B-09 | 变量判断-等于-常量值 | 运算符=等于，比较值类型=常量值 | 显示「变量名」「运算符」「比较值类型」「比较值」4个字段 |
| B-10 | 变量判断-等于-变量名 | 运算符=等于，比较值类型=变量名 | 显示「变量名」「运算符」「比较值类型」「比较变量」4个字段，「比较值」隐藏 |
| B-11 | 变量判断-存在 | 运算符=存在 | 显示「变量名」「运算符」2个字段，「比较值类型」「比较值」「比较变量」隐藏 |
| B-12 | 变量判断-不存在 | 运算符=不存在 | 同 B-11 |
| B-13 | 操作切换字段联动 | 设置→递增→删除→设置 | 每次切换后字段正确显示/隐藏，无残留 |
| B-14 | 运算符切换字段联动 | 等于→存在→大于→不存在 | 每次切换后字段正确显示/隐藏，无残留 |
| B-15 | 保存并重新加载 | 配置设变量和变量判断节点后保存，重新加载 | 所有字段值正确恢复，字段可见性正确 |

---

## 四、阶段 3 — 后端逻辑改造

### 任务 3.1：改造 SetVariableNode 后端逻辑

**文件**：`bt_nodes/actions/variable.py`

**改动内容**：

1. `_execute_action` 方法中 `set` 操作分支增加 `value_type` 判断
2. 删除 `clear` 操作相关逻辑（当前无实现，无需删除代码，只需确认不遗漏）
3. `__init__` 中增加 `value_type` 和 `source_variable` 属性
4. `from_dict` 中增加 `value_type` 和 `source_variable` 属性

**改动后完整代码**：

```python
class SetVariableNode(ActionNode):
    NODE_TYPE = "SetVariableNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.variable_name = self.config.get("variable_name", "")
        self.value = self.config.get("value", "")
        self.operation = self.config.get("operation", "set")
        self.value_type = self.config.get("value_type", "constant")
        self.source_variable = self.config.get("source_variable", "")

    def _execute_action(self, context) -> NodeStatus:
        try:
            variable_name = self.config.get("variable_name", "")
            operation = self.config.get("operation", "set")

            if not variable_name:
                LogManager.instance().log_failure(
                    node_type="变量节点",
                    node_name=self.name,
                    reason="未配置变量名"
                )
                return NodeStatus.FAILURE

            if operation == "set":
                value_type = self.config.get("value_type", "constant")
                if value_type == "variable":
                    source_var = self.config.get("source_variable", "")
                    if source_var:
                        source_value = context.blackboard.get(source_var)
                        context.blackboard.set(variable_name, source_value)
                    else:
                        LogManager.instance().log_failure(
                            node_type="变量节点",
                            node_name=self.name,
                            reason="未配置来源变量"
                        )
                        return NodeStatus.FAILURE
                else:
                    value = self.config.get("value", "")
                    parsed_value = self._parse_value(value)
                    context.blackboard.set(variable_name, parsed_value)

            elif operation == "increment":
                value = self.config.get("value", "")
                try:
                    amount = float(value) if value else 1
                    amount = int(amount) if amount == int(amount) else amount
                except (ValueError, TypeError):
                    amount = 1
                context.blackboard.increment(variable_name, amount)

            elif operation == "delete":
                context.blackboard.delete(variable_name)

            LogManager.instance().log_success(
                node_type="变量节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"SetVariableNode '{self.name}'")
            LogManager.instance().log_failure(
                node_type="变量节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE

    @staticmethod
    def _parse_value(raw: str):
        if raw.lower() == "true":
            return True
        if raw.lower() == "false":
            return False
        if raw.lower() == "none":
            return None
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        return raw

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetVariableNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.variable_name = config.get("variable_name", "")
        node.value = config.get("value", "")
        node.operation = config.get("operation", "set")
        node.value_type = config.get("value_type", "constant")
        node.source_variable = config.get("source_variable", "")
        return node
```

---

### 任务 3.2：改造 VariableConditionNode 后端逻辑

**文件**：`bt_nodes/conditions/variable.py`

**改动内容**：

1. `_check_condition` 方法中增加 `compare_type` 判断
2. 当 `compare_type == "variable"` 时，从黑板读取比较变量的值
3. `__init__` 中增加 `compare_type` 和 `compare_variable` 属性

**改动后完整代码**：

```python
class VariableConditionNode(ConditionNode):
    NODE_TYPE = "VariableConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.variable_name = self.config.get("variable_name", "")
        self.comparison = self.config.get("comparison") or self.config.get("operator", "==")
        self.target_value = self.config.get("target_value") or self.config.get("compare_value", "")
        self.compare_type = self.config.get("compare_type", "constant")
        self.compare_variable = self.config.get("compare_variable", "")

    def _check_condition(self, context) -> bool:
        try:
            variable_name = self.config.get("variable_name", "")
            comparison = self.config.get("comparison") or self.config.get("operator", "==")
            compare_type = self.config.get("compare_type", "constant")

            if not variable_name:
                self._log_condition_result(False, "未设置变量名")
                return False

            value = context.blackboard.get(variable_name)
            exists = context.blackboard.exists(variable_name)

            if comparison == "exists":
                if exists:
                    self._log_condition_result(True, extra_info=f"变量存在: {variable_name}")
                    return True
                else:
                    self._log_condition_result(False, f"变量不存在: {variable_name}")
                    return False

            if comparison == "not_exists":
                if not exists:
                    self._log_condition_result(True, extra_info=f"变量不存在: {variable_name}")
                    return True
                else:
                    self._log_condition_result(False, f"变量存在: {variable_name}")
                    return False

            if value is None:
                self._log_condition_result(False, f"变量不存在: {variable_name}")
                return False

            if compare_type == "variable":
                compare_var = self.config.get("compare_variable", "")
                if compare_var:
                    target_value = context.blackboard.get(compare_var)
                    if target_value is None:
                        self._log_condition_result(False,
                            f"比较变量 '{compare_var}' 不存在或值为 None")
                        return False
                else:
                    self._log_condition_result(False, "未配置比较变量")
                    return False
            else:
                target_value = self.config.get("target_value") or self.config.get("compare_value", "")

            result = self._compare_value(value, comparison, target_value)

            if result:
                self._log_condition_result(True, extra_info=f"值: {value}")
                return True
            else:
                self._log_condition_result(False,
                    f"变量比较失败: {value} {comparison} {target_value}")
                return False
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"VariableConditionNode '{self.name}'")
            self._log_condition_result(False, "检测异常，详情见终端日志")
            return False

    def _compare_value(self, value, comparison: str, target_value) -> bool:
        try:
            ops = {
                ">": lambda a, b: a > b,
                ">=": lambda a, b: a >= b,
                "<": lambda a, b: a < b,
                "<=": lambda a, b: a <= b,
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
            }

            if comparison in ops:
                try:
                    num_value = float(value) if isinstance(value, str) else value
                    num_target = float(target_value) if isinstance(target_value, str) else target_value

                    if isinstance(num_value, (int, float)) and isinstance(num_target, (int, float)):
                        return ops[comparison](num_value, num_target)
                except (ValueError, TypeError):
                    pass

            str_value = str(value)
            str_target = str(target_value)

            if comparison == "==":
                return str_value == str_target
            elif comparison == "!=":
                return str_value != str_target
            elif comparison == "contains":
                return str_target in str_value
            elif comparison == "not_contains":
                return str_target not in str_value
            elif comparison == "starts_with":
                return str_value.startswith(str_target)
            elif comparison == "ends_with":
                return str_value.endswith(str_target)
            else:
                return str_value == str_target
        except Exception:
            return False
```

---

### 检查点 C 测试用例

**测试方式**：编写 Python 测试脚本，直接调用后端逻辑验证。

| 编号 | 测试项 | 测试方法 | 预期结果 |
|------|--------|---------|---------|
| C-01 | set 常量值-整数 | config={variable_name:"counter", operation:"set", value_type:"constant", value:"100"}，执行后 blackboard.get("counter") | `100`（int） |
| C-02 | set 常量值-浮点数 | config={variable_name:"ratio", operation:"set", value_type:"constant", value:"3.14"}，执行后 blackboard.get("ratio") | `3.14`（float） |
| C-03 | set 常量值-布尔 | config={variable_name:"flag", operation:"set", value_type:"constant", value:"true"}，执行后 blackboard.get("flag") | `True`（bool） |
| C-04 | set 常量值-字符串 | config={variable_name:"name", operation:"set", value_type:"constant", value:"hello"}，执行后 blackboard.get("name") | `"hello"`（str） |
| C-05 | set 变量名-整数类型保留 | blackboard.set("last_detection_x", 100)，config={variable_name:"prev_x", operation:"set", value_type:"variable", source_variable:"last_detection_x"}，执行后 blackboard.get("prev_x") | `100`（int，类型保留） |
| C-06 | set 变量名-元组类型保留 | blackboard.set("last_detection_position", (100, 200))，config={variable_name:"prev_pos", operation:"set", value_type:"variable", source_variable:"last_detection_position"}，执行后 blackboard.get("prev_pos") | `(100, 200)`（tuple，类型保留） |
| C-07 | set 变量名-来源变量不存在 | config={variable_name:"target", operation:"set", value_type:"variable", source_variable:"nonexistent_var"}，执行后 blackboard.get("target") | `None` |
| C-08 | set 变量名-来源变量为空 | config={variable_name:"target", operation:"set", value_type:"variable", source_variable:""}，执行后返回 | `NodeStatus.FAILURE` |
| C-09 | increment 正常 | blackboard.set("counter", 10)，config={variable_name:"counter", operation:"increment", value:"5"}，执行后 blackboard.get("counter") | `15` |
| C-10 | delete 正常 | blackboard.set("temp", "value")，config={variable_name:"temp", operation:"delete"}，执行后 blackboard.exists("temp") | `False` |
| C-11 | 变量判断-常量值-大于 | blackboard.set("x", 100)，config={variable_name:"x", operator:">", compare_type:"constant", compare_value:"50"}，结果 | `True` |
| C-12 | 变量判断-常量值-等于 | blackboard.set("x", 100)，config={variable_name:"x", operator:"==", compare_type:"constant", compare_value:"100"}，结果 | `True` |
| C-13 | 变量判断-变量名-大于 | blackboard.set("x", 150)，blackboard.set("prev_x", 100)，config={variable_name:"x", operator:">", compare_type:"variable", compare_variable:"prev_x"}，结果 | `True` |
| C-14 | 变量判断-变量名-等于 | blackboard.set("x", 100)，blackboard.set("prev_x", 100)，config={variable_name:"x", operator:"==", compare_type:"variable", compare_variable:"prev_x"}，结果 | `True` |
| C-15 | 变量判断-变量名-小于 | blackboard.set("y", 180)，blackboard.set("prev_y", 200)，config={variable_name:"y", operator:"<", compare_type:"variable", compare_variable:"prev_y"}，结果 | `True` |
| C-16 | 变量判断-变量名-比较变量不存在 | blackboard.set("x", 100)，config={variable_name:"x", operator:">", compare_type:"variable", compare_variable:"nonexistent"}，结果 | `False`（日志：比较变量 'nonexistent' 不存在或值为 None） |
| C-17 | 变量判断-变量名-比较变量为空 | blackboard.set("x", 100)，config={variable_name:"x", operator:">", compare_type:"variable", compare_variable:""}，结果 | `False`（未配置比较变量） |
| C-18 | 变量判断-存在 | blackboard.set("x", 100)，config={variable_name:"x", operator:"exists"}，结果 | `True` |
| C-19 | 变量判断-不存在 | config={variable_name:"nonexistent", operator:"not_exists"}，结果 | `True` |
| C-20 | 完整坐标比较工作流 | ① blackboard.set("last_detection_x", 100) ② set prev_x from last_detection_x ③ blackboard.set("last_detection_x", 150) ④ compare last_detection_x > prev_x | prev_x=100，比较结果 True |

---

## 五、阶段 4 — 旧数据兼容与清理

### 任务 4.1：旧树 operation="clear" 迁移

**问题**：旧的行为树文件中可能存在 `operation: "clear"` 的配置。删除 clear 后，SelectField 的 `set_value` 找不到匹配的 display_name，会原样显示 "clear"。

**解决方案**：在 PropertyPanel 加载节点配置时，对 SetVariableNode 的 operation 字段做一次迁移。

**文件**：`bt_gui/bt_editor/property.py`

**改动位置**：`load_node` 方法中，加载 config 值之前

**具体操作**：在 `load_node` 方法中，当节点类型为 `SetVariableNode` 且 `operation` 为 `"clear"` 时，将其替换为 `"delete"`。

**实现方式**：在 `_create_field` 方法中，对 SetVariableNode 的 operation 字段值做修正：

```python
# 在 _create_field 方法开头，value 赋值之前
if (self.current_node_type == "SetVariableNode" and key == "operation" 
    and str(value) == "clear"):
    value = "delete"
```

> 此处选择在 `_create_field` 中处理而非 `load_node`，因为 `_create_field` 是所有字段值的统一入口，改动最小。

---

### 任务 4.2：确认无需其他迁移

| 字段 | 旧树中可能的状态 | 迁移策略 |
|------|----------------|---------|
| `value_type` | 不存在 | `config.get("value_type", "constant")` 默认为 `constant`，行为与旧版一致 |
| `source_variable` | 不存在 | `config.get("source_variable", "")` 默认为空，不影响旧逻辑 |
| `compare_type` | 不存在 | `config.get("compare_type", "constant")` 默认为 `constant`，行为与旧版一致 |
| `compare_variable` | 不存在 | `config.get("compare_variable", "")` 默认为空，不影响旧逻辑 |
| `operation` | 可能是 `"clear"` | 迁移为 `"delete"`（任务 4.1） |

---

### 检查点 D 测试用例

| 编号 | 测试项 | 测试方法 | 预期结果 |
|------|--------|---------|---------|
| D-01 | 旧树 operation=clear 迁移 | 构造含 operation:"clear" 的 JSON，加载后查看操作字段 | 显示「删除」（内部值 "delete"） |
| D-02 | 旧树无 value_type 字段 | 构造不含 value_type 的 SetVariableNode JSON，加载后查看 | 赋值方式默认显示「常量值」，行为与旧版一致 |
| D-03 | 旧树无 compare_type 字段 | 构造不含 compare_type 的 VariableConditionNode JSON，加载后查看 | 比较值类型默认显示「常量值」，行为与旧版一致 |
| D-04 | 旧树保存后重新加载 | 加载旧格式 JSON → 修改 → 保存 → 重新加载 | 新字段正确保存和恢复 |

---

## 六、阶段 5 — 冒烟测试与回归测试

### 6.1 冒烟测试

| 编号 | 测试项 | 操作步骤 | 预期结果 |
|------|--------|---------|---------|
| ST-01 | 应用启动 | 双击启动应用 | 应用正常启动，无报错 |
| ST-02 | 创建行为树 | 新建行为树，添加各种节点 | 正常创建 |
| ST-03 | 设变量节点-操作中文化 | 添加设变量节点，查看操作下拉 | 显示「设置/递增/删除」三个中文选项 |
| ST-04 | 设变量-设置-常量值模式 | 操作=设置，赋值方式=常量值，值输入100，变量名输入counter | 显示4个字段，保存后重新加载值正确 |
| ST-05 | 设变量-设置-变量名模式 | 操作=设置，赋值方式=变量名，来源变量选择「最近检测点x值」，变量名输入prev_x | 显示4个字段（值隐藏，来源变量显示），保存后重新加载值正确 |
| ST-06 | 设变量-设置-变量名自定义 | 操作=设置，赋值方式=变量名，来源变量输入自定义名my_var | 可正常输入自定义变量名 |
| ST-07 | 设变量-递增模式 | 操作=递增，值输入5，变量名输入counter | 显示3个字段（赋值方式和来源变量隐藏） |
| ST-08 | 设变量-删除模式 | 操作=删除，变量名输入temp | 仅显示2个字段（赋值方式、值、来源变量均隐藏） |
| ST-09 | 操作切换联动 | 在设置/递增/删除之间切换 | 字段正确显示/隐藏，无闪烁或残留 |
| ST-10 | 变量判断-运算符中文化 | 添加变量判断节点，查看运算符下拉 | 显示12个中文选项 |
| ST-11 | 变量判断-等于-常量值 | 运算符=等于，比较值类型=常量值，比较值输入50 | 显示4个字段 |
| ST-12 | 变量判断-大于-变量名 | 运算符=大于，比较值类型=变量名，比较变量选择「最近检测点x值」 | 显示4个字段（比较值隐藏，比较变量显示） |
| ST-13 | 变量判断-存在 | 运算符=存在 | 仅显示2个字段（比较值类型、比较值、比较变量隐藏） |
| ST-14 | 运算符切换联动 | 在等于/存在/大于/不存在之间切换 | 字段正确显示/隐藏 |
| ST-15 | 来源变量下拉 | 点击来源变量下拉框 | 显示「最近检测点」「最近检测点x值」「最近检测点y值」「最近数字值」4个选项 |
| ST-16 | 比较变量下拉 | 点击比较变量下拉框 | 显示同上4个选项 |
| ST-17 | 保存并重新加载 | 配置完整的设变量和变量判断节点，保存，关闭，重新打开 | 所有字段值正确恢复，字段可见性正确 |
| ST-18 | 其他节点不受影响 | 添加 OCR/图像/颜色/数字条件节点，检查 region_mode 相关字段 | hide_if 行为与改造前一致 |
| ST-19 | 其他 select 字段不受影响 | 检查按键节点的动作下拉、点击节点的按钮下拉等 | 显示和行为与改造前一致 |

### 6.2 回归测试

回归测试确保改造不影响现有功能。以下用例覆盖核心功能路径。

| 编号 | 测试项 | 测试方法 | 预期结果 |
|------|--------|---------|---------|
| RT-01 | 设变量-设置-常量值（向后兼容） | 加载旧格式行为树（无 value_type 字段），运行设变量节点 | 行为与改造前一致，value_type 默认 constant |
| RT-02 | 设变量-递增（向后兼容） | 运行 increment 操作的设变量节点 | 递增行为与改造前一致 |
| RT-03 | 设变量-删除（向后兼容） | 运行 delete 操作的设变量节点 | 删除行为与改造前一致 |
| RT-04 | 变量判断-常量值比较（向后兼容） | 加载旧格式行为树（无 compare_type 字段），运行变量判断节点 | 比较行为与改造前一致 |
| RT-05 | 变量判断-存在/不存在（向后兼容） | 运算符为 exists/not_exists | 行为与改造前一致 |
| RT-06 | 变量判断-字符串操作（向后兼容） | 运算符为 contains/not_contains/starts_with/ends_with | 行为与改造前一致 |
| RT-07 | 黑板内置变量 | 运行条件节点检测，检查 last_detection_position/last_detection_x/last_detection_y | 自动写入正确 |
| RT-08 | 黑板订阅通知 | 订阅变量变化，修改变量值 | 回调正确触发 |
| RT-09 | 其他节点 hide_if | 加载含 region_mode 的条件节点，切换 fixed/dynamic | 字段隐藏/显示行为与改造前一致 |
| RT-10 | 其他节点 display_names | 加载含 region_mode 的条件节点，查看下拉显示 | 显示「固定区域检测/动态区域检测」 |
| RT-11 | 行为树保存/加载 | 创建含各类节点的行为树，保存，重新加载 | 所有节点配置正确恢复 |
| RT-12 | 行为树执行 | 运行包含设变量和变量判断节点的行为树 | 执行结果正确 |

### 6.3 端到端集成测试

验证完整的「坐标比较」工作流。

| 编号 | 测试项 | 操作步骤 | 预期结果 |
|------|--------|---------|---------|
| E2E-01 | 坐标保存与比较 | ① 设变量: prev_x ← last_detection_x（变量名赋值）② 模拟更新 last_detection_x ③ 变量判断: last_detection_x > prev_x（变量名比较） | prev_x 保留旧值，比较结果 True |
| E2E-02 | 坐标双向比较 | ① 保存 prev_x, prev_y ② 更新 last_detection_x, last_detection_y ③ 判断 x 增大且 y 减小 | 两个判断均为 True |
| E2E-03 | 变量赋值类型保留 | ① last_detection_position = (100, 200) ② 设变量: prev_pos ← last_detection_position（变量名赋值）③ 检查 prev_pos 类型 | `tuple`，值 `(100, 200)` |
| E2E-04 | 变量赋值后修改不影响来源 | ① last_detection_x = 100 ② 设变量: prev_x ← last_detection_x ③ 设变量: last_detection_x = 200（常量值）④ 检查 prev_x | `prev_x` 仍为 100（值拷贝，非引用） |

---

## 七、执行顺序与依赖关系

```
任务1.1 (hide_if扩展) ─────────────────────┐
                                            │
任务1.2 (Blackboard内置变量扩展) ────────────┤
                                            │
任务1.3 (VariableSelectField) ──────────────┤
                                            ├─→ 检查点A
任务1.4 (注册variable_select) ──────────────┘
                                            │
                                            ↓
任务2.1 (SetVariableNode Schema) ───────────┤
                                            ├─→ 检查点B
任务2.2 (VariableConditionNode Schema) ─────┘
                                            │
                                            ↓
任务3.1 (SetVariableNode后端) ──────────────┤
                                            ├─→ 检查点C
任务3.2 (VariableConditionNode后端) ────────┘
                                            │
                                            ↓
任务4.1 (clear迁移) ────────────────────────┤
                                            ├─→ 检查点D
任务4.2 (确认无需其他迁移) ─────────────────┘
                                            │
                                            ↓
                                    冒烟测试 + 回归测试
```

**关键依赖**：
- 任务 1.3（VariableSelectField）依赖任务 1.2（Blackboard 内置变量扩展）
- 任务 1.4 依赖任务 1.3
- 任务 2.1/2.2 依赖任务 1.1（hide_if OR 逻辑）和任务 1.2/1.3（VariableSelectField）
- 任务 3.1/3.2 可与任务 2.1/2.2 并行开发，但测试需在两者都完成后进行
- 任务 4.1 依赖任务 2.1（Schema 中删除了 clear 选项）
- 冒烟测试和回归测试需在所有任务完成后进行

---

## 八、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| CTkComboBox 在某些 customtkinter 版本中行为不一致 | VariableSelectField 可能无法正确输入自定义值 | 测试时验证输入功能；如有问题回退为 CTkEntry + CTkOptionMenu 组合方案 |
| hide_if 级联刷新时 value_type 隐藏后值未重置 | 切换到递增/删除再切回设置时，value_type 可能保留 "variable" | 这是预期行为（隐藏不重置值），但需在测试中验证字段可见性是否正确 |
| 旧树中 operation="clear" 迁移遗漏 | 用户看到 "clear" 原样显示 | 在 _create_field 中统一处理迁移 |
| 变量赋值来源变量不存在 | 目标变量被设为 None | 日志中提示，行为合理 |
| 变量比较时比较变量不存在或值为 None | `blackboard.get(compare_var)` 返回 None，传入 `_compare_value` 可能导致 TypeError | 在 `_check_condition` 中增加显式 None 检查，提前返回 False 并输出日志「比较变量 '{compare_var}' 不存在或值为 None」 |
