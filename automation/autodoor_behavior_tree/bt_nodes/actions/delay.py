import time
from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any
from bt_utils.log_manager import LogManager
from bt_utils.helpers import get_random_duration


class DelayNode(ActionNode):
    NODE_TYPE = "DelayNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.duration_ms = self.config.get_int("duration_ms", 1000)
        self.duration_ms_random = self.config.get_int("duration_ms_random", 0)
        self._delay_start_time = None
        self._actual_duration = None

    def _execute_action(self, context) -> NodeStatus:
        if self._delay_start_time is None:
            duration_ms = self.config.get_int("duration_ms", 1000)
            duration_ms_random = self.config.get_int("duration_ms_random", 0)
            self._actual_duration = get_random_duration(duration_ms, duration_ms_random)
            self._delay_start_time = time.time()

        elapsed = (time.time() - self._delay_start_time) * 1000

        if elapsed >= self._actual_duration:
            self._delay_start_time = None
            self._actual_duration = None
            LogManager.instance().log_success(
                node_type="延时节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        return NodeStatus.RUNNING

    
    def abort(self, context) -> None:
        self._delay_start_time = None
        self._actual_duration = None
        super().abort(context)

    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters=reset_counters)
        self._delay_start_time = None
        self._actual_duration = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DelayNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.duration_ms = config.get_int("duration_ms", 1000)
        node.duration_ms_random = config.get_int("duration_ms_random", 0)
        return node
