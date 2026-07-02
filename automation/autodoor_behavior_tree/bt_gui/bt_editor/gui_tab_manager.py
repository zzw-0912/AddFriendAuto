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
        self.on_tab_start_request: Optional[Callable[[str], bool]] = None
        self.on_tab_stop_request: Optional[Callable[[str], bool]] = None
    
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
            if tab_id in self._trees:
                raise ValueError(f"Tab ID '{tab_id}' already exists")
            
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
            
            tab_keys = list(self._trees.keys())
            closed_index = tab_keys.index(tab_id) if tab_id in tab_keys else -1
            
            del self._trees[tab_id]
            
            if self._active_tab_id == tab_id:
                tab_ids = list(self._trees.keys())
                if tab_ids:
                    if closed_index < len(tab_ids):
                        self._active_tab_id = tab_ids[closed_index]
                    else:
                        self._active_tab_id = tab_ids[-1]
                else:
                    self._active_tab_id = None
            
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
    
    def start_tab(self, tab_id: str, skip_sound: bool = False) -> bool:
        if self.on_tab_start_request:
            return self.on_tab_start_request(tab_id, skip_sound=skip_sound)
        
        instance = self._trees.get(tab_id)
        if not instance or instance.status == "running":
            return False
        
        instance.engine.start(instance.context)
        self.update_tab_status(tab_id, True)
        return True
    
    def stop_tab(self, tab_id: str, skip_sound: bool = False) -> bool:
        if self.on_tab_stop_request:
            return self.on_tab_stop_request(tab_id, skip_sound=skip_sound)
        
        instance = self._trees.get(tab_id)
        if not instance or instance.status != "running":
            return False
        
        instance.engine.stop()
        self.update_tab_status(tab_id, False)
        return True
    
    def start_all(self) -> int:
        """启动所有 Tab 的行为树
        
        Returns:
            成功启动的数量
        """
        count = 0
        for tab_id in list(self._trees.keys()):
            if self.start_tab(tab_id):
                count += 1
        return count
    
    def stop_all(self) -> int:
        """停止所有 Tab 的行为树
        
        Returns:
            成功停止的数量
        """
        count = 0
        for tab_id in list(self._trees.keys()):
            if self.stop_tab(tab_id):
                count += 1
        return count
    
    def get_all_status(self) -> list:
        """获取所有 Tab 状态
        
        Returns:
            状态列表
        """
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
    
    def get_tab_count(self) -> int:
        """获取 Tab 数量"""
        return len(self._trees)
