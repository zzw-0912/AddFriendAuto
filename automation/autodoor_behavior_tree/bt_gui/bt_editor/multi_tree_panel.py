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

import customtkinter as ctk
import tkinter as tk
from typing import Dict, Any, Optional, Callable


class MultiTreePanel(ctk.CTkFrame):
    """多行为树管理面板

    在 GUI 中管理多个独立行为树实例的并行运行。
    
    ⚠️ 已废弃：请使用 TabBar + GuiTabManager 替代
    """

    def __init__(self, master, app=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self._dark_colors = self._get_dark_colors()
        self.configure(fg_color=self._dark_colors['bg_secondary'])

        self._tree_manager = None
        self._tree_rows: Dict[str, dict] = {}

        self._create_ui()

    def _get_dark_colors(self):
        try:
            from bt_gui.bt_editor.theme import Theme
            return Theme.get_dark_colors()
        except Exception:
            return {
                'bg_primary': '#1a1a2e',
                'bg_secondary': '#16213e',
                'bg_tertiary': '#0f3460',
                'text_primary': '#e0e0e0',
                'text_secondary': '#a0a0a0',
                'primary': '#6c63ff',
                'primary_hover': '#5a52d5',
                'success': '#4caf50',
                'warning': '#ff9800',
                'danger': '#f44336',
                'border': '#2a2a4a',
            }

    def _create_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent", height=30)
        header.pack(fill="x", padx=5, pady=(5, 0))
        header.pack_propagate(False)

        title = ctk.CTkLabel(
            header,
            text="🌲 多树管理",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self._dark_colors['text_primary']
        )
        title.pack(side="left")

        add_btn = ctk.CTkButton(
            header,
            text="+ 添加",
            font=ctk.CTkFont(size=10),
            width=60,
            height=24,
            fg_color=self._dark_colors['primary'],
            hover_color=self._dark_colors['primary_hover'],
            command=self._on_add_tree
        )
        add_btn.pack(side="right")

        self._tree_list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            height=120
        )
        self._tree_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self._status_label = ctk.CTkLabel(
            self,
            text="尚未添加行为树",
            font=ctk.CTkFont(size=10),
            text_color=self._dark_colors['text_secondary']
        )
        self._status_label.pack(pady=5)

        control_frame = ctk.CTkFrame(self, fg_color="transparent", height=30)
        control_frame.pack(fill="x", padx=5, pady=(0, 5))

        self._start_all_btn = ctk.CTkButton(
            control_frame,
            text="▶ 全部启动",
            font=ctk.CTkFont(size=10),
            width=80,
            height=24,
            fg_color=self._dark_colors['success'],
            hover_color="#43a047",
            command=self._on_start_all
        )
        self._start_all_btn.pack(side="left", padx=2)

        self._stop_all_btn = ctk.CTkButton(
            control_frame,
            text="⏹ 全部停止",
            font=ctk.CTkFont(size=10),
            width=80,
            height=24,
            fg_color=self._dark_colors['danger'],
            hover_color="#e53935",
            command=self._on_stop_all
        )
        self._stop_all_btn.pack(side="left", padx=2)

    def set_tree_manager(self, manager):
        """设置 MultiTreeManager 实例"""
        self._tree_manager = manager
        self._refresh_tree_list()

    def _on_add_tree(self):
        """添加行为树"""
        from tkinter import filedialog, messagebox
        import os

        folder_path = filedialog.askdirectory(title="选择行为树项目文件夹")
        if not folder_path:
            return

        project_json = os.path.join(folder_path, "project.json")
        tree_json = os.path.join(folder_path, "tree.json")
        if not os.path.exists(project_json) and not os.path.exists(tree_json):
            result = messagebox.askyesno(
                "提示",
                "所选文件夹中未找到 project.json 或 tree.json。\n\n是否仍要添加？"
            )
            if not result:
                return

        tree_name = os.path.basename(folder_path)

        if self._tree_manager:
            try:
                from bt_core.serializer import Serializer
                from bt_core.registry import register_all_nodes
                register_all_nodes()

                tree_file = tree_json if os.path.exists(tree_json) else None
                if not tree_file and os.path.exists(project_json):
                    import json
                    with open(project_json, 'r', encoding='utf-8') as f:
                        proj_data = json.load(f)
                    main_tree = proj_data.get("main_tree", "tree.json")
                    candidate = os.path.join(folder_path, main_tree)
                    if os.path.exists(candidate):
                        tree_file = candidate

                if not tree_file:
                    json_files = [f for f in os.listdir(folder_path)
                                  if f.endswith('.json') and f != 'project.json']
                    if json_files:
                        tree_file = os.path.join(folder_path, json_files[0])

                if not tree_file:
                    messagebox.showerror("错误", "未找到行为树文件")
                    return

                root_node, _, _ = Serializer.load_from_file(tree_file)
                instance = self._tree_manager.add_tree(tree_name, root_node)
                self._add_tree_row(tree_name, instance)
                self._update_status()
            except ValueError as e:
                messagebox.showerror("错误", str(e))
            except Exception as e:
                messagebox.showerror("错误", f"添加行为树失败: {e}")

    def _add_tree_row(self, name: str, instance):
        """添加行为树行"""
        row_frame = ctk.CTkFrame(
            self._tree_list_frame,
            fg_color=self._dark_colors['bg_tertiary'],
            corner_radius=6,
            height=36
        )
        row_frame.pack(fill="x", pady=2)
        row_frame.pack_propagate(False)

        name_label = ctk.CTkLabel(
            row_frame,
            text=f"🌲 {name}",
            font=ctk.CTkFont(size=11),
            text_color=self._dark_colors['text_primary'],
            anchor="w"
        )
        name_label.pack(side="left", padx=8)

        status_label = ctk.CTkLabel(
            row_frame,
            text="空闲",
            font=ctk.CTkFont(size=9),
            text_color=self._dark_colors['text_secondary']
        )
        status_label.pack(side="left", padx=4)

        start_btn = ctk.CTkButton(
            row_frame,
            text="▶",
            font=ctk.CTkFont(size=10),
            width=28,
            height=22,
            fg_color=self._dark_colors['success'],
            hover_color="#43a047",
            command=lambda n=name: self._on_start_tree(n)
        )
        start_btn.pack(side="right", padx=2)

        stop_btn = ctk.CTkButton(
            row_frame,
            text="⏹",
            font=ctk.CTkFont(size=10),
            width=28,
            height=22,
            fg_color=self._dark_colors['danger'],
            hover_color="#e53935",
            command=lambda n=name: self._on_stop_tree(n)
        )
        stop_btn.pack(side="right", padx=2)

        remove_btn = ctk.CTkButton(
            row_frame,
            text="✕",
            font=ctk.CTkFont(size=10),
            width=28,
            height=22,
            fg_color=self._dark_colors['bg_secondary'],
            hover_color=self._dark_colors['border'],
            command=lambda n=name: self._on_remove_tree(n)
        )
        remove_btn.pack(side="right", padx=2)

        self._tree_rows[name] = {
            'frame': row_frame,
            'status_label': status_label,
            'instance': instance
        }

    def _on_start_tree(self, name: str):
        """启动指定行为树"""
        if self._tree_manager:
            self._tree_manager.start_tree(name)
            self._update_tree_status(name)

    def _on_stop_tree(self, name: str):
        """停止指定行为树"""
        if self._tree_manager:
            self._tree_manager.stop_tree(name)
            self._update_tree_status(name)

    def _on_remove_tree(self, name: str):
        """移除指定行为树"""
        if self._tree_manager:
            self._tree_manager.remove_tree(name)
            if name in self._tree_rows:
                self._tree_rows[name]['frame'].destroy()
                del self._tree_rows[name]
            self._update_status()

    def _on_start_all(self):
        """启动所有行为树"""
        if self._tree_manager:
            self._tree_manager.start_all()
            self._refresh_tree_list()

    def _on_stop_all(self):
        """停止所有行为树"""
        if self._tree_manager:
            self._tree_manager.stop_all()
            self._refresh_tree_list()

    def _update_tree_status(self, name: str):
        """更新单个树的状态显示"""
        if name in self._tree_rows and self._tree_manager:
            status = self._tree_manager.get_tree_status(name)
            if status:
                status_text = {
                    "idle": "空闲",
                    "running": "运行中",
                    "paused": "已暂停",
                    "stopped": "已停止",
                    "completed": "已完成",
                    "error": "错误"
                }.get(status['status'], status['status'])
                self._tree_rows[name]['status_label'].configure(text=status_text)

    def _refresh_tree_list(self):
        """刷新所有树的状态"""
        for name in self._tree_rows:
            self._update_tree_status(name)
        self._update_status()

    def _update_status(self):
        """更新底部状态"""
        count = len(self._tree_rows)
        if count == 0:
            self._status_label.configure(text="尚未添加行为树")
        else:
            running = sum(1 for r in self._tree_rows.values()
                         if r.get('instance') and r['instance'].status == "running")
            self._status_label.configure(text=f"共 {count} 个行为树，{running} 个运行中")
