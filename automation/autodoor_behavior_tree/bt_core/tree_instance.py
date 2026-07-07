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
    selected_node_id: Optional[str] = None
    project_manager: Optional[Any] = None

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
            "selected_node_id": self.selected_node_id,
        }
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self.status == "running"
    
    def set_running(self, running: bool) -> None:
        """设置运行状态
        
        Args:
            running: True 设置为 running，False 设置为 stopped
        """
        self.status = "running" if running else "stopped"
