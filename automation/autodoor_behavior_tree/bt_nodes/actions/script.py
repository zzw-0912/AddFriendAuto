import os
import threading
from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any, Optional
from bt_utils.log_manager import LogManager


class ScriptNode(ActionNode):
    NODE_TYPE = "ScriptNode"
    SKIP_WINDOW_SWITCH = True

    _pool_lock = threading.Lock()

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.script_path = self.config.get("script_path", "")
        self.loop = self.config.get_bool("loop", False)
        self._executor: Optional[Any] = None
        self._script_started = False
        self._aborted = False
        self._script_content: Optional[str] = None
        self._lock = threading.Lock()

    def _get_or_create_executor(self) -> Any:
        from bt_utils.script_executor import ScriptExecutor
        
        if self._executor is None or not self._executor.is_running:
            self._executor = ScriptExecutor()
        
        return self._executor
    
    @classmethod
    def cleanup_executor_pool(cls) -> None:
        pass
    
    @classmethod
    def clear_executor_pool(cls) -> None:
        pass
    
    def stop_executor(self) -> None:
        executor = None
        with self._lock:
            executor = self._executor
            self._executor = None
            self._script_started = False
            self._script_content = None
        
        if executor is not None and executor.is_running:
            try:
                executor.stop_script()
            except Exception:
                pass

    def _execute_action(self, context) -> NodeStatus:
        with self._lock:
            self._aborted = False

        try:
            script_path = self.config.get("script_path", "")
            
            if not script_path:
                LogManager().log_failure(
                    node_type="脚本节点",
                    node_name=self.name,
                    reason="脚本路径为空"
                )
                return NodeStatus.FAILURE
            
            absolute_script_path = self._resolve_script_path(script_path, context)
            
            with self._lock:
                if self._aborted:
                    return NodeStatus.FAILURE
                
                if not self._script_started:
                    status = self._start_script(absolute_script_path, script_path, context)
                    if status != NodeStatus.RUNNING:
                        return status
                    return NodeStatus.RUNNING
            
            executor_to_stop = None
            result_status = None
            with self._lock:
                if self._aborted:
                    return NodeStatus.FAILURE
                
                if self._executor is None:
                    return NodeStatus.FAILURE
                
                if self._executor.is_running:
                    if not context.check_running():
                        executor_to_stop = self._executor
                        self._executor = None
                        self._script_started = False
                        self._script_content = None
                        result_status = NodeStatus.ABORTED
                    else:
                        return NodeStatus.RUNNING
                else:
                    self._cleanup_executor()
            
            if executor_to_stop is not None and executor_to_stop.is_running:
                try:
                    executor_to_stop.stop_script()
                except Exception:
                    pass
            
            if result_status is not None:
                return result_status
            
            LogManager().log_success(
                node_type="脚本节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS
            
        except Exception as e:
            with self._lock:
                if self._aborted:
                    return NodeStatus.FAILURE
            
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"ScriptNode '{self.name}'")
            LogManager().log_failure(
                node_type="脚本节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE
    
    def _resolve_script_path(self, script_path: str, context) -> str:
        """解析脚本路径"""
        absolute_script_path = script_path
        
        if script_path.startswith("./"):
            if hasattr(context, 'resolve_path') and context.resolve_path:
                absolute_script_path = context.resolve_path(script_path)
            elif hasattr(context, 'project_root'):
                project_root = context.project_root
                absolute_script_path = os.path.join(project_root, script_path[2:])
        else:
            if not os.path.isabs(script_path):
                absolute_script_path = os.path.abspath(script_path)
        
        return absolute_script_path
    
    def _parse_window_marker(self, content: str) -> dict:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("# Window:"):
                return {
                    "has_marker": True,
                    "window_title": line[len("# Window:"):].strip()
                }
        return {"has_marker": False, "window_title": ""}

    def _convert_to_absolute_coords(self, content: str, context) -> str:
        import re

        def replace_coord(match):
            x, y = int(match.group(1)), int(match.group(2))
            result = context.convert_to_screen_coords((x, y))
            if result and result != (x, y):
                return f"MoveTo {result[0]}, {result[1]}"
            return match.group(0)

        return re.sub(r'MoveTo\s+(\d+)\s*,\s*(\d+)', replace_coord, content)

    def _start_script(self, absolute_script_path: str, script_path: str, context=None) -> NodeStatus:
        if not os.path.exists(absolute_script_path):
            LogManager().log_failure(
                node_type="脚本节点",
                node_name=self.name,
                reason=f"脚本文件不存在: {absolute_script_path}"
            )
            return NodeStatus.FAILURE

        with open(absolute_script_path, 'r', encoding='utf-8') as f:
            self._script_content = f.read()

        if not self._script_content.strip():
            LogManager().log_failure(
                node_type="脚本节点",
                node_name=self.name,
                reason="脚本内容为空"
            )
            return NodeStatus.FAILURE

        marker = self._parse_window_marker(self._script_content)
        if marker["has_marker"] and context:
            bound_window = context.get_bound_window()
            if bound_window:
                self._script_content = self._convert_to_absolute_coords(self._script_content, context)
                LogManager().log_info(
                    node_type="脚本节点",
                    node_name=self.name,
                    message="已将窗口相对坐标转换为屏幕绝对坐标"
                )
            else:
                LogManager().log_info(
                    node_type="脚本节点",
                    node_name=self.name,
                    message=f"脚本含窗口标记（窗口：{marker['window_title']}）但未绑定窗口，坐标可能不正确"
                )

        self._executor = self._get_or_create_executor()
        use_loop = self.config.get_bool("loop", False) and self.config.repeat_count == 0
        self._executor.run_script(self._script_content, loop=use_loop)
        self._script_started = True

        LogManager().log_info(
            node_type="脚本节点",
            node_name=self.name,
            message=f"开始执行脚本 {script_path}"
        )
        return NodeStatus.RUNNING
    
    def _stop_executor(self) -> None:
        """停止执行器
        
        注意：调用此方法前必须持有 self._lock
        """
        if self._executor is not None:
            try:
                self._executor.stop_script()
            except Exception:
                pass
        self._executor = None
        self._script_started = False
        self._script_content = None
    
    def _cleanup_executor(self) -> None:
        """清理执行器状态
        
        注意：调用此方法前必须持有 self._lock
        """
        self._script_started = False
        self._executor = None
        self._script_content = None

    def abort(self, context) -> None:
        with self._lock:
            self._aborted = True
            executor = self._executor
            self._executor = None
            self._script_started = False
            self._script_content = None
        
        if executor is not None and executor.is_running:
            try:
                executor.stop_script()
            except Exception:
                pass
        
        super().abort(context)
    
    def reset(self, reset_counters: bool = True) -> None:
        with self._lock:
            executor = self._executor
            self._executor = None
            self._script_started = False
            self._aborted = False
            self._script_content = None
        
        if executor is not None and executor.is_running:
            try:
                executor.stop_script()
            except Exception:
                pass
        
        super().reset(reset_counters=reset_counters)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.script_path = config.get("script_path", "")
        node.loop = config.get_bool("loop", False)
        return node
