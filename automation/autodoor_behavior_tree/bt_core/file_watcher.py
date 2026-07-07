import os
import threading
from typing import Dict, Set, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class SubtreeFileWatcher:
    """子树文件变更监听器

    监听子树文件的变更，通知相关节点重新加载。
    """

    _watched_files: Dict[str, Set[str]] = field(default_factory=dict)
    _file_mtimes: Dict[str, float] = field(default_factory=dict)
    _on_file_changed: Optional[Callable] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def watch(self, filepath: str, node_id: str) -> None:
        """开始监听文件

        Args:
            filepath: 文件路径
            node_id: 引用该文件的节点ID
        """
        with self._lock:
            if filepath not in self._watched_files:
                self._watched_files[filepath] = set()
            self._watched_files[filepath].add(node_id)

            if os.path.exists(filepath):
                self._file_mtimes[filepath] = os.path.getmtime(filepath)

    def unwatch(self, filepath: str, node_id: str = None) -> None:
        """取消监听文件

        Args:
            filepath: 文件路径
            node_id: 节点ID，为None时取消所有监听
        """
        with self._lock:
            if filepath not in self._watched_files:
                return

            if node_id is None:
                del self._watched_files[filepath]
                self._file_mtimes.pop(filepath, None)
            else:
                self._watched_files[filepath].discard(node_id)
                if not self._watched_files[filepath]:
                    del self._watched_files[filepath]
                    self._file_mtimes.pop(filepath, None)

    def get_watching_nodes(self, filepath: str) -> Set[str]:
        """获取监听某文件的所有节点"""
        with self._lock:
            return set(self._watched_files.get(filepath, set()))

    def check_changes(self) -> Dict[str, Set[str]]:
        """检查所有监听文件的变更

        Returns:
            {变更的文件路径: 需要通知的节点ID集合}
        """
        changed = {}

        with self._lock:
            for filepath, node_ids in self._watched_files.items():
                if not os.path.exists(filepath):
                    continue

                current_mtime = os.path.getmtime(filepath)
                old_mtime = self._file_mtimes.get(filepath)

                if old_mtime is None or current_mtime > old_mtime:
                    changed[filepath] = set(node_ids)
                    self._file_mtimes[filepath] = current_mtime

        return changed

    def set_on_file_changed(self, callback: Callable) -> None:
        """设置文件变更回调"""
        self._on_file_changed = callback

    def notify_changes(self) -> None:
        """通知所有变更"""
        changed = self.check_changes()

        if self._on_file_changed:
            for filepath, node_ids in changed.items():
                for node_id in node_ids:
                    try:
                        self._on_file_changed(filepath, node_id)
                    except Exception:
                        pass
