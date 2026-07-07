import tkinter as tk
import customtkinter as ctk
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
import math

from ..theme import Theme
from .constants import NODE_DISPLAY_NAMES
from .node_item import NodeItem, NodeExecutionStatus, SubtreeNodeItem, GroupNodeItem
from bt_utils.log_manager import LogManager


class BehaviorTreeCanvas(ctk.CTkFrame):
    def __init__(self, master, app, on_node_select: Optional[Callable] = None,
                 on_node_move: Optional[Callable] = None,
                 on_nodes_move: Optional[Callable] = None,
                 on_connection_add: Optional[Callable] = None,
                 on_node_deselect: Optional[Callable] = None,
                 property_panel: Optional[Any] = None,
                 **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.property_panel = property_panel
        
        self._node_counter = 0
        
        self.nodes: Dict[str, NodeItem] = {}
        self.connections: List[tuple] = []
        self.connection_items: Dict[tuple, int] = {}
        self.connection_order_items: Dict[tuple, int] = {}  # 连线序号文本项索引
        # node→connections反向索引，用于按需重绘关联连线
        self._node_connections_map: Dict[str, List[tuple]] = {}
        self.selected_node: Optional[str] = None
        self.selected_nodes: List[str] = []
        self.selected_connection: Optional[tuple] = None
        self.selected_connections: List[tuple] = []
        self.on_node_select = on_node_select
        self.on_node_move = on_node_move
        self.on_nodes_move = on_nodes_move
        self.on_connection_add = on_connection_add
        self.on_node_deselect = on_node_deselect
        
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        self.grid_enabled = True
        self.grid_size = 20
        
        self._dirty_nodes: Set[str] = set()
        self._dirty_connections: Set[Tuple[str, str]] = set()
        self._redraw_scheduled = False
        self._redraw_all_flag = False
        
        self._drag_throttle_timer = None
        self._drag_pending_redraw = False
        self._drag_throttle_ms = 16
        
        self._dragging = False
        self._drag_node: Optional[str] = None
        self._drag_start = (0, 0)
        self._drag_start_pos = (0, 0)
        self._drag_start_positions: Dict[str, tuple] = {}
        self._click_pos: Optional[tuple] = None
        self._click_node_id: Optional[str] = None
        self._drag_threshold = 5
        
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0, 0)
        
        self._right_panning = False
        self._right_pan_start = (0, 0)
        self._right_pan_start_offset = (0, 0)
        self._right_pan_moved = False
        self._right_pan_threshold = 5
        self._right_click_canvas_pos = None
        
        self._selecting = False
        self._selection_start = (0, 0)
        self._selection_box = None
        self._selection_append = False
        
        self._connecting = False
        self._connect_start_node: Optional[str] = None
        self._temp_line = None
        
        self._dark_colors = Theme.get_dark_colors()
        self.configure(fg_color=self._dark_colors['canvas_bg'], corner_radius=0)

        # Canvas虚拟化：仅渲染视口内可见节点
        self._visible_node_ids: Set[str] = set()
        self._virtualization_enabled = True
        self._group_contents: Dict[str, set] = {}   # 组ID -> 打包节点ID集合
        self._collapsed_descendants: Set[str] = set()  # 所有被折叠的节点ID
        self._group_proxy_connections: Dict[str, list] = {}  # 组ID -> [临时线ID列表]

        self._create_canvas()
        self._bind_events()
    
    def _create_canvas(self):
        self.canvas = tk.Canvas(
            self,
            bg=self._dark_colors['canvas_bg'],
            highlightthickness=0,
            cursor="arrow"
        )
        self.canvas.pack(fill="both", expand=True)
        
        self._draw_grid()
    
    def _draw_grid(self):
        if not self.grid_enabled:
            self.canvas.delete("grid")
            return

        grid_color = self._dark_colors['canvas_grid']

        self.canvas.delete("grid")

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1:
            width = 800
        if height <= 1:
            height = 600

        offset_x = int(self.pan_x) % self.grid_size
        offset_y = int(self.pan_y) % self.grid_size

        for x in range(-self.grid_size + offset_x, width + self.grid_size, self.grid_size):
            self.canvas.create_line(
                x, 0, x, height,
                fill=grid_color,
                tags="grid"
            )

        for y in range(-self.grid_size + offset_y, height + self.grid_size, self.grid_size):
            self.canvas.create_line(
                0, y, width, y,
                fill=grid_color,
                tags="grid"
            )

        self.canvas.tag_lower("grid")

    def set_grid_enabled(self, enabled: bool) -> None:
        self.grid_enabled = enabled
        self._draw_grid()

    def set_grid_size(self, size: int) -> None:
        self.grid_size = max(10, min(100, size))
        self._draw_grid()

    def get_grid_config(self) -> dict:
        return {
            "enabled": self.grid_enabled,
            "size": self.grid_size
        }
    
    def _bind_events(self):
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-3>", self._on_right_click_menu)
        self.canvas.bind("<Button-2>", self._on_middle_click)
        self.canvas.bind("<B2-Motion>", self._on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_middle_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Control-Button-1>", self._on_ctrl_click)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<FocusIn>", self._on_canvas_focus_in)
        self.canvas.bind("<FocusOut>", self._on_canvas_focus_out)
        self.canvas.bind("<KeyPress>", self._on_key_press)
    
    def _on_resize(self, event):
        self._draw_grid()
        # Canvas尺寸变化时更新可见节点（虚拟化模式下视口范围改变）
        if self._virtualization_enabled and self.nodes:
            self._update_visible_nodes()
    
    def _on_canvas_focus_in(self, event):
        pass
    
    def _on_canvas_focus_out(self, event):
        pass
    
    def _on_motion(self, event):
        x = (self.canvas.canvasx(event.x) - self.pan_x) / self.zoom
        y = (self.canvas.canvasy(event.y) - self.pan_y) / self.zoom
        
        for node_id, node in self.nodes.items():
            if node.is_on_output_port(x, y) or node.is_on_input_port(x, y):
                self.canvas.config(cursor="hand2")
                return
        
        self.canvas.config(cursor="arrow")
    
    def _on_click(self, event):
        if self.property_panel:
            self.property_panel.force_save_current_field()
        
        self.canvas.focus_set()
        
        x = (self.canvas.canvasx(event.x) - self.pan_x) / self.zoom
        y = (self.canvas.canvasy(event.y) - self.pan_y) / self.zoom
        
        for node_id, node in self.nodes.items():
            if node.is_on_output_port(x, y):
                self._start_connecting(node_id, x, y)
                return
            
            if node.is_on_input_port(x, y):
                return
            
            if node.contains_point(x, y):
                if node.node_type == "SubtreeNode" and isinstance(node, SubtreeNodeItem):
                    if node.is_on_toggle_btn(x, y):
                        node.toggle_preview()
                        return
                if node.node_type == "GroupNode" and isinstance(node, GroupNodeItem):
                    if node.is_on_toggle_btn(x, y):
                        node.toggle_collapse()
                        return
                self._click_pos = (x, y)
                self._click_node_id = node_id
                if node_id not in self.selected_nodes:
                    self._select_node(node_id, trigger_callback=False)
                return
        
        clicked_connection = self._find_connection_at(x, y)
        if clicked_connection:
            self._select_connection(clicked_connection)
            return
        
        self._deselect_all()
        self._selecting = True
        self._selection_start = (x, y)
        self._selection_append = False
    
    def _on_ctrl_click(self, event):
        x = (self.canvas.canvasx(event.x) - self.pan_x) / self.zoom
        y = (self.canvas.canvasy(event.y) - self.pan_y) / self.zoom
        
        for node_id, node in self.nodes.items():
            if node.contains_point(x, y):
                if node_id in self.selected_nodes:
                    self.selected_nodes.remove(node_id)
                    node.set_selected(False)
                else:
                    self.selected_nodes.append(node_id)
                    node.set_selected(True)
                return
        
        clicked_connection = self._find_connection_at(x, y)
        if clicked_connection:
            if clicked_connection in self.selected_connections:
                self.selected_connections.remove(clicked_connection)
                self._update_connection_style(clicked_connection, selected=False)
            else:
                self.selected_connections.append(clicked_connection)
                self._update_connection_style(clicked_connection, selected=True)
            return
    
    def _start_connecting(self, node_id: str, x: float, y: float):
        self._connecting = True
        self._connect_start_node = node_id
        
        node = self.nodes[node_id]
        start_x, start_y = node.get_output_port_pos()
        
        self._temp_line = self.canvas.create_line(
            start_x * self.zoom + self.pan_x, start_y * self.zoom + self.pan_y,
            x * self.zoom + self.pan_x, y * self.zoom + self.pan_y,
            fill=self._dark_colors.get('connection_line', '#666666'),
            width=2,
            dash=(5, 3),
            arrow=tk.LAST,
            tags="temp_connection"
        )
        
        node.highlight_port("output", True)
        self.canvas.config(cursor="crosshair")
    
    def _update_connecting_line(self, x: float, y: float):
        if self._connecting and self._temp_line and self._connect_start_node:
            node = self.nodes[self._connect_start_node]
            start_x, start_y = node.get_output_port_pos()
            
            self.canvas.coords(self._temp_line, 
                start_x * self.zoom + self.pan_x, start_y * self.zoom + self.pan_y,
                x * self.zoom + self.pan_x, y * self.zoom + self.pan_y)
    
    def _finish_connecting(self, target_node_id: str):
        if self._connect_start_node and self._connect_start_node != target_node_id:
            self.add_connection(self._connect_start_node, target_node_id)
            if self.on_connection_add:
                self.on_connection_add(self._connect_start_node, target_node_id)
        
        self._cancel_connecting()
    
    def _cancel_connecting(self):
        if self._temp_line:
            self.canvas.delete(self._temp_line)
            self._temp_line = None
        
        if self._connect_start_node and self._connect_start_node in self.nodes:
            node = self.nodes[self._connect_start_node]
            node.highlight_port("output", False)
        
        self._connecting = False
        self._connect_start_node = None
        self.canvas.config(cursor="arrow")
    
    def _on_drag(self, event):
        x = (self.canvas.canvasx(event.x) - self.pan_x) / self.zoom
        y = (self.canvas.canvasy(event.y) - self.pan_y) / self.zoom
        
        if self._connecting:
            self._update_connecting_line(x, y)
            
            for node_id, node in self.nodes.items():
                if node_id != self._connect_start_node:
                    # 跳过不可见节点，避免无意义的Canvas操作
                    if self._virtualization_enabled and not node._canvas_items_exist:
                        continue
                    if node.is_on_input_port(x, y):
                        node.highlight_port("input", True)
                    else:
                        node.highlight_port("input", False)
            return
        
        if self._selecting:
            self._update_selection_box(x, y)
            return
        
        if not self._dragging and self._click_pos and self._click_node_id:
            mouse_pressed = event.state & 0x0100
            if not mouse_pressed:
                self._click_pos = None
                self._click_node_id = None
                return
            
            dx = x - self._click_pos[0]
            dy = y - self._click_pos[1]
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance >= self._drag_threshold:
                if self._click_node_id in self.nodes and self._click_node_id in self.selected_nodes:
                    self._dragging = True
                    self._drag_node = self._click_node_id
                    node = self.nodes[self._click_node_id]
                    self._drag_start = (self._click_pos[0] - node.x, self._click_pos[1] - node.y)
                    self._drag_start_pos = (node.x, node.y)
                    self._drag_start_positions = {}
                    for nid in self.selected_nodes:
                        if nid in self.nodes:
                            n = self.nodes[nid]
                            self._drag_start_positions[nid] = (n.x, n.y)
        
        if self._dragging and self._drag_node:
            mouse_pressed = event.state & 0x0100
            if not mouse_pressed:
                self._dragging = False
                self._drag_node = None
                self._click_pos = None
                self._click_node_id = None
                return
            dx = x - self._drag_start[0] - self._drag_start_pos[0]
            dy = y - self._drag_start[1] - self._drag_start_pos[1]
            
            if len(self.selected_nodes) > 1 and self._drag_start_positions:
                for node_id in self.selected_nodes:
                    if node_id in self.nodes and node_id in self._drag_start_positions:
                        start_x, start_y = self._drag_start_positions[node_id]
                        self.nodes[node_id].move_to(start_x + dx, start_y + dy)
            else:
                node = self.nodes[self._drag_node]
                node.move_to(x - self._drag_start[0], y - self._drag_start[1])
            
            self._schedule_drag_redraw()
            return
        
        if self._panning:
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self.pan_x = self._pan_start_offset[0] + dx
            self.pan_y = self._pan_start_offset[1] + dy
            self._schedule_drag_redraw()
            self._draw_grid()
    
    def _on_release(self, event):
        x = (self.canvas.canvasx(event.x) - self.pan_x) / self.zoom
        y = (self.canvas.canvasy(event.y) - self.pan_y) / self.zoom
        
        if self._connecting:
            for node_id, node in self.nodes.items():
                if node_id != self._connect_start_node and node.is_on_input_port(x, y):
                    self._finish_connecting(node_id)
                    return
            
            self._cancel_connecting()
            return
        
        if self._selecting:
            self._finish_selection(x, y)
            return
        
        if self._dragging and self._drag_node:
            if len(self.selected_nodes) > 1 and self._drag_start_positions and self.on_nodes_move:
                old_positions = {}
                new_positions = {}
                for node_id in self.selected_nodes:
                    if node_id in self.nodes and node_id in self._drag_start_positions:
                        node = self.nodes[node_id]
                        old_positions[node_id] = self._drag_start_positions[node_id]
                        new_positions[node_id] = (node.x, node.y)
                
                self.on_nodes_move(old_positions, new_positions)
            elif self.on_node_move:
                node = self.nodes[self._drag_node]
                self.on_node_move(
                    self._drag_node,
                    self._drag_start_pos[0], self._drag_start_pos[1],
                    node.x, node.y
                )

            selected_set = set(self.selected_nodes)
            for node_id in list(self.selected_nodes):
                if node_id not in self.nodes:
                    continue
                gn = self.nodes[node_id]
                if not (isinstance(gn, GroupNodeItem) and gn._collapsed):
                    continue
                old_x, old_y = self._drag_start_positions.get(node_id, self._drag_start_pos)
                dx = gn.x - old_x
                dy = gn.y - old_y
                if dx != 0 or dy != 0:
                    for child_id in self._group_contents.get(node_id, set()):
                        if child_id in selected_set:
                            continue
                        if child_id in self.nodes:
                            child = self.nodes[child_id]
                            child.x += dx
                            child.y += dy
                            if child._canvas_items_exist:
                                self.canvas.move(child.node_id, dx * self.zoom, dy * self.zoom)
        
        if not self._dragging and self._click_node_id:
            if self._click_node_id in self.nodes and self.on_node_select:
                node = self.nodes[self._click_node_id]
                self.on_node_select(self._click_node_id, node.node_type)
        
        self._dragging = False
        self._drag_node = None
        self._click_pos = None
        self._click_node_id = None
        self._panning = False
    
    def _on_scroll(self, event):
        mouse_x = event.x
        mouse_y = event.y
        
        canvas_x_before = (mouse_x - self.pan_x) / self.zoom
        canvas_y_before = (mouse_y - self.pan_y) / self.zoom
        
        if event.delta > 0:
            new_zoom = self.zoom * 1.1
        else:
            new_zoom = self.zoom / 1.1
        
        new_zoom = max(0.25, min(4.0, new_zoom))
        
        self.pan_x = mouse_x - canvas_x_before * new_zoom
        self.pan_y = mouse_y - canvas_y_before * new_zoom
        self.zoom = new_zoom
        
        self._redraw_all()
        self._draw_grid()
    
    def _on_right_click_menu(self, event):
        x = (self.canvas.canvasx(event.x) - self.pan_x) / self.zoom
        y = (self.canvas.canvasy(event.y) - self.pan_y) / self.zoom
        self._right_click_canvas_pos = (x, y)

        clicked = self.canvas.find_closest(event.x, event.y)
        if clicked:
            tags = self.canvas.gettags(clicked[0])
            node_id = None
            for tag in tags:
                if tag.startswith("node:"):
                    node_id = tag[5:]
                    break
            if node_id and node_id in self.nodes:
                self._on_click(event)
        self._show_context_menu(event)

    def _on_middle_click(self, event):
        self._right_panning = True
        self._right_pan_start = (event.x, event.y)
        self._right_pan_start_offset = (self.pan_x, self.pan_y)
        self._right_pan_moved = False
    
    def _on_middle_drag(self, event):
        if not self._right_panning:
            return
        
        dx = event.x - self._right_pan_start[0]
        dy = event.y - self._right_pan_start[1]
        distance = math.sqrt(dx*dx + dy*dy)
        
        if not self._right_pan_moved and distance >= self._right_pan_threshold:
            self._right_pan_moved = True
        
        if self._right_pan_moved:
            self.pan_x = self._right_pan_start_offset[0] + dx
            self.pan_y = self._right_pan_start_offset[1] + dy
            self._schedule_drag_redraw()
            self._draw_grid()
    
    def _on_middle_release(self, event):
        if not self._right_panning:
            return
        self._right_panning = False
    
    def _show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg=self._dark_colors['bg_secondary'], 
                       fg=self._dark_colors['text_primary'],
                       activebackground=self._dark_colors['bg_tertiary'])
        
        if self.selected_nodes:
            menu.add_command(label=f"删除 {len(self.selected_nodes)} 个节点", 
                           command=lambda: self._delete_selected_nodes())
            menu.add_command(label=f"复制 {len(self.selected_nodes)} 个节点", 
                           command=self._copy_selected_nodes_to_clipboard)
            menu.add_separator()
            menu.add_command(label="禁用选中节点" if any(self.nodes[nid].enabled for nid in self.selected_nodes) else "启用选中节点",
                           command=lambda: self._toggle_selected_nodes_enabled())
            menu.add_separator()
            menu.add_command(label="打包成组",
                           command=self._wrap_in_group)
        elif self.selected_node:
            menu.add_command(label="删除节点", command=lambda: self.remove_node(self.selected_node))
            menu.add_command(label="复制节点", command=lambda: self._copy_node(self.selected_node))
            menu.add_separator()
            node = self.nodes.get(self.selected_node)
            if node:
                if node.enabled:
                    menu.add_command(label="禁用节点", command=lambda: self._toggle_node_enabled(self.selected_node))
                else:
                    menu.add_command(label="启用节点", command=lambda: self._toggle_node_enabled(self.selected_node))
        elif self.selected_connections:
            if len(self.selected_connections) > 1:
                menu.add_command(label=f"删除 {len(self.selected_connections)} 条连线", 
                               command=self._delete_selected_connections)
            else:
                menu.add_command(label="删除连线", command=self.remove_selected_connection)
        elif self.selected_connection:
            menu.add_command(label="删除连线", command=self.remove_selected_connection)
        else:
            editor = self._get_editor()
            if editor and editor._clipboard_data:
                paste_pos = getattr(self, '_right_click_canvas_pos', None)
                menu.add_command(label="粘贴节点", 
                               command=lambda: self._paste_at_position(paste_pos))
            if self.nodes:
                menu.add_separator()
                menu.add_command(label="自动整理 (X)", command=self.auto_arrange)
        
        if menu.index("end") is not None:
            menu.post(event.x_root, event.y_root)
    
    def _toggle_node_enabled(self, node_id: str):
        node = self.nodes.get(node_id)
        if not node:
            return
        new_enabled = not node.enabled
        node.update_config("enabled", new_enabled)
        editor = self._get_editor()
        if editor:
            editor._on_property_change(node_id, "enabled", new_enabled)

    def _toggle_selected_nodes_enabled(self):
        if not self.selected_nodes:
            return
        any_enabled = any(self.nodes[nid].enabled for nid in self.selected_nodes if nid in self.nodes)
        new_enabled = False if any_enabled else True
        editor = self._get_editor()
        for node_id in self.selected_nodes:
            node = self.nodes.get(node_id)
            if node:
                node.update_config("enabled", new_enabled)
                if editor:
                    editor._on_property_change(node_id, "enabled", new_enabled)

    def _on_key_press(self, event):
        from config.settings_manager import SettingsManager
        try:
            settings_mgr = SettingsManager.get_instance()
            toggle_key = settings_mgr.get("shortcuts.toggle_disable", "Space")
            if event.keysym.lower() == toggle_key.lower():
                if self.selected_nodes:
                    self._toggle_selected_nodes_enabled()
                elif self.selected_node:
                    self._toggle_node_enabled(self.selected_node)
            
            arrange_key = settings_mgr.get("shortcuts.auto_arrange", "X")
            if event.char in (arrange_key.lower(), arrange_key.upper()):
                self.auto_arrange()
            
            fit_key = settings_mgr.get("shortcuts.fit_view", "Z")
            if event.char in (fit_key.lower(), fit_key.upper()):
                self.reset_view()
        except Exception:
            pass

    def _get_editor(self):
        try:
            app = self.canvas.winfo_toplevel()
            if hasattr(app, 'behavior_tree'):
                return app.behavior_tree
        except Exception:
            pass
        return None
    
    def _paste_at_position(self, pos=None):
        editor = self._get_editor()
        if not editor or not editor._clipboard_data:
            return
        if pos:
            editor._paste_selected(paste_x=pos[0], paste_y=pos[1])
        else:
            editor._paste_selected()
    
    def _on_double_click(self, event):
        x = (self.canvas.canvasx(event.x) - self.pan_x) / self.zoom
        y = (self.canvas.canvasy(event.y) - self.pan_y) / self.zoom
        
        for node_id, node in self.nodes.items():
            if node.contains_point(x, y):
                if node.node_type == "SubtreeNode":
                    from .node_item import SubtreeNodeItem
                    if isinstance(node, SubtreeNodeItem):
                        node.toggle_preview()
                        return
                self._edit_node_properties(node_id)
                return
    
    def _select_node(self, node_id: str, trigger_callback: bool = True):
        self._deselect_all()
        self.selected_node = node_id
        self.selected_nodes = [node_id]
        node = self.nodes[node_id]
        node.set_selected(True)
        
        if trigger_callback and self.on_node_select:
            self.on_node_select(node_id, node.node_type)
    
    def _select_node_add(self, node_id: str):
        if node_id not in self.nodes:
            return
        
        if node_id not in self.selected_nodes:
            self.selected_nodes.append(node_id)
            self.nodes[node_id].set_selected(True)
        
        if self.selected_nodes:
            self.selected_node = self.selected_nodes[0]
    
    def _deselect_all(self):
        if self.on_node_deselect and self.selected_node:
            self.on_node_deselect()
        self.selected_node = None
        self.selected_nodes = []
        for node in self.nodes.values():
            node.set_selected(False)
        self._deselect_connection()
    
    def _find_connection_at(self, x: float, y: float) -> Optional[tuple]:
        for conn_key, line_id in self.connection_items.items():
            coords = self.canvas.coords(line_id)
            if len(coords) >= 4:
                for i in range(0, len(coords) - 2, 2):
                    x1, y1 = (coords[i] - self.pan_x) / self.zoom, (coords[i + 1] - self.pan_y) / self.zoom
                    x2, y2 = (coords[i + 2] - self.pan_x) / self.zoom, (coords[i + 3] - self.pan_y) / self.zoom
                    
                    dist = self._point_to_line_distance(x, y, x1, y1, x2, y2)
                    if dist < 10:
                        return conn_key
        return None
    
    def _point_to_line_distance(self, px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        line_len_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
        if line_len_sq == 0:
            return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_len_sq))
        proj_x = x1 + t * (x2 - x1)
        proj_y = y1 + t * (y2 - y1)
        
        return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)
    
    def _select_connection(self, conn_key: tuple):
        self._deselect_all()
        self.selected_connection = conn_key
        self.selected_connections = [conn_key]
        
        if conn_key in self.connection_items:
            line_id = self.connection_items[conn_key]
            self.canvas.itemconfig(line_id, fill=self._dark_colors.get('node_selected', '#FFD700'), width=3)
    
    def _update_connection_style(self, conn_key: tuple, selected: bool):
        if conn_key in self.connection_items:
            line_id = self.connection_items[conn_key]
            if selected:
                self.canvas.itemconfig(line_id, fill=self._dark_colors.get('node_selected', '#FFD700'), width=3)
            else:
                self.canvas.itemconfig(line_id, fill=self._dark_colors['connection_line'], width=2)
    
    def _deselect_connection(self):
        if self.selected_connection and self.selected_connection in self.connection_items:
            line_id = self.connection_items[self.selected_connection]
            self.canvas.itemconfig(line_id, fill=self._dark_colors['connection_line'], width=2)
        self.selected_connection = None
        
        for conn_key in self.selected_connections:
            if conn_key in self.connection_items:
                line_id = self.connection_items[conn_key]
                self.canvas.itemconfig(line_id, fill=self._dark_colors['connection_line'], width=2)
        self.selected_connections = []
    
    def remove_selected_connection(self):
        if self.selected_connection:
            conn_key = self.selected_connection
            if conn_key in self.connections:
                self.connections.remove(conn_key)
            if conn_key in self.connection_items:
                self.canvas.delete(self.connection_items[conn_key])
                del self.connection_items[conn_key]
            if conn_key in self.connection_order_items:
                self.canvas.delete(self.connection_order_items[conn_key])
                del self.connection_order_items[conn_key]
            self.selected_connection = None
            self._redraw_connections()

    def _delete_selected_connections(self):
        for conn_key in self.selected_connections[:]:
            if conn_key in self.connections:
                self.connections.remove(conn_key)
            if conn_key in self.connection_items:
                self.canvas.delete(self.connection_items[conn_key])
                del self.connection_items[conn_key]
            if conn_key in self.connection_order_items:
                self.canvas.delete(self.connection_order_items[conn_key])
                del self.connection_order_items[conn_key]
        self.selected_connections = []
        self.selected_connection = None
        self._redraw_connections()
    
    def _show_add_dialog(self, x: float, y: float):
        pass
    
    def _edit_node_properties(self, node_id: str):
        pass
    
    def _copy_node(self, node_id: str):
        pass
    
    def add_node(self, node_id: str, node_type: str, x: float, y: float, name: str = "", config: dict = None, enabled: bool = True, protected: bool = False) -> NodeItem:
        if not name:
            name = NODE_DISPLAY_NAMES.get(node_type, node_type)

        if node_type == "SubtreeNode":
            node = SubtreeNodeItem(self.canvas, node_id, node_type, x, y, name, config, enabled, self.zoom, self.pan_x, self.pan_y)
        elif node_type == "GroupNode":
            node = GroupNodeItem(self.canvas, node_id, node_type, x, y, name, config, enabled, self.zoom, self.pan_x, self.pan_y)
        else:
            node = NodeItem(self.canvas, node_id, node_type, x, y, name, config, enabled, self.zoom, self.pan_x, self.pan_y)
        node._protected = protected
        self.nodes[node_id] = node

        # 虚拟化：如果节点在视口内，立即渲染；否则删除构造函数创建的图元
        if self._virtualization_enabled:
            if self._is_node_visible(node):
                node.set_zoom(self.zoom)
                node.set_pan(self.pan_x, self.pan_y)
                node.redraw()
                self._visible_node_ids.add(node_id)
            else:
                # 构造函数已创建Canvas图元，但节点不在视口内，需清理
                self.canvas.delete(node_id)
                node._canvas_items_exist = False

        return node
    
    def remove_node(self, node_id: str):
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.reset_status()
            if isinstance(node, SubtreeNodeItem) and node._expanded:
                node._collapse_preview()
            if isinstance(node, GroupNodeItem) and node._collapsed:
                self._expand_group(node_id)
            self.canvas.delete(node.node_id)
            del self.nodes[node_id]
            
            if node_id == self.selected_node:
                self.selected_node = None
            
            if node_id in self.selected_nodes:
                self.selected_nodes.remove(node_id)
            
            # 移除关联连线并清理反向索引
            removed_connections = [c for c in self.connections if c[0] == node_id or c[1] == node_id]
            self.connections = [c for c in self.connections if c[0] != node_id and c[1] != node_id]
            for conn in removed_connections:
                pid, cid = conn
                if pid in self._node_connections_map:
                    self._node_connections_map[pid] = [
                        x for x in self._node_connections_map[pid] if x != conn
                    ]
                    if not self._node_connections_map[pid]:
                        del self._node_connections_map[pid]
                if cid in self._node_connections_map:
                    self._node_connections_map[cid] = [
                        x for x in self._node_connections_map[cid] if x != conn
                    ]
                    if not self._node_connections_map[cid]:
                        del self._node_connections_map[cid]
            # 清理被删节点自身的索引
            self._node_connections_map.pop(node_id, None)
            # 清理可见集合
            self._visible_node_ids.discard(node_id)
            # 清理组相关数据
            self._group_contents.pop(node_id, None)
            for contents in self._group_contents.values():
                contents.discard(node_id)
            self._collapsed_descendants.discard(node_id)
            proxy_lines = self._group_proxy_connections.pop(node_id, [])
            for line_id in proxy_lines:
                try:
                    self.canvas.delete(line_id)
                except Exception:
                    pass
            self._redraw_connections()
    
    def redraw_node(self, node_id: str):
        if node_id in self.nodes:
            node = self.nodes[node_id]
            # 虚拟化模式下，仅重绘可见节点
            if self._virtualization_enabled and node_id not in self._visible_node_ids:
                return
            node.redraw()
    
    def add_connection(self, parent_id: str, child_id: str) -> bool:
        if parent_id not in self.nodes or child_id not in self.nodes:
            return False
        
        if any(c[0] == parent_id and c[1] == child_id for c in self.connections):
            return False
        
        existing_parents = [c[0] for c in self.connections if c[1] == child_id]
        if existing_parents:
            child_node = self.nodes.get(child_id)
            child_name = child_node.name if child_node else child_id
            LogManager.instance().log_info(
                "连接操作",
                child_name,
                "节点已有父节点，不能重复连接"
            )
            return False
        
        if self._would_create_cycle(parent_id, child_id):
            LogManager.instance().log_info(
                "连接操作",
                "循环检测",
                "不能形成循环连接"
            )
            return False
        
        conn = (parent_id, child_id)
        self.connections.append(conn)
        # 维护反向索引
        self._node_connections_map.setdefault(parent_id, []).append(conn)
        self._node_connections_map.setdefault(child_id, []).append(conn)
        self._redraw_connections()
        return True
    
    def _would_create_cycle(self, parent_id: str, child_id: str) -> bool:
        visited = set()
        stack = [child_id]
        
        while stack:
            current = stack.pop()
            if current == parent_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            
            for p, c in self.connections:
                if p == current:
                    stack.append(c)
        
        return False
    
    def _redraw_connections(self):
        self.canvas.delete("connection")
        self.canvas.delete("connection_order")
        self.canvas.delete("group_proxy")
        self.connection_items.clear()
        self.connection_order_items.clear()
        # 重建反向索引
        self._node_connections_map.clear()

        # 预计算全局编号：基于connections列表中的实际位置
        conn_order_map: Dict[tuple, int] = {}
        parent_counter: Dict[str, int] = {}
        for parent_id, child_id in self.connections:
            conn = (parent_id, child_id)
            self._node_connections_map.setdefault(parent_id, []).append(conn)
            self._node_connections_map.setdefault(child_id, []).append(conn)

            parent_counter.setdefault(parent_id, 0)
            parent_counter[parent_id] += 1
            conn_order_map[conn] = parent_counter[parent_id]

        for parent_id, child_id in self.connections:
            # 虚拟化模式下，跳过不可见连线
            if self._virtualization_enabled:
                if parent_id not in self._visible_node_ids or child_id not in self._visible_node_ids:
                    continue
            # 跳过已被折叠的节点之间的连线
            if parent_id in self._collapsed_descendants or child_id in self._collapsed_descendants:
                continue

            order_num = conn_order_map.get((parent_id, child_id), 1)
            
            if parent_id in self.nodes and child_id in self.nodes:
                parent = self.nodes[parent_id]
                child = self.nodes[child_id]
                
                start_x, start_y = parent.get_output_port_pos()
                end_x, end_y = child.get_input_port_pos()
                
                start_x = start_x * self.zoom + self.pan_x
                start_y = start_y * self.zoom + self.pan_y
                end_x = end_x * self.zoom + self.pan_x
                end_y = end_y * self.zoom + self.pan_y
                
                mid_x = (start_x + end_x) / 2
                
                is_selected = ((parent_id, child_id) == self.selected_connection or 
                              (parent_id, child_id) in self.selected_connections)
                line_color = self._dark_colors.get('node_selected', '#FFD700') if is_selected else self._dark_colors['connection_line']
                line_width = 3 if is_selected else 2
                
                line_id = self.canvas.create_line(
                    start_x, start_y,
                    mid_x, start_y,
                    mid_x, end_y,
                    end_x, end_y,
                    fill=line_color,
                    width=line_width,
                    smooth=True,
                    arrow=tk.LAST,
                    arrowshape=(10, 12, 5),
                    tags="connection"
                )
                
                self.connection_items[(parent_id, child_id)] = line_id

                if order_num > 1 or len([c for c in self.connections if c[0] == parent_id]) > 1:
                    text_id = self.canvas.create_text(
                        mid_x,
                        end_y - 15,
                        text=str(order_num),
                        fill=self._dark_colors['text_secondary'],
                        font=("Arial", max(8, int(10 * self.zoom)), "bold"),
                        tags="connection_order"
                    )
                    self.connection_order_items[(parent_id, child_id)] = text_id
        
        self.canvas.tag_lower("connection_order")
        self.canvas.tag_lower("connection")
        self.canvas.tag_lower("grid")
        self._rebuild_proxy_connections()

    def _rebuild_proxy_connections(self):
        for group_id in list(self._group_proxy_connections.keys()):
            old_lines = self._group_proxy_connections.pop(group_id, [])
            for line_id in old_lines:
                try:
                    self.canvas.delete(line_id)
                except Exception:
                    pass
            if group_id not in self.nodes:
                continue
            contents = self._group_contents.get(group_id, set())
            if not contents:
                continue
            proxy_lines = []
            group_node = self.nodes[group_id]
            gx = group_node._transform_x(group_node.x)
            gy = group_node._transform_y(group_node.y)
            gw = group_node._scale(group_node.width)
            start_x = gx + gw / 2
            start_y = gy
            for conn in self.connections:
                if conn[0] in contents and conn[1] not in contents:
                    child = self.nodes.get(conn[1])
                    if child:
                        cx = child._transform_x(child.x)
                        cy = child._transform_y(child.y)
                        cw = child._scale(child.width)
                        end_x = cx - cw / 2
                        end_y = cy
                        mid_y = (start_y + end_y) / 2
                        line_id = self.canvas.create_line(
                            start_x, start_y, start_x, mid_y,
                            end_x, mid_y, end_x, end_y,
                            fill="#8B5CF6", width=2, dash=(4, 3),
                            smooth=True, tags=("group_proxy",)
                        )
                        proxy_lines.append(line_id)
            self._group_proxy_connections[group_id] = proxy_lines
    
    def _scale(self, value: float) -> float:
        return value * self.zoom
    
    def _redraw_all(self):
        self._redraw_all_flag = True
        self._schedule_redraw()
    
    def mark_node_dirty(self, node_id: str):
        self._dirty_nodes.add(node_id)
        self._schedule_redraw()
    
    def mark_connection_dirty(self, parent_id: str, child_id: str):
        self._dirty_connections.add((parent_id, child_id))
        self._schedule_redraw()
    
    def mark_all_dirty(self):
        self._redraw_all_flag = True
        self._schedule_redraw()
    
    def _schedule_redraw(self):
        if not self._redraw_scheduled:
            self._redraw_scheduled = True
            self.after(16, self._do_incremental_redraw)
    
    def _schedule_drag_redraw(self):
        """节流式拖拽重绘，避免高频鼠标事件导致重绘过于频繁"""
        if self._drag_throttle_timer is None:
            self._drag_throttle_timer = self.after(
                self._drag_throttle_ms, self._do_drag_redraw
            )
        else:
            self._drag_pending_redraw = True
    
    def _do_drag_redraw(self):
        """执行节流后的拖拽重绘

        区分两种场景：
        - 拖拽节点：仅重绘被拖动节点及其关联连线
        - 平移画布：使用虚拟化更新可见节点
        """
        self._drag_throttle_timer = None

        if self._drag_pending_redraw:
            self._drag_pending_redraw = False
            self._drag_throttle_timer = self.after(
                self._drag_throttle_ms, self._do_drag_redraw
            )

        is_panning = self._panning or self._right_panning

        if is_panning:
            if self._virtualization_enabled:
                # 虚拟化模式：根据新视口动态增删Canvas图元
                self._update_visible_nodes()
            else:
                for node in self.nodes.values():
                    node.set_zoom(self.zoom)
                    node.set_pan(self.pan_x, self.pan_y)
                    node.redraw()
                self._do_redraw_all_connections()
        else:
            # 拖拽节点：仅重绘被选中的节点及其关联连线
            has_collapsed = False
            for node_id in self.selected_nodes:
                if node_id in self.nodes:
                    self.nodes[node_id].set_zoom(self.zoom)
                    self.nodes[node_id].set_pan(self.pan_x, self.pan_y)
                    self.nodes[node_id].redraw()
                    node = self.nodes[node_id]
                    if isinstance(node, GroupNodeItem) and node._collapsed:
                        has_collapsed = True
            if not has_collapsed:
                self._redraw_connections_for_nodes(self.selected_nodes)
            self.canvas.delete("group_proxy")
            self._rebuild_proxy_connections()
    
    def _do_incremental_redraw(self):
        self._redraw_scheduled = False

        if self._redraw_all_flag:
            self._redraw_all_flag = False
            if self._virtualization_enabled:
                # 虚拟化模式：仅更新视口内可见节点
                self._update_visible_nodes()
            else:
                for node in self.nodes.values():
                    node.set_zoom(self.zoom)
                    node.set_pan(self.pan_x, self.pan_y)
                    node.redraw()
                self._do_redraw_all_connections()
            self._dirty_nodes.clear()
            self._dirty_connections.clear()
            return

        for node_id in self._dirty_nodes:
            if node_id in self.nodes:
                if self._virtualization_enabled and node_id not in self._visible_node_ids:
                    continue
                self.nodes[node_id].redraw()

        if self._dirty_connections:
            self._redraw_affected_connections()

        self._dirty_nodes.clear()
        self._dirty_connections.clear()
    
    def _do_redraw_all_connections(self):
        self.canvas.delete("connection")
        self.canvas.delete("connection_order")
        self.canvas.delete("group_proxy")
        self.connection_items.clear()
        self.connection_order_items.clear()
        # 重建反向索引
        self._node_connections_map.clear()

        # 预计算全局编号：基于connections列表中的实际位置
        conn_order_map: Dict[tuple, int] = {}
        parent_counter: Dict[str, int] = {}
        for parent_id, child_id in self.connections:
            conn = (parent_id, child_id)
            self._node_connections_map.setdefault(parent_id, []).append(conn)
            self._node_connections_map.setdefault(child_id, []).append(conn)

            parent_counter.setdefault(parent_id, 0)
            parent_counter[parent_id] += 1
            conn_order_map[conn] = parent_counter[parent_id]

        for parent_id, child_id in self.connections:
            # 虚拟化模式下，跳过不可见连线
            if self._virtualization_enabled:
                if parent_id not in self._visible_node_ids or child_id not in self._visible_node_ids:
                    continue
            # 跳过已被折叠的节点之间的连线
            if parent_id in self._collapsed_descendants or child_id in self._collapsed_descendants:
                continue

            order_num = conn_order_map.get((parent_id, child_id), 1)

            if parent_id in self.nodes and child_id in self.nodes:
                self._draw_single_connection(parent_id, child_id, order_num)

        self.canvas.tag_lower("connection_order")
        self.canvas.tag_lower("connection")
        self.canvas.tag_lower("grid")
        self._rebuild_proxy_connections()
    
    def _redraw_affected_connections(self):
        self.canvas.delete("group_proxy")
        for parent_id, child_id in self._dirty_connections:
            conn_key = (parent_id, child_id)
            if conn_key in self.connection_items:
                self.canvas.delete(self.connection_items[conn_key])
                del self.connection_items[conn_key]
            if conn_key in self.connection_order_items:
                self.canvas.delete(self.connection_order_items[conn_key])
                del self.connection_order_items[conn_key]

        # 收集受影响连线的所有兄弟连线，它们的序号可能变化
        affected_parents = set()
        for parent_id, child_id in self._dirty_connections:
            affected_parents.add(parent_id)

        sibling_conns_to_update = set()
        for parent_id in affected_parents:
            for c in self.connections:
                if c[0] == parent_id:
                    sibling_conns_to_update.add(c)

        for conn_key in sibling_conns_to_update:
            if conn_key in self.connection_order_items:
                self.canvas.delete(self.connection_order_items[conn_key])
                del self.connection_order_items[conn_key]

        for parent_id, child_id in self._dirty_connections:
            if parent_id in self.nodes and child_id in self.nodes:
                # 基于全局位置计算编号
                siblings = [c for c in self.connections if c[0] == parent_id]
                order = siblings.index((parent_id, child_id)) + 1 if (parent_id, child_id) in siblings else 1
                self._draw_single_connection(parent_id, child_id, order)

        # 重建受影响父节点下其他兄弟连线的序号标签
        for conn_key in sibling_conns_to_update:
            if conn_key not in self._dirty_connections:
                parent_id, child_id = conn_key
                if (parent_id in self.nodes and child_id in self.nodes
                        and conn_key in self.connection_items
                        and conn_key not in self.connection_order_items):
                    siblings = [c for c in self.connections if c[0] == parent_id]
                    order = siblings.index(conn_key) + 1 if conn_key in siblings else 1
                    if order > 1 or len(siblings) > 1:
                        child = self.nodes[child_id]
                        end_x, end_y = child.get_input_port_pos()
                        end_x = end_x * self.zoom + self.pan_x
                        end_y = end_y * self.zoom + self.pan_y
                        text_id = self.canvas.create_text(
                            end_x + 15,
                            end_y - 15,
                            text=str(order),
                            fill=self._dark_colors['text_secondary'],
                            font=("Arial", max(8, int(10 * self.zoom)), "bold"),
                            tags="connection_order"
                        )
                        self.connection_order_items[conn_key] = text_id

        self.canvas.tag_lower("connection_order")
        self.canvas.tag_lower("connection")
        self.canvas.tag_lower("grid")
        self._rebuild_proxy_connections()
    
    def _draw_single_connection(self, parent_id: str, child_id: str, order_num: int):
        parent = self.nodes[parent_id]
        child = self.nodes[child_id]
        
        start_x, start_y = parent.get_output_port_pos()
        end_x, end_y = child.get_input_port_pos()
        
        start_x = start_x * self.zoom + self.pan_x
        start_y = start_y * self.zoom + self.pan_y
        end_x = end_x * self.zoom + self.pan_x
        end_y = end_y * self.zoom + self.pan_y
        
        mid_x = (start_x + end_x) / 2
        
        is_selected = ((parent_id, child_id) == self.selected_connection or 
                      (parent_id, child_id) in self.selected_connections)
        line_color = self._dark_colors.get('node_selected', '#FFD700') if is_selected else self._dark_colors['connection_line']
        line_width = 3 if is_selected else 2
        
        line_id = self.canvas.create_line(
            start_x, start_y,
            mid_x, start_y,
            mid_x, end_y,
            end_x, end_y,
            fill=line_color,
            width=line_width,
            smooth=True,
            arrow=tk.LAST,
            arrowshape=(10, 12, 5),
            tags="connection"
        )
        
        conn_key = (parent_id, child_id)
        self.connection_items[conn_key] = line_id

        # 清理旧的序号文本项（如果存在）
        if conn_key in self.connection_order_items:
            self.canvas.delete(self.connection_order_items[conn_key])
            del self.connection_order_items[conn_key]

        if order_num > 1 or len([c for c in self.connections if c[0] == parent_id]) > 1:
            text_id = self.canvas.create_text(
                mid_x,
                end_y - 15,
                text=str(order_num),
                fill=self._dark_colors['text_secondary'],
                font=("Arial", max(8, int(10 * self.zoom)), "bold"),
                tags="connection_order"
            )
            self.connection_order_items[conn_key] = text_id

    def _redraw_connections_for_nodes(self, node_ids: List[str]):
        """仅重绘与指定节点关联的连线

        Args:
            node_ids: 需要重绘关联连线的节点ID列表
        """
        # 收集所有需要重绘的连线
        affected_conns = set()
        for node_id in node_ids:
            if node_id in self._node_connections_map:
                affected_conns.update(self._node_connections_map[node_id])

        if not affected_conns:
            return

        # 删除旧连线及其序号标签
        for conn_key in affected_conns:
            if conn_key in self.connection_items:
                self.canvas.delete(self.connection_items[conn_key])
                del self.connection_items[conn_key]
            if conn_key in self.connection_order_items:
                self.canvas.delete(self.connection_order_items[conn_key])
                del self.connection_order_items[conn_key]

        # 收集受影响连线的所有兄弟连线（同父节点的其他子节点），它们的序号可能变化
        affected_parents = set()
        for parent_id, child_id in affected_conns:
            affected_parents.add(parent_id)

        # 删除受影响父节点下所有兄弟连线的序号标签（序号可能因连线变化而重新编号）
        sibling_conns_to_update = set()
        for parent_id in affected_parents:
            for c in self.connections:
                if c[0] == parent_id:
                    sibling_conns_to_update.add(c)

        for conn_key in sibling_conns_to_update:
            if conn_key in self.connection_order_items:
                self.canvas.delete(self.connection_order_items[conn_key])
                del self.connection_order_items[conn_key]

        # 重绘受影响的连线
        for parent_id, child_id in affected_conns:
            if self._virtualization_enabled:
                if parent_id not in self._visible_node_ids or child_id not in self._visible_node_ids:
                    continue
            if parent_id in self._collapsed_descendants or child_id in self._collapsed_descendants:
                continue
            if parent_id in self.nodes and child_id in self.nodes:
                siblings = [c for c in self.connections if c[0] == parent_id]
                order = siblings.index((parent_id, child_id)) + 1 if (parent_id, child_id) in siblings else 1
                self._draw_single_connection(parent_id, child_id, order)

        # 重建受影响父节点下其他兄弟连线的序号标签
        for conn_key in sibling_conns_to_update:
            if conn_key not in affected_conns:
                parent_id, child_id = conn_key
                if (parent_id in self.nodes and child_id in self.nodes
                        and conn_key in self.connection_items
                        and conn_key not in self.connection_order_items):
                    siblings = [c for c in self.connections if c[0] == parent_id]
                    order = siblings.index(conn_key) + 1 if conn_key in siblings else 1
                    if order > 1 or len(siblings) > 1:
                        parent = self.nodes[parent_id]
                        child = self.nodes[child_id]
                        end_x, end_y = child.get_input_port_pos()
                        end_x = end_x * self.zoom + self.pan_x
                        end_y = end_y * self.zoom + self.pan_y
                        text_id = self.canvas.create_text(
                            end_x + 15,
                            end_y - 15,
                            text=str(order),
                            fill=self._dark_colors['text_secondary'],
                            font=("Arial", max(8, int(10 * self.zoom)), "bold"),
                            tags="connection_order"
                        )
                        self.connection_order_items[conn_key] = text_id

        self.canvas.tag_lower("connection_order")
        self.canvas.tag_lower("connection")
        self.canvas.tag_lower("grid")
    
    def clear_canvas(self, force: bool = False):
        start_node = None
        if not force:
            for node_id, node_item in list(self.nodes.items()):
                if node_item.is_protected():
                    start_node = node_item
                    break
        
        # 清空画布
        self.canvas.delete("all")
        self.nodes.clear()
        self.connections.clear()
        self.connection_items.clear()
        self.connection_order_items.clear()
        self._node_connections_map.clear()
        self._visible_node_ids.clear()
        self.selected_node = None
        self.selected_nodes = []
        self.selected_connection = None
        self._dragging = False
        self._drag_node = None
        self._drag_start = (0, 0)
        
        # 恢复开始节点
        if start_node:
            self.nodes[start_node.node_id] = start_node
            start_node.redraw()
        self._drag_start_pos = (0, 0)
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0, 0)
        self._right_panning = False
        self._right_pan_start = (0, 0)
        self._right_pan_start_offset = (0, 0)
        self._right_pan_moved = False
        self._selecting = False
        self._selection_start = (0, 0)
        self._selection_box = None
        self._selection_append = False
        self._connecting = False
        self._connect_start_node = None
        self._connect_start_pos = None
        self._connect_line = None
        self._group_contents.clear()
        self._collapsed_descendants.clear()
        self._group_proxy_connections.clear()
        self._draw_grid()
    
    def reset_view(self):
        if not self.nodes:
            self.zoom = 1.0
            self.pan_x = 0
            self.pan_y = 0
            self._redraw_all()
            self._draw_grid()
            return
        
        min_x = float('inf')
        min_y = float('inf')
        max_x = float('-inf')
        max_y = float('-inf')
        
        for node in self.nodes.values():
            x = node.x
            y = node.y
            w = node.width
            h = node.height
            
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = 800
            canvas_height = 600
        
        nodes_width = max_x - min_x
        nodes_height = max_y - min_y
        
        padding = 100
        zoom_x = (canvas_width - 2 * padding) / nodes_width if nodes_width > 0 else 1.0
        zoom_y = (canvas_height - 2 * padding) / nodes_height if nodes_height > 0 else 1.0
        
        self.zoom = min(zoom_x, zoom_y, 1.0)
        self.zoom = max(0.25, min(4.0, self.zoom))
        
        self.pan_x = canvas_width / 2 - center_x * self.zoom
        self.pan_y = canvas_height / 2 - center_y * self.zoom
        
        self._redraw_all()
        self._draw_grid()
    
    def auto_arrange(self):
        if not self.nodes:
            return
        
        all_children = {c for _, c in self.connections}
        roots = [nid for nid in self.nodes if nid not in all_children]
        if not roots:
            return
        
        for nid in roots:
            if self.nodes[nid].node_type == "StartNode":
                roots.remove(nid)
                roots.insert(0, nid)
                break
        
        h_gap = 180
        v_gap = 24
        
        def get_children(node_id):
            return [c for p, c in self.connections if p == node_id]
        
        def calc_subtree_height(node_id):
            node = self.nodes.get(node_id)
            if not node:
                return 0
            children = get_children(node_id)
            if not children:
                return node.height
            total = sum(calc_subtree_height(c) for c in children)
            total += v_gap * (len(children) - 1)
            return max(node.height, total)
        
        positions = {}
        
        def layout_node(node_id, x, y):
            positions[node_id] = (x, y)
            node = self.nodes.get(node_id)
            if not node:
                return
            children = get_children(node_id)
            if children:
                total_child_height = sum(calc_subtree_height(c) for c in children)
                children_v_total = total_child_height + v_gap * (len(children) - 1)
                current_y = y - children_v_total / 2
                for child in children:
                    child_node = self.nodes.get(child)
                    if not child_node:
                        continue
                    child_h = calc_subtree_height(child)
                    child_y = current_y + child_h / 2
                    layout_node(child, x + h_gap, child_y)
                    current_y += child_h + v_gap
        
        root = roots[0]
        root_node = self.nodes.get(root)
        if not root_node:
            return
        
        old_positions = {nid: (n.x, n.y) for nid, n in self.nodes.items()}
        
        layout_node(root, 100, 300)
        
        for node_id, (nx, ny) in positions.items():
            self.nodes[node_id].x = nx
            self.nodes[node_id].y = ny
        
        min_x = min(p[0] for p in positions.values())
        max_x = max(p[0] for p in positions.values())
        min_y = min(p[1] for p in positions.values())
        max_y = max(p[1] for p in positions.values())
        
        min_x -= max(node.width for node in self.nodes.values()) / 2
        max_x += max(node.width for node in self.nodes.values()) / 2
        min_y -= max(node.height for node in self.nodes.values()) / 2
        max_y += max(node.height for node in self.nodes.values()) / 2
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1:
            canvas_width = 800
        if canvas_height <= 1:
            canvas_height = 600
        
        tree_width = max_x - min_x
        tree_height = max_y - min_y
        
        padding = 60
        zoom_x = (canvas_width - 2 * padding) / tree_width if tree_width > 0 else 1.0
        zoom_y = (canvas_height - 2 * padding) / tree_height if tree_height > 0 else 1.0
        zoom = min(zoom_x, zoom_y, 1.0)
        zoom = max(0.5, zoom)
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        self.zoom = zoom
        self.pan_x = canvas_width / 2 - center_x * zoom
        self.pan_y = canvas_height / 2 - center_y * zoom
        
        editor = self._get_editor()
        if editor:
            new_positions = {nid: (n.x, n.y) for nid, n in self.nodes.items()}
            editor._on_nodes_move(old_positions, new_positions)
        
        self._redraw_all()
        self._draw_grid()
    
    def set_node_status(self, node_id: str, status: NodeExecutionStatus):
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.show_status_indicator()
            node.set_status(status)
    
    def show_all_status_indicators(self):
        for node in self.nodes.values():
            node.show_status_indicator()
    
    def hide_all_status_indicators(self):
        for node in self.nodes.values():
            node.hide_status_indicator()
    
    def reset_all_status(self):
        for node in self.nodes.values():
            node.reset_status()
    
    def clear_all_node_status(self):
        for node in self.nodes.values():
            node.hide_status_indicator()
            node.reset_status()
    
    def _is_node_visible(self, node: NodeItem) -> bool:
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        # winfo_width/height在Canvas未布局时返回1，需fallback到默认尺寸
        if canvas_width <= 1:
            canvas_width = 800
        if canvas_height <= 1:
            canvas_height = 600

        # node.x/y 是节点中心坐标，需减去半宽/半高得到左上角
        half_w = node.width * self.zoom / 2
        half_h = node.height * self.zoom / 2
        center_x = node.x * self.zoom + self.pan_x
        center_y = node.y * self.zoom + self.pan_y

        node_left = center_x - half_w
        node_top = center_y - half_h
        node_right = center_x + half_w
        node_bottom = center_y + half_h

        margin = 50

        return not (
            node_right < -margin or
            node_left > canvas_width + margin or
            node_bottom < -margin or
            node_top > canvas_height + margin
        )

    def get_visible_nodes(self) -> List[str]:
        visible = []
        for node_id, node in self.nodes.items():
            if self._is_node_visible(node):
                visible.append(node_id)
        return visible

    def _update_visible_nodes(self):
        """Canvas虚拟化核心方法：根据视口更新可见节点集合

        策略：
        1. 视口内节点直接可见
        2. 视口内节点的直接连接节点（1跳，双向）可见
        3. 从所有可见节点沿父节点方向向上追溯完整祖先链
        这样确保：父节点可见时子节点和连线完整，祖先链不断裂，
        同时兄弟分支（与可见节点无直接连接）被正确隐藏。
        """
        if not self._virtualization_enabled:
            return

        # Canvas未完成布局时（winfo_width/height <= 1），所有节点视为可见
        canvas_not_ready = self.canvas.winfo_width() <= 1 or self.canvas.winfo_height() <= 1

        # 第1步：确定视口内基础可见节点
        viewport_visible = set()
        for node_id, node in self.nodes.items():
            if canvas_not_ready or self._is_node_visible(node):
                viewport_visible.add(node_id)

        # 第2步：1跳扩展——视口内节点的直接连接节点也可见
        new_visible = set(viewport_visible)
        for parent_id, child_id in self.connections:
            if parent_id in viewport_visible or child_id in viewport_visible:
                new_visible.add(parent_id)
                new_visible.add(child_id)

        # 第3步：沿父节点方向向上追溯完整祖先链
        # 只向上（child→parent），不向下扩展，避免兄弟分支被意外显示
        changed = True
        while changed:
            changed = False
            for parent_id, child_id in self.connections:
                if child_id in new_visible and parent_id not in new_visible:
                    new_visible.add(parent_id)
                    changed = True

        # 折叠的节点强制不可见
        new_visible -= self._collapsed_descendants

        # 离开可见集合的节点：删除Canvas图元
        removed = self._visible_node_ids - new_visible
        for node_id in removed:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node._canvas_items_exist = False
                self.canvas.delete(node_id)
                # 子树预览也要清理
                try:
                    self.canvas.delete(f"subtree_preview_{node_id}")
                except Exception:
                    pass

        # 持续可见的节点：更新zoom/pan并重绘
        stayed = self._visible_node_ids & new_visible
        for node_id in stayed:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.set_zoom(self.zoom)
                node.set_pan(self.pan_x, self.pan_y)
                node.redraw()

        # 新进入可见集合的节点：创建Canvas图元
        added = new_visible - self._visible_node_ids
        for node_id in added:
            if node_id in self.nodes:
                node = self.nodes[node_id]
                node.set_zoom(self.zoom)
                node.set_pan(self.pan_x, self.pan_y)
                node.redraw()

        self._visible_node_ids = new_visible

        # 重绘可见连线
        self._redraw_visible_connections()

    def _redraw_visible_connections(self):
        """仅重绘视口内可见节点之间的连线

        编号(order_num)始终基于connections列表中的全局位置，
        不因部分连线不可见而改变。
        """
        self.canvas.delete("connection")
        self.canvas.delete("connection_order")
        self.canvas.delete("group_proxy")
        self.connection_items.clear()
        self.connection_order_items.clear()

        # 预计算全局编号：基于connections列表中的实际位置
        parent_child_order: Dict[str, int] = {}
        for parent_id, child_id in self.connections:
            parent_child_order.setdefault(parent_id, 0)
            parent_child_order[parent_id] += 1

        # 记录每条连线的全局编号
        conn_order_map: Dict[tuple, int] = {}
        parent_counter: Dict[str, int] = {}
        for parent_id, child_id in self.connections:
            parent_counter.setdefault(parent_id, 0)
            parent_counter[parent_id] += 1
            conn_order_map[(parent_id, child_id)] = parent_counter[parent_id]

        for parent_id, child_id in self.connections:
            # 仅绘制两端节点都在视口内的连线
            if parent_id not in self._visible_node_ids or child_id not in self._visible_node_ids:
                continue

            order_num = conn_order_map.get((parent_id, child_id), 1)

            if parent_id in self.nodes and child_id in self.nodes:
                self._draw_single_connection(parent_id, child_id, order_num)

        self.canvas.tag_lower("connection_order")
        self.canvas.tag_lower("connection")
        self.canvas.tag_lower("grid")
        self._rebuild_proxy_connections()

    def load_tree(self, tree_data: Dict[str, Any]):
        self.clear_canvas(force=True)
        
        nodes_data = tree_data.get("nodes", {})
        root_id = tree_data.get("root_node")
        
        if not nodes_data:
            return
        
        canvas_state = tree_data.get("canvas", {})
        if canvas_state:
            viewport = canvas_state.get("viewport", {})
            if viewport:
                self.zoom = viewport.get("zoom", 1.0)
                self.pan_x = viewport.get("offset_x", 0)
                self.pan_y = viewport.get("offset_y", 0)
        
        has_positions = any("position" in node_data for node_data in nodes_data.values())
        
        if not has_positions:
            positions = self._auto_layout(nodes_data, root_id)
        else:
            positions = {}
        
        for node_id, node_data in nodes_data.items():
            node_type = node_data.get("type", "Node")
            config = node_data.get("config", {})
            
            name = node_data.get("name", "")
            if not name:
                name = config.get("name", "")
            
            enabled = node_data.get("enabled", None)
            if enabled is None:
                enabled = config.get("enabled", True)
            
            if "position" in node_data:
                x = node_data["position"].get("x", 200)
                y = node_data["position"].get("y", 100)
            elif node_id in positions:
                x, y = positions[node_id]
            else:
                x, y = 200, 100
            
            self.add_node(node_id, node_type, x, y, name, config, enabled)
        
        for node_id, node_data in nodes_data.items():
            children = node_data.get("children", [])
            for child_info in children:
                if isinstance(child_info, dict):
                    child_id = child_info.get("id", "")
                else:
                    child_id = child_info
                if child_id:
                    self.add_connection(node_id, child_id)
        
            if "child" in node_data:
                self.add_connection(node_id, node_data["child"])
        
        for conn in tree_data.get("connections", []):
            if isinstance(conn, dict):
                p, c = conn.get("parent_id"), conn.get("child_id")
                if p and c and (p, c) not in self.connections:
                    self.add_connection(p, c)
        
        if root_id and root_id in self.nodes:
            self.root_node = root_id
        
        group_data = tree_data.get("group_contents", {})
        if group_data:
            self._group_contents = {gid: set(cids) for gid, cids in group_data.items()}
        collapsed_data = tree_data.get("collapsed_descendants", [])
        if collapsed_data:
            self._collapsed_descendants = set(collapsed_data)
        for group_id, child_ids in self._group_contents.items():
            if child_ids and all(cid in self._collapsed_descendants for cid in child_ids):
                if group_id in self.nodes:
                    self.nodes[group_id]._collapsed = True
                    if self.nodes[group_id].config is not None:
                        self.nodes[group_id].config["collapsed"] = True
        
        self._redraw_all()
        
        editor_state = tree_data.get("editor_state", {})
        if editor_state:
            selected_node = editor_state.get("selected_node")
            if selected_node and selected_node in self.nodes:
                self._select_node(selected_node)
    
    def _auto_layout(self, nodes_data: Dict, root_id: str) -> Dict[str, tuple]:
        positions = {}
        node_width = 180
        node_height = 80
        v_gap = 100
        
        def get_children(node_id):
            node_data = nodes_data.get(node_id, {})
            children = node_data.get("children", [])
            result = []
            for child in children:
                if isinstance(child, dict):
                    result.append(child.get("id", ""))
                else:
                    result.append(child)
            return [c for c in result if c]
        
        def calc_subtree_width(node_id):
            node_data = nodes_data.get(node_id, {})
            if node_data.get("type") == "GroupNode":
                config = node_data.get("config", {})
                if config.get("collapsed"):
                    return node_width
            children = get_children(node_id)
            if not children:
                return node_width
            total = 0
            for child in children:
                total += calc_subtree_width(child)
            return max(total, node_width)
        
        def layout_node(node_id, x, y):
            positions[node_id] = (x, y)
            node_data = nodes_data.get(node_id, {})
            if node_data.get("type") == "GroupNode":
                config = node_data.get("config", {})
                if config.get("collapsed"):
                    return
            children = get_children(node_id)
            if children:
                total_width = sum(calc_subtree_width(c) for c in children)
                current_x = x - total_width / 2
                for child in children:
                    child_width = calc_subtree_width(child)
                    layout_node(child, current_x + child_width / 2, y + node_height + v_gap)
                    current_x += child_width
        
        if root_id:
            layout_node(root_id, 400, 100)
        
        return positions
    
    def get_tree_data(self) -> Dict[str, Any]:
        nodes_data = {}
        
        for node_id, node in self.nodes.items():
            node_config = node.config if hasattr(node, 'config') else {}
            
            nodes_data[node_id] = {
                "id": node_id,
                "type": node.node_type,
                "name": getattr(node, 'name', ''),
                "enabled": getattr(node, 'enabled', True),
                "config": node_config,
                "position": {
                    "x": node.x,
                    "y": node.y
                }
            }
        
        for parent_id, child_id in self.connections:
            if parent_id in nodes_data:
                if "children" not in nodes_data[parent_id]:
                    nodes_data[parent_id]["children"] = []
                nodes_data[parent_id]["children"].append(child_id)
        
        root_id = None
        all_children = {c for _, c in self.connections}
        # 优先选择 StartNode 类型的节点作为根节点
        for node_id, node in self.nodes.items():
            if node_id not in all_children and node.node_type == "StartNode":
                root_id = node_id
                break
        # 如果没有找到 StartNode，回退到第一个非子节点
        if root_id is None:
            for node_id in self.nodes:
                if node_id not in all_children:
                    root_id = node_id
                    break
        
        return {
            "version": "2.0",
            "format_type": "behavior_tree_editor",
            "canvas": {
                "name": "未命名",
                "description": "",
                "viewport": {
                    "zoom": self.zoom,
                    "offset_x": self.pan_x,
                    "offset_y": self.pan_y
                }
            },
            "root_node": root_id,
            "nodes": nodes_data,
            "connections": [{"parent_id": p, "child_id": c} for p, c in self.connections],
            "group_contents": {gid: list(cids) for gid, cids in self._group_contents.items()},
            "collapsed_descendants": list(self._collapsed_descendants)
        }
    
    def _delete_selected_nodes(self):
        if not self.selected_nodes:
            return
        
        from tkinter import messagebox
        
        nodes_to_delete = []
        protected_nodes = []
        
        for node_id in list(self.selected_nodes):
            if node_id in self.nodes:
                node_item = self.nodes[node_id]
                if node_item.is_protected():
                    protected_nodes.append(node_id)
                    continue
                nodes_to_delete.append(node_id)
        
        # 如果有受保护的节点,显示提示
        if protected_nodes:
            messagebox.showwarning("无法删除", "开始节点不可删除")
        
        # 删除非保护节点
        for node_id in nodes_to_delete:
            self.remove_node(node_id)
    
    def _copy_selected_nodes_to_clipboard(self):
        if not self.selected_nodes:
            return None
        
        import copy
        
        nodes_to_copy = []
        for node_id in self.selected_nodes:
            if node_id not in self.nodes:
                continue
            node_item = self.nodes[node_id]
            if node_item.is_protected():
                continue
            nodes_to_copy.append(node_id)
        
        if not nodes_to_copy:
            return None
        
        min_x = min(self.nodes[nid].x for nid in nodes_to_copy if nid in self.nodes)
        min_y = min(self.nodes[nid].y for nid in nodes_to_copy if nid in self.nodes)
        
        nodes_data = []
        relative_positions = {}
        
        for node_id in nodes_to_copy:
            if node_id not in self.nodes:
                continue
            node = self.nodes[node_id]
            nodes_data.append({
                'id': node_id,
                'type': node.node_type,
                'name': node.name,
                'config': copy.deepcopy(node.config) if node.config else {},
                'enabled': node.enabled
            })
            relative_positions[node_id] = (node.x - min_x, node.y - min_y)
        
        connections = [
            (parent_id, child_id)
            for parent_id, child_id in self.connections
            if parent_id in nodes_to_copy and child_id in nodes_to_copy
        ]
        
        return {
            'nodes': nodes_data,
            'connections': connections,
            'relative_positions': relative_positions
        }
    
    def paste_nodes(self, clipboard_data: Dict[str, Any], offset_x: float = 50, offset_y: float = 50) -> List[str]:
        if not clipboard_data or not clipboard_data.get('nodes'):
            return []
        
        nodes_data = clipboard_data['nodes']
        connections = clipboard_data.get('connections', [])
        relative_positions = clipboard_data.get('relative_positions', {})
        
        id_map = {}
        new_node_ids = []
        
        for node_data in nodes_data:
            old_id = node_data['id']
            self._node_counter += 1
            new_id = f"node_{self._node_counter}"
            id_map[old_id] = new_id
            
            rel_x, rel_y = relative_positions.get(old_id, (0, 0))
            new_x = rel_x + offset_x
            new_y = rel_y + offset_y
            
            self.add_node(
                new_id,
                node_data['type'],
                new_x, new_y,
                node_data.get('name', ''),
                node_data.get('config', {}),
                node_data.get('enabled', True)
            )
            new_node_ids.append(new_id)
        
        for old_parent, old_child in connections:
            new_parent = id_map.get(old_parent)
            new_child = id_map.get(old_child)
            if new_parent and new_child:
                self.add_connection(new_parent, new_child)
        
        return new_node_ids
    
    def _update_selection_box(self, x: float, y: float):
        if self._selection_box:
            self.canvas.delete(self._selection_box)
        
        start_x, start_y = self._selection_start
        
        screen_start_x = start_x * self.zoom + self.pan_x
        screen_start_y = start_y * self.zoom + self.pan_y
        screen_end_x = x * self.zoom + self.pan_x
        screen_end_y = y * self.zoom + self.pan_y
        
        self._selection_box = self.canvas.create_rectangle(
            screen_start_x, screen_start_y,
            screen_end_x, screen_end_y,
            outline=self._dark_colors.get('node_selected', '#FFD700'),
            width=2,
            dash=(5, 3),
            tags="selection_box"
        )
    
    def _finish_selection(self, x: float, y: float):
        if self._selection_box:
            self.canvas.delete(self._selection_box)
            self._selection_box = None
        
        selected_ids = self._get_nodes_in_selection_box(
            self._selection_start[0], self._selection_start[1],
            x, y
        )
        
        selected_connections = self._get_connections_in_selection_box(
            self._selection_start[0], self._selection_start[1],
            x, y
        )
        
        if not self._selection_append:
            self._deselect_all()
        
        for node_id in selected_ids:
            if node_id not in self.selected_nodes:
                self.selected_nodes.append(node_id)
                self.nodes[node_id].set_selected(True)
        
        for conn_key in selected_connections:
            if conn_key not in self.selected_connections:
                self.selected_connections.append(conn_key)
                self._update_connection_style(conn_key, selected=True)
        
        if self.selected_nodes:
            self.selected_node = self.selected_nodes[0]
            if self.on_node_select and len(self.selected_nodes) == 1:
                node = self.nodes[self.selected_node]
                self.on_node_select(self.selected_node, node.node_type)
        
        if self.selected_connections:
            self.selected_connection = self.selected_connections[0]
        
        self._selecting = False
    
    def _get_nodes_in_selection_box(self, x1: float, y1: float, 
                                     x2: float, y2: float) -> List[str]:
        selected = []
        
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        
        for node_id, node in self.nodes.items():
            nx1, ny1, nx2, ny2 = node.get_bounds()
            
            if not (nx2 < min_x or nx1 > max_x or 
                    ny2 < min_y or ny1 > max_y):
                selected.append(node_id)
        
        return selected
    
    def _get_connections_in_selection_box(self, x1: float, y1: float,
                                          x2: float, y2: float) -> List[tuple]:
        selected = []
        
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        
        for conn_key in self.connections:
            parent_id, child_id = conn_key
            if parent_id in self.nodes and child_id in self.nodes:
                parent_node = self.nodes[parent_id]
                child_node = self.nodes[child_id]
                
                start_x, start_y = parent_node.get_output_port_pos()
                end_x, end_y = child_node.get_input_port_pos()
                
                mid_y = (start_y + end_y) / 2
                
                line_points = [
                    (start_x, start_y),
                    (start_x, mid_y),
                    (end_x, mid_y),
                    (end_x, end_y)
                ]
                
                for px, py in line_points:
                    if min_x <= px <= max_x and min_y <= py <= max_y:
                        selected.append(conn_key)
                        break
        
        return selected

    def _wrap_in_group(self):
        if len(self.selected_nodes) < 2:
            return

        nodes_to_wrap = [nid for nid in self.selected_nodes
                         if nid in self.nodes and not self.nodes[nid].is_protected()]
        if len(nodes_to_wrap) < 2:
            return

        selected_set = set(nodes_to_wrap)

        entry_nodes = []
        for nid in nodes_to_wrap:
            parents = [c[0] for c in self.connections if c[1] == nid]
            if not parents or parents[0] not in selected_set:
                entry_nodes.append(nid)

        if not entry_nodes:
            return

        common_parent = None
        for nid in entry_nodes:
            parents = [c[0] for c in self.connections if c[1] == nid]
            parent = parents[0] if parents else None
            if parent is None:
                continue
            if common_parent is None:
                common_parent = parent
            elif parent != common_parent:
                from tkinter import messagebox
                messagebox.showwarning("无法打包", "选中的节点入口指向了不同的父节点，无法放入同一个组")
                return

        avg_x = sum(self.nodes[nid].x for nid in nodes_to_wrap) / len(nodes_to_wrap)
        avg_y = sum(self.nodes[nid].y for nid in nodes_to_wrap) / len(nodes_to_wrap)

        self._node_counter += 1
        group_id = f"node_{self._node_counter}"
        while group_id in self.nodes:
            self._node_counter += 1
            group_id = f"node_{self._node_counter}"

        self.add_node(group_id, "GroupNode", avg_x, avg_y - 80, "组合组")

        self._group_contents[group_id] = set(nodes_to_wrap)

        original_positions = {}
        for nid in nodes_to_wrap:
            node = self.nodes[nid]
            original_positions[nid] = (node.x, node.y)
            node.move_to(node.x, node.y + 40)

        old_connections = []
        for nid in entry_nodes:
            for c in list(self.connections):
                if c[1] == nid:
                    old_connections.append(c)
                    self.connections.remove(c)

        if common_parent:
            self.add_connection(common_parent, group_id)
        for nid in entry_nodes:
            self.add_connection(group_id, nid)

        self._redraw_connections()

        editor = self._get_editor()
        if editor and hasattr(editor, '_wrap_in_group_undo'):
            editor._wrap_in_group_undo(
                group_id=group_id,
                to_wrap=nodes_to_wrap,
                common_parent=common_parent or "",
                old_connections=old_connections,
                original_positions=original_positions
            )

    def _collapse_group(self, group_id: str):
        if group_id not in self.nodes:
            return
        contents = self._group_contents.get(group_id, set())
        if not contents:
            return
        for nid in contents:
            if nid in self.nodes:
                self.nodes[nid].hide()
                self._visible_node_ids.discard(nid)
            self._collapsed_descendants.add(nid)
        for conn in list(self.connections):
            if conn[0] in contents and conn[1] in contents:
                if conn in self.connection_items:
                    self.canvas.itemconfig(self.connection_items[conn], state='hidden')
        self._redraw_connections()

        proxy_lines = []
        group_node = self.nodes[group_id]
        gx = group_node._transform_x(group_node.x)
        gy = group_node._transform_y(group_node.y)
        gw = group_node._scale(group_node.width)
        start_x = gx + gw / 2
        start_y = gy

        for conn in self.connections:
            if conn[0] in contents and conn[1] not in contents:
                child = self.nodes.get(conn[1])
                if child:
                    cx = child._transform_x(child.x)
                    cy = child._transform_y(child.y)
                    cw = child._scale(child.width)
                    end_x = cx - cw / 2
                    end_y = cy
                    mid_y = (start_y + end_y) / 2
                    line_id = self.canvas.create_line(
                        start_x, start_y, start_x, mid_y,
                        end_x, mid_y, end_x, end_y,
                        fill="#8B5CF6", width=2, dash=(4, 3),
                        smooth=True, tags=("group_proxy",)
                    )
                    proxy_lines.append(line_id)
        self._group_proxy_connections[group_id] = proxy_lines

    def _expand_group(self, group_id: str):
        if group_id not in self.nodes:
            return
        proxy_lines = self._group_proxy_connections.pop(group_id, [])
        for line_id in proxy_lines:
            try:
                self.canvas.delete(line_id)
            except Exception:
                pass
        contents = self._group_contents.get(group_id, set())
        if not contents:
            return
        for nid in contents:
            if nid in self.nodes:
                node = self.nodes[nid]
                node.set_zoom(self.zoom)
                node.set_pan(self.pan_x, self.pan_y)
                node.redraw()
                self._visible_node_ids.add(nid)
            self._collapsed_descendants.discard(nid)
        for conn in list(self.connections):
            if conn[0] in contents and conn[1] in contents:
                if conn in self.connection_items:
                    self.canvas.itemconfig(self.connection_items[conn], state='normal')
        self._redraw_connections()

    def _get_all_descendants(self, node_id: str) -> set:
        result = set()
        queue = []
        for conn in self.connections:
            if conn[0] == node_id:
                queue.append(conn[1])
        while queue:
            child_id = queue.pop(0)
            if child_id in result:
                continue
            result.add(child_id)
            for conn in self.connections:
                if conn[0] == child_id and conn[1] not in result:
                    queue.append(conn[1])
        return result
