import customtkinter as ctk
import os
import sys
from tkinter import messagebox

from .theme import Theme, init_theme
from .bt_editor import BehaviorTreeEditor
from .script_tab import ScriptTab
from .schedule_tab import ScheduleTab
from .settings_tab import SettingsTab
from config.settings_manager import SettingsManager
from bt_utils.log_manager import LogManager


def _get_app_title() -> str:
    """获取应用标题，包含版本号"""
    try:
        from main import VERSION
        return f"autodoor - 行为树 {VERSION}"
    except ImportError:
        return "autodoor - 行为树"


class BehaviorTreeApp(ctk.CTk):
    
    def __init__(self):
        init_theme()
        
        super().__init__()
        
        self._dark_colors = Theme.get_dark_colors()
        self._keyfield_active = False
        
        self._settings = SettingsManager.get_instance()
        
        self.title(_get_app_title())
        
        saved_geometry = self._settings.get("session.window_geometry", "1280x800")
        self.geometry(saved_geometry)
        self.minsize(800, 600)
        
        self.configure(fg_color=self._dark_colors['bg_primary'])
        
        self._set_icon()
        
        self._create_ui()
        self._setup_shortcuts()
        
        self._restore_last_file()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _restore_last_file(self):
        """恢复上次打开的文件和 Tab 列表"""
        open_tabs = self._settings.get_open_tabs()
        
        if open_tabs:
            restored_active_id = self._settings.get_active_tab_id()
            first_tab_id = None
            
            for i, tab_info in enumerate(open_tabs):
                file_path = tab_info.get("file_path", "")
                project_root = tab_info.get("project_root", "")
                name = tab_info.get("name", "")
                
                if not file_path or not os.path.exists(file_path):
                    continue
                
                if i == 0:
                    self.behavior_tree.load_tree(file_path)
                    if project_root and os.path.exists(project_root):
                        self.behavior_tree.project_root = project_root
                        from bt_utils.project_manager import ProjectManager
                        self.behavior_tree.project_manager = ProjectManager(project_root)
                        self.behavior_tree.toolbar.set_project_path(project_root)
                    if name:
                        self.behavior_tree._update_tab_name(
                            self.behavior_tree.tab_manager.get_active_tab().tab_id, name
                        )
                    first_tab_id = self.behavior_tree.tab_manager.active_tab_id
                else:
                    if project_root and os.path.exists(project_root):
                        self.behavior_tree.import_project_to_new_tab(project_root)
                    else:
                        tab_id = self.behavior_tree._create_new_tab(
                            name or os.path.splitext(os.path.basename(file_path))[0],
                            project_root or None,
                            file_path
                        )
                        self.behavior_tree._load_tree_to_tab(tab_id, file_path)
                        self.behavior_tree.tab_manager.switch_tab(tab_id)
                        self.behavior_tree.tab_bar.set_active(tab_id)
                        instance = self.behavior_tree.tab_manager.get_tab(tab_id)
                        self.behavior_tree._on_tab_switched(tab_id, instance)
            
            if restored_active_id:
                active_instance = self.behavior_tree.tab_manager.get_tab(restored_active_id)
                if active_instance:
                    self.behavior_tree.tab_manager.switch_tab(restored_active_id)
                    self.behavior_tree.tab_bar.set_active(restored_active_id)
                    self.behavior_tree._on_tab_switched(restored_active_id, active_instance)
            
            self._update_window_title()
        else:
            last_file = self._settings.get_last_file_path()
            if last_file and os.path.exists(last_file):
                try:
                    if hasattr(self, 'behavior_tree') and self.behavior_tree:
                        self.behavior_tree.load_tree(last_file)
                        self._update_window_title()
                except Exception:
                    pass
    
    def _update_window_title(self):
        """更新窗口标题，显示项目名称"""
        project_name = None
        if hasattr(self.behavior_tree, 'project_root') and self.behavior_tree.project_root:
            project_name = os.path.basename(self.behavior_tree.project_root)
        
        if project_name:
            try:
                from main import VERSION
                self.title(f"autodoor - 行为树 {VERSION} - {project_name}")
            except ImportError:
                self.title(f"autodoor - 行为树 - {project_name}")
        else:
            self.title(_get_app_title())
    
    def _set_icon(self):
        """设置应用图标"""
        try:
            from bt_utils.resource_manager import get_resource_manager
            rm = get_resource_manager()
            icon_path = rm.get_icon_path()
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            LogManager.debug_print(f"[WARN] 设置图标失败: {e}")
    
    def _create_ui(self):
        self._create_main_container()
    
    def _create_main_container(self):
        """创建主容器，包含顶部栏和内容区域"""
        self.main_container = ctk.CTkFrame(
            self,
            fg_color=self._dark_colors['bg_primary']
        )
        self.main_container.pack(fill='both', expand=True)
        
        self._create_top_bar()
        self._create_content_area()
    
    def _create_top_bar(self):
        """创建顶部栏（包含标题、Tab按钮、操作按钮）"""
        self.top_bar = ctk.CTkFrame(
            self.main_container,
            height=Theme.DIMENSIONS['header_height'],
            fg_color=self._dark_colors['bg_secondary'],
            corner_radius=0
        )
        self.top_bar.pack(fill='x')
        self.top_bar.pack_propagate(False)
        
        top_bar_content = ctk.CTkFrame(self.top_bar, fg_color='transparent')
        top_bar_content.pack(fill='x', padx=Theme.DIMENSIONS['spacing_md'], 
                            pady=Theme.DIMENSIONS['spacing_sm'])
        
        left_section = ctk.CTkFrame(top_bar_content, fg_color='transparent')
        left_section.pack(side='left')
        
        ctk.CTkLabel(
            left_section,
            text='◉',
            font=Theme.get_font('xl'),
            text_color=self._dark_colors['primary']
        ).pack(side='left', padx=(0, Theme.DIMENSIONS['spacing_xs']))
        
        ctk.CTkLabel(
            left_section,
            text='AutoDoor Behavior Tree',
            font=Theme.get_font('lg'),
            text_color=self._dark_colors['text_primary']
        ).pack(side='left')
        
        try:
            from main import VERSION
            ctk.CTkLabel(
                left_section,
                text=VERSION,
                font=Theme.get_font('xs'),
                text_color=self._dark_colors['primary'],
                fg_color=self._dark_colors['info_light'],
                corner_radius=4,
                padx=6,
                pady=1
            ).pack(side='left', padx=Theme.DIMENSIONS['spacing_sm'])
        except ImportError:
            pass
        
        center_section = ctk.CTkFrame(top_bar_content, fg_color='transparent')
        center_section.pack(side='left', expand=True)
        
        self.tab_buttons_frame = ctk.CTkFrame(
            center_section,
            fg_color=self._dark_colors['bg_tertiary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius']
        )
        self.tab_buttons_frame.pack()
        
        self.tab_buttons = {}
        tab_config = [
            ('bt', '🌲 行为树编辑器'),
            ('script', '📝 脚本录制'),
            ('schedule', '⏰ 定时执行'),
            ('settings', '⚙ 设置')
        ]
        
        for i, (tab_id, tab_text) in enumerate(tab_config):
            btn = ctk.CTkButton(
                self.tab_buttons_frame,
                text=tab_text,
                width=120,
                height=32,
                font=Theme.get_font('sm'),
                fg_color=self._dark_colors['primary'] if i == 0 else 'transparent',
                hover_color=self._dark_colors['primary_hover'] if i == 0 else self._dark_colors['border'],
                text_color=self._dark_colors['text_primary'],
                corner_radius=Theme.DIMENSIONS['button_corner_radius'],
                command=lambda tid=tab_id: self._switch_tab(tid)
            )
            btn.pack(side='left', padx=2, pady=2)
            self.tab_buttons[tab_id] = btn
        
        right_section = ctk.CTkFrame(top_bar_content, fg_color='transparent')
        right_section.pack(side='right')
        
        from bt_utils.version_checker import open_tool_intro
        
        self.check_update_btn = ctk.CTkButton(
            right_section,
            text='检查更新',
            width=80,
            height=35,
            font=Theme.get_font('sm'),
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            command=self._check_for_updates
        )
        self.check_update_btn.pack(side='left', padx=Theme.DIMENSIONS['spacing_xs'])
        
        self.tool_intro_btn = ctk.CTkButton(
            right_section,
            text='使用文档',
            width=80,
            height=35,
            font=Theme.get_font('sm'),
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            command=open_tool_intro
        )
        self.tool_intro_btn.pack(side='left', padx=Theme.DIMENSIONS['spacing_xs'])
    
    def _switch_tab(self, tab_id: str):
        """切换Tab"""
        for tid, btn in self.tab_buttons.items():
            if tid == tab_id:
                btn.configure(
                    fg_color=self._dark_colors['primary'],
                    hover_color=self._dark_colors['primary_hover']
                )
            else:
                btn.configure(
                    fg_color='transparent',
                    hover_color=self._dark_colors['border']
                )
        
        for tid, frame in self.tab_frames.items():
            if tid == tab_id:
                frame.pack(fill='both', expand=True)
            else:
                frame.pack_forget()
    
    def _create_content_area(self):
        """创建内容区域"""
        self.content_frame = ctk.CTkFrame(
            self.main_container,
            fg_color=self._dark_colors['bg_primary']
        )
        self.content_frame.pack(fill='both', expand=True, padx=Theme.DIMENSIONS['spacing_sm'], 
                               pady=Theme.DIMENSIONS['spacing_sm'])
        
        self.tab_frames = {}
        
        bt_frame = ctk.CTkFrame(self.content_frame, fg_color='transparent')
        script_frame = ctk.CTkFrame(self.content_frame, fg_color='transparent')
        schedule_frame = ctk.CTkFrame(self.content_frame, fg_color='transparent')
        settings_frame = ctk.CTkFrame(self.content_frame, fg_color='transparent')
        
        self.tab_frames['bt'] = bt_frame
        self.tab_frames['script'] = script_frame
        self.tab_frames['schedule'] = schedule_frame
        self.tab_frames['settings'] = settings_frame
        
        self.behavior_tree = BehaviorTreeEditor(bt_frame, self)
        self.behavior_tree.pack(fill='both', expand=True)
        
        self.script_editor = ScriptTab(script_frame, self)
        self.script_editor.pack(fill='both', expand=True)
        
        self.schedule_tab = ScheduleTab(schedule_frame, self)
        self.schedule_tab.pack(fill='both', expand=True)
        
        self.settings = SettingsTab(settings_frame, self)
        self.settings.pack(fill='both', expand=True)
        
        saved_settings = self._settings.get_all_settings()
        if saved_settings:
            self.settings.load_settings(saved_settings)
        
        bt_frame.pack(fill='both', expand=True)
    
    def _check_for_updates(self):
        """检查更新"""
        if hasattr(self, '_version_checker'):
            self._version_checker.check_for_updates(manual=True)
        else:
            from tkinter import messagebox
            messagebox.showinfo("检查更新", "版本检查器未初始化")
    
    def _get_current_tab(self) -> str:
        """获取当前Tab ID"""
        for tab_id, frame in self.tab_frames.items():
            if frame.winfo_ismapped():
                return tab_id
        return 'bt'
    
    def _setup_shortcuts(self):
        shortcuts = [
            ("<Control-z>", self._undo),
            ("<Control-y>", self._redo),
            ("<Control-Shift-Z>", self._redo),
            ("<Control-s>", self._save),
            ("<Control-Shift-S>", lambda: self._save(save_as=True)),
            ("<Control-o>", self._open),
            ("<Control-n>", self._new),
            ("<Delete>", self._delete),
            ("<BackSpace>", self._delete),
            ("<Control-c>", self._copy),
            ("<Control-v>", self._paste),
            ("<Control-x>", self._cut),
            ("<Control-d>", self._duplicate),
        ]
        
        for key, callback in shortcuts:
            self.bind(key, lambda e, cb=callback, k=key: self._handle_shortcut(e, cb, k))
    
    def _handle_shortcut(self, event, callback, key_name):
        if key_name in ("<Delete>", "<BackSpace>"):
            if self._keyfield_active:
                return "break"
        
        if callable(callback):
            callback()
        return "break"
    
    def set_keyfield_active(self, active: bool):
        self._keyfield_active = active
    
    def _undo(self):
        if hasattr(self.behavior_tree, 'undo'):
            self.behavior_tree.undo()
    
    def _redo(self):
        if hasattr(self.behavior_tree, 'redo'):
            self.behavior_tree.redo()
    
    def _save(self, save_as=False):
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, 'save_tree'):
                self.behavior_tree.save_tree(save_as=save_as)
        elif current_tab == 'script':
            if hasattr(self.script_editor, '_save_script'):
                self.script_editor._save_script()
    
    def _open(self):
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, 'load_tree'):
                self.behavior_tree.load_tree()
        elif current_tab == 'script':
            if hasattr(self.script_editor, '_load_script'):
                self.script_editor._load_script()
    
    def _new(self):
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, 'new_tree'):
                self.behavior_tree.new_tree()
        elif current_tab == 'script':
            if hasattr(self.script_editor, '_new_script'):
                self.script_editor._new_script()
    
    def _delete(self):
        if self._is_focused_on_input_widget():
            return
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, '_delete_selected'):
                self.behavior_tree._delete_selected()
    
    def _is_focused_on_input_widget(self) -> bool:
        """检查当前焦点是否在输入控件上"""
        focused = self.focus_get()
        if focused:
            widget_type = str(type(focused).__name__)
            if widget_type in ("CTkEntry", "Entry", "CTkTextbox", "Text"):
                return True
        return False
    
    def _copy(self):
        if self._is_focused_on_input_widget():
            return
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, '_copy_selected'):
                self.behavior_tree._copy_selected()
    
    def _paste(self):
        if self._is_focused_on_input_widget():
            return
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, '_paste_selected'):
                self.behavior_tree._paste_selected()
    
    def _cut(self):
        if self._is_focused_on_input_widget():
            return
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, '_cut_selected'):
                self.behavior_tree._cut_selected()
    
    def _duplicate(self):
        if self._is_focused_on_input_widget():
            return
        current_tab = self._get_current_tab()
        if current_tab == 'bt':
            if hasattr(self.behavior_tree, '_duplicate_selected'):
                self.behavior_tree._duplicate_selected()
    
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
                self._settings.set("shortcuts.tab_shortcuts", shortcuts.get("tab_shortcuts", []), auto_save=False)
        
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
    
    def _restart_with_methods(self, keyboard_method: str, mouse_method: str, as_admin: bool) -> bool:
        from bt_utils.app_restarter import restart_app

        if hasattr(self, 'behavior_tree') and self.behavior_tree:
            engine = getattr(self.behavior_tree, 'engine', None)
            if engine and getattr(engine, 'is_running', lambda: False)():
                messagebox.showwarning(
                    "无法重启",
                    "行为树正在运行中，请先停止运行再切换输入方式。"
                )
                return False

        self._settings.set("input.keyboard_method", keyboard_method)
        self._settings.set("input.mouse_method", mouse_method)
        self._save_state()
        self._settings.save_settings()

        success = restart_app(as_admin=as_admin)

        if success:
            self.destroy()
            sys.exit(0)
        else:
            self._settings.set("input.keyboard_method", "pyautogui")
            self._settings.set("input.mouse_method", "pyautogui")
            messagebox.showwarning(
                "重启失败",
                "无法以管理员身份重启应用，输入方式已恢复为 PyAutoGUI。"
            )
            return False
    
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


def create_app() -> BehaviorTreeApp:
    return BehaviorTreeApp()
