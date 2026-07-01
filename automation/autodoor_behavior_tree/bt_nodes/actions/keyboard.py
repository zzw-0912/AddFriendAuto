from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any, Optional
import time
from bt_utils.log_manager import LogManager
from bt_utils.helpers import get_random_duration


class KeyPressNode(ActionNode):
    NODE_TYPE = "KeyPressNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.key = self.config.get("key", "space")
        self.action = self.config.get("action", "press")
        self.duration = self.config.get_int("duration", 0)
        self.duration_random = self.config.get_int("duration_random", 0)
        
        self._key_started = False
        self._start_time: Optional[float] = None
        self._actual_duration: Optional[int] = None
        self._abort_flag = False
        self._context = None

    def _execute_action(self, context) -> NodeStatus:
        try:
            self._context = context

            key = self.config.get("key", "space")
            action = self.config.get("action", "press")
            duration = self.config.get_int("duration", 0)
            duration_random = self.config.get_int("duration_random", 0)

            if not key:
                LogManager.instance().log_failure(
                    node_type="按键节点",
                    node_name=self.name,
                    reason="未配置按键"
                )
                return NodeStatus.FAILURE

            if self._abort_flag or not context.check_running():
                self._release_key()
                LogManager.instance().log_aborted(
                    node_type="按键节点",
                    node_name=self.name
                )
                return NodeStatus.ABORTED

            if action == "press" and duration > 0:
                return self._non_blocking_press(context)
            else:
                actual_duration = get_random_duration(duration, duration_random)
                context.execute_key_press(key, action, actual_duration)
                LogManager.instance().log_success(
                    node_type="按键节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
                
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"KeyboardNode '{self.name}'")
            LogManager.instance().log_failure(
                node_type="按键节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE

    def _non_blocking_press(self, context) -> NodeStatus:
        key = self.config.get("key", "space")
        duration = self.config.get_int("duration", 0)
        duration_random = self.config.get_int("duration_random", 0)

        if not self._key_started:
            context.execute_key_press(key, "down", 0)
            self._key_started = True
            self._start_time = time.time() * 1000
            self._actual_duration = get_random_duration(duration, duration_random)

        if self._abort_flag or not context.check_running():
            self._release_key()
            LogManager.instance().log_aborted(
                node_type="按键节点",
                node_name=self.name
            )
            return NodeStatus.ABORTED

        current_time = time.time() * 1000

        if current_time - self._start_time < self._actual_duration:
            return NodeStatus.RUNNING

        context.execute_key_press(key, "up", 0)
        self._reset_key_state()

        LogManager.instance().log_success(
            node_type="按键节点",
            node_name=self.name
        )
        return NodeStatus.SUCCESS

    def _release_key(self) -> None:
        """释放按键"""
        key = self.config.get("key", "space")
        if self._key_started and self._context:
            try:
                self._context.execute_key_press(key, "up", 0)
            except Exception:
                pass
        self._reset_key_state()

    def _reset_key_state(self) -> None:
        self._key_started = False
        self._start_time = None
        self._actual_duration = None
        self._abort_flag = False

    def abort(self, context) -> None:
        """中止节点执行"""
        self._abort_flag = True
        self._release_key()
        super().abort(context)

    def reset(self, reset_counters: bool = True) -> None:
        """重置节点状态"""
        self._release_key()
        self._context = None
        super().reset(reset_counters=reset_counters)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeyPressNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.key = config.get("key", "space")
        node.action = config.get("action", "press")
        node.duration = config.get_int("duration", 0)
        node.duration_random = config.get_int("duration_random", 0)
        return node
