import threading
import time
from typing import Optional, Callable, Dict, Any

from .nodes import Node, NodeStatus
from .context import ExecutionContext
from bt_utils.stats import get_stats_collector


class BehaviorTreeEngine:
    """行为树执行引擎

    负责行为树的加载、执行、暂停、停止等生命周期管理。
    执行在独立线程中进行，支持状态回调通知。

    Args:
        root_node: 行为树根节点
    """

    def __init__(self, root_node: Node = None):
        self.root_node = root_node
        self.context: Optional[ExecutionContext] = None
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._tick_interval = 0.01
        self._on_status_change: Optional[Callable] = None
        self._on_node_status: Optional[Callable] = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stats = get_stats_collector()

    def load_tree(self, data: Dict[str, Any]) -> None:
        """从字典数据加载行为树

        Args:
            data: 行为树字典数据
        """
        from .serializer import Serializer
        result = Serializer.deserialize(data)
        if isinstance(result, tuple):
            self.root_node = result[0]
        else:
            self.root_node = result

    def load_from_file(self, filepath: str) -> None:
        """从文件加载行为树

        Args:
            filepath: 文件路径
        """
        from .serializer import Serializer
        result = Serializer.load_from_file(filepath)
        if isinstance(result, tuple):
            self.root_node = result[0]
        else:
            self.root_node = result

    def save_to_file(self, filepath: str, format: str = "json") -> None:
        """保存行为树到文件

        Args:
            filepath: 文件路径
            format: 文件格式 (json/yaml/txt)
        """
        from .serializer import Serializer
        Serializer.save_to_file(self.root_node, filepath, format)

    def start(self, context: ExecutionContext = None) -> None:
        """启动执行

        Args:
            context: 执行上下文，为None时自动创建
        """
        with self._lock:
            if self._running:
                return

            self.context = context or ExecutionContext()
            self.context.set_stats_collector(self._stats)
            self._running = True
            self._paused = False
            self._stats.start_session()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

            if self._on_status_change:
                self._on_status_change("running")

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._paused = False
            self._stop_event.set()
            self._pause_event.set()

            if self.context:
                self.context._is_running = False

            if self.root_node and self.context:
                self.root_node.abort(self.context)
            elif self.root_node:
                self.root_node.reset()

            self._stop_all_script_nodes()

            self._stats.end_session()
            self._output_stats_report()

            if self._on_status_change:
                self._on_status_change("stopped")

    def _stop_all_script_nodes(self) -> None:
        if not self.root_node:
            return
        from bt_nodes.actions.script import ScriptNode
        for node in self._iter_all_nodes(self.root_node):
            if isinstance(node, ScriptNode):
                node.stop_executor()

    def _iter_all_nodes(self, node):
        yield node
        if hasattr(node, 'children'):
            for child in node.children:
                yield from self._iter_all_nodes(child)

    def pause(self) -> None:
        self._paused = True
        self._pause_event.clear()
        if self._on_status_change:
            self._on_status_change("paused")

    def resume(self) -> None:
        self._paused = False
        self._pause_event.set()
        if self._on_status_change:
            self._on_status_change("running")

    def get_status(self) -> Dict[str, Any]:
        """获取执行状态

        Returns:
            状态字典
        """
        return {
            "running": self._running,
            "paused": self._paused,
            "elapsed_time": self.context.elapsed_time if self.context else 0,
            "tick_count": self.context.tick_count if self.context else 0,
        }

    def _output_stats_report(self):
        """输出统计报告（仅终端显示，不显示在前端日志）"""
        from bt_utils.log_manager import LogManager
        
        if not self._stats.is_enabled():
            return
        
        report = self._stats.get_report()
        if not report:
            return
        
        session = report.get("session", {})
        summary = report.get("summary", {})
        
        LogManager.debug_print("📊 执行统计报告")
        LogManager.debug_print(f"  执行时长: {session.get('duration_ms', 0):.0f}ms")
        LogManager.debug_print(f"  Tick次数: {session.get('tick_count', 0)}")
        LogManager.debug_print(f"  节点执行总数: {session.get('total_node_executions', 0)}")
        LogManager.debug_print(f"  成功率: {summary.get('success_rate', 0):.1f}%")
        
        top_by_time = report.get("top_by_time", [])
        if top_by_time:
            LogManager.debug_print("  耗时最多的节点:")
            for i, node in enumerate(top_by_time[:5], 1):
                LogManager.debug_print(
                    f"    {i}. {node.get('node_name', '')} ({node.get('node_type', '')}): "
                    f"{node.get('total_time_ms', 0):.2f}ms, {node.get('total_executions', 0)}次"
                )
        
        top_by_count = report.get("top_by_count", [])
        if top_by_count:
            LogManager.debug_print("  执行最多的节点:")
            for i, node in enumerate(top_by_count[:5], 1):
                LogManager.debug_print(
                    f"    {i}. {node.get('node_name', '')} ({node.get('node_type', '')}): "
                    f"{node.get('total_executions', 0)}次, 成功率{node.get('success_rate', 0):.1f}%"
                )

    def get_stats_report(self) -> Dict[str, Any]:
        """获取统计报告

        Returns:
            统计报告字典
        """
        return self._stats.get_report()

    def export_stats(self, filepath: str) -> bool:
        """导出统计报告到文件

        Args:
            filepath: 文件路径

        Returns:
            是否成功
        """
        return self._stats.export_to_file(filepath)

    def _run_loop(self) -> None:
        start_time = time.time()
        self._stop_event.clear()

        while self._running and not self._stop_event.is_set():
            if not self._pause_event.wait(0.1):
                continue

            if self._stop_event.is_set() or not self._running:
                break

            self.context.elapsed_time = time.time() - start_time
            self.context.tick_count += 1
            self._stats.record_tick()

            if self.root_node:
                status = self.root_node.tick(self.context)

                from bt_utils.log_manager import LogManager
                LogManager.debug_print(
                    f"[DEBUG] Engine._run_loop: tick={self.context.tick_count}, "
                    f"root_node status={status.name}"
                )

                if self._on_node_status:
                    self._on_node_status(self.root_node.node_id, status.value)

                if status != NodeStatus.RUNNING:
                    self._running = False
                    
                    self._stats.end_session()
                    self._output_stats_report()
                    
                    if self.root_node and self.context:
                        self.root_node.abort(self.context)
                    elif self.root_node:
                        self.root_node.reset()
                    
                    if self._on_status_change:
                        self._on_status_change("completed", status)

            if self._stop_event.wait(self._tick_interval):
                break
