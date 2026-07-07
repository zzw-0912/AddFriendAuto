# DD版本与Normal版本合并 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 DD 版本和 Normal 版本合并为单一版本，通过设置项控制输入方式，切换后重启应用加载对应输入控制器，DD 模式自动以管理员身份重启。

**Architecture:** 在 SettingsManager 中新增 `input.method` 配置项，InputController 从设置驱动而非环境变量驱动。新增 `app_restarter.py` 工具模块封装管理员检测与重启逻辑。SettingsTab 新增输入方式设置区域。main.py 启动时根据配置检测管理员权限。合并 spec 文件为单一构建产物。

**Tech Stack:** Python 3.11 / ctypes (Windows API) / CustomTkinter / PyInstaller

---

## Task 1: 新增 app_restarter.py 工具模块

**Files:**
- Create: `bt_utils/app_restarter.py`

**Step 1: 创建 app_restarter.py**

```python
import ctypes
import sys
import os


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def is_dd_available() -> bool:
    possible_paths = []
    base_path = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    possible_paths.extend([
        os.path.join(base_path, "DD64.dll"),
        os.path.join(base_path, "drivers", "DD64.dll"),
        os.path.join(base_path, "..", "drivers", "DD64.dll"),
        os.path.join(os.path.dirname(base_path), "drivers", "DD64.dll"),
    ])
    return any(os.path.exists(p) for p in possible_paths)


def _get_restart_command():
    if is_frozen():
        exe_path = sys.executable
        params = " ".join(sys.argv[1:])
        return exe_path, params
    else:
        exe_path = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        params = f'"{script_path}"'
        if len(sys.argv) > 1:
            params += " " + " ".join(f'"{a}"' for a in sys.argv[1:])
        return exe_path, params


def restart_as_admin() -> bool:
    exe_path, params = _get_restart_command()
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe_path,
        params,
        None,
        1
    )
    if ret <= 32:
        return False
    return True


def restart_normal():
    exe_path, params = _get_restart_command()
    if is_frozen():
        os.execv(exe_path, [exe_path] + sys.argv[1:])
    else:
        import subprocess
        subprocess.Popen([exe_path] + sys.argv)


def restart_app(as_admin: bool = False) -> bool:
    if as_admin:
        if is_admin():
            restart_normal()
            return True
        success = restart_as_admin()
        if success:
            return True
        return False
    else:
        restart_normal()
        return True
```

**Step 2: 验证模块可导入**

Run: `python -c "from bt_utils.app_restarter import is_admin, is_dd_available, restart_app; print('is_admin:', is_admin()); print('is_dd_available:', is_dd_available())"`
Expected: 输出两个布尔值，无报错

**Step 3: Commit**

```bash
git add bt_utils/app_restarter.py
git commit -m "feat: add app_restarter utility module for admin restart"
```

---

## Task 2: SettingsManager 新增 input 配置项

**Files:**
- Modify: `config/settings_manager.py:92-139` (DEFAULT_SETTINGS)

**Step 1: 在 DEFAULT_SETTINGS 中新增 input 配置**

在 `DEFAULT_SETTINGS` 字典中，在 `"update"` 键之前，新增 `"input"` 键：

```python
        "input": {
            "method": "pyautogui",
        },
```

完整的 DEFAULT_SETTINGS 变为：

```python
    DEFAULT_SETTINGS = {
        "version": VERSION,
        "tesseract_path": "",
        "alarm_sound_path": "",
        "alarm_volume": 70,
        "default_project_path": "",
        "shortcuts": {
            "start": "F10",
            "stop": "F12",
            "record": "F11"
        },
        "behavior_tree": {
            "tick_interval": 50,
            "auto_save_interval": 30,
            "default_format": "json",
            "default_check_interval_ms": 300,
            "default_timeout_ms": 0,
            "default_retry_count": 0,
            "default_repeat_count": 0,
            "default_child_interval": 0,
            "max_undo_history": 50
        },
        "ui": {
            "theme": "dark",
            "language": "zh_CN",
            "font_size": 10
        },
        "session": {
            "last_file_path": "",
            "recent_files": [],
            "window_geometry": "1280x800",
            "last_export_path": "",
            "open_tabs": [],
            "active_tab_id": ""
        },
        "blackboard": {
            "default_position_key": "last_detection_position",
            "default_value_key": "last_number_value",
            "default_ocr_text_key": "last_ocr_text",
            "default_color_key": "last_color_value",
            "default_image_match_key": "last_image_match"
        },
        "input": {
            "method": "pyautogui",
        },
        "update": {
            "ignored_version": "",
            "last_check_time": "",
            "check_interval": 86400,
            "force_update_cache": {}
        }
    }
```

**Step 2: 在 _migrate_config 中新增旧版环境变量迁移逻辑**

在 `_migrate_config` 方法中，`if config_version != self.VERSION:` 代码块内，新增：

```python
        if os.environ.get('AUTODOOR_USE_DD', '0') == '1':
            if 'input' not in self.settings:
                self.settings['input'] = {}
            self.settings['input']['method'] = 'dd'
```

完整的 `_migrate_config` 方法：

```python
    def _migrate_config(self) -> None:
        config_version = self.settings.get("version", "0.0.0")
        
        if config_version != self.VERSION:
            self.settings["version"] = self.VERSION
            self.settings["last_save_time"] = datetime.datetime.now().isoformat()
            
            if os.environ.get('AUTODOOR_USE_DD', '0') == '1':
                if 'input' not in self.settings:
                    self.settings['input'] = {}
                self.settings['input']['method'] = 'dd'
            
            self.save_settings()
```

**Step 3: 验证配置读写**

Run: `python -c "from config.settings_manager import SettingsManager; s = SettingsManager(); print(s.get('input.method', 'default')); s.set('input.method', 'dd'); print(s.get('input.method', 'default')); s.set('input.method', 'pyautogui')"`
Expected: 先输出 `default`，再输出 `dd`

**Step 4: Commit**

```bash
git add config/settings_manager.py
git commit -m "feat: add input.method setting and DD migration logic"
```

---

## Task 3: InputController 改为设置驱动

**Files:**
- Modify: `bt_utils/input_controller_factory.py:1-296`

**Step 1: 移除 USE_DD_INPUT 模块级变量，改为函数**

将文件头部的：

```python
USE_DD_INPUT = os.environ.get('AUTODOOR_USE_DD', '0') == '1'
```

替换为：

```python
def _get_input_method_from_settings() -> str:
    try:
        from config.settings_manager import SettingsManager
        method = SettingsManager.get_instance().get("input.method", "pyautogui")
    except Exception:
        method = "pyautogui"
    
    if method == "dd":
        from .app_restarter import is_dd_available
        if not is_dd_available():
            method = "pyautogui"
    
    return method
```

**Step 2: 修改 InputController._init_implementation**

将 `_init_implementation` 方法中：

```python
    def _init_implementation(self):
        """初始化具体实现"""
        method = self._method
        
        if method is None:
            if USE_DD_INPUT:
                method = 'dd'
            else:
                method = 'pyautogui'
        
        if method == 'dd':
            dd_instance = _get_dd_input(self.app)
            if dd_instance and dd_instance.is_available:
                self._impl = DDInputWrapper(dd_instance, self.app)
                self._method = 'dd'
                return
            else:
                # DD版本：如果DD不可用，不回退到PyAutoGUI，保持为None
                self._impl = None
                self._method = 'dd'
                return
        
        # 非DD版本：使用PyAutoGUI
        self._impl = PyAutoGUIInput(self.app)
        self._method = 'pyautogui'
```

替换为：

```python
    def _init_implementation(self):
        method = self._method
        
        if method is None:
            method = _get_input_method_from_settings()
        
        if method == 'dd':
            dd_instance = _get_dd_input(self.app)
            if dd_instance and dd_instance.is_available:
                self._impl = DDInputWrapper(dd_instance, self.app)
                self._method = 'dd'
                return
            else:
                self._impl = PyAutoGUIInput(self.app)
                self._method = 'pyautogui'
                return
        
        self._impl = PyAutoGUIInput(self.app)
        self._method = 'pyautogui'
```

**关键变更**：
1. `USE_DD_INPUT` 全局变量 → `_get_input_method_from_settings()` 函数，从 SettingsManager 读取
2. DD 不可用时**回退到 PyAutoGUI**（而非 `_impl = None`），确保功能始终可用
3. DD 选项前检查 `is_dd_available()`，避免在无 DLL 时尝试加载

**Step 3: 验证 InputController 正常工作**

Run: `python -c "from bt_utils.input_controller_factory import InputController; ic = InputController(); print('method:', ic.method, 'available:', ic.is_available)"`
Expected: `method: pyautogui available: True`

**Step 4: Commit**

```bash
git add bt_utils/input_controller_factory.py
git commit -m "feat: InputController reads input method from settings instead of env var"
```

---

## Task 4: main.py 启动时管理员检测与提权

**Files:**
- Modify: `main.py:186-229` (initialize_input + main)

**Step 1: 修改 initialize_input 函数**

将：

```python
def initialize_input():
    """初始化输入控制器（预加载DD虚拟键盘）"""
    try:
        from bt_utils.input_controller_factory import InputController
        # 预加载输入控制器，会自动加载DD虚拟键盘（如果启用）
        InputController()
        return True
    except Exception:
        return False
```

替换为：

```python
def initialize_input():
    """初始化输入控制器"""
    try:
        from bt_utils.input_controller_factory import InputController
        InputController()
        return True
    except Exception:
        return False


def check_admin_for_dd():
    """检查DD模式是否需要管理员权限，如需要则提权重启"""
    from config.settings_manager import SettingsManager
    from bt_utils.app_restarter import is_admin, is_dd_available, restart_as_admin
    
    settings = SettingsManager.get_instance()
    input_method = settings.get("input.method", "pyautogui")
    
    if input_method != "dd":
        return True
    
    if not is_dd_available():
        write_log("DD64.dll not found, falling back to PyAutoGUI")
        settings.set("input.method", "pyautogui")
        return True
    
    if is_admin():
        write_log("DD mode: already running as admin")
        return True
    
    write_log("DD mode: not admin, requesting elevation")
    
    import tkinter as tk
    from tkinter import messagebox
    
    root = tk.Tk()
    root.withdraw()
    
    result = messagebox.askyesno(
        "需要管理员权限",
        "DD虚拟键盘需要管理员权限才能正常工作。\n\n"
        "是否以管理员身份重新启动应用？\n\n"
        "点击「否」将使用 PyAutoGUI 模式启动。",
        icon='warning'
    )
    root.destroy()
    
    if result:
        success = restart_as_admin()
        if success:
            write_log("Admin restart initiated, exiting current process")
            sys.exit(0)
        else:
            write_log("Admin restart failed (UAC denied or error)")
            root2 = tk.Tk()
            root2.withdraw()
            messagebox.showwarning(
                "权限获取失败",
                "无法获取管理员权限，将使用 PyAutoGUI 模式启动。"
            )
            root2.destroy()
    
    write_log("Falling back to PyAutoGUI mode")
    settings.set("input.method", "pyautogui")
    return True
```

**Step 2: 在 main() 函数中调用 check_admin_for_dd**

在 `main()` 函数中，`ensure_workspace_exists()` 之后、`initialize_ocr()` 之前，新增调用：

```python
def main():
    ensure_workspace_exists()
    
    check_admin_for_dd()
    
    initialize_ocr()
    initialize_input()
    # ... 后续代码不变
```

**Step 3: 验证启动流程**

Run: `python main.py`
Expected: 应用正常启动，使用 PyAutoGUI 模式（因为默认 input.method = "pyautogui"）

**Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add admin check for DD mode at startup"
```

---

## Task 5: BehaviorTreeApp 新增重启方法

**Files:**
- Modify: `bt_gui/app.py:448-511` (_on_close + 新增方法)

**Step 1: 在 BehaviorTreeApp 类中新增 _save_state 和 _restart_with_method 方法**

在 `_on_close` 方法之前，新增：

```python
    def _save_state(self):
        current_geometry = self.geometry()
        self._settings.set("session.window_geometry", current_geometry)
        
        if hasattr(self, 'settings') and self.settings:
            settings_data = self.settings.get_settings()
            self._settings.set("alarm_sound_path", settings_data.get("alarm_sound_path", ""), auto_save=False)
            self._settings.set("alarm_volume", settings_data.get("alarm_volume", 70), auto_save=False)
            self._settings.set("default_project_path", settings_data.get("default_project_path", ""), auto_save=False)
            if "shortcuts" in settings_data:
                shortcuts = settings_data["shortcuts"]
                self._settings.set("shortcuts.start", shortcuts.get("start", "F10"), auto_save=False)
                self._settings.set("shortcuts.stop", shortcuts.get("stop", "F12"), auto_save=False)
                self._settings.set("shortcuts.record", shortcuts.get("record", "F11"), auto_save=False)
        
        if hasattr(self, 'behavior_tree') and self.behavior_tree:
            if hasattr(self.behavior_tree, 'tab_manager'):
                tabs_info = []
                for tab_id, instance in self.behavior_tree.tab_manager._trees.items():
                    if instance.file_path and os.path.exists(instance.file_path):
                        tabs_info.append({
                            "tab_id": tab_id,
                            "name": instance.name,
                            "file_path": instance.file_path,
                            "project_root": instance.project_root or "",
                        })
                self._settings.set_open_tabs(tabs_info)
                active_tab = self.behavior_tree.tab_manager.get_active_tab()
                if active_tab:
                    self._settings.set_active_tab_id(active_tab.tab_id)
    
    def _restart_with_method(self, method: str, as_admin: bool) -> bool:
        from bt_utils.app_restarter import restart_app
        
        if hasattr(self, 'behavior_tree') and self.behavior_tree:
            engine = getattr(self.behavior_tree, 'engine', None)
            if engine and getattr(engine, 'is_running', lambda: False)():
                messagebox.showwarning(
                    "无法重启",
                    "行为树正在运行中，请先停止运行再切换输入方式。"
                )
                return False
        
        self._settings.set("input.method", method)
        self._save_state()
        self._settings.save_settings()
        
        success = restart_app(as_admin=as_admin)
        
        if success:
            self.destroy()
            sys.exit(0)
        else:
            self._settings.set("input.method", "pyautogui")
            messagebox.showwarning(
                "重启失败",
                "无法以管理员身份重启应用，输入方式已恢复为 PyAutoGUI。"
            )
            return False
```

**Step 2: 重构 _on_close 复用 _save_state**

将 `_on_close` 方法改为复用 `_save_state`：

```python
    def _on_close(self):
        self._save_state()
        
        if hasattr(self, 'behavior_tree') and self.behavior_tree:
            if hasattr(self.behavior_tree, 'property_panel'):
                self.behavior_tree.property_panel.cleanup_preview_images()
            
            if hasattr(self.behavior_tree, 'tab_manager'):
                for tab_id, instance in list(self.behavior_tree.tab_manager._trees.items()):
                    if instance.modified:
                        result = messagebox.askyesnocancel(
                            "未保存的改动",
                            f"项目 \"{instance.name}\" 有未保存的改动。\n\n是否保存？"
                        )
                        if result is None:
                            return
                        elif result:
                            self.behavior_tree._save_tab(tab_id)
            else:
                file_path = self.behavior_tree.file_path
                if file_path:
                    self._settings.set_last_file_path(file_path)
                
                if hasattr(self.behavior_tree, '_modified') and self.behavior_tree._modified:
                    result = messagebox.askyesnocancel(
                        "未保存的改动",
                        "当前项目有未保存的改动。\n\n是否保存？"
                    )
                    
                    if result is None:
                        return
                    elif result:
                        self.behavior_tree.save_tree()
            
            self.behavior_tree.destroy()
        
        self._settings.save_settings()
        self.destroy()
```

**Step 3: 在文件顶部确保 import sys**

检查 `bt_gui/app.py` 顶部是否有 `import sys`，如果没有则新增。

**Step 4: 验证应用正常关闭**

Run: `python main.py` → 关闭窗口
Expected: 应用正常关闭，无报错

**Step 5: Commit**

```bash
git add bt_gui/app.py
git commit -m "feat: add _restart_with_method and refactor _on_close to reuse _save_state"
```

---

## Task 6: SettingsTab 新增输入方式设置区域

**Files:**
- Modify: `bt_gui/settings_tab.py:1-357`

**Step 1: 在 _init_variables 中新增输入方式变量**

在 `_init_variables` 方法末尾新增：

```python
        from config.settings_manager import SettingsManager
        settings = SettingsManager()
        self.input_method_var = tk.StringVar(value=settings.get("input.method", "pyautogui"))
        self._current_input_method = settings.get("input.method", "pyautogui")
```

**Step 2: 在 _create_ui 中调用新 section**

在 `_create_ui` 方法中，在 `self._create_shortcut_section(scroll_frame)` 之后新增：

```python
        self._create_input_method_section(scroll_frame)
```

**Step 3: 新增 _create_input_method_section 方法**

在 `_create_shortcut_section` 方法之后新增：

```python
    def _create_input_method_section(self, parent):
        from bt_utils.app_restarter import is_dd_available, is_admin
        
        input_frame = CardFrame(parent)
        input_frame.pack(fill="x", pady=(0, Theme.DIMENSIONS['spacing_md']))
        
        input_header = ctk.CTkFrame(input_frame, fg_color="transparent")
        input_header.pack(fill="x", padx=Theme.DIMENSIONS['spacing_md'], pady=(Theme.DIMENSIONS['spacing_md'], Theme.DIMENSIONS['spacing_sm']))
        create_section_title(input_header, "输入方式", level=1).pack(side="left")
        
        create_divider(input_frame)
        
        dd_available = is_dd_available()
        
        method_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        method_row.pack(fill="x", padx=Theme.DIMENSIONS['spacing_md'], pady=Theme.DIMENSIONS['spacing_sm'])
        
        self.pyautogui_radio = ctk.CTkRadioButton(
            method_row,
            text="PyAutoGUI（标准模式）",
            variable=self.input_method_var,
            value="pyautogui",
            font=Theme.get_font("sm"),
            fg_color=Theme.COLORS['primary'],
            hover_color=Theme.COLORS['primary_hover'],
            command=self._on_input_method_changed
        )
        self.pyautogui_radio.pack(side="left", padx=(0, Theme.DIMENSIONS['spacing_md']))
        
        self.dd_radio = ctk.CTkRadioButton(
            method_row,
            text="DD虚拟键盘（驱动级）",
            variable=self.input_method_var,
            value="dd",
            font=Theme.get_font("sm"),
            fg_color=Theme.COLORS['primary'],
            hover_color=Theme.COLORS['primary_hover'],
            command=self._on_input_method_changed
        )
        self.dd_radio.pack(side="left")
        
        if not dd_available:
            self.dd_radio.configure(state="disabled")
        
        desc_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        desc_row.pack(fill="x", padx=Theme.DIMENSIONS['spacing_md'], pady=(0, Theme.DIMENSIONS['spacing_sm']))
        
        desc_text = "PyAutoGUI: 基于软件模拟，兼容性好，无需管理员权限"
        ctk.CTkLabel(
            desc_row,
            text=desc_text,
            font=Theme.get_font("xs"),
            text_color=self._dark_colors['text_secondary']
        ).pack(anchor="w")
        
        dd_desc = "DD虚拟键盘: 驱动级模拟，绕过部分输入检测，需管理员权限"
        if not dd_available:
            dd_desc += "（DD64.dll 未找到）"
        ctk.CTkLabel(
            desc_row,
            text=dd_desc,
            font=Theme.get_font("xs"),
            text_color=self._dark_colors['warning'] if not dd_available else self._dark_colors['text_secondary']
        ).pack(anchor="w")
        
        status_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        status_row.pack(fill="x", padx=Theme.DIMENSIONS['spacing_md'], pady=(0, Theme.DIMENSIONS['spacing_sm']))
        
        current_method = self._current_input_method
        admin_status = "管理员" if is_admin() else "普通用户"
        status_text = f"当前状态: {'DD虚拟键盘' if current_method == 'dd' else 'PyAutoGUI'} 已加载 ({admin_status})"
        ctk.CTkLabel(
            status_row,
            text=status_text,
            font=Theme.get_font("xs"),
            text_color=self._dark_colors['primary']
        ).pack(anchor="w")
        
        warn_row = ctk.CTkFrame(input_frame, fg_color="transparent")
        warn_row.pack(fill="x", padx=Theme.DIMENSIONS['spacing_md'], pady=(0, Theme.DIMENSIONS['spacing_md']))
        
        ctk.CTkLabel(
            warn_row,
            text="⚠ 切换输入方式后需要重启应用才能生效",
            font=Theme.get_font("xs"),
            text_color=self._dark_colors['warning']
        ).pack(anchor="w")
```

**Step 4: 新增 _on_input_method_changed 方法**

```python
    def _on_input_method_changed(self):
        new_method = self.input_method_var.get()
        
        if new_method == self._current_input_method:
            return
        
        if new_method == "dd":
            result = messagebox.askyesno(
                "切换输入方式",
                "DD虚拟键盘需要管理员权限才能正常工作。\n"
                "切换后应用将以管理员身份重新启动。\n\n"
                "是否立即重启？",
                icon='warning'
            )
            if result:
                if hasattr(self.app, '_restart_with_method'):
                    self.app._restart_with_method("dd", as_admin=True)
            else:
                self.input_method_var.set(self._current_input_method)
        else:
            result = messagebox.askyesno(
                "切换输入方式",
                "切换到 PyAutoGUI 模式后，应用将重新启动。\n\n"
                "是否立即重启？",
                icon='question'
            )
            if result:
                if hasattr(self.app, '_restart_with_method'):
                    self.app._restart_with_method("pyautogui", as_admin=False)
            else:
                self.input_method_var.set(self._current_input_method)
```

**Step 5: 更新 get_settings 和 load_settings**

在 `get_settings` 方法中新增：

```python
            "input_method": self.input_method_var.get(),
```

在 `load_settings` 方法末尾新增：

```python
        if "input" in settings:
            input_settings = settings["input"]
            if "method" in input_settings:
                self.input_method_var.set(input_settings["method"])
                self._current_input_method = input_settings["method"]
```

**Step 6: 验证设置界面**

Run: `python main.py` → 切换到设置标签页
Expected: 看到"输入方式"设置区域，PyAutoGUI 选中，DD 可选（如果 DD64.dll 存在）

**Step 7: Commit**

```bash
git add bt_gui/settings_tab.py
git commit -m "feat: add input method settings section with DD/PyAutoGUI switch"
```

---

## Task 7: 合并 spec 文件

**Files:**
- Modify: `autodoor_bt.spec` (合并为统一版本)
- Delete: `autodoor_bt_dd.spec` (不再需要)
- Delete: `hooks/hook_dd_input.py` (不再需要)

**Step 1: 修改 autodoor_bt.spec**

在 `data_files` 列表中，在 `(os.path.join(project_root, 'bt_utils/build_info.json'), 'bt_utils'),` 行之后新增：

```python
    (os.path.join(project_root, 'drivers/DD64.dll'), 'drivers'),
```

在 `hiddenimports` 列表中新增 `'ctypes'`：

找到 `'pythoncom',` 行，在其后新增：

```python
        'ctypes',
```

将 `hookspath` 改为空（确保不依赖 hooks 目录）：

```python
    hookspath=[],
```

将 `runtime_hooks` 确认为空：

```python
    runtime_hooks=[],
```

将输出名称改为统一名称：

```python
    name=f'autodoor-behaviortree-{VERSION}',
```

COLLECT 的 name 也同步修改：

```python
    name=f'autodoor-behaviortree-{VERSION}',
```

**Step 2: 删除不再需要的文件**

- 删除 `autodoor_bt_dd.spec`
- 删除 `hooks/hook_dd_input.py`
- 删除 `bt_utils/hook_dd_input.py`（如果存在）

**Step 3: 更新构建脚本**

将 `build_standard.bat` 重命名为 `build.bat`，内容修改为：

```batch
@echo off
chcp 65001 >nul
echo ========================================
echo AutoDoor Behavior Tree - Unified Build
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python environment...
python --version
if errorlevel 1 (
    echo Error: Python not found!
    pause
    exit /b 1
)

echo.
echo Checking required modules...
python -c "import customtkinter; import rapidocr; import pygame; import PIL; print('All modules OK')"
if errorlevel 1 (
    echo Error: Required modules not installed!
    echo Please run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo Generating build info from build_config.json...
python generate_build_info.py
if errorlevel 1 (
    echo Warning: Failed to generate build info, using defaults
)

echo.
echo Starting PyInstaller build (Unified version)...
pyinstaller autodoor_bt.spec --clean

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo Output: dist\autodoor-behaviortree-%VERSION%
echo ========================================
pause
```

删除 `build_dd.bat` 和 `run_dd.bat`。

**Step 4: 验证构建**

Run: `pyinstaller autodoor_bt.spec --clean`
Expected: 构建成功，输出目录包含 `drivers/DD64.dll`

**Step 5: Commit**

```bash
git add autodoor_bt.spec
git rm autodoor_bt_dd.spec hooks/hook_dd_input.py bt_utils/hook_dd_input.py build_standard.bat build_dd.bat run_dd.bat
git add build.bat
git commit -m "feat: merge spec files into unified build, remove DD-specific files"
```

---

## Task 8: 端到端验证

**Files:**
- 无代码修改，仅验证

**Step 1: 验证 PyAutoGUI 模式启动**

Run: `python main.py`
Expected:
- 应用正常启动
- 设置页面显示"输入方式"区域，PyAutoGUI 选中
- 状态显示"PyAutoGUI 已加载 (普通用户)"

**Step 2: 验证切换到 DD 模式**

1. 在设置中点击"DD虚拟键盘"
2. 弹出确认对话框
3. 点击"否" → 选项恢复为 PyAutoGUI
4. 再次点击"DD虚拟键盘"
5. 点击"是" → 应用尝试以管理员身份重启

Expected:
- 如果 DD64.dll 存在：UAC 弹窗 → 确认后以管理员身份重启
- 如果 DD64.dll 不存在：DD 选项灰色不可选

**Step 3: 验证 DD 模式启动**

1. 手动设置 `input.method = "dd"`（通过 SettingsManager 或直接编辑 config.json）
2. 以管理员身份运行 `python main.py`

Expected:
- 应用以管理员身份启动
- DD 虚拟键盘加载成功
- 设置页面显示"DD虚拟键盘 已加载 (管理员)"

**Step 4: 验证 DD → PyAutoGUI 切换**

1. 在 DD 模式下，切换到 PyAutoGUI
2. 确认重启
3. 应用以普通模式重启

Expected:
- 应用正常重启
- 使用 PyAutoGUI 模式

**Step 5: 验证打包后运行**

1. 执行 `pyinstaller autodoor_bt.spec --clean`
2. 运行打包后的 `.exe`
3. 重复 Step 1-4 的验证

Expected: 所有行为与开发环境一致

**Step 6: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: address issues found during end-to-end verification"
```

---

## Task 9: 清理与收尾

**Files:**
- 检查所有修改文件

**Step 1: 确认所有文件修改正确**

检查以下文件的修改是否完整：
- [x] `bt_utils/app_restarter.py` — 新增
- [x] `config/settings_manager.py` — 新增 input 配置 + 迁移逻辑
- [x] `bt_utils/input_controller_factory.py` — 设置驱动 + DD 回退
- [x] `main.py` — 启动时管理员检测
- [x] `bt_gui/app.py` — 重启方法 + 状态保存重构
- [x] `bt_gui/settings_tab.py` — 输入方式设置 UI
- [x] `autodoor_bt.spec` — 合并为统一构建
- [x] 删除 `autodoor_bt_dd.spec`
- [x] 删除 `hooks/hook_dd_input.py`
- [x] 删除 `bt_utils/hook_dd_input.py`
- [x] 删除 `build_standard.bat` / `build_dd.bat` / `run_dd.bat`
- [x] 新增 `build.bat`

**Step 2: 最终 Commit**

```bash
git add -A
git commit -m "feat: complete DD/Normal version merge - unified build with settings-driven input method"
```
