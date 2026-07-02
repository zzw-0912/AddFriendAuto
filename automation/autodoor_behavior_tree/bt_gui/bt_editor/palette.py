import customtkinter as ctk
from typing import List, Callable, Optional

from ..theme import Theme
from .constants import build_node_categories, NODE_DISPLAY_NAMES


NODE_CATEGORIES = build_node_categories(Theme.NODE_COLORS)


class NodeButton(ctk.CTkFrame):
    def __init__(self, master, node_type: str, display_name: str, description: str,
                 color_config: dict, on_click: Callable[[str], None],
                 shortcut: str = "", on_shortcut_capture: Callable[[str], None] = None,
                 **kwargs):
        super().__init__(master, **kwargs)
        self.node_type = node_type
        self.on_click = on_click
        self.on_shortcut_capture = on_shortcut_capture
        self.color_config = color_config

        self._dark_colors = Theme.get_dark_colors()
        self.configure(
            fg_color=self._dark_colors['bg_tertiary'],
            corner_radius=Theme.DIMENSIONS['button_corner_radius'],
            cursor="hand2"
        )

        self._orig_shortcut_text = shortcut if shortcut else "设置"
        self._create_ui(display_name, description, shortcut)
        self._bind_events()

    def _create_ui(self, display_name: str, description: str, shortcut: str):
        self.color_indicator = ctk.CTkFrame(
            self, width=4, height=32,
            fg_color=self.color_config['bg'], corner_radius=2
        )
        self.color_indicator.pack(side="left", fill="y", padx=(4, 8), pady=4)

        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(side="left", fill="both", expand=True, pady=4)

        top_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        top_row.pack(fill="x")

        self.name_label = ctk.CTkLabel(
            top_row, text=display_name,
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['text_primary'],
            anchor="w"
        )
        self.name_label.pack(side="left")

        self.shortcut_btn = ctk.CTkButton(
            top_row, text=shortcut if shortcut else "设置",
            font=Theme.get_font('xs'), width=40, height=20,
            fg_color="transparent",
            text_color=self._dark_colors['text_muted'] if shortcut else self._dark_colors.get('text_disabled', '#666666'),
            hover_color=self._dark_colors['bg_secondary'],
            command=lambda: self._do_capture()
        )
        self.shortcut_btn.pack(side="right", padx=(4, 46))

        self.desc_label = ctk.CTkLabel(
            content_frame, text=description,
            font=Theme.get_font('xs'),
            text_color=self._dark_colors['text_muted'],
            anchor="w"
        )
        self.desc_label.pack(fill="x")

    def update_shortcut(self, shortcut: str):
        self._orig_shortcut_text = shortcut if shortcut else "设置"
        if shortcut:
            self.shortcut_btn.configure(text=shortcut, text_color=self._dark_colors['text_muted'])
        else:
            self.shortcut_btn.configure(text="设置", text_color=self._dark_colors.get('text_disabled', '#666666'))

    def set_capturing(self, capturing: bool):
        if capturing:
            self.shortcut_btn.configure(text="按快捷键…", text_color=self._dark_colors['warning'],
                                        fg_color=self._dark_colors['bg_secondary'])
        else:
            self.shortcut_btn.configure(fg_color="transparent")
            self.shortcut_btn.configure(text=self._orig_shortcut_text)

    def _bind_events(self):
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._do_add_node)
        self.name_label.bind("<Button-1>", self._do_add_node)
        self.desc_label.bind("<Button-1>", self._do_add_node)

    def _on_enter(self, event):
        self.configure(fg_color=self._dark_colors['border'])

    def _on_leave(self, event):
        self.configure(fg_color=self._dark_colors['bg_tertiary'])

    def _do_add_node(self, event=None):
        if self.on_click:
            self.on_click(self.node_type)

    def _do_capture(self, event=None):
        if self.on_shortcut_capture:
            self.on_shortcut_capture(self.node_type)


class CategorySection(ctk.CTkFrame):
    def __init__(self, master, category_name: str, category_data: dict,
                 on_node_click: Callable[[str], None],
                 node_shortcuts: dict = None,
                 on_shortcut_capture: Callable[[str], None] = None,
                 **kwargs):
        super().__init__(master, **kwargs)
        self.category_name = category_name
        self.category_data = category_data
        self.on_node_click = on_node_click
        self.on_shortcut_capture = on_shortcut_capture
        self.node_shortcuts = node_shortcuts or {}
        self._is_expanded = True

        self._dark_colors = Theme.get_dark_colors()
        self.configure(fg_color="transparent")

        self._create_ui()

    def _create_ui(self):
        self.header = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        self.header.pack(fill="x")
        self.header.bind("<Button-1>", self._toggle_expand)

        self.expand_icon = ctk.CTkLabel(
            self.header, text="▼" if self._is_expanded else "▶",
            font=Theme.get_font('xs'),
            text_color=self._dark_colors['text_muted'], width=16
        )
        self.expand_icon.pack(side="left")
        self.expand_icon.bind("<Button-1>", self._toggle_expand)

        color_config = self.category_data['color']
        self.category_indicator = ctk.CTkFrame(
            self.header, width=12, height=12,
            fg_color=color_config['bg'], corner_radius=3
        )
        self.category_indicator.pack(side="left", padx=(4, 8))
        self.category_indicator.bind("<Button-1>", self._toggle_expand)

        self.category_label = ctk.CTkLabel(
            self.header, text=self.category_name,
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['text_primary']
        )
        self.category_label.pack(side="left")
        self.category_label.bind("<Button-1>", self._toggle_expand)

        self.nodes_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nodes_frame.pack(fill="x", pady=(Theme.DIMENSIONS['spacing_xs'], 0))

        self._buttons = []
        for node_type, display_name, description in self.category_data['nodes']:
            btn = NodeButton(
                self.nodes_frame,
                node_type=node_type,
                display_name=display_name,
                description=description,
                color_config=color_config,
                on_click=self.on_node_click,
                shortcut=self.node_shortcuts.get(node_type, ""),
                on_shortcut_capture=self.on_shortcut_capture
            )
            btn.pack(fill="x", pady=Theme.DIMENSIONS['spacing_xs'])
            self._buttons.append(btn)

    def update_shortcut(self, node_type: str, shortcut: str):
        for btn in self._buttons:
            if btn.node_type == node_type:
                btn.update_shortcut(shortcut)
                break

    def set_node_capturing(self, node_type: str, capturing: bool):
        for btn in self._buttons:
            btn.set_capturing(btn.node_type == node_type and capturing)

    def _toggle_expand(self, event=None):
        self._is_expanded = not self._is_expanded
        self.expand_icon.configure(text="▼" if self._is_expanded else "▶")
        if self._is_expanded:
            self.nodes_frame.pack(fill="x", pady=(Theme.DIMENSIONS['spacing_xs'], 0))
        else:
            self.nodes_frame.pack_forget()


class NodePalette(ctk.CTkFrame):
    def __init__(self, master, on_node_add: Optional[Callable[[str], None]] = None,
                 on_shortcut_change: Optional[Callable[[], None]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)
        self.on_node_add = on_node_add
        self.on_shortcut_change = on_shortcut_change
        self._settings_listener = None
        self._settings_timeout = None
        self._capturing_node_type = None
        self._capturing_hotkey_mgr = None
        self._capturing_was_running = False

        self._dark_colors = Theme.get_dark_colors()
        self.configure(
            fg_color=self._dark_colors['sidebar_bg'],
            corner_radius=0,
            width=Theme.DIMENSIONS['sidebar_width']
        )

        from config.settings_manager import SettingsManager
        self._settings = SettingsManager.get_instance()
        self._node_shortcuts = dict(self._settings.get("node_shortcuts", {}))

        self._create_ui()

    def _create_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=Theme.DIMENSIONS['spacing_md'], pady=Theme.DIMENSIONS['spacing_md'])

        title_label = ctk.CTkLabel(
            header_frame, text="节点面板",
            font=Theme.get_font('lg'),
            text_color=self._dark_colors['text_primary']
        )
        title_label.pack(side="left")

        search_frame = ctk.CTkFrame(self, fg_color=self._dark_colors['bg_tertiary'], corner_radius=6)
        search_frame.pack(fill="x", padx=Theme.DIMENSIONS['spacing_md'], pady=(0, Theme.DIMENSIONS['spacing_md']))

        self.search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="搜索节点...",
            font=Theme.get_font('sm'), height=Theme.DIMENSIONS['input_height'],
            fg_color="transparent", border_width=0,
            text_color=self._dark_colors['text_primary'],
            placeholder_text_color=self._dark_colors['text_muted']
        )
        self.search_entry.pack(fill="x", padx=Theme.DIMENSIONS['spacing_sm'], pady=Theme.DIMENSIONS['spacing_xs'])
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # ── 底部快捷键捕获栏（默认隐藏） ──
        self._capture_bar = ctk.CTkFrame(self, fg_color=self._dark_colors['bg_tertiary'], corner_radius=0)
        self._capture_label = ctk.CTkLabel(
            self._capture_bar, text="",
            font=Theme.get_font('sm'),
            text_color=self._dark_colors['warning']
        )
        self._capture_label.pack(side="left", padx=Theme.DIMENSIONS['spacing_md'], pady=Theme.DIMENSIONS['spacing_sm'])
        self._cancel_btn = ctk.CTkButton(
            self._capture_bar, text="取消", width=50, height=24,
            font=Theme.get_font('xs'),
            fg_color=self._dark_colors['bg_secondary'],
            hover_color=self._dark_colors['border'],
            text_color=self._dark_colors['text_primary'],
            command=self._cancel_capture
        )
        self._clear_btn = ctk.CTkButton(
            self._capture_bar, text="清除", width=50, height=24,
            font=Theme.get_font('xs'),
            fg_color=self._dark_colors['error'],
            hover_color=self._dark_colors['border'],
            text_color=self._dark_colors['text_primary'],
            command=self._clear_shortcut
        )

        self.content_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=self._dark_colors['bg_tertiary'],
            scrollbar_button_hover_color=self._dark_colors['border']
        )
        self.content_frame.pack(fill="both", expand=True, padx=Theme.DIMENSIONS['spacing_md'])

        self.category_sections: List[CategorySection] = []
        for category_name, category_data in NODE_CATEGORIES.items():
            section = CategorySection(
                self.content_frame,
                category_name=category_name,
                category_data=category_data,
                on_node_click=self._on_node_click,
                node_shortcuts=self._node_shortcuts,
                on_shortcut_capture=self._on_shortcut_capture
            )
            section.pack(fill="x", pady=(0, Theme.DIMENSIONS['spacing_md']))
            self.category_sections.append(section)

    def _on_search(self, event):
        search_text = self.search_entry.get().lower()
        for section in self.category_sections:
            has_match = False
            for child in section.nodes_frame.winfo_children():
                if isinstance(child, NodeButton):
                    node_data = section.category_data['nodes']
                    node_info = next((n for n in node_data if n[0] == child.node_type), None)
                    if node_info:
                        display_name = node_info[1].lower()
                        description = node_info[2].lower()
                        if search_text in display_name or search_text in description or search_text == "":
                            child.pack(fill="x", pady=Theme.DIMENSIONS['spacing_xs'])
                            has_match = True
                        else:
                            child.pack_forget()
            if search_text == "":
                section.pack(fill="x", pady=(0, Theme.DIMENSIONS['spacing_md']))
            elif has_match:
                section.pack(fill="x", pady=(0, Theme.DIMENSIONS['spacing_md']))
                if not section._is_expanded:
                    section._toggle_expand()
            else:
                section.pack_forget()

    def _on_node_click(self, node_type: str):
        if self.on_node_add:
            self.on_node_add(node_type)

    def _on_shortcut_capture(self, node_type: str):
        self._capturing_node_type = node_type
        from bt_utils.global_hotkey import GlobalHotkeyManager
        self._capturing_hotkey_mgr = GlobalHotkeyManager.get_instance()
        self._capturing_was_running = self._capturing_hotkey_mgr.is_running()
        if self._capturing_was_running:
            self._capturing_hotkey_mgr.stop()

        from pynput import keyboard
        from bt_utils.key_name_resolver import resolve_key_name

        node_display = NODE_DISPLAY_NAMES.get(node_type, node_type)
        self._show_capture_bar(node_display)

        for section in self.category_sections:
            section.set_node_capturing(node_type, True)

        _pressed_modifiers = set()
        _modifier_names = {
            'ctrl', 'ctrl_l', 'ctrl_r', 'ctrlleft', 'ctrlright',
            'alt', 'alt_l', 'alt_r', 'altleft', 'altright',
            'shift', 'shift_l', 'shift_r', 'shiftleft', 'shiftright',
            'cmd', 'cmd_l', 'cmd_r', 'win', 'win_l', 'win_r'
        }

        def _normalize_modifier(name):
            if name in ('ctrl', 'ctrl_l', 'ctrl_r', 'ctrlleft', 'ctrlright'):
                return 'ctrl'
            elif name in ('alt', 'alt_l', 'alt_r', 'altleft', 'altright'):
                return 'alt'
            elif name in ('shift', 'shift_l', 'shift_r', 'shiftleft', 'shiftright'):
                return 'shift'
            elif name in ('cmd', 'cmd_l', 'cmd_r', 'win', 'win_l', 'win_r'):
                return 'cmd'
            return None

        def on_press(key):
            key_name = resolve_key_name(key)
            if not key_name:
                return
            if key_name in _modifier_names:
                mod = _normalize_modifier(key_name)
                if mod:
                    _pressed_modifiers.add(mod)
                return
            parts = sorted(_pressed_modifiers) + [key_name]
            display_name = "+".join(p.upper() if len(p) > 1 else p for p in parts)
            try:
                self.after(0, lambda: self._apply_captured_key(node_type, display_name,
                                                               self._capturing_hotkey_mgr,
                                                               self._capturing_was_running))
            except Exception:
                pass
            return False

        def on_release(key):
            key_name = resolve_key_name(key)
            if key_name and key_name in _modifier_names:
                mod = _normalize_modifier(key_name)
                if mod:
                    _pressed_modifiers.discard(mod)

        self._settings_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._settings_listener.start()

        def reset_listening():
            self._stop_listener()
            self._clear_all_capturing()
            self._hide_capture_bar()
            if self._capturing_was_running:
                self._capturing_hotkey_mgr.start()

        self._settings_timeout = self.after(10000, reset_listening)

    def _show_capture_bar(self, node_display: str):
        self._capture_label.configure(text=f"为「{node_display}」设置快捷键，请按键…")
        self._capture_bar.pack(fill="x", side="bottom")
        self._clear_btn.pack(side="right", padx=(Theme.DIMENSIONS['spacing_sm'], Theme.DIMENSIONS['spacing_md']), pady=Theme.DIMENSIONS['spacing_sm'])
        self._cancel_btn.pack(side="right", padx=(0, 0), pady=Theme.DIMENSIONS['spacing_sm'])

    def _hide_capture_bar(self):
        self._clear_btn.pack_forget()
        self._cancel_btn.pack_forget()
        self._capture_bar.pack_forget()

    def _clear_all_capturing(self):
        for section in self.category_sections:
            section.set_node_capturing("", False)

    def _cancel_capture(self):
        self._stop_listener()
        self._clear_all_capturing()
        self._hide_capture_bar()
        if self._capturing_was_running:
            self._capturing_hotkey_mgr.start()

    def _clear_shortcut(self):
        self._stop_listener()
        self._hide_capture_bar()
        self._clear_all_capturing()

        node_type = self._capturing_node_type
        if node_type in self._node_shortcuts:
            del self._node_shortcuts[node_type]
        self._settings.set("node_shortcuts", dict(self._node_shortcuts), auto_save=True)

        for section in self.category_sections:
            section.update_shortcut(node_type, "")

        if self.on_shortcut_change:
            try:
                self.on_shortcut_change()
            except Exception:
                pass

        if self._capturing_was_running:
            self._capturing_hotkey_mgr.start()

    def _check_conflict(self, new_shortcut: str, exclude_node_type: str) -> Optional[str]:
        for nt, sk in self._node_shortcuts.items():
            if nt != exclude_node_type and sk and sk.lower() == new_shortcut.lower():
                dn = NODE_DISPLAY_NAMES.get(nt, nt)
                return f"节点「{dn}」已占用快捷键 {new_shortcut}"

        from config.settings_manager import SettingsManager
        sm = SettingsManager.get_instance()
        reserved = [
            ("shortcuts.start", "开始运行"),
            ("shortcuts.stop", "停止运行"),
            ("shortcuts.record", "录制按钮"),
            ("shortcuts.toggle_disable", "禁用节点"),
            ("shortcuts.auto_arrange", "自动整理"),
            ("shortcuts.fit_view", "适应窗口"),
        ]
        for key, label in reserved:
            val = sm.get(key, "")
            if val and val.lower() == new_shortcut.lower():
                return f"全局快捷键「{label}」({val}) 与 {new_shortcut} 冲突"

        tab_sc = sm.get("shortcuts.tab_shortcuts", [])
        for ts in tab_sc:
            hk = ts.get("hotkey", "")
            if hk and hk.lower() == new_shortcut.lower():
                return f"单树快捷键 {hk} 与 {new_shortcut} 冲突"
        return None

    def _apply_captured_key(self, node_type: str, key_name: str,
                            hotkey_mgr, was_running: bool):
        self._stop_listener()
        self._hide_capture_bar()
        self._clear_all_capturing()

        node_display = NODE_DISPLAY_NAMES.get(node_type, node_type)

        conflict = self._check_conflict(key_name, node_type)
        if conflict:
            from tkinter import messagebox
            if not messagebox.askyesno("快捷键冲突", f"{conflict}\n\n是否覆盖？"):
                if was_running:
                    hotkey_mgr.start()
                return

        self._node_shortcuts[node_type] = key_name
        self._settings.set("node_shortcuts", dict(self._node_shortcuts), auto_save=True)

        for section in self.category_sections:
            section.update_shortcut(node_type, key_name)

        if self.on_shortcut_change:
            try:
                self.on_shortcut_change()
            except Exception:
                pass

        if was_running:
            hotkey_mgr.start()

    def _stop_listener(self):
        if self._settings_listener:
            try:
                self._settings_listener.stop()
            except Exception:
                pass
            self._settings_listener = None
        if self._settings_timeout:
            self.after_cancel(self._settings_timeout)
            self._settings_timeout = None

    def get_node_shortcuts(self) -> dict:
        return dict(self._node_shortcuts)
