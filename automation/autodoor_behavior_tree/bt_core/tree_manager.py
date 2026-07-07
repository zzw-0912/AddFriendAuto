import threading
from typing import Dict, Optional, Callable, Any

from .engine import BehaviorTreeEngine
from .context import ExecutionContext
from .blackboard import Blackboard
from .nodes import Node
from .tree_instance import TreeInstance


class MultiTreeManager:
    """多行为树管理器

    管理多个独立行为树实例的并行运行。
    每个树实例拥有独立的引擎、上下文和黑板。
    可选共享黑板实现树间通信。
    """

    def __init__(self, shared_blackboard: bool = False):
        self._trees: Dict[str, TreeInstance] = {}
        self._shared_blackboard = Blackboard() if shared_blackboard else None
        self._lock = threading.Lock()
        self._on_tree_status: Optional[Callable] = None
        self._on_node_status: Optional[Callable] = None

    def add_tree(self, name: str, root_node: Node,
                 blackboard: Blackboard = None,
                 tick_interval: float = 0.01) -> TreeInstance:
        """添加行为树实例

        Args:
            name: 实例名称（唯一标识）
            root_node: 根节点
            blackboard: 黑板实例（None则使用共享黑板或新建）
            tick_interval: tick间隔（秒）

        Returns:
            TreeInstance 实例
        """
        with self._lock:
            if name in self._trees:
                raise ValueError(f"树实例 '{name}' 已存在")

            if blackboard is None:
                blackboard = self._shared_blackboard or Blackboard()

            context = ExecutionContext()
            context.blackboard = blackboard

            engine = BehaviorTreeEngine(root_node)
            engine._tick_interval = tick_interval

            instance = TreeInstance(
                name=name,
                engine=engine,
                context=context,
                blackboard=blackboard
            )

            self._trees[name] = instance
            return instance

    def add_tree_from_file(self, name: str, filepath: str,
                           blackboard: Blackboard = None,
                           tick_interval: float = 0.01) -> TreeInstance:
        """从文件添加行为树实例"""
        from .serializer import Serializer
        root_node, _, _ = Serializer.load_from_file(filepath)
        return self.add_tree(name, root_node, blackboard, tick_interval)

    def remove_tree(self, name: str) -> bool:
        """移除行为树实例"""
        with self._lock:
            if name not in self._trees:
                return False

            instance = self._trees[name]
            if instance.status == "running":
                instance.engine.stop()

            del self._trees[name]
            return True

    def start_tree(self, name: str) -> bool:
        """启动指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance:
                return False

            if instance.status == "running":
                return True

            instance.engine.start(instance.context)
            instance.status = "running"
            return True

    def stop_tree(self, name: str) -> bool:
        """停止指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance:
                return False

            instance.engine.stop()
            instance.status = "stopped"
            return True

    def pause_tree(self, name: str) -> bool:
        """暂停指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance or instance.status != "running":
                return False

            instance.engine.pause()
            instance.status = "paused"
            return True

    def resume_tree(self, name: str) -> bool:
        """恢复指定行为树"""
        with self._lock:
            instance = self._trees.get(name)
            if not instance or instance.status != "paused":
                return False

            instance.engine.resume()
            instance.status = "running"
            return True

    def start_all(self) -> None:
        """启动所有行为树"""
        for name in list(self._trees.keys()):
            self.start_tree(name)

    def stop_all(self) -> None:
        """停止所有行为树"""
        for name in list(self._trees.keys()):
            self.stop_tree(name)

    def get_tree_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定行为树状态"""
        instance = self._trees.get(name)
        if not instance:
            return None

        return {
            "name": name,
            "status": instance.status,
            "error": instance.error_message,
        }

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有行为树状态"""
        return {name: self.get_tree_status(name) for name in self._trees}

    def set_on_tree_status(self, callback: Callable) -> None:
        """设置树状态变化回调"""
        self._on_tree_status = callback

    def set_on_node_status(self, callback: Callable) -> None:
        """设置节点状态变化回调（应用到所有树）"""
        self._on_node_status = callback
        for instance in self._trees.values():
            instance.engine._on_node_status = callback
