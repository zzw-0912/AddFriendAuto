from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class Command:
    description: str = ""
    
    def execute(self) -> bool:
        return True
    
    def undo(self) -> bool:
        return True
    
    def redo(self) -> bool:
        return self.execute()


@dataclass
class AddNodeCommand(Command):
    canvas: Any = None
    node_id: str = ""
    node_type: str = ""
    x: float = 0
    y: float = 0
    node_data: Dict[str, Any] = field(default_factory=dict)
    
    description: str = "添加节点"
    
    def execute(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'add_node'):
            name = self.node_data.get('name', '')
            config = self.node_data.get('config', {})
            enabled = self.node_data.get('enabled', True)
            self.canvas.add_node(self.node_id, self.node_type, self.x, self.y, name, config, enabled)
            return True
        return False
    
    def undo(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'remove_node'):
            self.canvas.remove_node(self.node_id)
            return True
        return False


@dataclass
class AddNodesCommand(Command):
    canvas: Any = None
    nodes_data: List[Dict[str, Any]] = field(default_factory=list)
    connections: List[tuple] = field(default_factory=list)
    new_node_ids: List[str] = field(default_factory=list)
    
    description: str = "批量添加节点"
    
    def execute(self) -> bool:
        if not self.canvas or not hasattr(self.canvas, 'add_node'):
            return False
        
        self.new_node_ids = []
        
        for node_data in self.nodes_data:
            node_id = node_data['id']
            self.canvas.add_node(
                node_id,
                node_data['type'],
                node_data['x'],
                node_data['y'],
                node_data.get('name', ''),
                node_data.get('config', {}),
                node_data.get('enabled', True)
            )
            self.new_node_ids.append(node_id)
        
        for parent_id, child_id in self.connections:
            if hasattr(self.canvas, 'add_connection'):
                self.canvas.add_connection(parent_id, child_id)
        
        return True
    
    def undo(self) -> bool:
        if not self.canvas or not hasattr(self.canvas, 'remove_node'):
            return False
        
        for node_id in self.new_node_ids:
            self.canvas.remove_node(node_id)
        
        return True


@dataclass
class RemoveNodeCommand(Command):
    canvas: Any = None
    node_id: str = ""
    node_data: Dict[str, Any] = field(default_factory=dict)
    connections: List[tuple] = field(default_factory=list)
    
    description: str = "删除节点"
    
    def execute(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'remove_node'):
            if hasattr(self.canvas, 'nodes') and self.node_id in self.canvas.nodes:
                node = self.canvas.nodes[self.node_id]
                self.node_data = {
                    "id": node.node_id,
                    "type": node.node_type,
                    "x": node.x,
                    "y": node.y,
                    "name": getattr(node, 'name', ''),
                    "config": deepcopy(getattr(node, 'config', {})),
                    "enabled": getattr(node, 'enabled', True)
                }
                self.connections = [
                    c for c in self.canvas.connections 
                    if c[0] == self.node_id or c[1] == self.node_id
                ]
            self.canvas.remove_node(self.node_id)
            return True
        return False
    
    def undo(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'add_node'):
            self.canvas.add_node(
                self.node_data["id"],
                self.node_data["type"],
                self.node_data["x"],
                self.node_data["y"],
                self.node_data.get("name", ""),
                self.node_data.get("config", {}),
                self.node_data.get("enabled", True)
            )
            for parent_id, child_id in self.connections:
                self.canvas.add_connection(parent_id, child_id)
            return True
        return False


@dataclass
class RemoveNodesCommand(Command):
    canvas: Any = None
    node_ids: List[str] = field(default_factory=list)
    nodes_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    connections: List[tuple] = field(default_factory=list)
    
    description: str = "批量删除节点"
    
    def execute(self) -> bool:
        if not self.canvas or not hasattr(self.canvas, 'remove_node'):
            return False
        
        self.nodes_data = {}
        self.connections = []
        
        node_set = set(self.node_ids)
        
        for node_id in self.node_ids:
            if node_id in self.canvas.nodes:
                node = self.canvas.nodes[node_id]
                self.nodes_data[node_id] = {
                    "id": node.node_id,
                    "type": node.node_type,
                    "x": node.x,
                    "y": node.y,
                    "name": getattr(node, 'name', ''),
                    "config": deepcopy(getattr(node, 'config', {})),
                    "enabled": getattr(node, 'enabled', True)
                }
        
        self.connections = [
            c for c in self.canvas.connections 
            if c[0] in node_set or c[1] in node_set
        ]
        
        for node_id in self.node_ids:
            self.canvas.remove_node(node_id)
        
        return True
    
    def undo(self) -> bool:
        if not self.canvas or not hasattr(self.canvas, 'add_node'):
            return False
        
        for node_id, node_data in self.nodes_data.items():
            self.canvas.add_node(
                node_id,
                node_data["type"],
                node_data["x"],
                node_data["y"],
                node_data.get("name", ""),
                node_data.get("config", {}),
                node_data.get("enabled", True)
            )
        
        for parent_id, child_id in self.connections:
            if parent_id in self.canvas.nodes and child_id in self.canvas.nodes:
                self.canvas.add_connection(parent_id, child_id)
        
        return True


@dataclass
class MoveNodeCommand(Command):
    canvas: Any = None
    node_id: str = ""
    old_x: float = 0
    old_y: float = 0
    new_x: float = 0
    new_y: float = 0
    
    description: str = "移动节点"
    
    def execute(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'nodes') and self.node_id in self.canvas.nodes:
            node = self.canvas.nodes[self.node_id]
            node.move_to(self.new_x, self.new_y)
            if hasattr(self.canvas, '_redraw_connections'):
                self.canvas._redraw_connections()
            return True
        return False
    
    def undo(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'nodes') and self.node_id in self.canvas.nodes:
            node = self.canvas.nodes[self.node_id]
            node.move_to(self.old_x, self.old_y)
            if hasattr(self.canvas, '_redraw_connections'):
                self.canvas._redraw_connections()
            return True
        return False


@dataclass
class MoveNodesCommand(Command):
    canvas: Any = None
    node_ids: List[str] = field(default_factory=list)
    old_positions: Dict[str, tuple] = field(default_factory=dict)
    new_positions: Dict[str, tuple] = field(default_factory=dict)
    
    description: str = "批量移动节点"
    
    def execute(self) -> bool:
        if not self.canvas or not hasattr(self.canvas, 'nodes'):
            return False
        
        for node_id, (new_x, new_y) in self.new_positions.items():
            if node_id in self.canvas.nodes:
                self.canvas.nodes[node_id].move_to(new_x, new_y)
        
        if hasattr(self.canvas, '_redraw_connections'):
            self.canvas._redraw_connections()
        
        return True
    
    def undo(self) -> bool:
        if not self.canvas or not hasattr(self.canvas, 'nodes'):
            return False
        
        for node_id, (old_x, old_y) in self.old_positions.items():
            if node_id in self.canvas.nodes:
                node = self.canvas.nodes[node_id]
                node.x = old_x
                node.y = old_y
        
        if hasattr(self.canvas, '_update_visible_nodes'):
            self.canvas._update_visible_nodes()
        if hasattr(self.canvas, '_redraw_connections'):
            self.canvas._redraw_connections()
        
        return True


@dataclass
class WrapInGroupCommand(Command):
    canvas: Any = None
    group_id: str = ""
    to_wrap: List[str] = field(default_factory=list)
    common_parent: str = ""
    old_connections: List[tuple] = field(default_factory=list)
    original_positions: dict = field(default_factory=dict)
    
    description: str = "打包成组"
    
    def execute(self) -> bool:
        return True
    
    def undo(self) -> bool:
        if not self.canvas:
            return False
        if self.group_id in self.canvas.nodes:
            gn = self.canvas.nodes[self.group_id]
            if hasattr(gn, '_collapsed') and gn._collapsed:
                self.canvas._expand_group(self.group_id)
        for nid in self.to_wrap:
            node = self.canvas.nodes.get(nid)
            if node:
                orig = self.original_positions.get(nid)
                if orig:
                    node.move_to(orig[0], orig[1])
                else:
                    node.move_to(node.x, node.y - 40)
        self.canvas.connections = [c for c in self.canvas.connections
                                    if not (c[0] == self.group_id or c[1] == self.group_id)]
        if self.group_id in self.canvas.nodes:
            self.canvas.remove_node(self.group_id)
        for parent_id, child_id in self.old_connections:
            if parent_id in self.canvas.nodes and child_id in self.canvas.nodes:
                self.canvas.add_connection(parent_id, child_id)
        return True


@dataclass
class AddConnectionCommand(Command):
    canvas: Any = None
    parent_id: str = ""
    child_id: str = ""
    connection_index: int = -1
    
    description: str = "添加连线"
    
    def execute(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'add_connection'):
            self.canvas.add_connection(self.parent_id, self.child_id)
            # 记录连线在列表中的位置（用于undo时按正确位置恢复）
            if hasattr(self.canvas, 'connections'):
                for i, c in enumerate(self.canvas.connections):
                    if c[0] == self.parent_id and c[1] == self.child_id:
                        self.connection_index = i
                        break
            return True
        return False
    
    def undo(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'connections'):
            conn = (self.parent_id, self.child_id)
            self.canvas.connections = [
                c for c in self.canvas.connections
                if not (c[0] == self.parent_id and c[1] == self.child_id)
            ]
            # 更新反向索引
            if hasattr(self.canvas, '_node_connections_map'):
                for node_id in (self.parent_id, self.child_id):
                    if node_id in self.canvas._node_connections_map:
                        self.canvas._node_connections_map[node_id] = [
                            x for x in self.canvas._node_connections_map[node_id] if x != conn
                        ]
                        if not self.canvas._node_connections_map[node_id]:
                            del self.canvas._node_connections_map[node_id]
            if hasattr(self.canvas, '_redraw_connections'):
                self.canvas._redraw_connections()
            return True
        return False


@dataclass
class RemoveConnectionCommand(Command):
    canvas: Any = None
    parent_id: str = ""
    child_id: str = ""
    connection_index: int = -1
    
    description: str = "删除连线"
    
    def execute(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'connections'):
            # 记录连线在列表中的原始位置
            for i, c in enumerate(self.canvas.connections):
                if c[0] == self.parent_id and c[1] == self.child_id:
                    self.connection_index = i
                    break
            self.canvas.connections = [
                c for c in self.canvas.connections 
                if not (c[0] == self.parent_id and c[1] == self.child_id)
            ]
            if hasattr(self.canvas, '_redraw_connections'):
                self.canvas._redraw_connections()
            return True
        return False
    
    def undo(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'connections'):
            # 在原始位置插入连线，而非追加到末尾
            conn = (self.parent_id, self.child_id)
            insert_idx = self.connection_index if 0 <= self.connection_index <= len(self.canvas.connections) else len(self.canvas.connections)
            self.canvas.connections.insert(insert_idx, conn)
            # 维护反向索引
            if hasattr(self.canvas, '_node_connections_map'):
                self.canvas._node_connections_map.setdefault(self.parent_id, []).append(conn)
                self.canvas._node_connections_map.setdefault(self.child_id, []).append(conn)
            if hasattr(self.canvas, '_redraw_connections'):
                self.canvas._redraw_connections()
            return True
        return False


@dataclass
class SetPropertyCommand(Command):
    property_panel: Any = None
    node_id: str = ""
    property_key: str = ""
    old_value: Any = None
    new_value: Any = None
    
    description: str = "设置属性"
    
    def execute(self) -> bool:
        return True
    
    def undo(self) -> bool:
        if self.property_panel and hasattr(self.property_panel, 'on_change'):
            self.property_panel.on_change(self.node_id, self.property_key, self.old_value)
            return True
        return False


@dataclass
class ClearCanvasCommand(Command):
    canvas: Any = None
    nodes_backup: Dict[str, Any] = field(default_factory=dict)
    connections_backup: List[tuple] = field(default_factory=list)
    
    description: str = "清空画布"
    
    def execute(self) -> bool:
        if self.canvas:
            self.nodes_backup = {}
            self.connections_backup = []
            
            if hasattr(self.canvas, 'nodes'):
                for node_id, node in self.canvas.nodes.items():
                    self.nodes_backup[node_id] = {
                        "id": node.node_id,
                        "type": node.node_type,
                        "x": node.x,
                        "y": node.y,
                    }
            
            if hasattr(self.canvas, 'connections'):
                self.connections_backup = list(self.canvas.connections)
            
            if hasattr(self.canvas, 'clear_canvas'):
                self.canvas.clear_canvas()
            return True
        return False
    
    def undo(self) -> bool:
        if self.canvas and hasattr(self.canvas, 'add_node'):
            for node_id, node_data in self.nodes_backup.items():
                self.canvas.add_node(
                    node_data["id"],
                    node_data["type"],
                    node_data["x"],
                    node_data["y"]
                )
            for parent_id, child_id in self.connections_backup:
                self.canvas.add_connection(parent_id, child_id)
            return True
        return False


class CommandManager:
    def __init__(self, max_history: int = 100):
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
        self.max_history = max_history
        self._is_executing = False
    
    def execute(self, command: Command) -> bool:
        if self._is_executing:
            return False
        
        self._is_executing = True
        try:
            if command.execute():
                self.undo_stack.append(command)
                self.redo_stack.clear()
                
                if len(self.undo_stack) > self.max_history:
                    self.undo_stack.pop(0)
                
                return True
            return False
        finally:
            self._is_executing = False
    
    def undo(self) -> bool:
        if not self.can_undo():
            return False
        
        self._is_executing = True
        try:
            command = self.undo_stack.pop()
            if command.undo():
                self.redo_stack.append(command)
                return True
            self.undo_stack.append(command)
            return False
        finally:
            self._is_executing = False
    
    def redo(self) -> bool:
        if not self.can_redo():
            return False
        
        self._is_executing = True
        try:
            command = self.redo_stack.pop()
            if command.redo():
                self.undo_stack.append(command)
                return True
            self.redo_stack.append(command)
            return False
        finally:
            self._is_executing = False
    
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0
    
    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
    
    def get_undo_description(self) -> Optional[str]:
        if self.undo_stack:
            return self.undo_stack[-1].description
        return None
    
    def get_redo_description(self) -> Optional[str]:
        if self.redo_stack:
            return self.redo_stack[-1].description
        return None
